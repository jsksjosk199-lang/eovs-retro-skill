#!/usr/bin/env python3
"""Read-only EOVS reconciliations. No network, credentials, or workbook edits."""
import argparse
import json
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

ZERO = Decimal('0')


def number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean is not a numeric amount')
    result = Decimal(str(value).replace(',', '').strip())
    if not result.is_finite():
        raise ValueError('Non-finite amount')
    return result


def total(values):
    parsed = [number(v) for v in values]
    return sum(parsed, ZERO) if parsed and all(v is not None for v in parsed) else None


def serial(value):
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serial(v) for v in value]
    return value


def audit(data):
    rules = data.get('rules', {})
    rows = data.get('quarters', [])
    qs = [r.get('quarter') for r in rows]
    if any(not isinstance(q, int) or isinstance(q, bool) for q in qs):
        raise ValueError('quarter must be an integer')
    if qs != sorted(set(qs)):
        raise ValueError('quarters must be ascending and unique')
    money_tolerance = number(rules.get('money_tolerance', '0.02'))
    quantity_tolerance = number(rules.get('quantity_tolerance', '0.000001'))
    checks, skipped, warnings, period_results = [], [], [], []

    def check(q, code, actual, expected, unit='money'):
        if actual is None or expected is None:
            skipped.append({'quarter': q, 'check': code, 'reason': '缺数据或未验证规则，不把未知填0'})
            return
        tolerance = money_tolerance if unit == 'money' else quantity_tolerance
        residual = actual - expected
        checks.append({'quarter': q, 'check': code, 'status': 'passed' if abs(residual) <= tolerance else 'failed',
                       'actual': actual, 'expected': expected, 'residual': residual})

    previous = data.get('opening', {})
    previous_q = qs[0] - 1 if qs else None
    for row in rows:
        q = row['quarter']
        prev = previous if previous_q == q - 1 else {}
        n = lambda key, obj=row: number(obj.get(key))
        p = lambda key: number(prev.get(key))
        equity_adjustment = n('equity_adjustment') if 'equity_adjustment' in row else ZERO
        dividend = n('dividend')
        eq_expected = (p('equity') + n('net_profit') - dividend + equity_adjustment
                       if all(v is not None for v in [p('equity'), n('net_profit'), dividend, equity_adjustment]) else None)
        check(q, 'equity_roll', n('equity'), eq_expected)
        check(q, 'assets_minus_liabilities', n('equity'), n('assets') - n('liabilities')
              if n('assets') is not None and n('liabilities') is not None else None)
        check(q, 'profit_income_less_expense', n('net_profit'), n('sales_revenue') + n('other_income') - n('total_expense')
              if all(n(k) is not None for k in ['sales_revenue', 'other_income', 'total_expense']) else None)
        check(q, 'expense_components', n('total_expense'), total(row.get('expense_components', [])))
        check(q, 'cash_payment_components', n('cash_out'), total(row.get('cash_out_components', [])))
        liabilities = [n('normal_debt'), n('abnormal_debt'), n('other_liabilities')]
        liability_expected = sum(liabilities, ZERO) if rules.get('liability_components_complete') is True and all(
            v is not None for v in liabilities) else None
        check(q, 'liability_components', n('liabilities'), liability_expected)
        cash_expected = p('cash') + n('net_cash_flow') + n('abnormal_debt') if rules.get('abnormal_adds_to_cash') is True and all(
            v is not None for v in [p('cash'), n('net_cash_flow'), n('abnormal_debt')]) else None
        check(q, 'cash_roll_model', n('cash'), cash_expected)

        debt_base, premium, interest = None, None, None
        debt_inputs = [p('normal_debt'), p('abnormal_debt'), n('borrow'), n('repay')]
        if rules.get('abnormal_rolls_into_ordinary') is True and all(v is not None for v in debt_inputs):
            debt_base = debt_inputs[0] + debt_inputs[1] + debt_inputs[2] - debt_inputs[3]
            ordinary, abnormal = number(rules.get('ordinary_quarter_rate')), number(rules.get('abnormal_quarter_rate'))
            if ordinary is not None and abnormal is not None:
                premium = p('abnormal_debt') * (abnormal - ordinary)
                interest = debt_base * ordinary + premium
        check(q, 'normal_debt_roll_model', n('normal_debt'), debt_base)
        check(q, 'interest_model', n('bank_interest'), interest)

        fraction = number(rules.get('sales_budget_fraction'))
        budget_inputs = [n('budget_opening_cash'), n('borrow'), n('sales_revenue'), n('cash_out'), fraction]
        budget = budget_inputs[0] + budget_inputs[1] + budget_inputs[2] * fraction - budget_inputs[3] if all(
            v is not None for v in budget_inputs) else None
        check(q, 'abnormal_cash_gap_model', n('abnormal_debt'), max(ZERO, -budget) if budget is not None else None)

        markets = row.get('markets', [])
        sold = total(m.get('sales') for m in markets)
        demand = total(m.get('demand') for m in markets)
        stock = total(m.get('end_stock') for m in markets)
        revenues = total(m.get('revenue') for m in markets)
        check(q, 'regional_sales_revenue', n('sales_revenue'), revenues)
        check(q, 'regional_stock_total', n('finished_units'), stock, 'quantity')
        stock_adjustment = n('finished_adjustment') if 'finished_adjustment' in row else ZERO
        stock_expected = p('finished_units') + n('production_units') - sold + stock_adjustment if all(
            v is not None for v in [p('finished_units'), n('production_units'), sold, stock_adjustment]) else None
        check(q, 'production_sales_inventory', n('finished_units'), stock_expected, 'quantity')

        unmet = surplus = False
        for i, market in enumerate(markets):
            label = str(market.get('label', i)).replace('\n', ' ')
            price, sales, revenue = [number(market.get(k)) for k in ['price', 'sales', 'revenue']]
            mdemand, mstock, capacity = [number(market.get(k)) for k in ['demand', 'end_stock', 'effective_capacity']]
            check(q, 'price_times_sales:' + label, revenue, price * sales if price is not None and sales is not None else None)
            for code, limit in [('sales_le_demand', mdemand), ('sales_le_effective_capacity', capacity)]:
                if sales is not None and limit is not None:
                    check(q, code + ':' + label, max(ZERO, sales - limit), ZERO, 'quantity')
            if mdemand is not None and sales is not None and mdemand > sales:
                unmet = True
                if capacity is not None and sales >= capacity:
                    warnings.append({'quarter': q, 'code': 'staff_capacity_binding', 'market': label,
                                     'message': '需求未满足但有效人员容量已满；不能只搬货，需核提前招聘与生效期'})
            if mstock is not None and mstock > 0:
                surplus = True
        if markets and demand is not None and sold is not None and stock is not None:
            if demand > sold and stock == 0:
                state = 'supply_or_staff_limited'
                warnings.append({'quarter': q, 'code': state, 'message': '真实需求超过销量且货已卖完；核产能和正式人员，不只解释为市场不足'})
            elif unmet and surplus:
                state = 'regional_supply_or_staff_mismatch'
                warnings.append({'quarter': q, 'code': state, 'message': '某区需求未满足、另区留货；调货前核目标市场的有效人员容量'})
            elif demand == sold and stock > 0:
                state = 'demand_met_with_inventory'
                warnings.append({'quarter': q, 'code': state, 'message': '实际需求已满足仍有货；同价同需求调货不会增加销量，需比较生产与定价组合'})
            else:
                state = 'no_simple_bottleneck_identified'
        else:
            state = 'unknown'

        carbon = row.get('carbon', {})
        c = lambda key: number(carbon.get(key))
        gap, emission, complied = c('gap'), c('current_emission'), c('notice_net_complied')
        check(q, 'carbon_net_notice', gap, emission - complied if emission is not None and complied is not None else None, 'quantity')
        prior_carbon = prev.get('carbon', {})
        old_gap = number(prev.get('carbon_gap', prior_carbon.get('gap')))
        gross_used, ccer = c('gross_cea_used'), c('ccer_used')
        gross_expected = max(ZERO, old_gap + emission - gross_used - ccer) if all(
            v is not None for v in [old_gap, emission, gross_used, ccer]) else None
        check(q, 'carbon_gross_roll', gap, gross_expected, 'quantity')
        rate = c('fine_per_ton')
        check(q, 'carbon_fine', c('fine'), gap * rate if gap is not None and rate is not None else None)
        cap_fraction = number(rules.get('ccer_cap_fraction'))
        cap = emission * cap_fraction if rules.get('ccer_cap_base') == 'current_emission' and emission is not None and cap_fraction is not None else None
        rounding = rules.get('ccer_cap_rounding')
        if cap is not None and rounding == 'floor':
            cap = cap.to_integral_value(rounding=ROUND_FLOOR)
        elif cap is not None and rounding == 'half_up':
            cap = cap.to_integral_value(rounding=ROUND_HALF_UP)
        if cap is not None and ccer is not None and (rounding is not None or ccer > cap + 1 or ccer <= cap):
            check(q, 'ccer_offset_cap', max(ZERO, ccer - cap), ZERO, 'quantity')
        else:
            skipped.append({'quarter': q, 'check': 'ccer_offset_cap', 'reason': '缺字段或1吨内边界舍入未确认'})
        if c('fine') is not None and gap == 0 and rate is None:
            warnings.append({'quarter': q, 'code': 'zero_fine_does_not_identify_rate', 'message': '无欠额不能从0罚款反推本季罚率'})

        period_results.append({'quarter': q, 'market_state': state, 'sales': sold, 'demand': demand,
                               'ending_stock': stock, 'cash_budget_candidate': budget, 'interest_candidate': interest,
                               'abnormal_premium_included_in_interest': premium, 'carbon_gap': gap})
        previous, previous_q = row, q

    passed = sum(c['status'] == 'passed' for c in checks)
    failed = sum(c['status'] == 'failed' for c in checks)
    result = {'match': data.get('match', {}), 'status': 'failed' if failed else ('passed' if passed else 'insufficient_data'),
              'counts': {'passed': passed, 'failed': failed, 'skipped': len(skipped), 'warnings': len(warnings)},
              'checks': checks, 'skipped': skipped, 'warnings': warnings, 'quarters': period_results,
              'limits': ['核对通过不等于决策最优，也不表示复盘资料或来源完整', '模型仅适用于已确认的本场规则', '未知数据和未核规则不以0或历史数替代',
                         '净口径通知与总口径滚动分开核，不重复加旧欠', '异常利差已含在总利息，不能再次相加']}
    return serial(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8-sig'))
    result = audit(data)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# EOVS核账结果', '', '数据类型：' + ('合成演示' if data.get('match', {}).get('synthetic') else '使用者提供的数据'),
             '', '核对状态：' + result['status'], '', '统计：' + json.dumps(result['counts'], ensure_ascii=False), '',
             '|季|检查|结果|实际|应为|残差|', '|---|---|---|---:|---:|---:|']
    for c in result['checks']:
        label = c['check'].replace('|', '\\|')
        lines.append(f"|{c['quarter']}|{label}|{c['status']}|{c['actual']}|{c['expected']}|{c['residual']}|")
    lines += ['', '## 每季经营与资金', '',
              '|季|销量|本公司需求|期末成品|季内预算候选|总利息候选|其中异常利差|碳欠额|',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for period in result['quarters']:
        fields = ['quarter', 'sales', 'demand', 'ending_stock', 'cash_budget_candidate', 'interest_candidate',
                  'abnormal_premium_included_in_interest', 'carbon_gap']
        lines.append('|' + '|'.join(str(period[key]) if period[key] is not None else '未知' for key in fields) + '|')
    lines += ['', '预算与利息是按已确认规则计算的候选；异常利差已在总利息中，不能再次加上。', '', '## 经营线索']
    lines += [f"- Q{w['quarter']}：{w['message']}" for w in result['warnings']]
    lines += ['', '## 待补数据与规则']
    lines += [f"- Q{s['quarter']} {s['check']}：{s['reason']}" for s in result['skipped']]
    lines += ['', '## 使用边界'] + ['- ' + item for item in result['limits']]
    (args.out / '核账结果.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'counts': result['counts']}, ensure_ascii=False))
    return 1 if result['counts']['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Behavior tests using invented inputs only. No real files or network."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'eovs-retro'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


AUDIT = module('audit_match')
XLSX = module('inspect_xlsx')
PRIVACY = module('check_public_package')


class SkillBehavior(unittest.TestCase):
    def setUp(self):
        self.demo = json.loads((ROOT / 'assets' / 'demo-match.json').read_text(encoding='utf-8'))

    def find(self, report, q, code):
        return next(c for c in report['checks'] if c['quarter'] == q and c['check'] == code)

    def test_complete_demo_reconciles_and_reports_constraints(self):
        report = AUDIT.audit(self.demo)
        self.assertEqual(report['counts']['failed'], 0)
        self.assertGreater(report['counts']['passed'], 40)
        self.assertEqual(report['quarters'][0]['market_state'], 'supply_or_staff_limited')
        self.assertEqual(report['quarters'][1]['market_state'], 'demand_met_with_inventory')

    def test_repayment_is_not_added_to_expense_and_premium_not_doubled(self):
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 3, 'interest_model')['expected'], '12.00')
        self.assertEqual(report['quarters'][2]['abnormal_premium_included_in_interest'], '4.50')
        self.assertEqual(self.find(report, 3, 'profit_income_less_expense')['status'], 'passed')

    def test_bad_expense_and_old_carbon_double_count_are_detected(self):
        self.demo['quarters'][1]['total_expense'] = 701
        self.demo['quarters'][1]['carbon']['gap'] = 42
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 2, 'expense_components')['status'], 'failed')
        self.assertEqual(self.find(report, 2, 'carbon_gross_roll')['status'], 'failed')
        self.assertEqual(self.find(report, 2, 'carbon_net_notice')['expected'], '22')

    def test_unknown_demand_is_not_zero(self):
        del self.demo['quarters'][0]['markets'][0]['demand']
        report = AUDIT.audit(self.demo)
        self.assertIsNone(report['quarters'][0]['demand'])
        self.assertEqual(report['quarters'][0]['market_state'], 'unknown')

    def test_missing_version_rules_skip_models(self):
        del self.demo['rules']['abnormal_quarter_rate']
        del self.demo['rules']['abnormal_adds_to_cash']
        report = AUDIT.audit(self.demo)
        self.assertIsNone(report['quarters'][0]['interest_candidate'])
        self.assertTrue(any(x['check'] == 'cash_roll_model' for x in report['skipped']))

    def test_other_liabilities_are_included_only_when_complete(self):
        self.demo['quarters'][0]['other_liabilities'] = 50
        self.demo['quarters'][0]['liabilities'] = 750
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 1, 'liability_components')['status'], 'passed')
        del self.demo['rules']['liability_components_complete']
        report = AUDIT.audit(self.demo)
        self.assertTrue(any(x['check'] == 'liability_components' for x in report['skipped']))

    def test_available_unsubmitted_cea_does_not_clear_actual_gap(self):
        self.demo['quarters'][1]['carbon']['available_cea'] = 200
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 2, 'carbon_gross_roll')['expected'], '22')
        del self.demo['quarters'][1]['carbon']['gross_cea_used']
        report = AUDIT.audit(self.demo)
        self.assertTrue(any(x['quarter'] == 2 and x['check'] == 'carbon_gross_roll' for x in report['skipped']))

    def test_unverified_ccer_cap_base_is_skipped(self):
        del self.demo['rules']['ccer_cap_base']
        report = AUDIT.audit(self.demo)
        self.assertTrue(any(x['check'] == 'ccer_offset_cap' for x in report['skipped']))

    def test_reduced_emission_invalidates_old_ccer_amount(self):
        self.demo['quarters'][2]['carbon']['current_emission'] = 10000
        self.demo['quarters'][2]['carbon']['ccer_used'] = 1300
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 3, 'ccer_offset_cap')['residual'], '300')

    def test_staff_binding_identified_before_recommending_more_delivery(self):
        self.demo['quarters'][0]['markets'][0]['effective_capacity'] = 100
        report = AUDIT.audit(self.demo)
        self.assertTrue(any(x['code'] == 'staff_capacity_binding' for x in report['warnings']))

    def test_quarter_gap_does_not_roll_wrong_previous_quarter(self):
        self.demo['quarters'].pop(1)
        report = AUDIT.audit(self.demo)
        self.assertTrue(any(x['quarter'] == 3 and x['check'] == 'equity_roll' for x in report['skipped']))
        self.assertTrue(any(x['quarter'] == 3 and x['check'] == 'carbon_gross_roll' for x in report['skipped']))

    def test_duplicate_quarters_rejected(self):
        self.demo['quarters'][1]['quarter'] = 1
        with self.assertRaises(ValueError):
            AUDIT.audit(self.demo)

    def test_negative_inventory_adjustment_component_allowed(self):
        self.demo['quarters'][0]['expense_components'] = [800, -100]
        report = AUDIT.audit(self.demo)
        self.assertEqual(self.find(report, 1, 'expense_components')['status'], 'passed')

    def test_workbook_candidates_and_no_mutation(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, current = root / 'baseline.xlsx', root / 'current.xlsx'
            book = Workbook()
            sheet = book.active
            sheet.title = '主表'
            sheet['A1'], sheet['A2'], sheet['A3'], sheet['A4'], sheet['A5'] = '营销', '成本', '错误', '待算', '空白引用'
            sheet['B1'], sheet['B2'], sheet['B4'], sheet['B5'] = '=C1+D1', '=SUM(C2:D2)', '=1+1', '=2+2'
            book.save(baseline)
            sheet['B1'], sheet['B2'], sheet['B3'], sheet['B4'], sheet['B5'] = 'C1+D1', 3, '#DIV/0!', '=1+2', None
            book.save(current)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [baseline, current]}
            result = XLSX.inspect(current, baseline)
            kinds = {item['kind'] for item in result['findings']}
            self.assertTrue({'formula_like_text', 'formula_overridden', 'formula_differs_from_template', 'literal_error', 'formula_cache_missing'} <= kinds)
            self.assertTrue(any(x['cell'] == 'B5' and x['kind'] == 'formula_overridden' for x in result['findings']))
            after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [baseline, current]}
            self.assertEqual(before, after)

    def test_different_workbook_layout_refuses_baseline(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            book = Workbook()
            book.active['A1'] = '旧标签'
            book.active['B1'] = '=2+2'
            book.save(root / 'baseline.xlsx')
            book.active['A1'] = '新标签'
            book.active['B1'] = 1
            book.save(root / 'current.xlsx')
            result = XLSX.inspect(root / 'current.xlsx', root / 'baseline.xlsx')
            self.assertFalse(any(x['kind'] == 'formula_overridden' for x in result['findings']))
            self.assertTrue(any('95%' in note for note in result['notes']))

    def test_privacy_detection_does_not_echo_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invented = '1' + '3800001234'
            (root / 'example.md').write_text(invented + '\n' + 'pass' + 'word' + '=' + chr(34) + 'InventedSecret' + chr(34) + '\n匿名旧标识', encoding='utf-8')
            report = PRIVACY.scan(root, ['匿名旧标识'])
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(invented, serialized)
            self.assertNotIn('InventedSecret', serialized)
            self.assertTrue({'mobile_number', 'credential_value', 'forbidden_identifier'} <= {x['kind'] for x in report['findings']})

    def test_privacy_filename_is_redacted_in_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invented = '1' + '3800001234'
            (root / (invented + '_匿名旧标识.md')).write_text('示例', encoding='utf-8')
            report = PRIVACY.scan(root, ['匿名旧标识'])
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(invented, serialized)
            self.assertNotIn('匿名旧标识', serialized)
            self.assertTrue(any(x['kind'] == 'mobile_number_in_filename' for x in report['findings']))


if __name__ == '__main__':
    unittest.main(verbosity=2)

# 核账助手输入约定

`audit_match.py`接受UTF-8 JSON，只读输入。输出到独立目录，不写原Excel。金额与数量可用数字或数值字符串；缺失用`null`或省略，不用0代替未知。

```json
{
  "match": {"label": "匿名演示", "company": "队A", "synthetic": true},
  "rules": {
    "ordinary_quarter_rate": 0.01,
    "abnormal_quarter_rate": 0.04,
    "abnormal_rolls_into_ordinary": true,
    "abnormal_adds_to_cash": true,
    "liability_components_complete": true,
    "sales_budget_fraction": 0.5,
    "ccer_cap_fraction": 0.1,
    "ccer_cap_base": "current_emission"
  },
  "opening": {"equity": 1000, "cash": 0, "normal_debt": 0, "abnormal_debt": 0, "finished_units": 0, "carbon_gap": 0},
  "quarters": [
    {
      "quarter": 1,
      "equity": 1100, "net_profit": 100, "dividend": 0,
      "assets": 1800, "liabilities": 700,
      "cash": 400, "net_cash_flow": 200,
      "normal_debt": 500, "abnormal_debt": 200, "borrow": 500, "repay": 0,
      "other_liabilities": 0,
      "bank_interest": 5, "budget_opening_cash": 0,
      "sales_revenue": 800, "other_income": 0, "total_expense": 700,
      "cash_out": 1100, "cash_out_components": [1100],
      "production_units": 100, "finished_units": 0,
      "markets": [{"label":"市场X", "price":8,"sales":100,"revenue":800,"demand":130,"end_stock":0,"effective_capacity":120}],
      "carbon": {"current_emission":60,"notice_net_complied":40,"gap":20,"fine_per_ton":10,"fine":200,"gross_cea_used":40,"ccer_used":0}
    }
  ]
}
```

这段只说明字段，实际试跑用已自洽的`assets/demo-match.json`。以上配置是本场已验证规则或带标签的试算，不是EOVS全版本默认规则。

|字段|含义与注意|
|---|---|
|`quarter`|整数季度，按实际顺序给；缺季度时滚动校验跳过，不拿更早一季作上季|
|`opening`|首个季度前的实际状态，不一定是筹建前；原料与库存特殊出入库可另外说明|
|`equity_adjustment`|增资等其他权益变化；没发生才为0|
|`finished_adjustment`|非生产销售的成品出入库，正数增加库存；需给来源|
|`markets[].demand`|本公司结算需求或有标签的预测，不是全市场规模|
|`effective_capacity`|已生效正式人员与规则形成的可卖量；不是报表总人数|
|`cash`|与现金流表相同口径的总现金；与可动用基本账户分开|
|`budget_opening_cash`|实际付款时可动用期初现金；不要自动拿交易账户充预算|
|`cash_out_components`|互不重复的实际现金付款项，已含还本时不能再加还本|
|`expense_components`|互不重复的利润费用项，可含负的库存调整；不可含费用合计本身|
|`abnormal_rolls_into_ordinary`|只有实账验证下期滚入的版本才开此候选模型|
|`abnormal_adds_to_cash`|只有已核实净现金流不含本季异常融资、该融资另加期末现金的版本才开；避免再加一次融资|
|`liability_components_complete`|只有本场全部负债已分类时开启负债合计核对|
|`other_liabilities`|除正常与异常借款之外的全部负债；确认没有才填0，未核不填0|
|`sales_budget_fraction`|只有已核定季内到账比例时才给；未知就不算现金缺口|
|`carbon.current_emission`|本期实际排放，不含旧欠|
|`notice_net_complied`|平台已先处理旧欠后的净抵本期数量|
|`gross_cea_used`|实际已用于旧欠＋本期履约的总CEA量，未先扣旧欠；不是可用未提交余额|
|`carbon.gap`|实际期末未清欠额，不是银行负债金额|
|`fine_per_ton`|本场当季有依据的罚率；无缺口时不能从零罚款反推|
|`ccer_used`|实际抵扣总量；开发与购入来源另列，不能全归给项目|
|`ccer_cap_base`／`ccer_cap_fraction`|只在本场已核上限按当期排放计算时分别填`current_emission`和比例；其他或未知分母跳过|

脚本做数值核对和有限经营状态诊断，不估计隐藏需求公式，不重算Excel公式，不计算未知评分模型，不自动生成最优决策。`warning`表示可解释的业务问题／数据覆盖，`failed`表示账量不平或硬约束冲突；未执行校验单独列为`skipped`。

即使`skipped=0`，也只代表输入支持这些算式，不证明实盘来源、市场环境、对手或项目资料收齐了。费用组件没有标签时，只能核合计，不能据数字推断是哪种费用；进一步复盘应保留每项标签及证据来源。

`inspect_xlsx.py --baseline`要求使用者确认是同版本、同布局的原模板。脚本会做额外文本布局相似性检查，但相似不证明公式正确；报告中的`formula_overridden`与`formula_differs_from_template`都是候选，差异可能是合理修正，不自动恢复公式。

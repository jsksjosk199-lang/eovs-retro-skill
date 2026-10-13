# EOVS复盘Skill · eovs-retro

**把八季度比赛看明白，把利润、现金和排名的差距算明白。**

这套方法来自一次已确认**校赛总分第一**的EOVS企业低碳节能运营仿真实战案例。我们使用**Codex**完成逐季复盘，将核账、前五名对标和多轮用户纠正整理成了可以反复使用的Skill。

它的价值，是把价格、需求、人员、生产、库存、资金与碳接成完整的经营链：解释差距发生在哪一季，哪些选择值得保留，哪些问题下一场能够提前发现；再一步一步说明表格填什么、在哪里取数、怎样验算。

**校赛第一名是实战成绩，Codex复盘是方法沉淀。** Skill是在赛后封装的，学校、队伍和原始比赛数据保持匿名。演示使用匿名合成数据；项目不保证名次，也不把赛后已知需求冒充赛前准确预测。

## 能做什么

- 从筹建期到第八季复盘，分别分析前三／前五名的公开打法。
- 联合市场环境、上季需求、报价、库存与有效人员，比较定价、营销和投放。
- 核对产销存、两条权益账、正常与异常利息、季内付款和借还款。
- 区分碳旧欠、实际总履约与净履约，比较生产、CEA及CCER项目。
- 只读检查Excel公式文字、错误缓存、覆盖和模板差异，教使用者逐格填写。

## 安装与调用

将仓库内的 **`eovs-retro`文件夹**放进你的技能目录。Codex默认目录是`~/.codex/skills/`；配置了`CODEX_HOME`时使用对应目录。不要把整个仓库目录当成Skill目录。

```text
技能目录/
└── eovs-retro/
    ├── SKILL.md
    ├── agents/
    ├── references/
    ├── scripts/
    └── assets/
```

中文名：**EOVS复盘Skill**；调用名：**`$eovs-retro`**。

> 使用 $eovs-retro，结合本场数据、我的预测表和教学字幕，逐季复盘我和前五名。解释需求、定价、库存、借还款、权益和碳的问题，给出下一场改进顺序，并一步一步教我填表。不要修改原文件。

只分析一季也可以：

> 使用 $eovs-retro，比较第八季满产和减产。把售价、预计销量、旧库存、免费CEA、CCER上限和季内现金一起算，标明缺失数据和成立条件。

## 阅读顺序

1. [技能入口](eovs-retro/SKILL.md)：选择整场、单季、老师复刻或填表教学。
2. 按入口加载参考：[采集与填表](eovs-retro/references/collection-and-sheet.md)、[联动判断](eovs-retro/references/decision-rules.md)。
3. [报告模板](eovs-retro/assets/report-template.md)：按季度、对手、方案和表格组织结果。
4. 需要计算时看[数据格式](eovs-retro/references/data-schema.md)，再运行助手。

[项目介绍](docs/项目介绍.md)、[验证说明](docs/验证说明.md)和[脱敏案例](eovs-retro/references/sanitized-case.md)分别说明能力、证据和实战来源。

## 本地试跑

核账和隐私检查使用Python标准库。Excel检查与行为测试需要`openpyxl`：

```bash
python -m pip install -r requirements.txt
python -B eovs-retro/scripts/audit_match.py eovs-retro/assets/demo-match.json --out demo-output
python -B -m unittest discover -s tests -v
```

合成演示的核账结果应为60项通过、0失败、3条经营提示。17项行为测试覆盖未知数据、旧欠重复扣除、未提交CEA、人员瓶颈、利差重复累计、其他负债、公式问题和隐私报告。

实际工作簿可只读检查：

```bash
python -B eovs-retro/scripts/inspect_xlsx.py current.xlsx --out inspection-output/report.json
```

确认原模板同版同布局后，可以增加`--baseline template.xlsx`。助手不执行Excel公式，缺缓存不能当0，模板差异也不能自动判成错误。

## 隐私与资料

本仓库只公开自写流程、规则说明、脚本、报告模板和合成演示。账号、密码、服务器、真实机构与公司、原始工作簿、截图、完整教学字幕和真实标识映射均未纳入。原始私有目录与Git历史没有导入本仓库。

新分析资料需要由使用者另外提供，读取本场身份与规则后再用。公开新报告前重新脱敏；隐私扫描是线索，仍需人工检查昵称、头像、精确数字组合及元数据。默认只读分析，不自行推进比赛、竞拍或覆盖原表。

## 开源协议

本项目采用 **[MIT License](LICENSE)**，可使用、修改和分发，也可用于商业项目，需保留版权及许可声明。许可证适用于仓库内的原创内容，不授予EOVS平台、他人教材、视频、标识或私有比赛数据的权利。

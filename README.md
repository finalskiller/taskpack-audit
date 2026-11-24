# taskpack-audit

> 任务包审计：把「读一遍、找几个典型问题」变成「建账本、跑反证、留证据、过门禁」。

`taskpack-audit` 是一个用于审核 **LLM 编程评测任务包** 的 agent skill。输入一个任务包（题面、环境、测试、rubric），输出一份 `review.json`：每条问题五项齐全，证据逐字可核。

**English overview:** A skill for auditing benchmark task packages (instruction / environment / tests / rubric) used to evaluate LLM coding ability. It builds coverage ledgers, runs mutation probes and rubric simulations, and emits a quote-verifiable `review.json`.

---

## 它解决什么问题

评测任务包的质量决定评测结果可不可信：

- 一条只检查“异常类型”的测试，会让一个跑完全部步骤再抛错的实现拿满分；
- 一条“reward=1 就直接给满分”的评分规则，会让错误的模型产出绕过人工核对；
- 一条“必须使用某个库”的评分项，会惩罚官方参考解本身。

这个 skill 不写解法、不修任务包，只做三件事：**找全、说准、留证据**。

## 为什么不是普通 code review

| 普通 code review | taskpack-audit |
|---|---|
| 看代码写得对不对 | 看测试是否真的验证了题面要求 |
| 找到几个典型问题 | 用覆盖账本逐函数、逐断言、逐 rubric 条目遍历 |
| 凭经验判断“可能有问题” | 写变异实现跑测试，用 `run_output` 证明漏洞 |
| 评价代码风格 | 用 rubric 三仿真（参考解 / 坏解 / 双标注员）量化评分 |
| 口头说“建议补充测试” | 每条 suggestion 落到具体断言/用例/条目文本 |

## 安装

### DeepSeek Harness (DSH)

```bash
git clone https://github.com/finalskiller/taskpack-audit.git ~/.dsh/skills/taskpack-audit
```

或在支持 skill 的 agent 中把本目录加入 skill 搜索路径。入口是 `SKILL.md`。

### 依赖

- Python 3.8+（脚本只用标准库）
- Docker（可选；只用于第一部分的容器环境复现）
- 不需要安装 pytest；如果任务包需要，按任务包自己的 `test.sh` 走

## 快速开始

把任务包放在任意目录（不要修改材料），在包同级建 `work/`，然后对 agent 说：

> 用 `taskpack-audit` 审 `<任务包路径>`，产出 `review.json`。

它会按 `SKILL.md` 的 P0–P7 执行。你也可以单独跑工具：

```bash
# 1. 生成测试账本骨架
python scripts/inventory.py --root <pkg> --ledger

# 2. 校验收据格式（schema / id / 枚举 / 空串 / 类型-来源配对）
python scripts/validate_review.py review.json --strict

# 3. 逐条核对 evidence 引文是否在原文行范围内
python scripts/verify_evidence.py review.json --root <pkg> --work work --strict
```

如果 `rubric.md` 不在任务包根目录（例如放在 `材料包/` 上一层），可以做一个只读校验根，把 `rubric.md`、`instruction.md`、`tests/`、`solution/` 拼在一起，再用 `--root` 指过去；不要为了校验去改材料。

## 工作流

| 阶段 | 产出 | 门禁 |
|---|---|---|
| P0 接包 | `work/contract.md`：原子 R 表 + 预期断言 | 每条 MUST/禁止项有 R；每条 R 有预期断言 |
| P1 环境 | `environment` 10 个必填键、`work/env.md` | 字段与 `completed`/`reward`/`stopped_at` 自洽 |
| P2 建模 | 状态 × 事件矩阵、`work/ledger-trace.md` | 每条 R 的预期断言已对照测试 |
| P3 静态遍历 | 测试账本、流程账本、三向追溯 | 每个测试函数/流程行/R 都有结论 |
| P4 变异探针 | `work/mutants/`、运行日志 | 每个高风险 R 有变异结果 |
| P5 rubric 三仿真 | `work/ledger-rubric.md`、四项算术 | 坏解 ≥2、双标注员或标“未双盲” |
| P6 归并成稿 | `review.json` | 每条能指到“哪一行会让它失败” |
| P7 自检提交 | `work/selfcheck.md` | strict VALID、0 FAIL 0 WARN |

默认 120 分钟，附 60/30 分钟降级路径；Docker 不可用时第一部分如实 `completed=false`，不阻塞第二、三部分。

## 目录

```
taskpack-audit/
├─ SKILL.md                    # 入口：红线、流程、门禁、反模式
├─ references/
│  ├─ review-schema.md         # review.json 唯一权威 schema
│  ├─ issue-taxonomy.md        # 14 类 issue_type 的判据与边界
│  ├─ defect-patterns.md       # 测试/rubric 缺陷模式库（42 条）
│  ├─ sweep-protocol.md        # 账本模板、三向追溯、归并规则
│  ├─ rubric-audit.md          # 参考解/坏解/双标注员三仿真 + 四算术
│  ├─ evidence-rules.md        # 引文、行号、source 规则
│  ├─ env-runbook.md           # Docker 构建/运行/取字段
│  ├─ async-cancel-lens.md     # 异步取消题族的状态 × 事件矩阵
│  └─ worked-example.md        # 五种 issue 的完整写法
├─ scripts/
│  ├─ inventory.py             # AST 测试清单 → 账本骨架
│  ├─ validate_review.py       # schema / 枚举 / id / 类型-来源校验
│  └─ verify_evidence.py       # 引文逐字可核（含多文件行号）
└─ templates/review.json       # 材料没有模板时的起稿
```

## 设计原则

1. **账本优先**：覆盖率按行数算，不按“读得多细”算。第一产物是账本，不是问题清单。
2. **反证优先**：能用一个变异实现证明的，不用“可能/风险”描述。
3. **引用即断言**：写不出原文位置的问题，不算问题。
4. **一因一条**：同一机理多处症状合并；同一位置不同机理可以并存。
5. **时间盒与降级**：先保证合法 JSON 和可提交的覆盖，再谈深度。

## 验证

本 skill 在一个 **合成任务包**（19 条预埋缺陷：12 测试/流程 + 7 rubric）上做过盲测：

| 版本 | recall | precision | evidence | 加权总分 |
|---|---|---|---|---|
| v0（初版） | 18/19 | 19/22 | 18/22 | 90.77 |
| v1 | **19/19** | 20/21 | 21/21 | **97.47** |

裁判按预注册协议盲评，v1 胜出后安装；随后对校验器/文档做硬化（v1.1），v1 的产出在 v1.1 strict 下复跑 21/21，无回归。

需要说明：

- 这是**合成包**上的方法有效性测试，不是对隐藏 gold 的召回承诺。
- 合成包与 skill 的缺陷模式库同源设计，19/19 偏乐观；真实任务包到手要按题面重跑，不要套结论。
- 环境部分在没有 Docker 的机器上应如实记 `completed=false`；本仓库不提供伪造的容器结果。

## 限制

- 看不到隐藏的核心问题清单，覆盖账本只是代理指标；账本有空行一定漏，但账本全绿不等于命中 gold。
- 静态审计不能替代运行；没跑过的变异体，证据只能降级为 `test_code`，不能写成 `run_output`。
- `undefined_requirement` / `undefined_criterion` 的边界有判断空间；类型拿不准时按 `issue-taxonomy.md` 的主导类型规则走。
- 本 skill 不判断“这道题该不该出”，只判断“验证与评分对不对”。

## 贡献

欢迎提 issue / PR：

- 新增缺陷模式（附最小复现包或真实案例）
- 改进 `verify_evidence.py` 的多文件/中文标点处理
- 增加不同题族的 lens（当前只有异步取消）
- 把 skill 跑在真实任务包上，反馈漏报/误报

## License

MIT © 2026 孟科航 (finalskiller)

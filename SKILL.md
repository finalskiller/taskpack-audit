---
name: taskpack-audit
description: |
  任务包审计：审核评测大模型编程能力的任务包（instruction / environment / tests / rubric），
  先建覆盖账本逐函数、逐断言、逐评分条目遍历，再用变异实现与 rubric 三仿真做反证，
  最后逐字校验证据，产出一份五项齐全的 review.json。
  触发语：审任务包、审测试、找测试漏洞、评 rubric、review.json、任务包质检、评测包审核、taskpack audit。
  不用于：从零写测试、修任务包、给模型写解法、只跑一遍测试、普通项目的单元测试审查。
---

# 任务包审计

> 覆盖率是门槛，证据是货币，反证是方法。

## 这个 skill 解决什么

审一个评测任务包：题面要求了什么、测试是否真的验证了、rubric 是否打得准。
产出 `review.json`：每条问题五项齐全（location / description / evidence / impact / suggestion），证据逐字可核。

**核心判断**：覆盖率按「条」算，不按「读得多细」算。所以第一产物不是问题清单，是覆盖账本。

## 这个 skill 不做什么

- 不替你写解法、不改材料包、不修测试。只审计、只出报告。
- 不判断题目本身难不难、有没有价值。只判断验证与评分是否正确、是否遗漏。
- 不把「我觉得可能有问题」写成问题。写不出位置和原文的，不进 `review.json`。

---

## 三条红线（先读，再动手）

1. **没跑过的，不许写成跑通。** `environment` 的 10 个必填键只填实际观测值（见 `references/review-schema.md`）；没跑到就 `completed: false` + `stopped_at`，`problems` 写现象。第一部分允许失败，不允许编造。
2. **引用必须逐字可核。** `evidence.content` 是原文连续子串，`where` 的行号对得上。提交前必须过 `scripts/verify_evidence.py`；抄错一个字就重抄，不改行号迁就引用。
3. **题面没约定的，先查再定。** 题面**明确写「未规定」**而测试仍当判据 → `false_rejection`（改测试）；题面**沉默** → `undefined_requirement`（补题面）。不要拿测试的实现当题面要求。

---

## 交付物

| 文件 | 是否提交 | 作用 |
|---|---|---|
| `review.json` | 是 | 唯一提交物；字段名以材料 `review_template.json` 为准，结构以 `references/review-schema.md` 为准 |
| `work/contract.md` | 否 | 题面要求表（R1…Rn），覆盖率的分子 |
| `work/ledger-tests.md` | 否 | 测试函数账本，每个函数一行，多断言拆行 |
| `work/ledger-flow.md` | 否 | test.sh 流程账本，奖励/退出码/路径逐行 |
| `work/ledger-trace.md` | 否 | R × 测试 × rubric 的三向追溯 |
| `work/ledger-rubric.md` | 否 | rubric 条目账本，每条一行 |
| `work/candidates.md` | 否 | 候选问题池，先求全，后求准 |
| `work/mutants/` | 否 | 变异实现与运行输出，`run_output` 证据的来源 |
| `work/env.md` | 否 | environment 10 个必填键与原始日志摘要 |
| `work/selfcheck.md` | 否 | P7 逐项勾选与两个校验器的实际输出 |

工作目录放材料包同级，**不要往材料包里写文件**。

---

## 角色分工（有多 agent 时）

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| 枚举者 | P2–P4：建契约表、填测试账本、写变异体 | 不写最终 issue 文案 |
| 证伪者 | 对每条候选反证：引用是否存在、判断是否成立、类型是否对 | 不新增候选 |
| 标注员 A / B | P5 双仿真，只看 rubric + 提交 | 不看题面、不看对方分数 |
| 主审 | rubric 审计、P6 归并、P7 提交 | 不替代证伪者给自己放行 |

**没有 subagent 时**：枚举与证伪由同一 agent 分两段做，中间清空上下文、重贴材料；双标注员按「同一 agent 两段、只重贴 rubric + 提交」降级，报告标「未双盲」，且**不能作为 `unobservable` 的证据**。

**证伪者的三问**（每条候选都过）：
1. 这条引文在原文里真的存在吗？
2. 它支持 description 里的判断吗，还是只能支持一个更弱的说法？
3. 有没有一个符合题面的实现，会被这条判断误伤？

三问有一问答不上，删掉或降级。

---

## 执行流程

默认 120 分钟，是硬上限。Docker 冷启动/拉镜像超过 10 分钟，就从 P4/P5 借时间，不延长总时长。60 分钟降级版见本节末。每个阶段有「产出」和「门禁」，门禁不过不进下一阶段；P3–P6 最多循环 2 次，第 2 次仍不达标就交当前最优版本 + 未解决清单。

### P0 · 接包（10 分钟）

读四样，先不读测试：`instruction.md`、`task.toml` / `README.md`、`review_template.json`、评分说明。
材料里没有 `review_template.json` 时，用本 skill 的 `templates/review.json` 起稿。
产出 `work/contract.md`：每条要求一个编号，写成**可观察**形式，并带一列「预期断言」。

**「预期断言」必须在跑 `tests/test.sh` 之前落盘**。这是防锚定的锚：先写下「我会怎么断言」，再去对照真实测试，差集才是 `missing_validation`。

```
| R | 原子要求（一个可观察量） | 预期断言 | 原文 |
| R2a | pending cancel 返回 True | assert ret is True | L16 |
| R2b | pending 取消后协程体零步 | assert steps == 0 | L16 |
| R2c | pending 取消后 await 抛 CancelledError | assert error == "CancelledError" | L16 |
| R3a | running cancel 停在检查点 | assert steps < 5 | L17 |
| R3b | finally 执行 | assert cleanup is True | L17 |
| U1 | 取消后 result 的值 | 题面未定义 | L27 |
```

**一条 R 里有多个可观察量就拆成 R2a/R2b/R2c。** 一行一个原子要求；G3 按原子行映射，否则「R2 已映射到 test_pending_cancel」会掩盖零步/返回值/异常三件里漏掉的两件。

同时列 `U*`：题面没写的边界（异常类型、返回值、并发时序、幂等语义、日志文案）。**列多少算多少，不硬凑。**

**门禁 G0**：每条 MUST/禁止项（题面含 必须/不得/只能/返回/需要/应当 的句子）都进了 R 表；每条 R 都有「预期断言」或标「题面模糊，候选 undefined」。

### P1 · 环境（10 分钟，可失败）

按 `references/env-runbook.md`：构建 → 跑 `solution/solve.sh` → 跑 `tests/test.sh` → 填 `environment` 的 10 个必填键，写 `work/env.md`。
契约表已在 P0 冻结，所以现在跑测试不会污染预期断言。

顺手记基线：**参考解能不能让测试全过**。参考解都过不了，优先查是不是测试错杀了正确实现（`false_rejection` 高发点）。
再跑一个**空实现**（`pass` / 返回占位）做对照：空实现也全绿，说明测试入口或断言有根本问题，优先查 `test.sh` 和恒真断言。

失败不阻塞：Docker 不可用、镜像拉不下、`/logs` 不可写，如实写进 `problems`，继续 P2。
第一部分只有 10 分，第二部分 55 分，时间跟着分数走。

**门禁 G1**：`environment` 10 个必填键都有值或 null；`completed` 与 `reward` / `test_result` / `stopped_at` 自洽（见 `references/review-schema.md`）。

### P2 · 建模（5 分钟）

读 `references/async-cancel-lens.md`（题族不是异步取消时，换成等价的状态 × 事件矩阵）。
把题面变成矩阵，每个格子问：**题面要求这里发生什么？现在有测试管它吗？**

拿 P0 的「预期断言」逐条对照真实测试：有 / 无 / 弱。差集就是 `missing_validation` 候选；写不出预期断言的 R 转 `undefined_requirement`。

**门禁 G2**：每条 R 的预期断言都已对照过测试，结论（有/无/弱）写进 `work/ledger-trace.md`。

### P3 · 静态遍历（30 分钟）

1. 跑 `python scripts/inventory.py --root <包> --ledger` 生成账本骨架（Windows 下不要依赖 shell 展开 `*`）。
   `tests/test.py` 这类被拉起的脚本用 `--all` 按函数过一遍：它的异常吞没、超时、输出格式都属于审计对象，不能只列 `test_*`。
2. 逐函数填 `work/ledger-tests.md`：位置 / 声称验证 / 实际断言 / 结论 / 依据 / issue。
3. 每个函数必问三句：
   - 被测函数是空实现，这条断言会失败吗？不会 → `wrong_validation`。
   - 实现只做断言里那件事、不做题面要求的事，会过吗？会 → `wrong_validation`。
   - 题面这条要求，哪一行断言会让违反它的实现失败？找不到 → `missing_validation`。
4. `tests/test.py` 这类 helper 另问一句：**它有没有吞异常、吞输出、改时序，让测试看不到真实行为？** 这类问题记 `tooling_defect`。
5. **流程账本**：`tests/test.sh` 每一行奖励/退出码/路径至少一行结论（`ledger-flow.md`）。命中率最高的问题就在这几行，不能没有账本行。
6. 填 `work/ledger-rubric.md` 的骨架（P5 补结论）。
7. 做三向追溯：`R 要求 × 测试函数 × rubric 条目`，写 `work/ledger-trace.md`。任何一列出现孤儿，进 `candidates.md`。

**门禁 G3**：每个测试函数、每条流程行、每条 R 都有结论，没有空行。

### P4 · 变异探针（20 分钟）

写 6–10 个变异实现（每个 10–30 行），逐个跑测试。**测试通过 = 漏洞**，这就是 `run_output` 证据。

三条硬要求：
1. **观测通道**：用 pytest / 包自带 runner 的退出码 + 失败用例名判断「杀死/存活」，**不要用 `test.sh` 的 reward**——它可能恒为 1（本包就是），拿它判会所有变异体假存活。`test.sh` 坏了先记 `tooling_defect`，再直跑 runner。
2. **注入点**：先找包提供的注入方式（环境变量、import 路径、复制覆盖）；没有就把包复制到 `work/pkg/` 改被测文件，**不要改材料包**。
3. **单点变异**：一个变异体只改一个行为，先写明「目标可观察量」和「哪条测试应该杀死它」。改两个行为，存活了也说不清漏洞在哪。
变异体放 `work/mutants/`，命令与输出原样保存。

异步取消的典型变异见 `references/async-cancel-lens.md` 的 M1–M14。每个变异体先写一句「哪条测试应该杀死它」，杀不死才有信息量。

**门禁 G4**：高风险 R 指含「不得 / 停止 / 返回 / finally / 隔离 / 顺序」任一词的 R；每个高风险 R 至少有一个变异体结果（杀死 / 存活 / 不适用）。其它 R 可标「低风险，未跑」，不硬凑。

### P5 · rubric 三仿真（20 分钟）

不要当散文读，当评分函数跑三遍（细则见 `references/rubric-audit.md`）：

1. **参考解仿真**：先解析 `task.toml` 的 `[solution].reference` / `[verification].entry_impl`；执行 `solution/solve.sh`，把**它产出的实现**当提交逐条打分（不是给 `solve.sh` 本身打分）。掉分条目 → `contradicts_code` 或 `penalizes_correct`。
2. **坏解仿真**：至少 2 个坏实现，其中一个必须是 P4 存活的变异体，另一个用「空实现 / 只让 test.sh 通过」原型。按 rubric 打分；坏解在核心条目拿满分 → `rewards_wrong_behavior`。
3. **双标注员仿真**：把 `rubric.md` + 一份提交包（实现文件 + 真实 pytest 汇总 + reward）复制到隔离目录，两个独立 agent 只看这两样，各打一次；分差条目 → `undefined_criterion` / `unobservable`。同一 agent 分两段只算「未双盲」，不能作为 `unobservable` 的证据。

外加**四项算术**：加总（Σ条目 vs rubric 声称满分 vs `task.toml max_score`）、上限（单条是否超总分/负分）、分布（核心 R 条目 vs 代理/风格/测试通过条目的分值倒挂）、重复（同一份证据能否同时拿两条的分）。
最后做要求覆盖：拿 **P0 的原子 R 表**逐行判定 rubric 覆盖，写进 `work/ledger-trace.md` 的 rubric 列；没有**行为锚点**条目 → `missing_criterion`。汇总型条目（测试全过、覆盖率、总分达标）不算覆盖锚点。

**门禁 G5**：每条 rubric 条目都有结论；坏解仿真至少跑了 2 个（含 1 个 P4 存活变异体；若 P4 没有存活体，用「空实现 / 只让 test.sh 通过」代替并说明）；四项算术都有数；双标注员至少 1 组，或标「未双盲」——`unobservable` 可以用静态证据写，但必须注明未双盲。

### P6 · 归并与成稿（15 分钟）

- 按「文件 + 函数 + 机理」去重；同一机理多处症状合并成一条，位置列全。
- **同一位置、不同机理不要合并**：同一个 test 里「只查异常类型」与「墙钟 flaky」是两条；同一 rubric 行上「重复计分」与「缺核心条目」也可以并存。
- **rubric 一行最多两条**：一条「现有条目有问题」（duplicate / undefined / unobservable / contradicts 选主导），一条「该要求没有条目」（`missing_criterion`）。不要再把 duplicate 拆成 duplicate + undefined + missing 三条。
- `location` 只放主位置；其它症状写进 `description` 和 `evidence.where`，不要为多个位置改 schema。
- 定 `issue_type`：先按 `references/issue-taxonomy.md` 的判定树走，不发明新类型；事实冲突优先 `contradicts_code`，纯算术优先 `process_defect`。
- 证据先抄原文（带行号），再写 reasoning；reasoning 回答「这段原文为什么能支持这个判断」，不是复述。
- `impact` 写两句：放行什么错误实现 / 误杀什么正确实现。写不出具体实现，说明这条没想清楚，回 P3/P4。
- `suggestion` 落到断言：改哪一行、断言写成什么样，最好直接给代码。
- **条数自检**：测试侧 <8 或 rubric 侧 <5 时，回到 `references/defect-patterns.md` 的「高分区的六个信号」再过一遍。确实没有的，在账本里写 OK 并给理由，不硬凑。

**门禁 G6**：
- `wrong_validation` / `false_rejection` / `flaky` / `tooling_defect` → 能指到具体 `file:line`。
- `missing_validation` → 能指到「题面 R + 测试里应该有断言的位置」；**不要求存在一行会让它失败的代码**——缺的就是那一行。
- rubric 侧 → 能指到条目编号 + 锚点/缺失。

答不出的删掉，或降级为 `candidates` 未确认。

### P7 · 自检与提交（10 分钟）

```bash
python scripts/verify_evidence.py review.json --root <包> --work <work目录> --strict
python scripts/validate_review.py review.json --strict
```

两个都绿（0 FAIL、0 WARN），再确认 `candidate` / `submitted_at`（YYYY-MM-DD）/ id 连续（T01…、R01…）/ 无空串，把结果写进 `work/selfcheck.md`，再过 `references/evidence-rules.md` 末尾的清单，提交。

**门禁 G7**：`validate_review.py --strict` VALID；`verify_evidence.py --strict` 0 FAIL 0 WARN；`work/selfcheck.md` 有逐项勾选。

### 60 分钟降级版

P0+P1 合并 10 分钟 → P2 5 分钟 → P3 20 分钟（账本 + 只跑 1 个最高风险变异体）→ P5 10 分钟（参考解仿真 + 1 个坏解）→ P6 10 分钟 → P7 5 分钟。
原则：**先保证 20 条以上候选和合法 JSON，再谈深度**。覆盖率按条算，空着就是 0。
降级模式在 `notes` 标 `degraded: 60min`；G4 只要求 1 个高风险 R 有结果，G5 坏解 1 个，其余标「降级未做」，不算通过。

### 30 分钟极限版

只做 P0 + P1 记录 + P3 账本 + 最确定的 6 条 issue；P4/P5 在账本里标 `not_run`，`notes` 标 `degraded: 30min`。P7 只要求 JSON 合法 + `verify` 0 FAIL（不要求 0 WARN），不假装跑过探针。

---

## 门禁汇总

| 门禁 | 时机 | 判据 |
|---|---|---|
| G0 | P0 后 | R 表覆盖全部 MUST/禁止项；每条 R 有预期断言或标「题面模糊」 |
| G1 | P1 后 | environment 10 个必填键有值或 null；completed 与 reward/test_result/stopped_at 自洽 |
| G2 | P2 后 | 每条 R 的预期断言已对照测试（有/无/弱）并写进 ledger-trace |
| G3 | P3 后 | 测试函数、流程行、R 三元组全部有结论，无空行 |
| G4 | P4 后 | 每个高风险 R 有变异结果（杀死/存活/不适用） |
| G5 | P5 后 | rubric 账本无空行；R 表的 rubric 列已填；坏解 ≥2（含 1 个 P4 存活变异体，无存活体则用空解）；四项算术有数；双标注员 ≥1 组或标「未双盲」 |
| G6 | P6 后 | 测试 issue 指到 `file:line`（missing 指到「应有断言的位置」）；rubric issue 指到条目 + 锚点 |
| G7 | P7 后 | strict 校验 VALID；0 FAIL 0 WARN；selfcheck 有勾选 |

---

## 反模式黑名单

| # | 反模式 | 为什么错 / 替代做法 |
|---|---|---|
| 1 | 「测试覆盖不全，建议补充边界用例」 | 没有位置、原文、具体断言，不得分。指到 R 编号 + 函数 + 行号 |
| 2 | 证据抄摘要或转述，不抄原文 | 核对时对不上，整条作废。照抄 2–5 行，保留标点 |
| 3 | 同一根因拆三条凑数 | 不重复计分，还稀释重点。按「文件 + 函数 + 机理」合并 |
| 4 | 把「测试没覆盖」写成 `wrong_validation` | 类型错。没覆盖是 `missing_validation`，断言没验到才是 `wrong_validation` |
| 5 | 题面沉默却写 `false_rejection` | 题面**明确写了「未规定」**而测试仍当判据 → `false_rejection`（改测试）；题面**沉默** → `undefined_requirement`（改题面） |
| 6 | `impact` 写「可能导致错误实现通过」 | 太空。写出具体实现：「cancel 只置标志、不打断执行」 |
| 7 | `suggestion` 写「建议加强断言」 | 没落地。给具体断言或具体条件 |
| 8 | 为凑数写没把握的条目 | 判断错误影响整体评估。宁可少一条，不写没证据的 |
| 9 | 环境没跑写成跑通 | 红线。`completed: false` + `stopped_at` + `problems` |
| 10 | 把 `solution/solve.sh` 当标准答案 | 它是对照组，不是满分模板。它也可能有 bug、也可能被 rubric 错杀 |

---

## 失败与降级

| 触发条件 | 一线修复 | 仍失败兜底 |
|---|---|---|
| Docker / 镜像不可用 | 换镜像源（`docker.m.daocloud.io/...`）；`mkdir -p logs` 后重跑 | `completed: false`，`stopped_at: "docker build"`，problems 写原始报错 |
| `/logs` 不可写 | 容器内 `mkdir -p /logs/verifier`；或挂载可写目录 | 如实记录，测试结果标「未观测」 |
| 材料包缺文件 | 按现有文件审；在 notes 说明缺哪份、影响哪部分 | 只交能证的部分，不补写 |
| 测试 collect 失败 | 先修运行方式（cwd、依赖），不改测试内容 | 记为 `tooling_defect`，继续静态审计 |
| 时间不足 60 分钟 | 走降级版：账本优先，探针只做 1 个（最高风险 R） | 先交合法 JSON + 20 条候选 |
| 无 subagent（双标注员做不了） | 同一 agent 分两段，中间清空上下文重贴 rubric | 报告里标「未双盲」 |
| 变异体跑不起来 | 只做静态反证，证据降为 `test_code` | 在 impact 里说明未做动态验证 |
| 没有 Python | 手写账本，用 `grep`/读文件代替 `inventory.py`；脚本不阻塞 | 在 notes 说明未用脚本 |
| 没有 `review_template.json` | 用 `templates/review.json` 起稿 | 在 `environment.notes` 记「package has no template」 |
| 没有 `rubric.md` | `rubric_review` 交 []，在 notes 说明材料缺 rubric | 不编条目 |
| 没有 `solution/solve.sh` | 找 `task.toml [solution].reference` 或包内实现；找不到就跳过参考解仿真并记 notes | 不把「没参考解」写成「参考解满分」 |
| 非 Python 包 | `inventory.py` 不适用；按目录/文件手写账本；变异体用包的语言写 | 只做静态审计，证据降级 |
| `work/` 不可写 | 换到系统临时目录，用 `--work` 指过去；notes 记路径 | 直接写 `review.json` 同级的 `work/` |
| 无 bash | 用 `sh` / PowerShell 翻译 `test.sh` 的命令；不改测试内容 | 只做静态审计，环境标未观测 |
| 校验器跑不起来 | 手动过五项 + 原文逐条对照；notes 记「未用脚本」 | 不假装 0 FAIL |

---

## 质量自检（交付前）

| 维度 | 通过标准 | 不通过信号 |
|---|---|---|
| 覆盖 | 账本（tests / flow / trace / rubric）无空行 | 有函数没看、有流程行没结论、有 rubric 条目没结论 |
| 证据 | `verify_evidence.py --strict` 0 FAIL 0 WARN | 引用对不上、行号漂移、run_output 无记录 |
| 类型 | 每条类型能用判定树解释 | 类型混用（missing vs wrong、undefined vs false_rejection） |
| 影响 | 每条能说出具体错误实现 / 正确实现 | 只有「可能」「风险」 |
| 修正 | 每条是具体断言或条件 | 「建议补充」「加强验证」 |
| 提交 | `validate_review.py --strict` VALID | 空串、id 断号、枚举错、completed 与 reward 冲突 |

---

## 诚实边界

- 你看不到隐藏的核心问题清单。覆盖账本是**代理指标**：账本全覆盖不等于命中 gold，但账本有空行一定漏。
- 合成包能测方法，不能替代真题。真题到手要重跑 P0–P5，不要套结论。
- 静态审计不能替代运行。没跑过的变异体，证据只能降级为 `test_code`，不能写成 `run_output`。
- 机器只能验证「引文存在」，不能验证「不存在」和「真的跑过」：`missing_validation` 要留 `work/search.log`，`run_output` 要留真实命令输出；两样造假都是编造。
- 类型边界有歧义时按判定树选主导类型，另一个写进 impact；不要为一条问题编两个类型。
- 本 skill 不判断「这道题该不该出」，只判断「验证与评分对不对」。

---

## 参考文件

| 文件 | 什么时候读 |
|---|---|
| `references/review-schema.md` | P0 起稿、P7 校验前（唯一权威 schema） |
| `references/issue-taxonomy.md` | 定 issue_type、写 evidence 时 |
| `references/defect-patterns.md` | P3/P5 找候选、判断「这算不算问题」时 |
| `references/sweep-protocol.md` | P3 建账本、P6 归并时 |
| `references/rubric-audit.md` | P5 rubric 三仿真时 |
| `references/evidence-rules.md` | 写证据、P7 自检时 |
| `references/env-runbook.md` | P1 构建与抓字段时 |
| `references/async-cancel-lens.md` | P2 建模、P4 选变异体时 |
| `references/worked-example.md` | 第一次写 issue，照格式时 |

模板：`templates/review.json`（材料没有模板时起稿用）。

脚本：`scripts/inventory.py`、`scripts/verify_evidence.py`、`scripts/validate_review.py`。没有 Python 就先手写账本，脚本不阻塞审计。

---

## 版本

v1.1 · 2026-11-25 · 方法来源：覆盖账本 + 变异探针 + rubric 三仿真；结构参考 Nuwa 的阶段门禁、失败降级与反模式清单。v1.1 经四路对抗审查修订：schema 文档化、类型判定树去歧义、strict 校验、原子 R、观测通道。

# issue_type 判定手册（14 类）

> 类型不是标签，是判断。选错类型，等于把「没覆盖」说成「验错了」，证据再足也不成立。

## 先走判定树

### 测试侧（6 类）

```
这条问题出在测试/验证流程？
├─ 题面有没有约定这个行为？
│  ├─ 明确写「未规定 / 未要求」，测试仍当判据 → false_rejection（测试越界，改测试）
│  ├─ 题面沉默（没写） → undefined_requirement（补题面）
│  └─ 有约定 → 继续
├─ 测试声称验证 X，断言能不能区分 X 与「非 X」？
│  ├─ 不能 → wrong_validation
│  └─ 能 → 继续
├─ 题面要求 X，测试完全没有？
│  ├─ 是 → missing_validation
│  └─ 否 → 继续
├─ 测试能区分，但合法替代实现会被判错？→ false_rejection
├─ 结果依赖时序/环境/执行顺序？→ flaky
└─ 问题在 test.sh / 收集 / 奖励计算 / 退出码？→ tooling_defect
```

### rubric 侧（8 类）

```
这条问题出在评分表？
├─ 与 instruction / README / task.toml / 参考解的事实冲突？→ contradicts_code
├─ 纯算术（分值加总、档位换算、上限）错？→ process_defect
├─ 坏解能拿高分？→ rewards_wrong_behavior
├─ 正确解被扣分（题面不冲突，只认一种合法实现）？→ penalizes_correct
├─ 标注员物理上拿不到判据所需信息（要运行/日志/内部状态）？→ unobservable
├─ 两条用同一份证据重复给分？→ duplicate_scoring
├─ 有判据但档位/程度词没有边界，两人会打出不同分？→ undefined_criterion
└─ 题面核心要求没有对应条目？→ missing_criterion
```

**主导类型优先规则**（同一现象能套多类时）：

1. 事实冲突 → `contradicts_code`；impact 里写「同时惩罚正确实现」，不要再拆 `penalizes_correct`。
2. 纯算术/流程 → `process_defect`；不要因为分数与 README 不一致就写 `contradicts_code`。
3. 完全没有条目 → `missing_criterion`；有条目但没锚点 → `undefined_criterion`；标注员物理上拿不到信息 → `unobservable`。
4. 题面**明确写「未规定」**而测试仍当判据 → `false_rejection`；题面**沉默** → `undefined_requirement`。这是最容易反的两类。
5. 同一位置不同机理可以并存；同一机理不同位置合并。

---

# 测试侧

## 1. wrong_validation（验证不正确）

**定义**：测试声称验证 X，但断言实际验证的是 Y，或断言弱到无法区分 X 与「非 X」。

**判据**（满足任一）：
- 把被测函数换成空实现 / 只做断言里那件事的实现，测试仍然通过。
- 断言只检查代理信号（状态标志、异常类型、文件存在、长度 >0），不检查题面要求的可观察结果（副作用、停止位置、返回值）。
- 断言在 `try/except: pass` 或 `assert True` 之后，永远不会失败。

**证据**：`source: test_code`；`where` 指向断言所在行（被断言量的定义行也写进 where）；`content` 只抄断言原文；`reasoning` 说明「哪个实现能同时满足断言、违反题面」。

**正例**：
> 声称验证「取消后不再执行任务体」，断言只有 `with pytest.raises(CancelledError)`；一个执行完全部步骤再抛 `CancelledError` 的实现同样通过。

**边界**：
- 断言弱但题面也只要求弱信号 → 不算，或标 `undefined_requirement`。
- 测试根本没有这条断言 → 是 `missing_validation`，不是 `wrong_validation`。

---

## 2. missing_validation（验证遗漏）

**定义**：题面明确要求 X，但没有任何测试能让违反 X 的实现失败。

**判据**：
- 在测试文件里搜不到对应断言/用例。
- 或者有同名用例，但断言的是别的东西（此时主导类型可能仍是 `missing_validation`，如果「完全没覆盖」比「断言弱」更本质）。
- 用变异体 M 违反 X，跑全部测试仍全绿。

**证据**：`source: instruction`（题面要求）或 `run_output`（存活变异体）；`where` 写题面行 + tests 全文搜索范围（或变异体命令）；`content` 抄题面要求原文（或存活输出）；`reasoning` 说明为什么现有用例覆盖不到。

**正例**：
> 题面 R4「取消已完成任务返回 False」；测试里没有 `after_done` 场景，也没有对 `cancel()` 返回值的断言。

**边界**：
- 题面没要求 → `undefined_requirement`。
- 有测试但断言弱 → 主导类型通常是 `wrong_validation`，除非该用例根本没碰这条要求。

---

## 3. false_rejection（错杀正确实现）

**定义**：测试能区分对错，但把题面允许的合法实现判成失败。

**判据**：
- 断言依赖题面没规定的实现细节：具体文案、日志格式、内部属性名、调用次数、异常消息、精确浮点、顺序。
- 题面**明确写「未规定」**，测试仍把这个细节当判据。
- 题面允许多种实现（如用 `create_task` 或 `TaskGroup`），测试只认一种。
- 参考解能过，但另一个符合题面的实现会挂。

**证据**：`source: test_code`（过严的那条断言）；`where` 同时写断言行号与题面 R 的行号；`content` 只抄断言原文（同一文件的连续子串）；`reasoning` 引题面原文说明它允许别的实现。

**正例**：
> 断言 `data["log"] == ["cleanup done"]`；题面只要求 `finally` 执行，没要求日志文案。不打日志的正确实现会挂。

**边界**：
- 题面明确规定了文案/格式 → 不算。
- 题面**沉默**、两种实现都合理 → `undefined_requirement`，不是 `false_rejection`。
- 参考解自己也挂 → 先查是不是参考解错，再判测试。

---

## 4. flaky（不稳定）

**定义**：结果依赖时序、调度、机器负载、网络、时钟、文件顺序、全局状态，重复跑会变。

**判据**：
- `sleep` / 墙钟阈值 / 无同步的并发 / 依赖 dict 顺序 / 依赖当前时间或时区。
- 测试之间共享全局状态，单独跑过、一起跑挂。
- 取消点用 `sleep` 近似，机器慢时取消发生在任务结束后。

**不要求本地复现。** 墙钟阈值 + 无同步/无界等待就够写；重复 50 次、加负载、改时区是增强证据，不是门槛。

**证据**：`source: test_code`；`where` 指到 `sleep`/时间断言/共享 fixture；`content` 抄那几行；`reasoning` 说明在什么负载/顺序下会翻转，并注明「本地未复现 / 复现 N 次」。最好附 `run_output`。

**正例**：
> `await asyncio.sleep(0.05)` 后 cancel，再断言 `elapsed < 0.5`；CI 负载高时任务先结束，cancel 返回 False，用例随机挂。

**边界**：
- 测试有确定性同步（Event/Barrier）→ 不算。
- 纯理论、没有任何时序依赖 → 不写；有 `sleep`/墙钟/无同步 → 可写，即使本地没翻转。

---

## 5. tooling_defect（工具/流程缺陷）

**定义**：问题不在断言，在验证入口、收集、执行、奖励计算、退出码、日志路径。

**判据**：
- `test.sh` 用 `|| true`、`set +e`、无条件写 reward、pytest 退出码没传播。
- reward 计算与测试结果脱钩（测试全挂也 reward 1）。
- `/logs` 没建、路径写错、cwd 错、依赖没装、只跑子集。
- 测试收集失败被当成通过。

**证据**：`source: test_code`；`where` 指到 `test.sh` 行；`content` 抄命令与 reward 写入；`reasoning` 说明「什么情况下会给出错误 reward」。附 `run_output` 更好（故意让测试挂，reward 仍为 1）。

**正例**：
> `python -m pytest test_outputs.py -q || true` 后无条件 `echo 1 > /logs/verifier/reward.txt`；测试全挂也拿 1。

**边界**：
- 断言本身的问题 → 归 `wrong_validation`，不要都塞进 tooling。

---

## 6. undefined_requirement（题面未定义）

**定义**：题面没有约定这个行为/边界，测试却按某个假设验证，或测试与实现的分歧根源在题面沉默。

**判据**：
- 在 `instruction.md` 里搜不到对应约定（异常类型、返回值、日志、取消点、幂等、并发时序）。
- 两种都合理的实现会得到不同测试结果，题面无法裁决。

**证据**：`source: instruction`；`where` 写「instruction.md 全文无 X 约定」+ 测试假设所在行；`content` 只抄题面最接近的那句（证明它没说）；`reasoning` 写测试做了什么假设、缺的是哪条约定。

**正例**：
> 题面没说取消后 `result` 返回什么；测试断言 `result is None`，另一种实现抛 `CancelledError` 也合理。

**边界**：
- 题面写了但模糊 → 仍是 `undefined_requirement`，在 description 里指出模糊点。
- 题面**明确写「未规定」**而测试仍当判据 → `false_rejection`（测试越界）。
- 题面写了且清楚，测试违反 → `wrong_validation`。

---

# rubric 侧

## 7. contradicts_code（与代码/题面事实矛盾）

**定义**：评分标准描述的事实与 `instruction.md`、`README.md`、`task.toml` 或 `solution/solve.sh` 不一致。

**判据**：
- rubric 说「必须用 X」，参考解用的是 Y。
- rubric 说「测试覆盖了 Z」，实际测试没覆盖。
- rubric 的分值/档位与 README 声称的不一致。
- rubric 要求的行为，题面没要求或明确不要求。

**证据**：`source: rubric`（主来源）；`where` 写条目编号 + `solve.sh` 行号；`content` 只抄 rubric 条目原文；`reasoning` 引 solve.sh 的那行代码说明冲突。

**正例**：
> rubric 条目 4「必须使用 `asyncio.TaskGroup`」，`solve.sh` 用的是 `asyncio.create_task`；参考解按此标准拿不到满分。

**边界**：
- rubric 比题面更严，但参考解做到了 → 可能只是冗余，不一定是矛盾；要看是否惩罚合法实现（→ `penalizes_correct`）。
- 纯粹分值加总/档位换算错 → `process_defect`，不要因为与 README 数字不一致就写 `contradicts_code`。
- 题面不冲突、只是只认一种合法实现 → `penalizes_correct`。

---

## 8. rewards_wrong_behavior（奖励错误做法）

**定义**：错误/投机的实现能拿到高分。

**判据**：
- 构造一个只做表面功夫的坏解，按 rubric 打分仍然高。
- 条目奖励「测试通过」「代码行数」「用了某个库」等可被钻空子的信号。
- 条目的判据与题面要考察的能力无关。

**证据**：`source: rubric`；`where` 写条目编号 + 坏解得分/代码位置；`content` 只抄条目原文；`reasoning` 写坏解怎么满足它、拿了多少分（可另附 `run_output`）。

**正例**：
> 条目 5「所有测试通过得 20 分」；测试本身有漏洞，一个只置标志不打断执行的实现也能全绿，拿满 20。

**边界**：
- 条目本身合理，但测试有漏洞导致坏解通过 → 主导类型可能是测试侧的 `wrong_validation`；rubric 侧写「依赖了不可靠的测试结果」。

---

## 9. penalizes_correct（惩罚正确实现）

**定义**：符合题面的正确实现，按 rubric 会掉分。

**判据**：
- 参考解掉分。
- 另一种合法实现（不同但符合题面）掉分。
- 条目要求题面没要求的风格/结构/库。

**证据**：`source: rubric`；`where` 写条目编号 + 参考解行号；`content` 只抄条目原文；`reasoning` 引参考解代码说明正确实现为什么不满足。

**正例**：
> 条目 4 要求 `TaskGroup`；参考解用 `create_task`，功能全对但被扣 15 分。

**边界**：
- 参考解本身有 bug → 不是惩罚正确，是参考解错；先确认题面。

---

## 10. unobservable（不可观察）

**定义**：标注员拿不到判据所需的信息，无法稳定打分。

**判据**：
- 判据需要运行测试/看 trace/看内部状态，但标注员只有代码 diff。
- 判据依赖未提供的产物（日志、覆盖率报告、性能数据）。
- 判据要求的信息在提交物里物理上不存在。

**证据**：`source: rubric`；`content` 抄条目；`reasoning` 说明标注员实际能看到什么、缺什么。

**正例**：
> 条目 5「所有测试通过（20 分）」；标注员只拿到代码 diff，没有测试输出或 reward，无法判断是否通过。

**边界**：
- 有条目、有判据，但档位/程度词没边界 → `undefined_criterion`。
- 有条目但完全没有可观察锚点（如「代码优雅」）→ `undefined_criterion`，不是 `unobservable`。
- 题面要求没有对应条目 → `missing_criterion`。

---

## 11. duplicate_scoring（重复计分）

**定义**：两条或多条 rubric 用同一份证据/同一个行为重复给分。

**判据**：
- 两条的判据指向同一个可观察量（如都看 `state == "cancelled"`）。
- 一条是另一条的子集。
- 同一处代码/同一个测试结果能同时满足两条。

**证据**：`source: rubric`；`content` 抄两条；`reasoning` 说明同一份证据如何同时得分。

**正例**：
> 条目 1「取消后状态为 cancelled」20 分；条目 2「取消生效」20 分，锚点仍是状态，没看副作用。

**边界**：
- 两条分别看不同维度（状态 vs 副作用）→ 不算重复。

---

## 12. undefined_criterion（标准不可判定）

**定义**：两个标注员按同一份 rubric 会打出不同的分，因为档位边界/判据没有定义。

**判据**：
- 档位描述重叠或缺失（「基本正确」「大致正确」没有边界）。
- 同一份提交落在两档之间，rubric 没有裁决规则。
- 判据用了程度词（充分、合理、较好）但没有锚点。

**证据**：`source: rubric`；`content` 抄档位/判据；`reasoning` 说明两种合理读法各打几分。

**正例**：
> 「部分正确 5–10 分」；一个覆盖 3/5 条要求的实现，两个标注员一个给 6 一个给 9，rubric 无法裁决。

**边界**：
- 完全不可观察 → `unobservable`；这里强调「能观察但判不准」。

---

## 13. missing_criterion（关键要求无条目）

**定义**：题面要求/任务核心能力，rubric 没有对应条目。

**判据**：
- 契约表每条 R 去 rubric 找条目，找不到。
- 任务最核心的能力（如「取消后真的停止」）没有独立条目，只被模糊条目顺带覆盖。

**证据**：`source: instruction`（主来源）；`where` 写 rubric 全文范围 + 题面行号；`content` 抄题面要求原文；`reasoning` 说明 rubric 里没有对应条目。

**正例**：
> 题面 R3「取消后不得再执行任务体」；rubric 只有「取消生效」，锚点是状态，没有条目看副作用。

**边界**：
- 已被某条目实质覆盖（有锚点、能判）→ 不算缺失。

---

## 14. process_defect（流程缺陷）

**定义**：评分表本身的算术/汇总/档位换算/使用流程有错。

**判据**：
- 权重加起来不等于声称的总分。
- 档位换算表与分值不匹配。
- 多条分值相加超过上限。
- 评分流程要求标注员做不可能/未定义的动作。

**证据**：`source: rubric`；`content` 抄分值表；`reasoning` 给出算术。

**正例**：
> 声称满分 100，六个条目 20+20+10+15+20+10=95，缺 5 分；标注员按表打分永远到不了 100。

**边界**：
- 单条判据模糊 → `undefined_criterion`；这里强调算术/流程。

---

## 证据字段的最低要求

> `evidence.source` 只能填一个值，`content` 只能是一段连续原文。
> 第二处引用写进 `where` 和 `reasoning`，**不要拼进 content**——`verify_evidence.py` 会按单文件连续子串校验。

| 类型 | source | where 必须包含 | content 必须包含 |
|---|---|---|---|
| wrong_validation | test_code | 断言行号 + 定义行 | 断言原文（一条）；定义行写 reasoning |
| missing_validation | instruction / run_output | 题面行 + 测试全文搜索范围（或变异体命令） | 题面要求原文（或存活输出）；测试缺失写 reasoning |
| false_rejection | test_code | 断言行号 + 题面 R 行号 | 过严断言原文；题面允许范围写 reasoning |
| flaky | test_code | sleep/时序/共享状态行 | 那几行；重复运行结果写 reasoning 或另附 run_output |
| tooling_defect | test_code | test.sh 行号 | 命令 + reward 写入 |
| undefined_requirement | instruction | 题面搜索范围 + 测试假设行 | 最接近的题面原文；测试假设写 reasoning |
| contradicts_code | rubric | 条目编号 + solve.sh 行号 | 条目原文；solve.sh 那行写 reasoning |
| rewards_wrong_behavior | rubric | 条目编号 + 坏解得分 | 条目原文；得分/代码写 reasoning 或 run_output |
| penalizes_correct | rubric | 条目编号 + 参考解行号 | 条目原文；参考解代码写 reasoning |
| unobservable | rubric | 条目编号 | 条目原文 |
| duplicate_scoring | rubric | 两条条目编号 | 主条目原文；另一条写 reasoning（两条不相邻时） |
| undefined_criterion | rubric | 条目/档位行号 | 档位原文 |
| missing_criterion | instruction | rubric 全文范围 + 题面行 | 题面要求原文；rubric 缺失写 reasoning |
| process_defect | rubric | 分值表行号 | 分值原文；算术写 reasoning |

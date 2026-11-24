# 证据规则

> 复核方式是「逐条核对位置和原文」。抄错一个字、行号漂了，这条就废了。

## 五项的最低标准

| 字段 | 不合格 | 合格 |
|---|---|---|
| location | 「测试文件里」 | `{file: "tests/test_outputs.py", ref: "test_cancel_running (L42-L55)"}` |
| description | 「验证不充分」 | 「声称验证 X，断言只检查 Y；只做 Y 的实现仍通过」 |
| evidence | 转述、摘要 | 原文连续子串 + 行号 + 为什么支持判断 |
| impact | 「可能导致错误实现通过」 | 「放行『cancel 只置标志、不打断执行』的实现」 |
| suggestion | 「建议加强断言」 | 「在 L50 后加 `assert data["steps"] == 1`」 |

## evidence.source 与允许的文件

| source | 只能引 | 典型 where |
|---|---|---|
| `instruction` | `instruction.md` | `instruction.md L12（R3）` |
| `test_code` | `tests/` 下任一文件 | `tests/test_outputs.py L48-L52` |
| `reference_solution` | `solution/` 下文件（含 `solve.sh` 写出的实现） | `solution/solve.sh L30-L44` |
| `run_output` | 你实际跑出的命令输出 | `python -m pytest tests/test_outputs.py -q（M1 存活）` |
| `task_metadata` | `task.toml` / `README.md` | `README.md L8` |
| `rubric` | `rubric.md` | `rubric.md L24（条目 4）` |

**一个 evidence 只有一个 source，一段 content。** `where` 可以写第二处引用的文件，但 `content` 必须来自 source 对应的文件；第二处的内容写进 `reasoning`。
`run_output` 不需要文件行号，但 `where` 要写清命令和场景，`content` 抄输出里的关键行，并且要在 `work/` 下有对应记录（`--work` 指向它）。

## where 的写法

- 单行：`tests/test_outputs.py L52`
- 范围：`tests/test_outputs.py L48-L55`
- 函数优先：`tests/test_outputs.py test_cancel_running (L42-L55)`
- 多条：`tests/test_outputs.py L52；L60-L62`
- 两处引用：`tests/test_outputs.py L48-L52；instruction.md R3（L18-L20）`（content 仍取 source 对应文件）
- rubric：`rubric.md 条目 4（L22-L26）`
- 题面：`instruction.md R3（L18-L20）`

行号从 1 开始。范围用半角连字符。不要写「大约」「附近」。**行号不能超界**；验证器不会 clamp，超界直接 FAIL。

## content 的写法

**照抄，不翻译，不改标点。** 规则：

1. 连续 2–5 行，能独立说明问题。太长就截取关键断言，但必须是连续子串。
2. 不省略中间内容；不要用 `...` 或 `" / "` 拼两段。需要第二处引用就写进 `where` / `reasoning`。
3. 保留原缩进可以，但校验时会做空白归一化；**字词和标点不能改**。
4. 引断言时，被断言对象的定义行写进 `where` / `reasoning`，不要拼进 content。
5. 引题面时，引最接近的完整句，不要只引关键词。
6. 单条引文超过 40 行会被 `--strict` 判 WARN；引到能说明问题的那几行。

反例：
> content: "测试只检查了异常类型，没有检查 steps。"

这是转述，不是原文。正确：
> content: "with pytest.raises(asyncio.CancelledError):\n    await handle"

## reasoning 的三段式

```
① 这段原文说了什么（定位）
② 它没说什么 / 与什么冲突（缺口）
③ 因此哪种实现能通过、哪种要求没被验证（结论）
```

例：
> ① 断言只覆盖 `CancelledError`，L30 定义的 `steps` 在整条用例中从未被读取；
> ② 题面 R3 要求「取消后不得再执行任务体」，这条要求对应的是 `steps` 停止增长；
> ③ 所以一个执行完全部 5 步再抛 `CancelledError` 的实现会通过，R3 没有被验证。

不要写「显然」「众所周知」「按理说」。不要用 reasoning 复述 description。

## impact 的两句话

1. **放行**：什么样的错误实现会通过/拿高分。写到能想象出代码。
2. **误杀**（如有）：什么样的正确实现会失败/被扣分。

例：
> 放行「cancel 只置 `state`、循环继续跑完」的实现；该实现违反 R3，但 5 条用例全绿。
> 不涉及误杀。

## suggestion 的三种落法

1. **改断言**：给出改哪一行、断言写成什么。
   > 在 `await handle` 之后加 `assert data["steps"] == 1`；用 `asyncio.Event` 固定取消点，不用 `sleep`。
2. **加用例**：给出用例名、场景、断言。
   > 新增 `test_double_cancel`：运行中连续 `cancel()` 两次，断言 `returns == [True, False]`。
3. **改评分条目**：给出条目文本与锚点。
   > 条目 4 改为「取消后 `steps` 不再增长（读 `handle.steps`）」，删掉「必须用 TaskGroup」。

不要写「建议补充边界测试」「加强验证」「完善文档」。

## 常见翻车

| 现象 | 后果 | 预防 |
|---|---|---|
| 引了测试，但行号是另一个函数的 | 核对失败 | 用 `inventory.py` 的行号，不手数 |
| 引了题面，但题面没这句 | 判断根基没了 | 复制前先在文件里搜一次 |
| content 用省略号或 `" / "` 拼接 | 不是连续子串 | 只引主来源一段；第二段写 where/reasoning |
| 行号写成 `L900-L999`（文件只有几十行） | 超界，strict 直接 FAIL | 用真实行号；不要用大范围兜底 |
| where 里两个文件顺序颠倒 | 旧版会取错文件；新版按 content 命中选 | content 必须来自 source 对应文件，顺序不影响 |
| reasoning 只说「这不对」 | 不能支持判断 | 用三段式，写出「哪种实现会过」 |
| impact 写「影响评分公平性」 | 空 | 写出具体实现/具体分数 |
| suggestion 写「补充测试」 | 不可执行 | 给用例名 + 断言代码 |
| `source: run_output` 但没跑过 | 编造 | 没跑就降级为 `test_code`，并在 impact 说明未动态验证 |
| `missing_validation` 只有一句「没有测试」 | 机器无法验证「不存在」 | 在 `work/search.log` 留 `grep`/搜索命令与无命中输出，`reasoning` 引它 |
| `run_output` 的日志是手写/补写的 | 机器只能查字符串，查不出真伪 | 只用 `work/mutants/` 里真实命令的输出；手写等于编造 |

## 校验器怎么判

`scripts/verify_evidence.py` 做五件事：

1. `source` 与所引文件的映射是否合法（instruction 只能引 instruction.md，等等）；
2. `content` 是否在**某个**所引文件的行范围内出现（空白归一化后做子串匹配；多文件按内容命中选，不按 where 顺序）；
3. 行号是否超界（**不 clamp**，超界直接 FAIL）；单条范围 > 40 行记 WARN；
4. `run_output` 是否在 `--work` 目录里有对应记录；
5. `--strict` 下，WARN（无行号、范围过大、run_output 无记录）一律算失败。

它不判「证据是否支持判断」——那是人的事。它只保证「引文存在」。

## 提交前清单

- [ ] `validate_review.py --strict` VALID
- [ ] `verify_evidence.py --root <包> --work <work目录> --strict` 0 FAIL 0 WARN
- [ ] 每条 content 都是原文连续子串，不是转述、没有拼接
- [ ] 每条 where 的行号能对上，没有超界
- [ ] 每条 evidence.source 与 issue_type 匹配（见 `review-schema.md`）
- [ ] 每条 reasoning 回答了「为什么支持」
- [ ] 每条 impact 说得出具体实现
- [ ] 每条 suggestion 是断言/用例/条目文本
- [ ] `run_output` 都有实际命令与输出，且在 work/ 有记录
- [ ] `missing_validation` 在 `work/search.log` 有搜索命令与无命中输出
- [ ] 没有 `N/A`、`无`、`-` 之类的占位

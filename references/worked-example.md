# 五项写法示例

> 下面的文件和行号是**格式示意**（`demo-task` 是虚构包），不是真实材料。
> 真实审计必须引你手上材料的原文；引之前先跑 `verify_evidence.py`。

## 示例 1：wrong_validation（只查异常，不查副作用）

**原始测试**（`tests/test_outputs.py`）：

```python
40  async def test_cancel_running():
41      result = run_scenario("running_cancel")
42      with pytest.raises(asyncio.CancelledError):
43          await result.handle
44      assert True
```

**问题条目**：

```json
{
  "id": "T01",
  "location": {"file": "tests/test_outputs.py", "ref": "test_cancel_running (L40-L44)"},
  "issue_type": "wrong_validation",
  "description": "该用例声称验证「取消正在执行的任务后任务体停止」，但断言只检查 await 抛出 CancelledError；一个执行完全部步骤再抛 CancelledError 的实现同样通过。",
  "evidence": {
    "source": "test_code",
    "where": "tests/test_outputs.py L40-L44",
    "content": "async def test_cancel_running():\n    result = run_scenario(\"running_cancel\")\n    with pytest.raises(asyncio.CancelledError):\n        await result.handle\n    assert True",
    "reasoning": "断言只覆盖异常类型；L28 定义的 result.steps 在整条用例中从未被读取，因此「执行完全部步骤再抛错」与「停在取消点」两种实现都会通过，题面 R3 要求的「停止」没有被验证。"
  },
  "impact": "放行「cancel 只置状态、任务体继续跑完再抛 CancelledError」的实现；该实现违反 R3，但 test_cancel_running 仍绿。",
  "suggestion": "在 await 之后加 `assert result.steps == 1`（取消发生在第 1 步之后），并删除 `assert True`；用 asyncio.Event 固定取消点，避免 sleep 竞态。"
}
```

要点：
- `content` 是连续原文，含 `assert True`（证明恒真断言）。
- `reasoning` 引了 `steps` 的定义行，说明「没被读取」。
- `impact` 写出具体错误实现，不是「可能导致」。

## 示例 2：missing_validation（题面要求，测试完全没有）

**题面**（`instruction.md`）：

```markdown
16  - R4 对已完成任务调用 cancel()，必须返回 False；重复调用第二次也返回 False。
```

**测试文件**：搜不到 `after_done` / `double_cancel`，也没有对 `cancel()` 返回值的断言。

```json
{
  "id": "T08",
  "location": {"file": "tests/test_outputs.py", "ref": "全文（无 after_done / double_cancel 用例）"},
  "issue_type": "missing_validation",
  "description": "题面 R4 要求「已完成任务 cancel 返回 False、第二次 cancel 返回 False」，测试里没有任何用例覆盖这两个返回值。",
  "evidence": {
    "source": "instruction",
    "where": "instruction.md L16（R4）",
    "content": "- R4 对已完成任务调用 cancel()，必须返回 False；重复调用第二次也返回 False。",
    "reasoning": "题面把返回值写成了硬性要求；tests/test_outputs.py 只断言 state 和异常类型，没有任何 `cancel()` 返回值的断言，也没有 after_done / double_cancel 场景，因此违反 R4 的实现不会被判失败。"
  },
  "impact": "放行「已完成任务 cancel 返回 True」「第二次 cancel 抛异常」的实现；两者都违反 R4。",
  "suggestion": "新增 `test_double_cancel`：运行中连续 cancel 两次，断言 `returns == [True, False]`；新增 `test_after_done`：任务自然结束后 cancel，断言 `returns == [False]` 且不抛异常。"
}
```

要点：
- `evidence.source` 用 `instruction`，引题面硬性要求。
- `where` 同时写了搜索范围（全文）。
- `suggestion` 给两个用例名 + 断言。

## 示例 3：tooling_defect（reward 与结果脱钩）

**`tests/test.sh`**：

```bash
7   python -m pytest test_outputs.py -q || true
8   echo 1 > /logs/verifier/reward.txt
```

```json
{
  "id": "T11",
  "location": {"file": "tests/test.sh", "ref": "L7-L8"},
  "issue_type": "tooling_defect",
  "description": "test.sh 用 `|| true` 吞掉 pytest 的失败退出码，并无条件写入 reward 1；测试全挂也会拿满分。",
  "evidence": {
    "source": "test_code",
    "where": "tests/test.sh L7-L8",
    "content": "python -m pytest test_outputs.py -q || true\necho 1 > /logs/verifier/reward.txt",
    "reasoning": "`|| true` 让整行的退出码恒为 0，下一行不检查任何结果直接写 1；reward 与 pytest 的通过/失败完全脱钩，验证入口本身失效。"
  },
  "impact": "放行任何实现：即使 0 条测试通过，reward 仍为 1。这是整包最严重的一类问题。",
  "suggestion": "改为 `set -e` + `python -m pytest test_outputs.py -q`，用 pytest 退出码决定 reward：0 → `echo 1`，非 0 → `echo 0`；并在失败时把 pytest 输出写入 `/logs/verifier/`。"
}
```

## 示例 4：rubric duplicate_scoring（两条看同一份证据）

**`rubric.md`**：

```markdown
5   1. 取消后任务状态为 cancelled（20 分）
6   2. 取消生效，任务停止（20 分）
```

```json
{
  "id": "R01",
  "location": {"file": "rubric.md", "ref": "条目 1-2（L5-L6）"},
  "issue_type": "duplicate_scoring",
  "description": "条目 1 和条目 2 都在奖励「取消后状态为 cancelled」：条目 1 的锚点是 state，条目 2 名为「取消生效」但判据仍只看 state，没有看任务体是否停止。同一份证据可同时拿 40 分。",
  "evidence": {
    "source": "rubric",
    "where": "rubric.md L5-L6",
    "content": "1. 取消后任务状态为 cancelled（20 分）\n2. 取消生效，任务停止（20 分）",
    "reasoning": "两条都没有给出「停止」的可观察锚点（如 steps 不再增长）；标注员只能看 state，一个只改 state、不打断执行的实现会同时满足两条，重复拿 40 分。"
  },
  "impact": "只置状态的错误实现拿 40/40；同时「取消后不再执行任务体」这条核心要求没有独立条目（见 R06）。",
  "suggestion": "条目 1 保留「state == cancelled」；条目 2 改成可观察的副作用条目：「取消后 handle.steps 不再增长，且小于任务总步数」，锚点写进 rubric。"
}
```

## 示例 5：false_rejection（错杀不打日志的正确实现）

**测试**：

```python
55      assert data["log"] == ["cleanup done"]
```

```json
{
  "id": "T07",
  "location": {"file": "tests/test_outputs.py", "ref": "test_cleanup_log (L50-L56)"},
  "issue_type": "false_rejection",
  "description": "用例断言日志严格等于 [\"cleanup done\"]，但题面只要求 finally 执行，没有规定日志文案；一个正确执行清理但不打日志的实现会被判失败。",
  "evidence": {
    "source": "test_code",
    "where": "tests/test_outputs.py L55；instruction.md R3（L18-L20）",
    "content": "assert data[\"log\"] == [\"cleanup done\"]",
    "reasoning": "题面 R3 只要求 finally 执行，没有规定日志文案；这条断言把日志当判据，正确执行清理但不打日志的实现会被判失败。"
  },
  "impact": "误杀所有不打印该日志、但 finally 正确执行的实现；测试通过与否取决于文案，不取决于行为。",
  "suggestion": "改为断言清理副作用：`assert data[\"cleanup\"] is True`；若要保留日志，先在题面写明日志格式，否则删掉日志断言。"
}
```

## 对照：不合格 vs 合格

| 字段 | 不合格 | 合格 |
|---|---|---|
| description | 「验证不充分」 | 「声称验证 X，断言只检查 Y；只做 Y 的实现仍通过」 |
| evidence.content | 「测试只查了异常类型」 | 原文连续子串（含断言行） |
| evidence.reasoning | 「显然不够」 | 「断言只覆盖 A；B 在 L28 定义但从未被读取；因此 C 实现会通过」 |
| impact | 「可能导致错误实现通过」 | 「放行『cancel 只置标志、不打断执行』的实现」 |
| suggestion | 「建议补充边界测试」 | 「新增 test_double_cancel，断言 returns == [True, False]」 |

## 一条自查

写完一条，问自己：

> 如果复核人只读我的 evidence，能不能独立得出同一个结论？

不能 → 回原文补引用，或者删掉这条。

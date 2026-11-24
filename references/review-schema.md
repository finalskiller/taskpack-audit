# review.json 契约（唯一权威）

> 材料的 `review_template.json` 只决定**字段名**；结构、类型、必填、交叉约束以本文件为准。
> 两者冲突时：字段名听模板，语义听本文件，并在 `environment.notes` 记一行差异。
> 材料没有模板时，直接用 `templates/review.json` 起稿。

## 顶层

| 键 | 类型 | 规则 |
|---|---|---|
| `candidate` | string | 真名，非空 |
| `submitted_at` | string | `YYYY-MM-DD`，真实日期 |
| `environment` | object | 见下，10 个必填键 |
| `test_review` | array | 每条为一个 issue，id 从 `T01` 连续 |
| `rubric_review` | array | 每条为一个 issue，id 从 `R01` 连续 |

## environment（10 个必填键）

| 键 | 类型 | 规则 |
|---|---|---|
| `built_from_dockerfile` | bool | 真的 `docker build` 成功才 true |
| `dockerfile_modified` | bool | 改过原始 Dockerfile 才 true |
| `build_command` | string | 实际执行的构建命令原文；没执行也写尝试的命令 |
| `run_command` | string | 实际执行的运行命令原文；不要把本地替代命令写进来 |
| `python_version` | string \| null | **容器内** `python -V` 输出；未观测填 null |
| `test_result` | string \| null | pytest 汇总行原文；未观测填 null |
| `reward` | `"0"` \| `"1"` \| null | `reward.txt` 内容；未观测填 null |
| `completed` | bool | build + solve + test + 取到 reward 全走完才 true |
| `stopped_at` | string \| null | `completed=false` 时必填；`completed=true` 时必须 null |
| `problems` | array | 每项 `{step, symptom, resolution}`；没遇到填 [] |

**交叉约束**（`validate_review.py --strict` 检查）：

- `completed=true` ⇒ `reward` 非 null、`test_result` 非空、`stopped_at=null`。
- `completed=false` ⇒ `stopped_at` 非空、`problems` 非空、`reward=null`、`test_result=null`。
- `built_from_dockerfile=true` 与 `stopped_at="docker build"` 不能同时出现（构建成功却说卡在 build）。
- `built_from_dockerfile=true` 但 `completed=false` 是允许的（构建成功、测试失败），在 `notes` 说明卡在哪。

可选：`notes`（string \| null）。本地降级结果、非容器观测都写这里，不写进上面六个观测字段。

## issue 对象

| 键 | 类型 | 规则 |
|---|---|---|
| `id` | string | `test_review[i].id == "T%02d" % (i+1)`；`rubric_review[i].id == "R%02d" % (i+1)` |
| `location` | object | `{file, ref}`，都非空；`file` 用包内相对路径 |
| `issue_type` | enum | 见下，14 类 |
| `description` | string | 一句话说清「声称验 X，实际验 Y」或「题面要求 X，没有条目」 |
| `evidence` | object | `{source, where, content, reasoning}`，四项非空 |
| `impact` | string | 放行什么错误实现 / 误杀什么正确实现 |
| `suggestion` | string | 具体断言、具体用例或具体条目文本 |

`location` 只能放一个主位置。多处症状写进 `description` 与 `evidence.where`，不要为了放多个位置改 schema。

## evidence

| 键 | 规则 |
|---|---|
| `source` | 六选一：`instruction` / `test_code` / `reference_solution` / `run_output` / `task_metadata` / `rubric` |
| `where` | 文件 + 行号；`run_output` 写完整命令 + 场景；可以写第二处引用的文件，但 **content 必须来自 source 对应的文件** |
| `content` | 原文**连续子串**，2–5 行；不翻译、不改标点、不用 `...` 拼接 |
| `reasoning` | 三段式：原文说了什么 / 没说什么 / 因此哪种实现会过 |

**一个 evidence 只有一个 source。** 需要第二个来源时，把它写进 `where` 与 `reasoning`，不要拼进 `content`。

## 类型 → source 的合法组合（strict 检查）

| issue_type | 主 source | 说明 |
|---|---|---|
| `wrong_validation` | `test_code` | 断言原文 |
| `missing_validation` | `instruction` 或 `run_output` | 题面要求原文，或存活变异体输出；测试缺失写 reasoning |
| `false_rejection` | `test_code` | 过严断言原文；题面允许范围写 reasoning |
| `flaky` | `test_code` 或 `run_output` | 时序行 / 重复运行输出 |
| `tooling_defect` | `test_code` | test.sh / test.py 原文 |
| `undefined_requirement` | `instruction` | 最接近的题面原文；测试假设写 reasoning |
| `contradicts_code` | `rubric` | 条目原文；solve.sh 行写 reasoning |
| `rewards_wrong_behavior` | `rubric` | 条目原文；坏解得分写 reasoning 或 run_output |
| `penalizes_correct` | `rubric` | 条目原文；参考解行写 reasoning |
| `unobservable` | `rubric` | 条目原文 |
| `duplicate_scoring` | `rubric` | 主条目原文；另一条写 reasoning |
| `undefined_criterion` | `rubric` | 档位/判据原文 |
| `missing_criterion` | `instruction` | 题面要求原文；rubric 缺失写 reasoning |
| `process_defect` | `rubric` | 分值表原文；算术写 reasoning |

`strict` 模式下，类型与 source 不匹配直接报错。

## 常见非法

| 写法 | 为什么非法 | 改法 |
|---|---|---|
| `evidence.source: "instruction + test_code"` | source 是枚举单值 | 主 source 选一个，另一处写 `where` / `reasoning` |
| `content` 用 `" / "` 拼两段原文 | 不是连续子串 | 只留主来源那段 |
| `where: "tests/test_outputs.py L900-L999"` | 行号超界 | 用真实行号 |
| `completed: true` + `reward: null` | 自相矛盾 | 填 reward 或改 completed=false |
| `id` 用 `T1` / 断号 / 重复 | 必须两位连续 | `T01`、`T02`… |
| `location.file: "test_outputs.py"` | 缺目录 | `tests/test_outputs.py` |

## 与模板的关系

1. 材料有 `review_template.json`：先读它，按它的字段名产出；缺的字段从本文件补。
2. 材料没有：用 `templates/review.json`。
3. 模板与本文件冲突：字段名听模板，语义听本文件，并在 `environment.notes` 记一行。
4. 提交前：`python scripts/validate_review.py review.json --strict` 必须 VALID。

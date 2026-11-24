# 环境复现 runbook

> 第一部分只有 10 分，但红线只有一条：**没跑过的不许写成跑通**。
> 目标：15 分钟内拿到 `environment` 的 10 个必填键；拿不到就如实记录，别耗到影响第二、三部分。

## 0. 预检（1 分钟）

```bash
docker version          # 客户端 + 服务端都要有
docker info --format '{{.ServerVersion}}'
```

没有 docker / 服务端没起 → 直接走「无法运行」分支，不要反复重试。

## 1. 构建

材料里的 Dockerfile 没有 `COPY`，构建上下文用 `environment/`：

```bash
docker build -t taskpack:cancel-async environment/ 2>&1 | tee logs/build.log
```

如果 Dockerfile 里有 `COPY`（合成包就是），构建上下文要用**包根目录**，否则 COPY 找不到文件：

```bash
docker build -f environment/Dockerfile -t taskpack:cancel-async . 2>&1 | tee logs/build.log
```

记录实际命令（填 `build_command`）。如果改了 Dockerfile，`dockerfile_modified: true`，并把改动写进 `notes`。

### 拉基础镜像卡住

优先换镜像源，**不要改 Dockerfile**（改了要标 modified）：

```bash
docker pull docker.m.daocloud.io/library/python:3.13-slim-bookworm
docker tag  docker.m.daocloud.io/library/python:3.13-slim-bookworm python:3.13-slim-bookworm
```

然后重跑 build。其它可用源：`docker.1ms.run`、`docker.xuanyuan.me`（能拉通一个就够）。
拉取超时 >5 分钟 → 停，记录 `problems`，不要无限等。

## 2. 运行

`tests/test.sh` 会去 `/tests` 找测试，往 `/logs/verifier/` 写结果，所以两个目录都要挂：

```bash
mkdir -p logs
docker run --rm \
  -v "$PWD/tests:/tests:ro" \
  -v "$PWD/solution:/solution:ro" \
  -v "$PWD/logs:/logs" \
  -w /app \
  taskpack:cancel-async \
  bash -lc "bash /solution/solve.sh && bash /tests/test.sh" \
  2>&1 | tee logs/run.log
```

要点：
- `/logs` 必须可写；容器内可以先 `mkdir -p /logs/verifier`。
- 若镜像 entrypoint 不是 bash，加 `--entrypoint bash`。
- 若 `solve.sh` 写死 `/app`，确认工作目录或挂载对得上。
- 若 `test.sh` 写死 `cd /tests`，上面的挂载已经满足。
- 若 `solve.sh` 用相对路径（如 `cp solution/runner.py app/runner.py`），把整包挂进去并从包根运行：

```bash
docker run --rm \
  -v "$PWD:/pkg" -v "$PWD/tests:/tests:ro" -v "$PWD/logs:/logs" \
  -w /pkg taskpack:cancel-async \
  bash -lc "bash solution/solve.sh && bash tests/test.sh"
```

### 分开跑（便于定位）

```bash
# 只跑参考解
docker run --rm -v "$PWD/solution:/solution:ro" -w /app taskpack:cancel-async bash /solution/solve.sh
# 只跑测试
docker run --rm -v "$PWD/tests:/tests:ro" -v "$PWD/logs:/logs" -w /app taskpack:cancel-async bash /tests/test.sh
```

## 3. 抓 10 个必填键

```bash
docker run --rm taskpack:cancel-async python -V | tee logs/python-version.txt
grep -E '[0-9]+ (passed|failed|error)' logs/run.log | tail -1 | tee logs/pytest-summary.txt
cat logs/verifier/reward.txt | tee logs/reward.txt
```

| 字段 | 来源 | 没拿到时 |
|---|---|---|
| `built_from_dockerfile` | 是否真的 `docker build` 成功 | false |
| `dockerfile_modified` | 是否改过原始 Dockerfile | false（没改） |
| `build_command` | 实际命令原文 | 填实际尝试的命令 |
| `run_command` | 实际命令原文 | 填实际尝试的命令 |
| `python_version` | `python -V` 输出 | null |
| `test_result` | pytest 汇总行原文 | null |
| `reward` | `reward.txt` 内容 `"0"` / `"1"` | null |
| `completed` | 是否走完 build + solve + test + 取到 reward | false |
| `stopped_at` | 卡在哪一步（`docker build` / `solve.sh` / `test.sh` / 取 reward） | completed=false 时必填 |

`test_result` 要抄**原行**，例如 `5 passed, 1 warning in 0.42s`，不要自己总结成「全部通过」。

`build_command` / `run_command` 只写**实际尝试的容器命令**；本地替代命令、非容器观测写进 `notes`，不要混进这两个字段。

如果 `reward.txt` 是 1 但 pytest 原行有失败，说明 `test.sh` 的 reward 与结果脱钩（`tooling_defect`）：`test_result` 照抄 pytest 原行，`reward` 照抄 1，`notes` 记这个矛盾。不要为了让两者一致去改材料。

## 3.5 本机没有 Docker

不要假装 `built_from_dockerfile: true`。可以做「本地等效」，把结果写进 notes：

```bash
python -m pytest tests/test_outputs.py -q   # 有 pytest 时
python tests/run_tests.py                   # 包自带 runner / 无 pytest 时
```

`environment` 仍填 `built_from_dockerfile: false`、`completed: false`、`stopped_at: "docker build"`；
`test_result` 保持 null，本地输出写 notes，并标明「非容器内观测」。

## 4. 失败时怎么写

```json
{
  "built_from_dockerfile": false,
  "completed": false,
  "stopped_at": "docker build",
  "python_version": null,
  "test_result": null,
  "reward": null,
  "problems": [
    {
      "step": "docker build",
      "symptom": "pull python:3.13-slim-bookworm timeout after 300s; TLS handshake error",
      "resolution": null
    }
  ]
}
```

- `symptom` 写现象 + 原始报错关键词，不写「网络问题」。
- `resolution` 解决了写怎么解决的；没解决写 null。
- 不要把「未观测」写成 `"0"` 或 `"1"`；`reward` 没拿到就是 null。

## 5. 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| `pull access denied` / timeout | 镜像源不通 | 换 daocloud / 1ms / xuanyuan；仍不通就停 |
| `permission denied: /logs/verifier` | 容器内用户无写权限 | 挂载前 `mkdir -p logs && chmod 777 logs`；或容器内 `mkdir -p` |
| `python: command not found` | 镜像里只有 `python3` | 用 `python3 -V`，并在 notes 说明 |
| `pytest: command not found` | 镜像没装 pytest | 记录为 tooling_defect 候选；不要临时改材料 |
| `test.sh: /tests: No such file` | 没挂载 / 路径不对 | 检查 `-v` 与 `cd` |
| 容器起不来，无输出 | entrypoint 不对 | 加 `--entrypoint bash`，或 `docker run ... sleep 60` 进去看 |
| `solve.sh` 权限不足 | 没执行位 | `bash solve.sh` 而不是 `./solve.sh` |
| 运行很久不结束 | 测试挂死 | `timeout 300 docker run ...`，记录为 flaky/挂死候选 |

## 6. Windows 主机注意

- PowerShell 里用 `${PWD}` 而不是 `$PWD`；路径含中文/空格时加引号。
- Docker Desktop 需要共享该盘符；OneDrive 路径可能同步锁文件，尽量在本地盘跑。
- 容器内是 Linux 路径，挂载源用绝对路径。
- `tee` 在 PowerShell 里可用，但 `bash -lc` 的双引号转义要检查。

## 7. 不要做的事

- 不要因为「应该是通的」就把 `completed` 写 true。
- 不要用 `docker build` 成功但 `test.sh` 没跑到来推断 reward。
- 不要为了让测试通过去改材料里的测试或 Dockerfile（改了要标 modified，且写进 notes）。
- 不要把容器里的 `/logs` 和主机的 `logs/` 搞混；以挂载后的主机文件为准。

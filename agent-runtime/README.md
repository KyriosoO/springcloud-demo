# agent-runtime

`agent-runtime` 是 Single Agent 的 Python 内部运行时。它负责模型任务编排、Capability 选择与单动作执行，并通过固定 Adapter 调用现有 Employee、Transaction 和 Knowledge 查询服务。

它不是浏览器直接访问的公共服务。正常调用链为：

```text
Browser
  -> gateway-service
  -> agent-service (Spring, public API)
  -> agent-runtime (FastAPI, internal API)
  -> Employee / Transaction / Knowledge services
```

公共与内部 HTTP 契约位于：

- [`../agent-contracts/openapi/agent-public-v1.yaml`](../agent-contracts/openapi/agent-public-v1.yaml)
- [`../agent-contracts/openapi/agent-runtime-internal-v1.yaml`](../agent-contracts/openapi/agent-runtime-internal-v1.yaml)

## 1. 运行环境

- Python `3.12`（项目约束为 `>=3.12,<3.13`）
- Windows PowerShell 示例命令
- 真实 Business 查询需要可访问的 Employee 和 Transaction 服务
- Knowledge 启用后还需要 es-query-service、embedding 和 rerank 服务
- DeepSeek 模式需要通过进程环境变量提供 `LLM_API_KEY`，不得写入仓库、README、日志或 `.env` 提交文件

## 2. 安装

在仓库根目录执行：

```powershell
cd D:\codex\agent-runtime

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

安装完成后会注册控制台命令：

```text
agent-runtime -> agent_runtime.main:main
```

不安装为 editable package 时，也可以临时从源码启动：

```powershell
$env:PYTHONPATH=(Resolve-Path "src").Path
python -m agent_runtime.main
```

推荐使用 editable 安装方式，避免测试子进程或隔离执行环境无法导入 `agent_runtime`。

## 3. 启动方式

### 3.1 默认 stub 冒烟模式

默认 `AGENT_MODEL_PROVIDER=stub`。该模式不读取模型密钥、不注册真实 Business/Knowledge 能力，业务问题会返回 `unsupported`，适合验证 HTTP 服务、健康检查和协议错误处理。

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\Activate.ps1

$env:AGENT_MODEL_PROVIDER="stub"
$env:AGENT_KNOWLEDGE_ENABLED="false"
agent-runtime
```

默认监听：

```text
http://127.0.0.1:8091
```

### 3.2 Employee/Transaction 真实 QueryPlan 模式

先确认以下依赖服务已启动：

- Employee：`http://127.0.0.1:9210`
- Transaction：`http://127.0.0.1:8182`
- `agent-service` 默认通过 `http://127.0.0.1:8091` 调用 Runtime

然后在当前 PowerShell 进程中设置配置并启动：

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\Activate.ps1

$env:AGENT_MODEL_PROVIDER="deepseek"
$env:LLM_API_KEY="<仅在当前进程中设置>"
$env:AGENT_EMPLOYEE_BASE_URL="http://127.0.0.1:9210"
$env:AGENT_TRANSACTION_BASE_URL="http://127.0.0.1:8182"
$env:AGENT_KNOWLEDGE_ENABLED="false"

agent-runtime
```

该模式注册的生产 Business 动作为：

- `employee.search`
- `employee.semantic_search`
- `transaction.search`

Runtime 只允许调用固定路径：

- `/employees/es/search`
- `/employees/es/vector-search`
- `/txn/search`

JWT 由 `agent-service` 从公共请求透传给业务服务，Runtime 不自行签发 JWT，也不直接访问业务数据库或业务 Elasticsearch。

### 3.3 同时启用 Knowledge

Knowledge 默认关闭。启用时必须同时使用真实模型 Provider，并明确启用逻辑域及检索依赖：

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\Activate.ps1

$env:AGENT_MODEL_PROVIDER="deepseek"
$env:LLM_API_KEY="<仅在当前进程中设置>"
$env:AGENT_EMPLOYEE_BASE_URL="http://127.0.0.1:9210"
$env:AGENT_TRANSACTION_BASE_URL="http://127.0.0.1:8182"

$env:AGENT_KNOWLEDGE_ENABLED="true"
$env:AGENT_KNOWLEDGE_ENABLED_DOMAINS="tax.policy,tax.law"
$env:AGENT_KNOWLEDGE_ES_BASE_URL="http://127.0.0.1:9200"
$env:AGENT_KNOWLEDGE_EMBEDDING_BASE_URL="http://127.0.0.1:8908"
$env:AGENT_KNOWLEDGE_RERANK_BASE_URL="http://127.0.0.1:8909"

agent-runtime
```

Knowledge 启用后，启动阶段会校验逻辑域、Profile、embedding 维度、rerank 模型、Evidence 策略和模型任务版本。任一配置无效都会失败关闭，不会退回 Business 或建立第二条查询链路。

## 4. 启动代码说明

启动入口由 [`pyproject.toml`](pyproject.toml) 定义：

```toml
[project.scripts]
agent-runtime = "agent_runtime.main:main"
```

核心启动代码位于 [`src/agent_runtime/main.py`](src/agent_runtime/main.py)：

```python
def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    app = create_app(settings, build_runtime)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
    )
```

启动过程如下：

1. `RuntimeHttpSettings.from_env()` 读取监听地址、端口、协议版本、请求体和并发上限。
2. `create_app(settings, build_runtime)` 创建 FastAPI 应用，但不在模块导入阶段连接外部服务。
3. Uvicorn 启动后，FastAPI lifespan 调用 `build_runtime()` 构建运行时对象图。
4. `build_runtime()` 根据 `AGENT_MODEL_PROVIDER` 选择安全 stub 或 DeepSeek transport。
5. DeepSeek 模式下创建 Business QueryPlan 模型任务、Employee/Transaction Adapter 和固定路径 HTTP Client。
6. `AGENT_KNOWLEDGE_ENABLED=true` 时才惰性创建 Knowledge 任务、检索 Provider 和三个 Knowledge HTTP Client。
7. 应用进入 ready 状态后才接收 invoke 请求。
8. 进程退出时 lifespan 调用 Runtime 的 `aclose()`，关闭模型和所有由组合根拥有的 HTTP Client。

固定使用 `workers=1`，避免单进程预算、取消状态和运行时资源生命周期被多个 worker 隐式拆分。监听地址必须是 loopback 地址，当前实现拒绝绑定到非本机地址。

## 5. 主要环境变量

| 变量 | 默认值 | 用途 |
|---|---:|---|
| `AGENT_RUNTIME_HOST` | `127.0.0.1` | Runtime监听地址；只允许loopback |
| `AGENT_RUNTIME_PORT` | `8091` | Runtime监听端口 |
| `AGENT_RUNTIME_CONTRACT_VERSION` | `1` | Java/Python内部协议版本，只允许1 |
| `AGENT_RUNTIME_MAX_BODY_BYTES` | `32768` | 最大请求体字节数 |
| `AGENT_RUNTIME_MAX_IN_FLIGHT` | `8` | 最大并发请求数 |
| `AGENT_MODEL_PROVIDER` | `stub` | `stub`或`deepseek` |
| `LLM_API_KEY` | 无 | DeepSeek模式必填；只驻留进程环境 |
| `AGENT_MODEL_MAX_CONCURRENCY` | `4` | 模型最大并发 |
| `AGENT_MODEL_ACTION_TIMEOUT_MS` | `8000` | 动作选择及QueryPlan超时 |
| `AGENT_EMPLOYEE_BASE_URL` | `http://127.0.0.1:9210` | Employee服务根地址 |
| `AGENT_TRANSACTION_BASE_URL` | `http://127.0.0.1:8182` | Transaction服务根地址 |
| `AGENT_KNOWLEDGE_ENABLED` | `false` | 是否注册`knowledge.query` |
| `AGENT_KNOWLEDGE_ENABLED_DOMAINS` | 空 | 启用的逻辑域；Knowledge开启时必填 |
| `AGENT_KNOWLEDGE_ES_BASE_URL` | 无 | es-query-service根地址；Knowledge开启时必填 |
| `AGENT_KNOWLEDGE_EMBEDDING_BASE_URL` | `http://127.0.0.1:8908` | embedding服务 |
| `AGENT_KNOWLEDGE_RERANK_BASE_URL` | `http://127.0.0.1:8909` | rerank服务 |

所有布尔配置必须使用小写 `true` 或 `false`。未知的 `AGENT_BUSINESS_*` 或 `AGENT_KNOWLEDGE_*` 配置会被严格拒绝。

## 6. 内部 HTTP 接口

| 接口 | 用途 |
|---|---|
| `GET /internal/health/live` | ASGI事件循环存活检查 |
| `GET /internal/health/ready` | Runtime对象图是否完成构建 |
| `POST /internal/v1/agent-runs:invoke` | `agent-service`调用的正式内部执行入口 |
| `POST /internal/v1/agent-runs:inspect` | 当前调试观察入口；只用于受控诊断，不是公共业务接口 |

正式 invoke 请求必须包含：

- `Authorization: Bearer <JWT>`
- `X-Agent-Contract-Version: 1`
- body中的 `contractVersion: 1`

Header和body版本不一致时返回409；缺失或未知字段失败关闭。浏览器和普通调用方应使用 `agent-service` 的 `/api/v1/agent/queries`，不要绕过 Spring 接入层直接调用 Runtime。

## 7. 健康检查

```powershell
Invoke-WebRequest http://127.0.0.1:8091/internal/health/live
Invoke-WebRequest http://127.0.0.1:8091/internal/health/ready
```

预期：

- `live`：进程和ASGI事件循环存活时返回200。
- `ready`：Runtime对象图完成构建后返回200；未就绪返回503。

## 8. 停止服务

在前台启动时使用 `Ctrl+C`。Uvicorn 会退出 lifespan，并调用 Runtime 的异步关闭逻辑。

如果由脚本启动后台进程，只能停止已记录并核实属于本次启动的 PID，不要按端口批量结束其他维护者进程。

## 9. 测试与验证

定向验证：

```powershell
cd D:\codex\agent-runtime
.\.venv\Scripts\Activate.ps1

python -m pytest tests/contract/test_runtime_openapi.py tests/integration/test_health_and_startup.py -q
python -m mypy src
python -m compileall -q src
```

正式全量 non-live 回归使用版本化脚本：

```powershell
.\scripts\run-nonlive-regression.ps1
```

该脚本创建隔离虚拟环境、安装当前源码、执行 Transaction host/preflight 与全量 non-live 测试，并在完成后清理临时环境。真实模型和 live/UAT 脚本具有独立预算、冻结资产和授权条件，不应作为普通启动或日常回归命令执行。

## 10. 常见启动问题

### `model.api_key_required`

已选择 `AGENT_MODEL_PROVIDER=deepseek`，但当前进程没有有效的 `LLM_API_KEY`。

### `knowledge.stub_transport_required`

启用了 Knowledge，但仍使用默认 stub Provider。生产 Knowledge 必须使用受控真实模型 transport。

### `knowledge.enabled_domains_required`

设置了 `AGENT_KNOWLEDGE_ENABLED=true`，但没有配置 `AGENT_KNOWLEDGE_ENABLED_DOMAINS`。

### `knowledge.retrieval_es_base_url_required`

Knowledge 已开启，但没有设置 `AGENT_KNOWLEDGE_ES_BASE_URL`。

### `runtime.settings_invalid:AGENT_RUNTIME_HOST`

监听地址不是合法loopback地址。Runtime是内部服务，当前设计不允许直接绑定外网网卡。

### `ModuleNotFoundError: agent_runtime`

当前解释器没有安装本项目。激活 `.venv` 并执行：

```powershell
python -m pip install -e ".[test]"
```

# LivingMind v1.0 · Expo 与完整后端

以下说明适用于原有休息服务、虚拟网关和数据库部署。家庭晚间浏览器演示的启动方式见[项目首页](../README.md)。

## Quick start 快速运行

以下命令适用于 macOS / Linux 终端。仓库 CI 使用 Node.js 22 与 Python 3.12；本地 Python 3.11 也已验证。容器方式需要 Docker 与 Docker Compose。

### 1. 获取项目

```bash
git clone https://github.com/Hector-sau/Livingmind.git LivingMind
cd LivingMind
```

### 2. 启动容器后端

在当前终端生成内部网关 token，启用 LangGraph，并启动 PostgreSQL、Redis、迁移、两个 API、持久化虚拟网关及后台进程：

```bash
export LIVINGMIND_GATEWAY_TOKEN="$(openssl rand -hex 32)"
export LIVINGMIND_ORCHESTRATOR=langgraph
docker compose -f compose.yaml -f compose.gateway.yaml --profile replicas up -d --build
```

- 主 API：<http://127.0.0.1:8000>
- 健康检查：<http://127.0.0.1:8000/health>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>
- 第二 API：<http://127.0.0.1:8001>
- 默认使用规则规划，不需要模型密钥。

API 默认只绑定本机。PostgreSQL / Redis 默认占用本机 5432 / 6379 端口，可通过 `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` 调整。仅需单实例体验时可使用 `docker compose up -d --build`，该模式不启用独立网关和后台回执核对。

关闭上述完整环境、保留数据卷：

```bash
docker compose -f compose.yaml -f compose.gateway.yaml --profile replicas down
```

网关 token 必须在执行对应 Compose 命令的终端中可用；也可保存在仓库根目录未跟踪的 `.env`，不要提交到 Git。

### 3. 启动客户端

打开另一个终端，在仓库根目录执行：

```bash
cd apps/mobile
npm ci
cp .env.example .env
```

首次配置时，将 `.env` 中的地址设为：

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

启动浏览器预览：

```bash
npm run web -- --clear
```

浏览器用于本机预览和自动化验证，产品客户端仍以原生平板 App 为目标。留空后端地址会进入明确标注的前端模拟模式；已配置后端但连接失败时，不会改用模拟数据冒充成功。

### 4. 平板连接

使用同一可信局域网中的电脑 IP 作为 `EXPO_PUBLIC_API_BASE_URL`，不能使用平板自身的 `localhost`。容器 API 需通过 `HOST_BIND=0.0.0.0` 重新启动以允许局域网访问，勿暴露到公网。

原生客户端使用 Expo development build；仓库已包含 iOS / Android 配置与 `eas.json`。安装与当前 SDK 匹配的开发构建后，在 `apps/mobile` 下连接开发服务器：

```bash
npx expo start --dev-client --clear
```

设备端语音识别依赖原生模块，不能用浏览器预览代替验收。当前已验证双平台 JavaScript / Hermes 导出，尚未完成安装包与真机验证。

### 本地 Python 后端

不使用 Docker 时，可运行单进程、内存存储的后端。不要与容器 API 同时占用 8000 端口。

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt -c constraints.txt
cp .env.example .env
uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

未配置 PostgreSQL 时，服务状态与虚拟设备数据随进程退出而重置；后台回执核对要求 PostgreSQL 与独立 HTTP 网关。

## Configuration 运行配置

| 变量 | 用途 |
|---|---|
| `EXPO_PUBLIC_API_BASE_URL` | 客户端连接的后端地址；空值为前端模拟模式 |
| `LIVINGMIND_DATABASE_URL` | PostgreSQL 连接；本地 Python 模式未设置时使用内存 |
| `LIVINGMIND_REDIS_URL` | 可选 Redis 协调连接 |
| `LIVINGMIND_ORCHESTRATOR` | `legacy` 或 `langgraph`；默认 `legacy` |
| `LIVINGMIND_PLANNER_MODE` | 默认计划来源：`rule` 或 `model` |
| `DEEPSEEK_API_KEY` | 后端模型密钥；客户端不保存此项 |
| `DEEPSEEK_MODEL` | 模型名称，默认 `deepseek-chat` |
| `LIVINGMIND_GATEWAY_TOKEN` | 独立网关内部访问 token |
| `LIVINGMIND_DEMO_LOCAL_HOUR` | 固定能源规则的模拟时段；不等同于夜间服务时钟 |

启用真实模型时，配置 `DEEPSEEK_API_KEY`，在 App 中选择模型计划，或把默认 `LIVINGMIND_PLANNER_MODE` 设为 `model`。真实调用会产生 API 费用；缺少密钥或调用失败时，系统明确显示规则降级。

Docker 从当前终端或仓库根目录 `.env` 读取 Compose 变量；本地 Python 使用启动命令指定的 `backend/.env`。修改配置后需要重新启动对应服务；客户端环境变量变更后用 `--clear` 重启。

## Example 场景体验

1. 选择人物和起床时间，输入“我想休息”。
2. 查看灯光、温度、窗帘方案及来源；此时设备状态不变。
3. 确认执行，查看动作结果、设备回读与服务状态。
4. 触发“模拟已入睡”或模拟室温变化，观察同一服务内的调整。
5. 推进模拟时钟至渐进唤醒，或随时停止；停止后取消剩余安排。
6. 在空间页查看操作记录；遇到未知结果时核对原动作，不重新执行。

## Energy 离线能源研究

项目包含独立的 24 小时家庭能源仿真，涵盖光伏、风电、基础负荷、空调、电池、电网与备用发电机。学习策略基于 MATD3 框架，当前实验配置为单智能体 `N=1`。

固定预设日的给定对比结果为：购电量 **13.61 → 0.76 kWh/day**，峰值购电 **1.95 → 0.37 kW**，日成本 **$1.87 → −$0.02**。这些是同一预设日、采用美元和华氏度参数的仿真结果，不代表真实家庭节能收益或跨日期泛化能力。

App 展示该离线结果，但在线控制仍使用可解释能源规则，不运行强化学习模型。

## Quality 验证与质量

截至 2026-10-03 的[完整 CI 验证](https://github.com/Hector-sau/Livingmind/actions/runs/37119652911)：

| 检查 | 结果 |
|---|---|
| PostgreSQL + Redis + LangGraph 后端 | 278 通过，1 跳过（内存模式专属用例） |
| 前端逻辑与类型检查 | 106 项测试通过，类型检查通过 |
| Docker API 浏览器端到端 | 29 / 29 场景通过 |
| API 契约与数据库迁移 | 类型一致性、测试空库升级与回退检查通过 |

故障测试覆盖双 API 并发确认、跨实例停止、回执丢失、进程崩溃，以及恢复 Worker 的实际数据库连接断开与重连。CI 使用虚拟设备和模型替身，不代表真机、真实设备或线上可用性认证。

## Source 核心目录

```text
apps/mobile/              原生客户端与浏览器预览
backend/app/              API、Agent、记忆、能源、执行器与存储
backend/workers/          事件发布与消费
backend/alembic/          数据库迁移
backend/tests/            后端与故障测试
packages/api-client/      OpenAPI 生成的 TypeScript 契约
simulation/home-energy/   独立离线能源研究
scripts/                  接口生成与运行验证工具
.github/workflows/        自动化持续集成
```

## Scope 使用边界

- 当前账户与人物 PIN 用于原型体验，不提供生产级身份认证。后端只应运行于本机或可信局域网；Compose 默认凭据不能用于公网部署。
- 密钥只保存在后端环境变量或未跟踪的本地配置中，不写入 App、日志或 Git。
- 夜间服务使用模拟事件与模拟时钟，没有真实睡眠传感器或生产定时调度器。
- SpaceMind、厂商设备和智能音箱尚未接入；当前故障验证不等于物理设备 exactly-once 或生产高可用保证。
- 长期记忆目前为结构化人物偏好与会话状态，不包含向量检索或自动学习人格。

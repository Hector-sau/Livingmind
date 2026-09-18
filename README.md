# LivingMind App

平板优先、手机兼容的 LivingMind 原型：一个 Expo 原生 App + 一个模块化 FastAPI 后端。

当前范围：**平板优先、手机兼容的 Home Living 演示闭环**。场景只有“我想休息”：计划 → 确认 → 虚拟设备回读 → 模拟入睡 / 室温事件 → 整晚模拟时钟 → 渐进唤醒或停止。
接手或协作前先读 [AGENT-HANDOFF.md](AGENT-HANDOFF.md)（统一交接文档，在仓库根目录持续维护）。实际完成情况以 [docs/status.md](docs/status.md) 为准；验收标准见 [docs/acceptance.md](docs/acceptance.md)。

## 三条架构边界

1. **页面不直接控制设备**：页面只调用 `apps/mobile/services/` 的接口；从模拟切到真实 API 不改页面。
2. **Agent 不绕过执行器**：规则计划和（以后的）模型计划都经过同一个执行器检查、执行、回读。
3. **模拟逻辑集中存放**：前端模拟在 `apps/mobile/services/mock/`，后端虚拟设备在 `backend/app/adapters/virtual/`，种子数据在 `backend/app/demo/`。

口径按三档区分，不要混用：**已实现并验证**（有代码、有测试、有实跑结果）/ **接口预留**（只有协议与契约替身测试，没有对端）/ **仍待执行**（需用户授权或外部条件）。对照表见 [AGENT-HANDOFF.md](AGENT-HANDOFF.md) 第 9 节。

## 当前做什么 / 不做什么

| 当前做 | 暂不做（后续批次） |
|---|---|
| 对话主页、四个入口、人物切换（演示 PIN）、访客模式、证据面板、场景库 | 真实后台定时器 |
| 1+2 Agent 编排：主 Agent（路由与编排）+ Experience Agent + Space Execution Agent，共享人物记忆、能源规则、Harness 预检，每个计划附协作过程 | 真实设备 / SpaceMind |
| Experience Agent 一次模型调用（DeepSeek，规则/模型可切换，失败降级为规则并标注） | 真实睡眠感知 / 传感器 |
| 模拟室温事件触发一次自动调整（冷却、次数上限、停止后忽略） | 真实传感器 |
| 歧义请求先澄清再执行：否定、设备冲突、指代不清；待澄清状态按账户/人物/空间/会话隔离，10 分钟过期，可取消 | 通用多轮对话记忆 |
| 启动恢复可查询（`GET /api/system/recovery`）：清理崩溃遗留标记，结果未知的步骤取消而非重放 | 真实硬件状态回读恢复 |
| 真实设备 V2（`DeviceGateway`）、语音（`VoiceGateway`）、传感器事件（`EnvironmentEventAdapter`）**协议**已定义并有契约测试 | 上述协议的真实对端接入 |
| 固定规则计划 + 有状态虚拟设备 + 统一执行器；模拟入睡、室温事件与整晚模拟时钟 | 真实设备 / SpaceMind / 音箱接入 |
| 内存或 PostgreSQL 两种存储（可切换）；配库后计划、服务、整晚步骤、活动与待澄清状态可恢复 | 正式登录、WebSocket、向量库 |
| 演示身份（demo account） | 真实设备 / SpaceMind / 音箱接入 |
| 24 小时家庭能源离线仿真：给定的固定日规则 vs 单智能体 MATD3 结果，只读展示（不参与控制） | 在线 MATD3 控制、重训或重新评估 |

## 目录

```text
apps/mobile/          Expo 原生 App（iPad / Android 平板优先）
backend/app/          FastAPI 后端（契约、规则、执行器、虚拟设备、服务状态）
backend/tests/        后端测试
packages/api-client/  由后端契约生成的 TypeScript 类型（不要手改生成文件）
scripts/              跨端脚本（类型生成）
docs/                 架构、验收、状态
.github/              PR 模板与 CI
simulation/home-energy/  给定的离线家庭能源研究快照、数据、权重与溯源（不在 App 运行路径）
```

## 演示流程

上台前：“我的”页点 **准备演示**（重置数据，切回林悦、舒适优先、清空对话、关闭证据面板、回到对话页）。完整讲解顺序见 [`docs/demo-script.md`](docs/demo-script.md)。

选人物 → 选模拟起床时间 → 输入“我想休息” → 选“规则”或“模型” → 生成计划（设备不变）→ 确认执行（设备改变并回读）→ 点“模拟已入睡”（明确的演示信号，不是传感器）→ 点“注入模拟事件”（室温升高 3°C，服务自动调整一次空调）→ 查看服务动态 → 停止服务（设备保持当前状态，之后的事件不再触发动作）。确认后同一个服务贯穿整晚：点“快进到 …”或“自动播放整晚”推进**模拟时钟**（23:00 关灯 → 01:00 空调调高 1°C → 起床前 30 / 15 / 0 分钟渐进唤醒），到所选时间后服务自动结束；中途停止会取消剩余步骤。“场景”页顶部的“1+2 Agent 如何协作”卡片可展示最近一次计划的真实协作过程。

计划来源在界面上分四种标注：规则计划、模型计划、规则降级（请求了模型但改用规则，附原因）、前端模拟计划。

## 快速启动

环境：Node.js 20+，Python 3.10+。

### 1. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

演示时建议固定为晚上 8 点（高峰电价时段），能源建议每次一致：

```bash
LIVINGMIND_DEMO_LOCAL_HOUR=20 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以写进 `.env`（`LIVINGMIND_DEMO_LOCAL_HOUR=20`，等号两边不要有空格）。让能源建议固定在高峰电价时段。`--host 0.0.0.0` 让同一局域网的平板能访问；只在可信网络这样做。需要改 CORS（仅浏览器预览用）时：`cp .env.example .env` 后加 `--env-file .env`。

打开 http://localhost:8000/health 应返回 `{"status":"ok"}`；接口文档在 http://localhost:8000/docs 。

**启用模型模式（DeepSeek）**：`cp .env.example .env`，填写 `DEEPSEEK_API_KEY`，然后启动时加 `--env-file .env`。密钥只放在后端 `.env`（已被 Git 忽略），绝不写进 App。不填密钥时模型模式会降级为规则计划并标注原因。

验证真实模型（需要 `.env` 里的密钥，只能在你自己的电脑上跑）：

```bash
cd backend && set -a && source .env && set +a
.venv/bin/python scripts/try_model.py "我想休息，有点热"   # 只测 Agent 一次调用
.venv/bin/python scripts/e2e_real_model.py                 # 可选：后端端到端，5 句话，含延迟统计
.venv/bin/python scripts/e2e_real_model.py --eval          # 可选：用设计的评测集给真实模型打分
```

浏览器端到端也可以用真实模型：`cd apps/mobile && python e2e/run_e2e.py --real-model`。

### 1b. 后端（Docker，可选）

装了 Docker Desktop 时可以不建虚拟环境：

```bash
./scripts/verify-t1.sh                  # 推荐：构建、测试、健康检查、完整闭环并自动关闭
docker compose up -d                    # 全栈：PostgreSQL / Redis / migration / API / 两个 Worker
docker compose down
```

- 端口默认只绑本机。平板要连时用 `HOST_BIND=0.0.0.0 docker compose up -d api`，且只在可信网络这样做。
- 演示时段固定在 `compose.yaml` 里（晚 8 点）。模型模式的密钥在运行时传入：`DEEPSEEK_API_KEY=... docker compose up api`，不会进镜像。
- 依赖版本锁在 `backend/constraints.txt`；镜像用 Python 3.12，以非 root 用户运行。
- API 只读挂载能源模块的两个结果 JSON；研究代码、环境和模型权重不会进入运行容器。
- PostgreSQL / Redis 的宿主端口可用 `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` 覆盖；验证脚本默认用 `55432` / `56379`，避免与本机服务冲突。
- Compose 默认使用 PostgreSQL：启动 `api` 时会先起数据库并执行迁移。只想跑内存模式时，请用本地 Python 启动后端，或参考 `scripts/verify-t1.sh` 中的 `docker compose run --no-deps` 测试命令；不要仅靠留空 Compose 环境变量切换。
- 一键验证已于 2026-09-18 在 Docker Desktop 29.6.2 / Compose 5.3.1 上通过；日志写到本机 `dist/t1-verify.log`。

### 2. App

```bash
cd apps/mobile
npm install
cp .env.example .env        # 按需修改
npx expo start
```

- **模拟模式**：`.env` 里不设置 `EXPO_PUBLIC_API_BASE_URL`，App 使用前端模拟接口，界面顶部显示“前端模拟模式”。
- **后端模式**：设置 `EXPO_PUBLIC_API_BASE_URL=http://<Mac 的局域网 IP>:8000`。平板上不能用 `localhost`（那是平板自己）。查 Mac IP：`ipconfig getifaddr en0`。
- 改了 `.env` 后要用 `npx expo start --clear` 重启，否则旧配置会被缓存。
- 在 iPad 上用 Expo Go 扫码预览；在 Mac 上按 `Shift + i` 选 iPad 模拟器（需要 Xcode）；按 `w` 用浏览器粗看布局。
- 装到平板（Expo Go 登录要求、开发版 EAS 构建、真机验收清单）见 [`docs/device-build.md`](docs/device-build.md)。**尚未在真机上跑过。**

### 2b. 持久化（T2，可选）

不配 `LIVINGMIND_DATABASE_URL` 时，后端和以前一样全部在内存里，重启即重置。配上 PostgreSQL 后，人物偏好、计划、服务、整晚步骤、动作结果和活动记录都会持久化，重启后运行中的服务还能继续停止：

```bash
cd backend
export LIVINGMIND_DATABASE_URL=postgresql+psycopg://livingmind:livingmind@127.0.0.1:5432/livingmind
.venv/bin/alembic upgrade head     # 建表 / 升级
.venv/bin/uvicorn app.main:app --port 8000
```

跑数据库相关测试（没配就自动跳过）：

```bash
cd backend
# 只加跑数据库专项测试
LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/livingmind .venv/bin/pytest
# 让整套测试都跑在 PostgreSQL 上（同一批用例，换一个存储实现）
LIVINGMIND_TEST_STORE=sql LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/livingmind .venv/bin/pytest
```

### 2c. 编排方式（T3，可选）

默认走原来的顺序编排。设 `LIVINGMIND_ORCHESTRATOR=langgraph` 后，同样的阶段以 LangGraph 图运行，多了节点轨迹和 checkpoint（配了数据库就存 PostgreSQL，否则存内存）：

```bash
cd backend
LIVINGMIND_ORCHESTRATOR=langgraph .venv/bin/uvicorn app.main:app --port 8000
.venv/bin/python scripts/compare_orchestrators.py       # 两条路径生成的计划是否等价
LIVINGMIND_ORCHESTRATOR=langgraph .venv/bin/pytest      # 整套测试走图路径再跑一遍
```

设备执行不在图里：图只产出计划，确认后仍由 Harness 与执行器写设备。

### 2d. 跨实例协调（T4，可选）

设 `LIVINGMIND_REDIS_URL` 后，同一空间在被驱动时会加一把短锁（带 TTL 和 token），事件冷却多一个快速判断。**Redis 不是事实来源**：没配、连不上或键被删掉，功能都照常，只是少了这层加速；正确性仍由数据库约束和执行器守卫保证。

```bash
cd backend
LIVINGMIND_REDIS_URL=redis://127.0.0.1:6379/0 .venv/bin/uvicorn app.main:app --port 8000
LIVINGMIND_TEST_REDIS_URL=redis://127.0.0.1:6379/15 .venv/bin/pytest   # 加跑 Redis 专项测试
```

### 3. 重新生成接口类型

后端契约改动后运行：

```bash
./scripts/gen-api.sh
```

脚本优先使用 `backend/.venv`；如果本地 Python 环境过旧但已构建 `livingmind-api:dev`，会自动改用 Docker 镜像生成契约。

## 检查命令

```bash
cd backend && pytest                      # 后端测试
cd apps/mobile && npm run typecheck && npm test   # 前端类型检查 + 逻辑测试
./scripts/gen-api.sh && git diff --exit-code packages/api-client   # 契约一致性
python apps/mobile/e2e/run_e2e.py         # 本地 Python 后端端到端
python apps/mobile/e2e/run_e2e.py --external-backend http://127.0.0.1:8000  # Docker API 20 场景
```

## 演示打包（D）

```bash
cd apps/mobile && python e2e/record_demo.py      # 三段网页版录屏 → e2e/.out/videos/*.mp4
python scripts/build_evidence.py --pdf           # 主张证据表 → docs/evidence.md + output/pdf/*.pdf
```

录屏每一帧都带“网页版录屏 · 后端虚拟设备 · 规则模式”字幕；证据表逐条对照汇报 PDF，写明原型实际情况、证据位置和来源类型（见 [`docs/evidence.md`](docs/evidence.md)）。

## 离线能源仿真（P07）

“空间”页的 **24 小时能源仿真** 卡读取的是给定研究快照的固定日结果：规则策略日成本 `$1.87`、MATD3 `$-0.02`，舒适违规均为 `0 F·h`。它有 7 类模拟资产（光伏、风电、基础负荷、空调、电池、电网、柴油备用），但都是离线展示，不新增可控制设备。完整来源、限制和可选研究依赖见 [`simulation/home-energy/README.md`](simulation/home-energy/README.md)。在线能源建议仍是 `backend/app/energy/rules.py` 的可解释规则。

## 安全说明

- 演示后端**没有正式认证**，只在本机或可信局域网运行，不要部署到公网。
- 密钥只放后端环境变量；App 与 Git 中不得出现密钥。本批次不需要任何密钥。

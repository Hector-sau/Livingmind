# LivingMind App

[![CI](https://github.com/Hector-sau/Livingmind/actions/workflows/ci.yml/badge.svg)](https://github.com/Hector-sau/Livingmind/actions/workflows/ci.yml)

平板优先、手机兼容的 LivingMind 原型：一个 Expo 原生 App + 一个模块化 FastAPI 后端。

当前范围：**平板优先、手机兼容的 Home Living 演示闭环**。场景只有“我想休息”：计划 → 确认 → 虚拟设备回读 → 模拟入睡 / 室温事件 → 整晚模拟时钟 → 渐进唤醒或停止。
接手或协作前先读 [AGENT-HANDOFF.md](AGENT-HANDOFF.md)（统一交接文档，在仓库根目录持续维护）。实际完成情况以 [docs/status.md](docs/status.md) 为准；验收标准见 [docs/acceptance.md](docs/acceptance.md)。

## 系统架构

一个 Expo App、一个 FastAPI 后端、一层由后端契约生成的共享类型。App 不认识设备，只认识接口；后端不让 Agent 碰设备，只让它产出计划。

### 组成部分

| 组件 | 职责 | 位置 |
|---|---|---|
| 页面层 | 12 个功能模块（对话、设备、语音、整晚、场景、证据、能源…），只调接口层 | `apps/mobile/features/` |
| 接口层 | 同一套方法两种实现：前端模拟与真实 HTTP，切换不改页面 | `apps/mobile/services/{mock,http}/` |
| 共享类型 | 由后端 OpenAPI 生成，禁止手改 | `packages/api-client/` |
| 路由与错误 | 21 个端点，统一错误结构与错误码 | `backend/app/api/` |
| 服务编排 | 单空间串行锁、计划生命周期、整晚服务、撤销窗口 | `backend/app/services/rest_service.py` |
| 主 Agent | 意图路由与三个阶段的编排，产出协作轨迹 | `backend/app/agents/orchestrator/` |
| 体验 Agent | **唯一会调用大模型的环节**，失败降级为规则并记录原因 | `backend/app/agents/experience/` |
| 空间执行 Agent | 按空间规则生成整晚安排 | `backend/app/agents/space_execution/` |
| 图编排（可选） | 同样的阶段跑成 LangGraph 图，多出节点轨迹与 checkpoint | `backend/app/graph/` |
| Harness | 预检、发放有界授权、执行动作 | `backend/app/harness/{policy,grants,executor}.py` |
| 设备网关 | 幂等 `actionId`、空间代次（`service_epoch`）fencing、受理/完成/失败/拒绝/未知回执 | `backend/app/adapters/gateway.py` |
| 虚拟设备 | 有状态的灯 / 空调 / 窗帘，写入后回读 | `backend/app/adapters/virtual/` |
| 存储 | 同一批用例两种实现：进程内存与 PostgreSQL | `backend/app/repositories/`、`backend/app/db/` |
| 记忆 / 能源 / 事件 / 缓存 | 人物偏好、可解释能源规则、事件出箱、跨实例短锁 | `backend/app/{memory,energy,events,cache}/` |

### 一次“我想休息”走过哪些环节

1. App 发 `POST /api/plans/rest`，带账户、人物、空间与这句话。
2. 主 Agent 判定意图，调体验 Agent 产出体验目标——这一步要么走 DeepSeek，要么走规则，结果带 `source` 标注。
3. 空间执行 Agent 按空间规则把体验目标落成具体设备动作，并生成整晚安排。
4. Harness 预检：白名单、参数范围、与人物偏好的偏离上限。越界的动作在这里就被拿掉，并写明原因。
5. 计划返回给 App。**此时设备一动没动。**
6. 用户确认 → `POST /api/plans/{id}/confirm`。Harness 这时才生成 `ExecutionGrant`：有界、会过期、数值被收窄到已批准的那些。
7. 执行器凭授权逐个动作写设备，每次写前重查空间代次，写后回读实际值。
8. 结果、回读值与失败原因一起落进活动记录，返回 App。

### 一次设备直接控制走过哪些环节

1. 用户拖滑块，松手才提交 `POST /api/spaces/{id}/devices/control`。
2. 后端记下**执行前的原值**，执行，回读，开一个 5 秒撤销窗口。
3. 用户点撤销 → `POST /api/devices/undo/{undo_id}`，写回记下的原值。不是猜一条相反指令。
4. 窗口过期、或同一空间来了新动作，旧窗口立即失效（`UNDO_EXPIRED` / `UNDO_INVALIDATED`）。

单个低风险动作（灯、空调、窗帘）走这条路，不弹确认框；多动作的休息计划仍然先确认后执行。

### 四个可切换的轴

| 轴 | 默认 | 可选 | 开关 |
|---|---|---|---|
| 存储 | 进程内存，重启即重置 | PostgreSQL，计划 / 服务 / 授权 / 动作账本 / 整晚步骤 / 活动 / 待澄清都可恢复 | `LIVINGMIND_DATABASE_URL` |
| 编排 | 顺序编排 | LangGraph 图，带节点轨迹与 checkpoint | `LIVINGMIND_ORCHESTRATOR=langgraph` |
| 跨实例协调 | 关 | Redis 短锁与事件冷却快速判断（**不是事实来源**，挂了功能照常） | `LIVINGMIND_REDIS_URL` |
| 计划来源 | 规则 | DeepSeek 一次调用，失败降级为规则并标注原因 | `DEEPSEEK_API_KEY` |

前三个轴互不依赖，CI 按内存 / PostgreSQL / PostgreSQL + Redis + LangGraph 三种组合各跑一遍完整测试。第四个轴需要密钥，不进 CI。

## 三条架构边界

1. **页面不直接控制设备**：页面只调用 `apps/mobile/services/` 的接口；从模拟切到真实 API 不改页面。
2. **Agent 不拥有设备凭据**：规则和模型都只能生成计划；确认后由 Harness 生成有界的 `ExecutionGrant`，再经 Executor、DeviceGateway、回执与回读执行。
3. **模拟逻辑集中存放**：前端模拟在 `apps/mobile/services/mock/`，后端虚拟设备在 `backend/app/adapters/virtual/`，种子数据在 `backend/app/demo/`。

口径按三档区分，不要混用：**已实现并验证**（有代码、有测试、有实跑结果）/ **接口预留**（只有协议与契约替身测试，没有对端）/ **仍待执行**（需用户授权或外部条件）。对照表见 [AGENT-HANDOFF.md](AGENT-HANDOFF.md) 第 9 节。

## 已实现的功能

### 对话与计划

- 对话主页、四个入口、场景库、证据面板。
- “我想休息”生成计划：**计划产出时设备不动**，确认后才执行并回读实际值。
- 计划来源在界面上分四档标注：规则计划、模型计划、规则降级（请求了模型但改用规则，附原因）、前端模拟计划。
- 歧义请求先澄清再执行，覆盖三类：否定、设备冲突、指代不清。待澄清状态按账户 / 人物 / 空间 / 会话隔离，10 分钟过期，可取消。

### Agent 编排

- 1+2 结构：主 Agent 负责路由与编排，体验 Agent 产出体验目标，空间执行 Agent 落成设备动作与整晚安排。
- 三者共享人物记忆与能源规则，计划经 Harness 预检；每个计划附真实的协作轨迹，“场景”页可展开查看。
- 体验 Agent 一次模型调用（DeepSeek）。规则与模型可切换；模型不可用时降级为规则并写明原因，链路不中断。
- 同一套阶段可改由 LangGraph 图执行，多出节点轨迹与 checkpoint；`scripts/compare_orchestrators.py` 验证两条路径产出的计划等价。

### 设备控制与执行

- 受控执行链：`PolicyDecision → ExecutionGrant → ActionExecution`。授权有界、会过期、被收窄到已批准的数值，迁移 `0005_execution_authority` 持久化全过程。
- `DeviceGateway` V2 已进入虚拟设备执行路径：幂等 `actionId`、空间代次（`service_epoch`）fencing、受理 / 完成 / 失败 / 拒绝 / 未知五种回执、持久化动作账本。
- 设备面板直接控制：双轨滑块（拖动时本地值优先、松手才提交）、目标值与回读值双指示、直接执行 + 5 秒真撤销。
- 有状态虚拟设备（灯 / 空调 / 窗帘），每次写入后回读；写设备成功但回读失败时返回明确的动作失败。

### 语音

- 完整语音回合：按住说话 → 状态机（`idle → armed → listening → resolving → sending → speaking`）→ 真实 TTS 播报与打断。
- **任何超时的默认结果都是不执行**，没有一条超时路径能走到发送。
- 设备端识别适配层（`expo-speech-recognition`，系统引擎、无密钥、可端侧）代码完整；未接入真实识别器时转写文本带来源标签，界面不出现“识别”字样。

### 整晚服务与事件

- 确认后同一个服务贯穿整晚，跑在**模拟时钟**上（22:30 起），只由接口推进，后端不读真实时间、不开后台定时器。
- 渐进唤醒三步（起床前 30 / 15 / 0 分钟），深夜空调调高 1°C 且不超出本人偏好 +3°C。
- 模拟室温事件触发一次自动调整，带冷却与次数上限；停止服务后事件被忽略，剩余步骤记为取消。
- 启动恢复可查询（`GET /api/system/recovery`）：清理崩溃遗留标记，**结果未知的步骤取消而非重放**。

### 身份、记忆与持久化

- 演示身份（demo account）、人物切换（演示 PIN）、访客模式（不读取任何人的个人偏好）。
- 内存或 PostgreSQL 两种存储可切换；配库后计划、服务、执行授权、动作账本、整晚步骤、活动与待澄清状态均可恢复，重启后运行中的服务还能继续停止。
- 可选 Redis 跨实例短锁与事件冷却加速；**Redis 不是事实来源**，正确性由数据库约束和执行器守卫保证。

### 能源展示

- 在线能源建议是 `backend/app/energy/rules.py` 的可解释规则。
- 24 小时家庭能源离线仿真：给定的固定日结果，规则策略 vs 单智能体 MATD3，只读展示，不参与控制，也不新增可控制设备。

### 演示与证据

- 一键“准备演示”重置；三段网页版录屏，每帧带“网页版录屏 · 后端虚拟设备 · 规则模式”字幕。
- 主张证据表逐条对照汇报 PDF，写明原型实际情况、证据位置与来源类型。
- `backend/scripts/model_latency_bench.py` 可复现真实模型的延迟分布与失败分类。

## 暂不做（后续批次）

真实设备 / SpaceMind / 厂商云 / 音箱 / 传感器接入 · 真实后台定时器 · 真实睡眠感知 · 真实硬件状态回读恢复 · 唤醒词、声纹、免手操作 · 高风险设备（门锁等）· 通用多轮对话记忆 · 正式登录、WebSocket、向量库 · 在线 MATD3 控制或重新训练评估

**所有设备都是后端虚拟设备**，执行链路是完整的，对端是模拟的。**设备端语音识别代码完整但未在真机验证**——它需要 development build，端到端测试与 CI 都覆盖不到这一项。

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

`deepseek-flash` 会在答案之前写推理内容，而推理与答案共用同一个 token 预算。实测（`docs/evidence/model-latency.json`）在较难的那句话上推理写了 1280–1387 个字符，400 的预算在答案开始之前就用光了，`content` 返回空。默认预算因此设为 2000，可用 `LIVINGMIND_MODEL_MAX_TOKENS` 调整；换模型时请自己测一遍再往下调。预算耗尽是独立的失败类型（`truncated`），和“模型真的没返回”分开统计。

验证真实模型（需要 `.env` 里的密钥，只能在你自己的电脑上跑）：

```bash
cd backend && set -a && source .env && set +a
.venv/bin/python scripts/try_model.py "我想休息，有点热"   # 只测 Agent 一次调用
.venv/bin/python scripts/e2e_real_model.py                 # 可选：后端端到端，5 句话，含延迟统计
.venv/bin/python scripts/e2e_real_model.py --eval          # 可选：用设计的评测集给真实模型打分
.venv/bin/python scripts/model_latency_bench.py --samples 24   # 延迟分布与失败分类
```

`model_latency_bench.py` 重复调用与产品同一条路径（`ExperienceAgent.plan()`，含 JSON 解析与结构校验），输出 p50 / p90 / p95、模型贡献率、按 kind 的失败分类和按话术的分组，写入 `docs/evidence/model-latency.json`。分位数只统计成功调用——超时那条的耗时等于预算本身，混进去会把中位数做得好看。密钥从环境变量读取，不会打印、也不会写进结果文件。

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

不配 `LIVINGMIND_DATABASE_URL` 时，后端和以前一样全部在内存里，重启即重置。配上 PostgreSQL 后，人物偏好、计划、服务、整晚步骤、动作结果和活动记录都会持久化，重启后运行中的服务还能继续停止。执行授权链也在库里：`0005_execution_authority` 建了 `policy_decisions` / `execution_grants` / `action_executions` 三张表，一次确认发放了什么授权、执行器凭它写了什么、回读到什么，事后都查得到：

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

checkpoint 连接每进程只建一个，按数据库 URL 缓存共享（`PostgresSaver` 自带线程锁）。它由 psycopg 自行持有，不受 SQLAlchemy 连接池设置管辖——每个编排器各开一条的话，一次完整测试运行就能耗尽 PostgreSQL 的 `max_connections`。

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
python apps/mobile/e2e/run_e2e.py --external-backend http://127.0.0.1:8000  # Docker API 27 场景
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

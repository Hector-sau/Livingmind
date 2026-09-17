# LivingMind AI 交接文档

更新日期：2026-09-17  
仓库位置：`/Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/`  
当前分支：`main`  
第一批实现基线提交：`99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI`  
当前基线：B 并发修正 + ⑤ Experience Agent（接口与测试就绪，真实调用未验证）— 见 `git log`

## 1. 接手结论

第一批步骤 0–4、B 并发修正、⑤ Experience Agent（接口与测试就绪）已完成。用户目前没有 iPad，真机验收（A）推迟到有设备时；在此之前继续做后端与接口联动，前端视觉统一留到 C。不要重搭架构，不要复制旧项目覆盖当前仓库，也不要同时开始多个步骤。

当前产品是一条可工作的纵向链路，规划阶段可选规则或模型：

```text
Expo App（计划来源开关：规则 / 模型）
  → 可切换的前端 Mock / HTTP API
  → FastAPI
  → Planner：固定休息规则，或 Experience Agent（DeepSeek）→ 失败时规则降级并标注
    （只生成计划，不改设备；等待模型时不持锁）
  → 用户确认
  → 统一执行器（白名单、参数、服务状态检查）
  → 有状态虚拟灯光 / 空调 / 窗帘
  → 状态回读与活动记录
  → App 更新
```

场景范围只有 Home Living 的“我想休息”。当前没有完整多 Agent、数据库、真实认证、事件触发的持续调整、整晚定时服务、SpaceMind 或真实设备接入。模型调用的代码和测试已就绪，但**尚未用真实 DeepSeek 密钥验证过一次调用**。

## 2. 接手后的必读顺序

1. 本文件：当前状态、边界和下一任务。
2. `README.md`：启动方法和三条架构边界。
3. `docs/status.md`：已实现、证据、未实现内容。
4. `docs/acceptance.md`：每阶段达到什么程度就停止。
5. `docs/architecture.md`：当前代码链路和目录职责。
6. `docs/ui-polish.md`：视觉整理清单，只在执行第 8 节 C 项时使用。
7. 修改 `apps/mobile/` 前阅读 `apps/mobile/AGENTS.md`，并查看其要求的 Expo SDK 57 版本文档。

不得把架构评审、PDF 或演讲稿中的描述直接当成“代码已经实现”。以仓库、测试和 `docs/status.md` 为准。

## 3. 不可破坏的架构边界

1. **页面不直接控制设备。** 页面只依赖 `apps/mobile/services/api.ts`；Mock 和 HTTP 实现遵循相同接口。
2. **Agent 不绕过执行器。** 规则计划和未来模型计划都必须进入 `backend/app/harness/executor.py`，经过检查、设备写入和回读。
3. **模拟逻辑集中存放。** 前端模拟在 `apps/mobile/services/mock/`，虚拟设备在 `backend/app/adapters/virtual/`，种子数据在 `backend/app/demo/`。
4. **后端契约是唯一类型来源。** 修改 `backend/app/contracts/` 后必须运行 `./scripts/gen-api.sh`；不要手改生成的 `packages/api-client/src/schema.ts`。
5. **所有来源必须如实标记。** `frontend_mock`、`rule`、未来的 `model` 和规则降级不能混写，不能伪造模型或设备调用轨迹。
6. **演示身份不等于认证。** 当前服务只能在本机或可信局域网运行，不得部署到公网。

统一深度标准：**演示可见、面试可答、代码可指。** 每个模块只做一条真实工作路径和相关关键失败路径，达到 `docs/acceptance.md` 后停止扩展。

## 4. 已实现内容

| 步骤 | 已完成内容 | 主要位置 |
|---|---|---|
| 0 实施基线 | 项目说明、架构、验收与状态文档 | `README.md`、`docs/` |
| 1 最小骨架 | Expo SDK 57 原生 App、平板配置、FastAPI 健康检查、可配置后端地址 | `apps/mobile/`、`backend/app/main.py` |
| 2 数据契约 | Pydantic 契约、统一错误、OpenAPI → TypeScript 类型、两个种子人物 | `backend/app/contracts/`、`packages/api-client/`、`scripts/gen-api.sh` |
| 3 可点击原型 | 人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 活动；平板/手机响应式布局 | `apps/mobile/features/`、`apps/mobile/services/mock/` |
| 4 无模型后端链路 | 固定规则、统一执行器、有状态虚拟设备、状态回读、活动记录、PR 模板与 CI | `backend/app/rules/`、`harness/`、`services/`、`adapters/virtual/`、`.github/` |
| B 并发修正 | 设备写入移出服务锁；每个动作前在锁内重查服务与代次；慢设备抢占测试（服务层 + HTTP 层） | `backend/app/services/rest_service.py`、`tests/test_concurrency.py` |
| ⑤ 最小 AI 证据 | Experience Agent（提示词、Pydantic 输出校验、DeepSeek Provider）、规则/模型切换、降级标注、延迟记录、App 来源开关与四种来源标签、`scripts/try_model.py` | `backend/app/agents/experience/`、`services/planner.py`、`apps/mobile/features/rest/ModeToggle.tsx` |

当前 Git 提交按步骤拆分：

```text
c4e8d9b docs: step 0 implementation baseline
19599db feat: step 1 minimal Expo app and FastAPI skeleton
386bc2e feat: step 2 data contracts, unified errors, generated API types
e8ffb61 feat: step 3 clickable rest-flow prototype with front-end mock
99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI
```

仓库当前没有远程地址，没有推送或发布。

## 5. 当前强制业务语义

以下规则由后端执行，不只依赖 UI：

- 创建计划不改变设备，只有确认后执行。
- 同一计划重复确认不重复写设备。
- 同一空间只允许一个活跃休息服务。
- 计划 10 分钟后过期，身份、人物、空间、计划版本不符会被拒绝。
- 停止后，空间此前未执行的计划失效；已执行计划不能重新启动服务。
- 停止后设备保持当前状态，不自动恢复。
- 每个设备动作经过白名单、参数范围检查、写入和回读。
- API 不可达时，App 显示失败和状态可能过期，不偷偷回退到 Mock 成功。
- 数据仅在进程内存中保存，后端重启或演示重置会清空。

主要接口：

```text
GET  /health
GET  /api/bootstrap
GET  /api/spaces/{spaceId}/devices
POST /api/plans/rest
POST /api/plans/{planId}/confirm
POST /api/services/{serviceId}/stop
GET  /api/spaces/{spaceId}/activity
POST /api/demo/reset
```

FastAPI 运行后可在 `http://localhost:8000/docs` 查看实时 OpenAPI 文档。

## 6. 启动与验证

要求 Node.js 20+、Python 3.10+。

### 后端

```bash
cd /Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 启用模型模式：cp .env.example .env，填 DEEPSEEK_API_KEY，再加 --env-file .env
```

验证一次真实模型调用：`set -a && source .env && set +a && .venv/bin/python scripts/try_model.py "我想休息，有点热"`

### App

```bash
cd /Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/apps/mobile
npm install
cp .env.example .env
npx expo start
```

- `EXPO_PUBLIC_API_BASE_URL` 留空：前端 Mock 模式。
- 设置为 `http://<Mac 局域网 IP>:8000`：真实后端模式。
- 平板不能使用 `localhost` 访问 Mac；可用 `ipconfig getifaddr en0` 查询常见 Wi-Fi 地址。
- 修改 `.env` 后用 `npx expo start --clear` 重启。

### 提交前必须运行

```bash
cd backend && pytest
cd ../apps/mobile && npm run typecheck && npm test
cd ../..
./scripts/gen-api.sh
git diff --exit-code -- packages/api-client
git status --short
```

上一轮记录：后端 40 项测试通过，前端 12 项逻辑测试与类型检查通过，干净副本 CI 模拟通过。网页版在 1180×820 和 390×844 下完成 Mock / 后端流程；断开后端时错误状态符合预期。接手 AI 不应只引用该记录，改动后必须重新运行相关检查。

## 7. 尚未验证与已知限制

- 尚未在 iPad、Android 平板、手机真机或 iOS 模拟器运行；网页预览不能替代真机验收。
- GitHub CI 尚未真实运行，因为没有远程仓库。
- 规则模式下用户文字只记录，固定规则不会理解任意自然语言；模型模式的真实调用尚未验证（见下）。
- 没有真实身份认证、持久化数据库、WebSocket、语音、睡眠传感器或厂商设备。
- 前端 Mock 和后端内存数据互不共享；切换模式应视为不同演示环境。
- 停止不会把灯光、温度、窗帘恢复到执行前状态，这是当前明确语义。

### 并发（B 已修正）

`confirm_plan()` 现在只在锁内做记账，设备批次在锁外执行；guard 在每个动作前于锁内重查 `service.status` 与空间代次。`tests/test_concurrency.py` 用一个会阻塞首个写入的慢设备证明：停止请求立即返回，已开始的动作完成，其余跳过。已开始的那一个动作不会被撤销，这是当前语义。模型调用同样在锁外进行。

### ⑤ 的真实调用未验证

`tests/test_experience_agent.py` 全部使用测试替身；本地 HTTP 桩只验证了请求格式、解析与超时路径。要把 ⑤ 标为“真实调用已验证”，必须在有 `DEEPSEEK_API_KEY` 的机器上运行 `backend/scripts/try_model.py`，把实际模型名与延迟写入 `docs/status.md`。8 秒目标（提交到显示计划）同样待此验证。

## 8. 后续执行顺序

一次只做一步，完成验收后停止并报告。字母项是第二批之外必须穿插的工作；⑤–⑨ 沿用架构评审编号。

| 顺序 | 内容 | 达到即停 | 备注 |
|---|---|---|---|
| A 真机验收 | iPad（及安卓平板，如有）用 Expo Go 跑 Mock 与后端两种模式 | 完整流程走通，问题记录到 `docs/status.md` | **推迟**：用户暂无 iPad；有设备时立即补做，期间状态保持“真机未验证” |
| B 并发修正 | 缩短 `confirm_plan` 持锁范围；每次外部写入前按 `serviceId + epoch` 重查；补慢设备/延迟 Adapter 测试 | 停止请求能中途打断慢设备批次 | **已完成**（`c639d5d`） |
| ⑤ 最小 AI 证据 | Experience Agent 一次真实模型调用；规则/模型开关；超时或非法输出降级并标注来源 | 提交到显示计划 8 秒内（待验证目标）；第 9 节测试全部通过 | **接口与测试就绪**；真实调用待用户用密钥运行 `try_model.py` 验证 |
| ⑥ 一次事件调整 | 注入一次模拟入睡或室温事件，触发一次调整；验证停止 | 休息 → 事件 → 调整 → 停止；停止后再注入不执行 | 功能底线到此完成 |
| C 视觉整理 | 按 `docs/ui-polish.md` 清单美化；只改 `theme/`、`components/`、`features/` | 两种尺寸截图前后对比；测试全部通过；来源标注仍清晰可见 | 放在 ⑥ 之后、演示之前，页面结构此时已稳定 |
| ⑦ 整晚服务 | 模拟时钟、夜间阶段、渐进唤醒；一个 `serviceId` 贯穿整晚 | 定时任务不重复执行；停止取消剩余任务 | 可选，视时间决定 |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源规则及所需 Harness 能力 | 每个模块一条真实工作路径、明确输入输出、调用证据 | 简历可写“多 Agent 编排”的门槛 |
| ⑨ 逐页迁移 | 按旧 HTML 的页面、组件、交互、数据清单逐页迁移 | 一页完成、一页验收 | 只迁演示需要的页面 |
| D 演示打包 | Development Build 装到平板；录屏三段（用户触发、事件调整、手动停止）；PDF 主张对证据表 | 每条主张有对应证据；模拟与真实来源分开标注 | 复赛前一周完成 |

两条底线：**功能底线 = A + B + ⑥（含第一批规则链路）；AI 演示底线 = 再加 ⑤。**

不能因为建立了目录或类名，就宣称相应 Agent 已经实现。功能声明必须对应真实调用轨迹和测试。

## 9. 下一位 AI 的当前任务：步骤 ⑥

前置：⑤ 的真实调用验证由用户在本机完成，不阻塞 ⑥；但不得把 ⑤ 改成“已验证”。

### 目标

在现有服务闭环上增加**一次**由环境事件触发的自动调整：休息服务运行中 → 注入一次模拟事件（先只做室温变化）→ 后端重新规划并执行一次调整 → 用户停止 → 再注入事件不再执行。

### 最小实现要求

- 事件入口：`POST /api/spaces/{spaceId}/events`，请求含 `RequestContext`、事件类型与数值；事件 `source` 固定为 `simulated`，UI 与活动记录都要标明是模拟事件。
- 只有空间存在 `active` 服务时才重规划；否则记录“事件已忽略：无活跃服务”并返回，不报错。
- 冷却时间（例如 30 秒，可配置）与最大重规划次数（例如每个服务 3 次）由后端强制；超出时记录“事件已忽略：冷却中 / 已达上限”。
- 重规划复用 `Planner`（遵循服务当前的规则/模型模式）与 `_execute`（guard + epoch）；调整不需要再次确认，但必须在活动记录里写明触发事件、生成来源和每个动作的结果。
- `Service` 增加 `adjustments` 计数与 `lastAdjustedAt`；契约改动后运行 `./scripts/gen-api.sh`。
- 停止后注入事件：必须被忽略，且不能产生任何设备动作。
- 前端只加“注入模拟事件（室温 +3°C）”按钮、事件在服务动态里的显示、服务卡片上的调整次数；不做视觉调整。
- 前端 Mock 同步实现同样的规则，标 `frontend_mock`。

### 必须补的测试

- 无活跃服务时事件被忽略，设备不变。
- 活跃服务 + 事件 → 一次调整，设备状态改变并回读，活动记录含事件与动作。
- 冷却时间内第二次事件被忽略。
- 达到最大次数后事件被忽略。
- 停止后事件被忽略，设备版本不变。
- 模型模式下事件重规划失败 → 规则降级并标注（复用 ⑤ 的替身）。
- 事件与停止并发：停止后不再有新动作（复用慢设备替身）。

### 停止条件

满足 `docs/acceptance.md` 中 ⑥；更新 `README.md`、`docs/status.md`、`docs/architecture.md` 和本文件；一次聚焦 commit；报告结果与未验证事项；停止，不进入 ⑦ 或 C。

## 10. 禁止事项

- 不整体重写现有 App 或 FastAPI 服务。
- 不引入微服务、向量库、正式登录、复杂数据库或 WebSocket 来完成步骤 ⑤。
- 不复制旧项目的 `.env`、密钥、数据库或大批无关代码。
- 不把 Mock、预录结果、测试替身描述成在线模型调用。
- 不创建远程仓库、不推送、不部署、不发布，除非用户另行明确授权。
- 不修改或删除用户的原始汇报材料和旧项目。

## 11. 接手 AI 的交付格式

每次完成后必须给出：

1. 本次只完成了哪个步骤。
2. 修改的文件和关键设计。
3. 启动与复现方法。
4. 自动检查、真机/模拟器/浏览器检查及各自结果。
5. 哪些仍是模拟、预留或未验证。
6. 当前提交哈希和工作区是否干净。
7. 下一步建议，但未经确认不继续执行。

可直接给下一位 AI 的指令：

> 请先阅读仓库根目录 `AGENT-HANDOFF.md`，然后依次阅读 `README.md`、`docs/status.md`、`docs/acceptance.md`、`docs/architecture.md`。保留现有实现和提交历史，重新运行基线检查。本轮只执行交接文档第 9 节的步骤 ⑥；达到验收条件后更新状态文档、提交一次聚焦 commit 并停止。不要把 Mock、规则降级或测试替身描述成真实模型调用，不要把 ⑤ 改成“真实调用已验证”，不要推送、部署或开始步骤 ⑦ 与 C。

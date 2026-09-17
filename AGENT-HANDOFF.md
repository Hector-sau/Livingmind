# LivingMind AI 交接文档

更新日期：2026-09-17  
仓库位置：`/Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/`  
当前分支：`main`  
第一批实现基线提交：`99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI`

## 1. 接手结论

第一批步骤 0–4 已完成，当前应先由团队在 iPad / Android 真机上验收，再逐项进入第二批。不要重搭架构，不要复制旧项目覆盖当前仓库，也不要同时开始步骤 ⑤–⑨。

当前产品是一条可工作的无模型纵向链路：

```text
Expo App
  → 可切换的前端 Mock / HTTP API
  → FastAPI
  → 固定休息规则（只生成计划，不改设备）
  → 用户确认
  → 统一执行器（白名单、参数、服务状态检查）
  → 有状态虚拟灯光 / 空调 / 窗帘
  → 状态回读与活动记录
  → App 更新
```

场景范围只有 Home Living 的“我想休息”。当前没有大模型、完整多 Agent、数据库、真实认证、整晚定时服务、SpaceMind 或真实设备接入。

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

## 4. 第一批已实现内容

| 步骤 | 已完成内容 | 主要位置 |
|---|---|---|
| 0 实施基线 | 项目说明、架构、验收与状态文档 | `README.md`、`docs/` |
| 1 最小骨架 | Expo SDK 57 原生 App、平板配置、FastAPI 健康检查、可配置后端地址 | `apps/mobile/`、`backend/app/main.py` |
| 2 数据契约 | Pydantic 契约、统一错误、OpenAPI → TypeScript 类型、两个种子人物 | `backend/app/contracts/`、`packages/api-client/`、`scripts/gen-api.sh` |
| 3 可点击原型 | 人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 活动；平板/手机响应式布局 | `apps/mobile/features/`、`apps/mobile/services/mock/` |
| 4 无模型后端链路 | 固定规则、统一执行器、有状态虚拟设备、状态回读、活动记录、PR 模板与 CI | `backend/app/rules/`、`harness/`、`services/`、`adapters/virtual/`、`.github/` |

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
```

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

上一轮记录：后端 22 项测试通过，前端 11 项逻辑测试与类型检查通过，干净副本 CI 模拟通过。网页版在 1180×820 和 390×844 下完成 Mock / 后端流程；断开后端时错误状态符合预期。接手 AI 不应只引用该记录，改动后必须重新运行相关检查。

## 7. 尚未验证与已知限制

- 尚未在 iPad、Android 平板、手机真机或 iOS 模拟器运行；网页预览不能替代真机验收。
- GitHub CI 尚未真实运行，因为没有远程仓库。
- 没有模型调用；用户文字只记录，固定规则不会理解任意自然语言。
- 没有真实身份认证、持久化数据库、WebSocket、语音、睡眠传感器或厂商设备。
- 前端 Mock 和后端内存数据互不共享；切换模式应视为不同演示环境。
- 停止不会把灯光、温度、窗帘恢复到执行前状态，这是当前明确语义。

### 重要并发限制

`Executor` 已在每个动作前调用 guard，且单元测试证明 guard 变化后剩余动作会跳过。但是，当前 `RestService.confirm_plan()` 在持有 `RLock` 时同步执行整批虚拟动作；另一个 HTTP 停止请求无法在这段同步临界区内取得同一把锁。因此目前只证明了执行器级检查，**尚未证明真实慢设备或异步 Adapter 场景下“停止能中途抢占正在执行的批次”**。

第一批的同步虚拟设备不受影响。进入步骤 ⑥或真实设备 Adapter 前，应缩短锁范围，并以 `serviceId + epoch/generation` 在每次外部写入前重新检查；不得在等待模型或设备网络调用期间持有长锁。需要增加真正的并发/延迟测试后，才能声称停止可抢占。

## 8. 后续执行顺序

一次只做一步，完成验收后停止并报告。字母项是第二批之外必须穿插的工作；⑤–⑨ 沿用架构评审编号。

| 顺序 | 内容 | 达到即停 | 备注 |
|---|---|---|---|
| A 真机验收 | iPad（及安卓平板，如有）用 Expo Go 跑 Mock 与后端两种模式 | 完整流程走通，问题记录到 `docs/status.md` | 第一批的最后一道关，先于一切 |
| B 并发修正 | 缩短 `confirm_plan` 持锁范围；每次外部写入前按 `serviceId + epoch` 重查；补慢设备/延迟 Adapter 测试 | 停止请求能中途打断慢设备批次 | 见第 7 节；必须在 ⑥ 或真实设备之前完成 |
| ⑤ 最小 AI 证据 | Experience Agent 一次真实模型调用；规则/模型开关；超时或非法输出降级并标注来源 | 提交到显示计划 8 秒内（待验证目标）；第 9 节测试全部通过 | 详见第 9 节 |
| ⑥ 一次事件调整 | 注入一次模拟入睡或室温事件，触发一次调整；验证停止 | 休息 → 事件 → 调整 → 停止；停止后再注入不执行 | 功能底线到此完成 |
| C 视觉整理 | 按 `docs/ui-polish.md` 清单美化；只改 `theme/`、`components/`、`features/` | 两种尺寸截图前后对比；测试全部通过；来源标注仍清晰可见 | 放在 ⑥ 之后、演示之前，页面结构此时已稳定 |
| ⑦ 整晚服务 | 模拟时钟、夜间阶段、渐进唤醒；一个 `serviceId` 贯穿整晚 | 定时任务不重复执行；停止取消剩余任务 | 可选，视时间决定 |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源规则及所需 Harness 能力 | 每个模块一条真实工作路径、明确输入输出、调用证据 | 简历可写“多 Agent 编排”的门槛 |
| ⑨ 逐页迁移 | 按旧 HTML 的页面、组件、交互、数据清单逐页迁移 | 一页完成、一页验收 | 只迁演示需要的页面 |
| D 演示打包 | Development Build 装到平板；录屏三段（用户触发、事件调整、手动停止）；PDF 主张对证据表 | 每条主张有对应证据；模拟与真实来源分开标注 | 复赛前一周完成 |

两条底线：**功能底线 = A + B + ⑥（含第一批规则链路）；AI 演示底线 = 再加 ⑤。**

不能因为建立了目录或类名，就宣称相应 Agent 已经实现。功能声明必须对应真实调用轨迹和测试。

## 9. 下一位 AI 的当前任务：步骤 ⑤

开始前先完成真机验收。如果团队暂时无法提供真机，可以继续实现，但必须保留“真机未验证”状态，不能改成已完成。

### 目标

在不破坏现有规则路径的前提下，实现 Experience Agent 的一次服务器端真实模型调用。输入为受控的 `RequestContext`、用户需求和当前人物种子偏好；输出为现有执行器能够处理的结构化 `Plan`。模型只负责生成体验计划，不能直接写设备。

### 最小实现要求

- 在 `backend/app/agents/experience/` 建立真正被服务调用的模块，而不是空目录。
- 模型供应商、模型名、超时和模式由后端环境变量配置；密钥只在后端，绝不使用 `EXPO_PUBLIC_*` 暴露密钥。
- 增加明确模式：`rule` 和 `model`。模型关闭或未配置时仍可运行规则模式。
- 模型输出必须通过 Pydantic schema、设备白名单和参数范围校验，再交给同一个 Executor。
- 提交到显示计划的端到端目标为 8 秒内，这是待验证目标，不包括用户确认和设备动作时间。
- 模型超时、网络失败、解析失败或校验失败时，从当前人物/空间重新生成规则计划；界面必须显示“默认方案 / 规则降级”及简短原因。
- 不自动使用上一次其他人物、空间或旧状态的模型结果。
- 活动记录只保存可展示的输入摘要、计划来源、耗时、降级原因和工具结果；不展示或保存模型隐藏思考过程。
- Mock、规则、模型、规则降级四种来源在 UI 和活动记录里不能混淆。

如果没有服务器端 API key 或无法完成一次真实网络调用，可以实现 Provider 接口和测试替身，但步骤 ⑤只能标为“接口已准备，真实调用未验证”，不能标为完成。

### 必须补的测试

- 合法结构化模型输出可形成计划，但创建计划阶段仍不改变设备。
- 模型计划确认后仍通过统一执行器和虚拟设备回读。
- 模型超时进入规则降级并标注来源。
- 非法 JSON、越界动作、未知设备或命令不能绕过校验。
- A/B 人物输入使用各自偏好，不能跨人物复用。
- 规则模式完全不请求模型。
- 模型模式失败不会影响停止、重复确认、计划过期等现有语义。
- 日志与错误中不出现 API key。

### 步骤 ⑤的停止条件

满足 `docs/acceptance.md` 中步骤 ⑤，更新 `README.md`、`docs/status.md`、`docs/acceptance.md` 和本交接文档；提交一次聚焦的 Git commit；报告实际模型、实际延迟、测试结果和未验证事项。然后停止，不自动进入步骤 ⑥。

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

> 请先阅读仓库根目录 `AGENT-HANDOFF.md`，然后依次阅读 `README.md`、`docs/status.md`、`docs/acceptance.md`、`docs/architecture.md`。保留现有第一批实现和提交历史，重新运行基线检查。本轮只执行交接文档第 9 节的步骤 ⑤；达到验收条件后更新状态文档、提交一次聚焦 commit 并停止。不要把 Mock、规则降级或测试替身描述成真实模型调用，不要推送、部署或开始步骤 ⑥。

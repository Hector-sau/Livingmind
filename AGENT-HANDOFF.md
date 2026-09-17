# LivingMind AI 交接文档

更新日期：2026-09-17  
仓库位置：`/Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/`  
当前分支：`main`  
第一批实现基线提交：`99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI`  
当前基线：B 并发修正 + ⑤ Experience Agent（已验证真实 DeepSeek 调用，2035 ms）— 见 `git log`

## 0. 项目背景与现状速览（给评审或新接手的 AI）

### 0.1 背景

- **项目**：LivingMind，参加 SpaceMind AI Agent 创新应用大赛，已进入复赛，需要约 8 分钟汇报 + 可演示原型。对外品牌统一用 LivingMind；历史代码名 KidMind 只在解释旧原型时出现。
- **定位**：家庭住宅（Home Living）为核心场景，酒店（Smart Stay）为延展；两者共享 Energy Intelligence。叙事核心：“一次表达，持续服务；体验是约束，能源是优化”。
- **目标架构**（汇报口径）：主 Agent + 两个专业 Agent（Experience、Space Execution）+ 共享 Memory + Harness；SpaceMind 为“拟对接能力”，具体接口待官方文档与联调确认。
- **团队约束**：学生团队，出发点是“演示有原型支持、简历有技术可讲”。深度标准：**演示可见、面试可答、代码可指**，够用即停。
- **相关材料**（只读参考，不是执行授权）：`../汇报演示/LivingMind_presentationV1.pdf`（10 页）、`../架构评审/LivingMind-架构评审与迁移步骤-v0.2.md`（架构定稿）、`/Users/macbookair/Documents/Project/KidMind-PPT/AGENT-HANDOFF.md`（汇报材料交接）。

### 0.2 已完成（有代码、有测试、有提交）

| 项 | 内容 | 证据 |
|---|---|---|
| 步骤 0–1 | 仓库骨架、文档基线、Expo SDK 57 App、FastAPI 健康检查、平板配置、可配置后端地址 | `c4e8d9b`、`19599db` |
| 步骤 2 | Pydantic 契约 → OpenAPI → TS 类型自动生成；统一错误格式；两个种子人物偏好不同 | `386bc2e`，`tests/test_contracts.py`、`test_seed.py` |
| 步骤 3 | 可点击原型：人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 动态；平板/手机响应式；前端 Mock 与后端规则一致 | `e8ffb61`，`apps/mobile/tests/` |
| 步骤 4 | 固定规则、统一执行器（白名单、范围、每动作前重查）、有状态虚拟设备、服务状态、幂等确认、停止失效、计划过期、活动记录、PR 模板 + CI | `99b1138`，`tests/test_rest_flow.py`（7 项验收） |
| B | 设备写入移出服务锁；停止可中途抢占慢设备批次（服务层 + HTTP 层测试） | `c639d5d`，`tests/test_concurrency.py` |
| ⑤ | Experience Agent：DeepSeek Provider、Pydantic 输出校验、规则/模型开关、六类失败降级为规则并标注、App 四种来源标签；真实调用已验证（deepseek-flash，2035 ms，单次） | `469dc9a`、`2ad87da`，`tests/test_experience_agent.py`（14 项） |
| 文档 | 本交接文档、README、architecture、acceptance、status、ui-polish；产品界面方向（第 12 节） | `587d7aa`、`8525718`、`c58a29f` |

检查基线：后端 40 项 pytest（Python 3.10/3.11）、前端 12 项测试 + 类型检查、契约一致性、干净副本 CI 模拟、网页版自动点击（平板/手机尺寸；模拟/后端/模型/降级/断网五条路径）。

### 0.3 未完成（按第 8 节顺序）

| 项 | 状态 | 说明 |
|---|---|---|
| A 真机验收 | 未做 | 用户暂无 iPad；所有界面验证来自网页版，不能替代真机 |
| ⑥ 一次事件调整 | 未开始 | 当前任务，要求见第 9 节 |
| ⑥b 对话外壳 | 未开始 | 主页改为对话流，“我的”页（PIN、访客、证据面板） |
| C 视觉整理 | 未开始 | 按 `docs/ui-polish.md` |
| ⑦ 整晚服务 | 未开始 | 可选 |
| ⑧ 主 Agent / 执行 Agent / 记忆 / 能源规则 | 未开始 | 目前只有 Experience Agent 一个真实模块；**“1+2 Agent 编排”尚未实现** |
| ⑨ 补齐四个入口 | 未开始 | 空间、场景页 |
| D 演示打包 | 未开始 | Development Build、录屏、PDF 证据表 |
| GitHub 远程与 CI 实跑 | 未做 | 未经用户授权不建远程 |

### 0.4 评审时最该核对的五个点

1. **声明与实现是否一致**：`docs/status.md` 每一行是否能在代码和测试里找到对应；PDF 第 6 页“1+2 Agent”目前只有 Experience Agent 是真实调用。
2. **来源标注是否可能被混淆**：前端模拟 / 规则 / 模型 / 规则降级 / 虚拟设备在界面和活动记录里是否始终可区分。
3. **安全边界**：所有设备写入是否都经过 `harness/executor.py`；模型输出是否先过 Pydantic 再进执行器；密钥是否只在后端 `.env`。
4. **并发语义**：停止后是否确实不再有新动作；已开始的单个动作不撤销是否可接受。
5. **范围控制**：后续步骤是否仍遵守“一次一步、达到即停”，没有空目录或类名冒充能力。

### 0.5 评审 AI 的复现命令

```bash
cd livingmind-app
git log --oneline                       # 提交按步骤拆分
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest
cd ../apps/mobile && npm install && npm run typecheck && npm test
cd ../.. && ./scripts/gen-api.sh && git diff --exit-code -- packages/api-client
```

评审 AI 只读不改；发现问题写成清单交给用户，不直接修改代码或本文件。

## 1. 接手结论

第一批步骤 0–4、B 并发修正、⑤ Experience Agent（含一次真实 DeepSeek 调用验证）已完成。用户目前没有 iPad，真机验收（A）推迟到有设备时；在此之前继续做后端与接口联动，前端视觉统一留到 C。不要重搭架构，不要复制旧项目覆盖当前仓库，也不要同时开始多个步骤。

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

场景范围只有 Home Living 的“我想休息”。当前没有完整多 Agent、数据库、真实认证、事件触发的持续调整、整晚定时服务、SpaceMind 或真实设备接入。模型调用已用真实 DeepSeek 密钥验证过一次（deepseek-flash，2035 ms）；延迟为单次样本。

## 2. 接手后的必读顺序

0. 第 0 节：背景、已完成/未完成、评审要点（评审 AI 读到这里即可开始）。
1. 本文件其余部分：边界和下一任务。
2. `README.md`：启动方法和三条架构边界。
3. `docs/status.md`：已实现、证据、未实现内容。
4. `docs/acceptance.md`：每阶段达到什么程度就停止。
5. `docs/architecture.md`：当前代码链路和目录职责。
6. 第 12 节：产品界面方向，执行 ⑥b、C、⑨ 前必读。
7. `docs/ui-polish.md`：视觉整理清单，只在执行第 8 节 C 项时使用。
8. 修改 `apps/mobile/` 前阅读 `apps/mobile/AGENTS.md`，并查看其要求的 Expo SDK 57 版本文档。

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
- 规则模式下用户文字只记录，固定规则不会理解任意自然语言；模型模式已验证一次真实调用（见下）。
- 没有真实身份认证、持久化数据库、WebSocket、语音、睡眠传感器或厂商设备。
- 前端 Mock 和后端内存数据互不共享；切换模式应视为不同演示环境。
- 停止不会把灯光、温度、窗帘恢复到执行前状态，这是当前明确语义。

### 并发（B 已修正）

`confirm_plan()` 现在只在锁内做记账，设备批次在锁外执行；guard 在每个动作前于锁内重查 `service.status` 与空间代次。`tests/test_concurrency.py` 用一个会阻塞首个写入的慢设备证明：停止请求立即返回，已开始的动作完成，其余跳过。已开始的那一个动作不会被撤销，这是当前语义。模型调用同样在锁外进行。

### ⑤ 的验证范围

`tests/test_experience_agent.py` 全部使用测试替身。真实调用已由用户在 Mac 上用 `backend/scripts/try_model.py` 验证一次（deepseek-flash，2035 ms，输出合法）。这是单次样本：8 秒目标在 Agent 层满足，但 App 内“提交到显示计划”的端到端计时尚未做，也没有多次调用的延迟分布。密钥只在用户本机 `backend/.env`，仓库和对话中都不应出现。

## 8. 后续执行顺序

一次只做一步，完成验收后停止并报告。字母项是第二批之外必须穿插的工作；⑤–⑨ 沿用架构评审编号。

| 顺序 | 内容 | 达到即停 | 备注 |
|---|---|---|---|
| A 真机验收 | iPad（及安卓平板，如有）用 Expo Go 跑 Mock 与后端两种模式 | 完整流程走通，问题记录到 `docs/status.md` | **推迟**：用户暂无 iPad；有设备时立即补做，期间状态保持“真机未验证” |
| B 并发修正 | 缩短 `confirm_plan` 持锁范围；每次外部写入前按 `serviceId + epoch` 重查；补慢设备/延迟 Adapter 测试 | 停止请求能中途打断慢设备批次 | **已完成**（`c639d5d`） |
| ⑤ 最小 AI 证据 | Experience Agent 一次真实模型调用；规则/模型开关；超时或非法输出降级并标注来源 | 提交到显示计划 8 秒内（待验证目标）；第 9 节测试全部通过 | **已完成**（`469dc9a`）；真实调用已验证 2035 ms（单次） |
| ⑥ 一次事件调整 | 注入一次模拟入睡或室温事件，触发一次调整；验证停止 | 休息 → 事件 → 调整 → 停止；停止后再注入不执行 | 功能底线到此完成 |
| ⑥b 对话外壳 | 按第 12 节把主页改为对话流（计划卡 / 结果卡）；新增“我的”页（人物切换 + 四位 PIN、访客模式、证据面板开关）；“空间”“场景”两页先用现有卡片搭出骨架 | 对话流走通休息 → 确认 → 停止；PIN 与访客模式可用；原始活动只在证据面板出现；测试全部通过 | 只改页面结构与 `services/`，不改后端契约（PIN 与访客上下文除外，需 `gen-api.sh`） |
| C 视觉整理 | 按 `docs/ui-polish.md` 清单美化；只改 `theme/`、`components/`、`features/` | 两种尺寸截图前后对比；测试全部通过；来源标注仍清晰可见 | 放在 ⑥b 之后、演示之前，页面结构此时已稳定 |
| ⑦ 整晚服务 | 模拟时钟、夜间阶段、渐进唤醒；一个 `serviceId` 贯穿整晚 | 定时任务不重复执行；停止取消剩余任务 | 可选，视时间决定 |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源规则及所需 Harness 能力 | 每个模块一条真实工作路径、明确输入输出、调用证据 | 简历可写“多 Agent 编排”的门槛 |
| ⑨ 补齐四个入口 | 按第 12 节完成“空间”“场景”两页（场景库 3 个场景、执行记录、节能档位）；旧 HTML 的页面/组件/交互/数据清单只作参考 | 一页完成、一页验收；场景状态标签与真实实现一致 | 依赖 ⑥、⑧；不迁移旧页面本身 |
| D 演示打包 | Development Build 装到平板；录屏三段（用户触发、事件调整、手动停止）；PDF 主张对证据表 | 每条主张有对应证据；模拟与真实来源分开标注 | 复赛前一周完成 |

两条底线：**功能底线 = A + B + ⑥（含第一批规则链路）；AI 演示底线 = 再加 ⑤。** 产品形态底线 = 再加 ⑥b + C。

不能因为建立了目录或类名，就宣称相应 Agent 已经实现。功能声明必须对应真实调用轨迹和测试。

## 9. 下一位 AI 的当前任务：步骤 ⑥

前置：⑤ 已验证真实调用。

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

满足 `docs/acceptance.md` 中 ⑥；更新 `README.md`、`docs/status.md`、`docs/architecture.md` 和本文件；一次聚焦 commit；报告结果与未验证事项；停止，不进入 ⑥b、⑦ 或 C。

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

> 请先阅读仓库根目录 `AGENT-HANDOFF.md`，然后依次阅读 `README.md`、`docs/status.md`、`docs/acceptance.md`、`docs/architecture.md`。保留现有实现和提交历史，重新运行基线检查。本轮只执行交接文档第 9 节的步骤 ⑥；达到验收条件后更新状态文档、提交一次聚焦 commit 并停止。不要把 Mock、规则降级或测试替身描述成真实模型调用，不要推送、部署或开始步骤 ⑦ 与 C。

## 12. 产品界面方向（用户已确认，2026-09-17）

以下是用户确认的产品形态目标。它决定 ⑥b、C、⑨ 的内容，不改变第 3 节的架构边界，也不提前任何后端步骤。

### 12.1 原则

- 用户默认看到的界面只有动画与交互，不显示 `action_executed` 这类原始活动细节。
- 原始调用轨迹保留在**证据面板**：从“我的”页开关打开，默认关闭。复赛 PDF 第 6 页与评委追问都依赖它，不得删除。
- 视觉目标：动画流畅、有 LivingMind Logo、颜色干净明亮、高端克制；具体清单见 `docs/ui-polish.md`。
- 来源标注（前端模拟 / 规则 / 模型 / 规则降级 / 虚拟设备 / 模拟事件）在产品界面上可以变得含蓄，但不能消失。

### 12.2 四个入口

| 入口 | 内容 | 依赖的后端步骤 |
|---|---|---|
| 对话（主页） | 聊天流：用户一句话 → AI 回复一张**计划卡**（可确认）→ 执行后回一张**结果卡**；停止按钮；语音/打字切换（首版只做打字，语音按钮为占位并标注“后续接入”） | ⑤ 已有；语音 ASR 后置 |
| 空间 | 可控设备状态、当前服务、节能档位 | 已有；节能档位依赖 ⑧ |
| 场景 | 主动服务场景库，每张卡带状态标签；点开看该场景的执行记录（人话，如“22:10 室温升高，空调降到 24°C”） | ⑥ |
| 我的 | 当前人物、个人偏好（只能看到自己的）、切换人物（四位 PIN）、访客模式、证据面板开关 | 已有；偏好编辑依赖 ⑧ |

对话主页只是换了容器：计划、确认、停止、来源标注的逻辑与接口不变。

### 12.3 身份与访客

- “切换人物 + 四位 PIN”是演示用的人物切换，后端仍是演示身份，**不是认证**。PIN 存在后端种子数据里，只用于演示防误切换。
- 没人选择自己时，使用**访客/空间公共上下文**：只用空间默认设置，没有私人偏好，动作需确认后执行。
- 智能音箱接入时一律按访客上下文处理；谁要私人偏好就在平板上选自己。**声纹识别不在范围内**，此决定已确认，不再反复讨论。

### 12.4 场景库首版（3 个）

| 场景 | 状态标签 | 何时可标“已实现” |
|---|---|---|
| 我想休息 | 已实现 | 现在 |
| 室温变化后自动调整 | 规划中 → 已实现 | ⑥ 验收后 |
| 起床渐进唤醒 | 规划中 | ⑦ 验收后 |

场景卡不是写死的“示例”，状态标签必须与真实实现一致；执行记录来自后端活动数据筛选，不得预录。

### 12.5 节能显示的限制

- ⑧ 之前，节能面板只显示“暂无数据”。
- ⑧ 之后，显示“本次计划的功耗档位”与一句可解释原因；**不显示节省百分比或金额**（见第 10 节与设计规范）。


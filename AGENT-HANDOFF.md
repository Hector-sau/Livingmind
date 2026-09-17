# LivingMind AI 交接文档

更新日期：2026-09-17  
仓库位置：`/Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/`  
当前分支：`main`  
第一批实现基线提交：`99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI`  
当前基线：B + ⑤（真实调用已验证）+ R1 + ⑥ + ⑥b + C + ⑧ 补齐模块（1+2 Agent 编排已实现）+ ⑨ 演示打磨 + ⑦ 整晚服务（模拟时钟）+ D 演示打包（云端部分）— 见 `git log`

## 0. 项目背景与现状速览（给评审或新接手的 AI）

### 0.1 背景

- **项目**：LivingMind，参加 SpaceMind AI Agent 创新应用大赛，已进入复赛，需要约 8 分钟汇报 + 可演示原型。对外品牌统一用 LivingMind；历史代码名 KidMind 只在解释旧原型时出现。
- **定位**：家庭住宅（Home Living）为核心场景，酒店（Smart Stay）为延展；两者共享 Energy Intelligence。叙事核心：“一次表达，持续服务；体验是约束，能源是优化”。
- **目标架构**（汇报口径）：主 Agent + 两个专业 Agent（Experience、Space Execution）+ 共享 Memory + Harness；SpaceMind 为“拟对接能力”，具体接口待官方文档与联调确认。
- **团队约束**：学生团队，出发点是“演示有原型支持、简历有技术可讲”。深度标准：**演示可见、面试可答、代码可指**，够用即停。
- **数据约定（用户已确认）**：测试与演示数据用设计的模拟数据即可，重点是讲清方案与验证方法、体现测试意识；数据设计见 `docs/test-data.md`。真实模型的多次统计是可选项。
- **相关材料**（只读参考，不是执行授权）：`../汇报演示/LivingMind_presentationV1.pdf`（10 页）、`../架构评审/LivingMind-架构评审与迁移步骤-v0.2.md`（架构定稿）、`/Users/macbookair/Documents/Project/KidMind-PPT/AGENT-HANDOFF.md`（汇报材料交接）。

### 0.2 已完成（有代码、有测试、有提交）

| 项 | 内容 | 证据 |
|---|---|---|
| 步骤 0–1 | 仓库骨架、文档基线、Expo SDK 57 App、FastAPI 健康检查、平板配置、可配置后端地址 | `c4e8d9b`、`19599db` |
| 步骤 2 | Pydantic 契约 → OpenAPI → TS 类型自动生成；统一错误格式；两个种子人物偏好不同 | `386bc2e`，`tests/test_contracts.py`、`test_seed.py` |
| 步骤 3 | 可点击原型：人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 动态；平板/手机响应式；前端 Mock 与后端规则一致 | `e8ffb61`，`apps/mobile/tests/` |
| 步骤 4 | 固定规则、统一执行器（白名单、范围、每动作前重查）、有状态虚拟设备、服务状态、幂等确认、停止失效、计划过期、活动记录、PR 模板 + CI | `99b1138`，`tests/test_rest_flow.py`（7 项验收） |
| B | 设备写入移出服务锁；停止可中途抢占慢设备批次（服务层 + HTTP 层测试） | `c639d5d`，`tests/test_concurrency.py` |
| ⑤ | Experience Agent：DeepSeek Provider、Pydantic 输出校验、规则/模型开关、六类失败降级为规则并标注、App 四种来源标签；真实调用已验证（deepseek-flash，2035 ms，单次） | `469dc9a`、`2ad87da`，`tests/test_experience_agent.py` |
| R1 评审修正 | 模型偏离上限（后端强制）、兜底异常、App 计划超时联动、过期提示刷新、`demo_reset` 记录、模拟模式措辞、PR 模板 Mock 同步项、`.env` 格式提示、**网页端到端脚本入库**；真实模型端到端脚本（`backend/scripts/e2e_real_model.py`、`run_e2e.py --real-model`） | 见 `git log`，`apps/mobile/e2e/` |
| ⑧ | 主 Agent（规则路由 + 编排 + 协作轨迹）、Space Execution Agent（设备能力、空间规则、指令解析）、人物记忆（本人偏好读取与编辑、空间规则、共享列表不含偏好）、能源智能（舒适范围、分时电价、估算档位、舒适优先 / 节能模式）、Harness 预检；设备指令简化分支；计划卡“查看协作过程” | `backend/tests/test_agents.py`（33 项）、`apps/mobile/tests/agents.test.ts`；端到端 `mock-agents`、`http-agents`、`http-energy-memory` |
| C | 天蓝色明亮主题（用户指定）、LivingMind Logo（头部 / App 图标 / 启动图 / AI 头像）、`@expo/vector-icons` 图标、渐变按钮、柔和阴影、入场 / 呼吸 / 数值条动画（React Native `Animated`，尊重减弱动态效果）、骨架屏 | 端到端 12/12 |
| ⑥b | 四个入口（对话 / 空间 / 场景 / 我的）；对话主页（计划卡、结果卡、系统消息、服务状态条、语音占位）；演示 PIN 切换与访客模式；只显示本人偏好；证据面板；场景库；数据重新设计（3 位成员 + 访客、15 条评测用例） | `tests/test_people_and_scenes.py`、`tests/test_eval_cases.py`、`apps/mobile/tests/conversation.test.ts`；端到端 12 个场景 |
| ⑥ | 模拟室温事件 → 一次自动调整：事件接口、冷却 30 秒、上限 3 次、单服务单调整、停止后忽略、规则调整（±1°C，偏好 ±3°C 内）、模型调整跟随服务模式并受偏离上限约束；App 注入按钮与调整次数；Mock 同步 | `backend/tests/test_events.py`（10 项）；端到端 `mock-event`、`http-event` |
| ⑨ | 一键“准备演示”（重置 → 林悦 · 舒适优先 · 设备 80/26/100 · 清空对话 · 关证据面板 · 回对话页）；“场景”页“1+2 Agent 如何协作”说明卡（有计划时展示真实协作过程）；信息提示 3 秒淡出；空态大图标；README 演示启动命令；`docs/demo-script.md` 3 分钟讲稿 | `apps/mobile/tests/notices.test.ts`；端到端 `http-prepare-demo` |
| ⑦ | 整晚服务：休息计划附带 5 步整晚安排（Space Execution Agent 规则生成、Harness 预检、随计划确认）；模拟时钟推进接口 `POST /api/services/{id}/clock/advance`；每步最多执行一次（锁内认领 + 单服务单推进）；停止取消剩余步骤；最后一步后服务 `completed`；App 运行条“快进 / 自动播放整晚”、计划卡整晚安排、空间页整晚时间线、场景“起床渐进唤醒”改为已实现 | `backend/tests/test_night_service.py`（10 项）、`apps/mobile/tests/night.test.ts`；端到端 `http-night`、`mock-night`、`http-night-stop-phone` |
| D（云端） | 三段网页版录屏脚本（每帧字幕标注来源）；主张证据表生成脚本（23 条，Markdown + PDF）；`eas.json` 开发版配置、`expo-dev-client`、包名、iOS 本地网络设置；平板安装与真机验收清单 | `apps/mobile/e2e/record_demo.py`、`scripts/build_evidence.py`、`docs/evidence.md`、`docs/device-build.md` |
| 文档 | 本交接文档、README、architecture、acceptance、status、ui-polish；产品界面方向（第 12 节） | `587d7aa`、`8525718`、`c58a29f` |

检查基线：后端 106 项 pytest、前端 29 项测试 + 类型检查、契约一致性、干净副本 CI 模拟、网页端到端 19/19（`apps/mobile/e2e/run_e2e.py`，模型路径连本地桩）。

### 0.3 未完成（按第 8 节顺序）

| 项 | 状态 | 说明 |
|---|---|---|
| A 真机验收 | 未做 | 用户暂无 iPad；所有界面验证来自网页版，不能替代真机 |
| 真实模型的多次统计 / 评测集打分 | 可选 | 脚本已入库（`e2e_real_model.py`、`--eval`）；用户确认不作为前提 |
| C 视觉整理 | 已完成 | 未做项见 `docs/ui-polish.md` 顶部 |
| ⑦ 整晚服务 | **已完成** | 模拟时钟，由按钮或自动播放推进；不是真实定时器 |
| ⑧ 主 Agent / 执行 Agent / 记忆 / 能源规则 | **已完成** | 如何如实描述见 0.4 |
| ⑨ 演示打磨 | **已完成** | 旧 HTML 清单未做（用户未提供旧页面） |
| D 演示打包 | **云端部分已完成** | 网页版录屏 3 段、主张证据表（`docs/evidence.md`）、开发版配置与安装说明（`docs/device-build.md`）；EAS 构建与平板录屏待设备 |
| P07 能源仿真证据 | 仓库外 | 汇报第 7 页的规则 vs MATD3 结果不在本仓库，需团队补仿真代码与输出 |
| GitHub 远程与 CI 实跑 | 未做 | 未经用户授权不建远程 |

### 0.4 评审时最该核对的五个点

1. **声明与实现是否一致**：`docs/status.md` 每一行是否能在代码和测试里找到对应。⑧ 之后“1+2 Agent 编排”已实现，如实描述应为：
   - 主 Agent：**规则**路由与编排，记录每一步协作轨迹；
   - Experience Agent：**可调用大模型**（DeepSeek），结构化输出、校验、偏离上限、失败降级；
   - Space Execution Agent：**规则**实现的能力感知动作规划与中文设备指令解析；
   - 共享人物记忆、能源规则（舒适范围内的分时电价建议，负荷为规则估算）、Harness（预检 + 执行前 guard）。
   不要说成“三个大模型 Agent”，也不要把能源规则说成 MATD3 在线控制。
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
# 可选：网页端到端（需 pip install -r apps/mobile/e2e/requirements.txt && python -m playwright install chromium）
python apps/mobile/e2e/run_e2e.py
# 仅在有密钥的机器上：真实模型端到端
cd backend && set -a && source .env && set +a && .venv/bin/python scripts/e2e_real_model.py
```

评审 AI 只读不改；发现问题写成清单交给用户，不直接修改代码或本文件。

## 1. 接手结论

第一批步骤 0–4、B 并发修正、⑤ Experience Agent（含一次真实 DeepSeek 调用验证）、R1 评审修正、⑥ 一次事件调整、⑥b 对话外壳、C 视觉整理、⑧ 补齐模块已完成。用户目前没有 iPad，真机验收（A）推迟到有设备时；在此之前继续做后端与接口联动，前端视觉统一留到 C。不要重搭架构，不要复制旧项目覆盖当前仓库，也不要同时开始多个步骤。

当前产品是一条可工作的纵向链路，规划阶段可选规则或模型：

```text
Expo App：对话 / 空间 / 场景 / 我的（计划来源开关：规则 / 模型；演示 PIN 切换人物或访客）
  → 可切换的前端 Mock / HTTP API
  → FastAPI：POST /api/assistant/messages
  → 主 Agent（规则路由）
      休息请求：人物记忆 → Experience Agent（规则或 DeepSeek，失败降级）→ 能源智能 → Space Execution Agent → Harness 预检
      设备指令：Space Execution Agent 解析 → Harness 预检
      状态查询 / 其他：直接回答
    （只生成计划，不改设备；等待模型时不持锁；计划附协作轨迹）
  → 用户确认
  → 统一执行器（白名单、参数、服务状态检查）
  → 有状态虚拟灯光 / 空调 / 窗帘
  → 状态回读与活动记录
  → App 更新

服务运行中：模拟室温事件 → 检查（服务 / 单调整 / 上限 / 冷却）→ 规划调整（跟随服务模式）
  → 同一执行器 → 回读 → 记录；停止后事件一律忽略
```

场景范围只有 Home Living 的“我想休息”。当前没有数据库、真实认证、真实传感器、整晚定时服务、SpaceMind 或真实设备接入；事件只有模拟室温一种；能源是在线规则，不是 MATD3。模型调用已用真实 DeepSeek 密钥验证过一次（deepseek-flash，2035 ms）；延迟为单次样本。

## 2. 接手后的必读顺序

0. 第 0 节：背景、已完成/未完成、评审要点（评审 AI 读到这里即可开始）。
1. 本文件其余部分：边界和下一任务。
2. `README.md`：启动方法和三条架构边界。
3. `docs/status.md`：已实现、证据、未实现内容。
4. `docs/acceptance.md`：每阶段达到什么程度就停止。
5. `docs/architecture.md`：当前代码链路和目录职责。
6. 第 12 节：产品界面方向，执行 ⑥b、C、⑨ 前必读。
7. `docs/ui-polish.md`：视觉整理清单，执行 C 时必读。
8. `docs/test-data.md`：演示与测试数据的设计。
9. 修改 `apps/mobile/` 前阅读 `apps/mobile/AGENTS.md`，并查看其要求的 Expo SDK 57 版本文档。

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
| R1 评审修正 | 偏离上限、兜底异常、超时联动、端到端脚本入库、真实模型端到端脚本 | `services/planner.py`、`api/errors.py`、`apps/mobile/e2e/`、`backend/scripts/e2e_real_model.py` |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源智能、Harness 预检、协作过程展示、偏好编辑、节能模式 | `backend/app/agents/orchestrator|space_execution/`、`memory/`、`energy/`、`harness/policy.py`；`apps/mobile/features/agents/`、`energy/`、`me/`、`space/` |
| ⑥b 对话外壳 | 四入口外壳、对话流、我的页（PIN / 访客 / 证据面板）、空间与场景简版、演示数据与评测集 | `apps/mobile/features/shell|chat|me|space|scenes/`、`backend/app/demo/seed.py`、`backend/evals/`、`app/agents/experience/evaluation.py` |
| ⑦ 整晚服务 | 整晚安排规则、模拟时钟推进、单次执行、停止取消、服务完成；App 快进与自动播放、整晚时间线 | `backend/app/rules/night_rule.py`、`agents/space_execution/agent.py::night_schedule`、`services/rest_service.py::advance_clock`；`apps/mobile/features/night/` |
| ⑨ 演示打磨 | 准备演示按钮、协作说明卡、提示淡出、空态、演示讲稿 | `apps/mobile/features/shell/AppShell.tsx`、`notices.ts`、`features/scenes/ScenesScreen.tsx`、`components/EmptyState.tsx`、`docs/demo-script.md` |
| ⑥ 一次事件调整 | 事件接口、检查顺序、调整规则、模型调整、App 注入按钮 | `services/rest_service.py::inject_event`、`rules/rest_rule.py::adjustment_rule`、`services/planner.py::plan_adjustment`、`apps/mobile/features/rest/ServiceCard.tsx` |

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
- 模拟事件只作用于正在运行的服务；没有服务、上一次调整未结束、达到 3 次上限、30 秒冷却中都会忽略并写明原因；停止后事件一律忽略。
- 事件调整跟随服务的计划模式；只对有变化的设备生成动作；调整次数在执行前计数。
- 演示 PIN 只防误切换：不签发令牌，后续请求不据此授权，任何接口都不返回 PIN。访客使用空间默认设置。
- 设备指令确认后执行，不创建休息服务；停止服务会让未确认的设备指令失效。
- 共享列表不含任何人的偏好；能源“舒适优先”只建议，“节能模式”才在舒适范围内改设定。

主要接口：

```text
GET  /health
GET  /api/bootstrap
GET  /api/scenes                        # 场景库（状态如实）
POST /api/assistant/messages            # 主 Agent 入口：计划或回答（附协作轨迹）
GET  /api/memory                        # 本人偏好 + 空间规则
PUT  /api/memory/preference             # 编辑本人偏好（访客不可）
PUT  /api/spaces/{spaceId}/energy-mode  # 舒适优先 / 节能模式
POST /api/persons/{personId}/unlock     # 演示 PIN，不是认证
GET  /api/spaces/{spaceId}/devices
POST /api/plans/rest
POST /api/plans/{planId}/confirm
POST /api/services/{serviceId}/stop
POST /api/services/{serviceId}/clock/advance  # 模拟时钟推进整晚安排（minutes 为空 = 下一步）
POST /api/spaces/{spaceId}/events      # 模拟环境事件（source=simulated）
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
python apps/mobile/e2e/run_e2e.py   # 改了界面或流程时
git status --short
```

上一轮记录：后端 96 项测试通过，前端 23 项逻辑测试与类型检查通过，干净副本 CI 模拟通过，网页端到端 15/15。网页版在 1180×820 和 390×844 下完成 Mock / 后端流程；断开后端时错误状态符合预期。接手 AI 不应只引用该记录，改动后必须重新运行相关检查。

## 7. 尚未验证与已知限制

- 尚未在 iPad、Android 平板、手机真机或 iOS 模拟器运行；网页预览不能替代真机验收。
- GitHub CI 尚未真实运行，因为没有远程仓库。
- 规则模式下用户文字只记录，固定规则不会理解任意自然语言；模型模式已验证一次真实调用（见下）。
- 没有真实身份认证、持久化数据库、WebSocket、语音、睡眠传感器或厂商设备。
- 前端 Mock 和后端内存数据互不共享；切换模式应视为不同演示环境。
- 停止不会把灯光、温度、窗帘恢复到执行前状态，这是当前明确语义。
- 计划确认即标 `executed`（已采纳），真实结果看 `results`；同一账户下任何人物都能停止服务（有意设计）。详见 `docs/architecture.md` 关键规则 10–14。
- 模型计划偏离本人偏好超过上限（灯光/窗帘 ±40、空调 ±3°C）会被后端拒绝并降级为规则。
- 网页端到端的模型路径连的是本地桩 `apps/mobile/e2e/fake_deepseek.py`，不是 DeepSeek；CI 目前不跑端到端。
- 事件没有真实传感器：室温由 App 按钮（当前设定 +3°C）或 API 直接给出，界面与记录都标“模拟事件”。
- 语音按钮是占位。Logo 为 PNG（来自旧 PPT 品牌目录，用户已同意使用），正式发布前需 SVG 母版与商标检索。
- 对话记录只在前端内存，刷新即清空。
- 主 Agent 路由与指令解析是规则；能源负荷是规则估算；室外温度与电价时段是模拟值（`LIVINGMIND_DEMO_LOCAL_HOUR` 可固定演示时段）。
- 偏好编辑与节能模式只在内存中，重置或重启即恢复。

### 并发（B 已修正）

`confirm_plan()` 现在只在锁内做记账，设备批次在锁外执行；guard 在每个动作前于锁内重查 `service.status` 与空间代次。`tests/test_concurrency.py` 用一个会阻塞首个写入的慢设备证明：停止请求立即返回，已开始的动作完成，其余跳过。已开始的那一个动作不会被撤销，这是当前语义。模型调用同样在锁外进行。

### ⑤ 的验证范围

`tests/test_experience_agent.py` 全部使用测试替身。真实调用已由用户在 Mac 上用 `backend/scripts/try_model.py` 验证一次（deepseek-flash，2035 ms，输出合法）。这是单次样本：8 秒目标在 Agent 层满足。多次统计、评测集打分与端到端计时的脚本已入库（`backend/scripts/e2e_real_model.py [--eval]`、`apps/mobile/e2e/run_e2e.py --real-model`），已用本地桩空跑通过；用户确认这些是**可选项**。注意：开发用的云端环境和 Mac 上的沙箱都无法访问 `api.deepseek.com`，真实模型只能在用户 Mac 的终端里跑。密钥只在用户本机 `backend/.env`，仓库和对话中都不应出现。

## 8. 后续执行顺序

一次只做一步，完成验收后停止并报告。字母项是第二批之外必须穿插的工作；⑤–⑨ 沿用架构评审编号。

| 顺序 | 内容 | 达到即停 | 备注 |
|---|---|---|---|
| A 真机验收 | iPad（及安卓平板，如有）用 Expo Go 跑 Mock 与后端两种模式 | 完整流程走通，问题记录到 `docs/status.md` | **推迟**：用户暂无 iPad；有设备时立即补做，期间状态保持“真机未验证” |
| B 并发修正 | 缩短 `confirm_plan` 持锁范围；每次外部写入前按 `serviceId + epoch` 重查；补慢设备/延迟 Adapter 测试 | 停止请求能中途打断慢设备批次 | **已完成**（`c639d5d`） |
| ⑤ 最小 AI 证据 | Experience Agent 一次真实模型调用；规则/模型开关；超时或非法输出降级并标注来源 | 提交到显示计划 8 秒内（待验证目标）；第 9 节测试全部通过 | **已完成**（`469dc9a`）；真实调用已验证 2035 ms（单次） |
| ⑥ 一次事件调整 | 注入一次模拟入睡或室温事件，触发一次调整；验证停止 | 休息 → 事件 → 调整 → 停止；停止后再注入不执行 | **已完成**；功能底线（除真机 A 外）已达成 |
| ⑥b 对话外壳 | **已完成**。按第 12 节把主页改为对话流（计划卡 / 结果卡）；新增“我的”页（人物切换 + 四位 PIN、访客模式、证据面板开关）；“空间”“场景”两页先用现有卡片搭出骨架 | 对话流走通休息 → 确认 → 停止；PIN 与访客模式可用；原始活动只在证据面板出现；测试全部通过 | 只改页面结构与 `services/`，不改后端契约（PIN 与访客上下文除外，需 `gen-api.sh`） |
| C 视觉整理 | 按 `docs/ui-polish.md` 清单美化；只改 `theme/`、`components/`、`features/` | 两种尺寸截图前后对比；测试全部通过；来源标注仍清晰可见 | **已完成**（天蓝色主题） |
| ⑦ 整晚服务 | 模拟时钟、夜间阶段、渐进唤醒；一个 `serviceId` 贯穿整晚 | 定时任务不重复执行；停止取消剩余任务 | **已完成**（模拟时钟；见 `docs/architecture.md` 规则 25–30） |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源规则及所需 Harness 能力 | 每个模块一条真实工作路径、明确输入输出、调用证据 | **已完成**；如实描述见 0.4 |
| ⑨ 补齐入口细节 | 演示脚本化与稳定性（一键演示数据、固定演示时段）、空态插画与提示淡出、“场景”页展示 1+2 Agent 场景卡；旧 HTML 清单只作参考 | 一页完成、一页验收；场景状态标签与真实实现一致 | **已完成**；旧 HTML 清单待用户提供旧页面 |
| D 演示打包 | Development Build 装到平板；录屏三段（用户触发、事件调整、手动停止）；PDF 主张对证据表 | 每条主张有对应证据；模拟与真实来源分开标注 | **云端部分已完成**：`e2e/record_demo.py`、`scripts/build_evidence.py`、`docs/device-build.md`；平板构建待设备 |

两条底线：**功能底线 = A + B + ⑥（含第一批规则链路）；AI 演示底线 = 再加 ⑤。** 产品形态底线 = 再加 ⑥b + C（已达成）。**“1+2 Agent 已实现”底线 = ⑧（已达成）。**

不能因为建立了目录或类名，就宣称相应 Agent 已经实现。功能声明必须对应真实调用轨迹和测试。

## 9. 下一位 AI 的当前任务：A 真机验收 + D 的设备部分（需要用户的平板）

前置：⑦、⑧、⑨ 与 D 的云端部分已完成。**不再新增后端能力。** 开始前先问用户手上有哪种平板、是否有 Expo 账号 / Apple 开发者账号。

### 有平板时

- 按 `docs/device-build.md` 先用 Expo Go 跑通，再做 EAS 开发版（Android 出 APK；iPad 需登记设备）。
- 逐项完成 `docs/device-build.md` 的真机验收清单，结果写进 `docs/status.md`（通过、问题、截图位置）。
- 按 `docs/demo-script.md` 在平板上录屏（屏幕录制），替换或补充网页版录屏；在 `scripts/build_evidence.py` 里把“平板 App”一行改为实际状态并重新生成。

### 没有平板时可做

- 团队提供 P07 能源仿真的代码与输出后，在 `scripts/build_evidence.py` 里补登证据（不要改成“已实现”，写“仿真，另一个项目”）。
- 用户提供旧 HTML 前端后，只列清单，不迁移代码。

### 停止条件

更新 `README.md`、`docs/status.md` 和本文件；一次聚焦 commit；停止并按第 11 节报告。

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

> 请先阅读仓库根目录 `AGENT-HANDOFF.md`，然后依次阅读 `README.md`、`docs/status.md`、`docs/acceptance.md`、`docs/architecture.md`。保留现有实现和提交历史，重新运行基线检查。先问用户手上有哪种平板和账号，再做 A 真机验收与 D 的设备部分；没有平板时只做第 9 节列出的补登工作；只执行选定的一步，达到验收条件后更新状态文档、提交一次聚焦 commit 并停止。描述能力时遵守 0.4 的如实口径；不要去掉来源标注，不要推送或部署。

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

**⑥b 已实现上述四个入口的骨架；⑧ 补上了节能与偏好编辑**（语音仍为占位）。

### 12.3 身份与访客

- “切换人物 + 四位 PIN”是演示用的人物切换，后端仍是演示身份，**不是认证**。PIN 存在后端种子数据里，只用于演示防误切换。
- 没人选择自己时，使用**访客/空间公共上下文**：只用空间默认设置，没有私人偏好，动作需确认后执行。
- 智能音箱接入时一律按访客上下文处理；谁要私人偏好就在平板上选自己。**声纹识别不在范围内**，此决定已确认，不再反复讨论。

### 12.4 场景库首版（3 个）

| 场景 | 状态标签 | 何时可标“已实现” |
|---|---|---|
| 我想休息 | 已实现 | 现在 |
| 室温变化后自动调整 | 已实现（网页与测试验证，真机未验证） | ⑥ 已完成 |
| 起床渐进唤醒 | 已实现（模拟时钟，网页与测试验证，真机未验证） | ⑦ 已完成 |

场景卡不是写死的“示例”，状态标签必须与真实实现一致；执行记录来自后端活动数据筛选，不得预录。

### 12.5 节能显示的限制

- ⑧ 已实现：计划卡与“空间”页显示能源建议、估算负荷档位（标注“规则估算，非实测”）与原因；可切换舒适优先 / 节能模式。
- **不显示节省百分比或金额**（见第 10 节与设计规范）。


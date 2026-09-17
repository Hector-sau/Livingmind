# 实现状态

更新：2026-09-17 · 第一批（步骤 0–4）完成；B 并发修正完成；⑤ Experience Agent **已完成并验证真实调用**（2026-09-17 在用户 Mac 上运行 `scripts/try_model.py`，deepseek-flash，2035 ms）。评审修正 R1 完成；⑥ 一次事件调整完成；⑥b 对话外壳完成；C 视觉整理完成；⑧ 补齐模块完成（1+2 Agent 编排已实现）。⑨ 演示打磨完成；⑦ 整晚服务完成（模拟时钟）。D 演示打包的云端部分完成（网页版录屏、主张证据表、开发版构建配置）；平板构建与真机录屏待有设备后做。真机验收仍未做。

## 已实现

| 能力 | 位置 | 证据 |
|---|---|---|
| 实施基线文档 | `README.md`、`docs/` | — |
| Expo App 骨架（平板横竖屏、可配置后端地址） | `apps/mobile/app.json`、`config.ts` | `tests/config.test.ts` |
| FastAPI 骨架 + 健康检查 | `backend/app/main.py`、`api/health.py` | `tests/test_health.py` |
| 数据契约 + 统一错误格式 | `backend/app/contracts/`、`api/errors.py` | `tests/test_contracts.py` |
| 契约生成前端类型 | `scripts/gen-api.sh` → `packages/api-client/` | CI `contracts` 任务 |
| 种子人物（2 人偏好不同）、演示账户 | `backend/app/demo/seed.py` | `tests/test_seed.py` |
| 可点击原型：人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 服务动态 | `apps/mobile/features/` | 浏览器自动点击（见下） |
| 前端模拟接口（与后端规则一致，标注“前端模拟”） | `apps/mobile/services/mock/` | `tests/mockApi.test.ts` |
| 真实 API 客户端（断网/超时明确报错，不回退模拟） | `apps/mobile/services/http/` | `tests/httpApi.test.ts` |
| 固定休息规则（无模型） | `backend/app/rules/rest_rule.py` | `tests/test_rest_flow.py` |
| 统一执行器：白名单、参数范围、每个动作前检查服务、回读 | `backend/app/harness/executor.py` | 同上 |
| 有状态虚拟设备（灯光、空调、窗帘） | `backend/app/adapters/virtual/devices.py` | 同上 |
| 服务状态、确认幂等、单空间单服务、停止失效、计划过期 | `backend/app/services/rest_service.py` | 同上 |
| 活动记录（按实际发生写入，标注来源） | 同上 | 同上 |
| PR 模板 + CI（后端测试、契约一致性、前端类型检查与测试） | `.github/` | 尚未在 GitHub 上运行（没有远程仓库） |
| B：设备写入在服务锁外执行；停止可中途抢占慢设备批次 | `backend/app/services/rest_service.py`、`adapters/virtual/devices.py` | `tests/test_concurrency.py`（服务层 + HTTP 线程池各一） |
| ⑤：Experience Agent（提示词、Pydantic 输出校验、DeepSeek Provider） | `backend/app/agents/experience/` | `tests/test_experience_agent.py`（14 项，用测试替身，不调 DeepSeek） |
| ⑤：规则/模型切换、降级为规则并标注原因、延迟记录 | `backend/app/services/planner.py`、`rules/rest_rule.py` | 同上；本地 HTTP 桩验证了真实 HTTP 路径与 2 秒超时降级 |
| ⑤：App 计划来源开关、四种来源标签、降级原因、模型/延迟信息 | `apps/mobile/features/rest/ModeToggle.tsx`、`PlanCard.tsx` | 网页端到端 `http-model-paths`、`mock-model-fallback` |
| R1：模型计划偏离上限（灯光/窗帘 ±40、空调 ±3°C），超出降级 | `backend/app/services/planner.py` | `tests/test_experience_agent.py`（超限 3 例 + 恰好在上限 1 例）；网页端到端 |
| R1：兜底异常 → `INTERNAL_ERROR`，不泄露细节 | `backend/app/api/errors.py` | `tests/test_rest_flow.py` |
| R1：App 计划请求超时 = 后端模型超时 + 3 秒 | `apps/mobile/services/http/httpApi.ts` | `tests/httpApi.test.ts` |
| R1：计划过期提示每 15 秒重新计算；模拟模式措辞修正；重置写入 `demo_reset` | `features/rest/useRestFlow.ts`、`ModeToggle.tsx`、`rest_service.py`、`mockApi.ts` | 前后端测试 |
| R1：网页端到端脚本入库（7 个场景，一条命令） | `apps/mobile/e2e/` | `python apps/mobile/e2e/run_e2e.py`：7/7 通过 |
| ⑥：模拟室温事件接口 `POST /api/spaces/{spaceId}/events`；冷却 30 秒、上限 3 次、单服务单调整、停止后忽略；规则调整（±1°C，不超出偏好 ±3°C）；模型调整跟随服务模式并受偏离上限约束 | `backend/app/services/rest_service.py`、`services/planner.py`、`rules/rest_rule.py` | `tests/test_events.py`（10 项，含停止与调整并发） |
| ⑥：App“注入模拟事件”按钮、调整次数、事件结果提示、服务动态中的事件记录；前端 Mock 同步规则 | `apps/mobile/features/rest/ServiceCard.tsx`、`services/mock/mockApi.ts` | `tests/mockApi.test.ts`；端到端 `mock-event`、`http-event` |
| ⑥b：四个入口（对话 / 空间 / 场景 / 我的）；对话主页（计划卡、结果卡、系统消息、服务状态条、快捷语、语音占位）；平板左栏 + 右侧房间面板，手机底部标签栏 | `apps/mobile/features/shell/`、`chat/` | `tests/conversation.test.ts`；端到端全部场景已改为走对话 |
| ⑥b：演示 PIN 切换人物（`POST /api/persons/{id}/unlock`，不是认证）、访客模式（空间默认设置）、只显示本人偏好、证据面板开关 | `backend/app/services/rest_service.py`、`apps/mobile/features/me/` | `tests/test_people_and_scenes.py`；端到端 `*-pin-evidence`、`http-guest-scenes` |
| ⑥b：场景库（`GET /api/scenes`，状态如实）与人话时间线 | `backend/app/demo/seed.py`、`apps/mobile/features/scenes/` | `test_scene_library_status_is_honest`；`tests/conversation.test.ts` |
| ⑥b：演示与测试数据重新设计（3 位成员 + 访客、场景库、事件序列、15 条 Experience Agent 评测用例与打分） | `backend/app/demo/seed.py`、`backend/evals/`、`docs/test-data.md` | `tests/test_eval_cases.py` |
| C：天蓝色明亮主题、LivingMind Logo（头部、App 图标、启动图、AI 头像）、统一图标、渐变按钮、柔和阴影、入场/呼吸/数值条动画（尊重减弱动态效果）、骨架屏 | `apps/mobile/theme/`、`components/`、`features/**`、`assets/` | 端到端 12/12（C 当时）；截图见 `apps/mobile/e2e/.out/screens/`（本地生成，不入库） |
| ⑧：主 Agent（规则路由 + 编排 + 协作轨迹）；完整分支 记忆 → Experience → 能源 → Space Execution → Harness；简化分支（设备指令）；状态查询与范围外回答 | `backend/app/agents/orchestrator/`、`POST /api/assistant/messages` | `tests/test_agents.py`；端到端 `mock-agents`、`http-agents` |
| ⑧：Space Execution Agent（设备能力、夜间灯光上限、动作生成、中文设备指令解析） | `backend/app/agents/space_execution/` | 同上（解析 6 例、能力缺失、规则限幅） |
| ⑧：人物记忆（本人偏好读取与编辑、空间规则；共享列表不含偏好） | `backend/app/memory/`、`GET /api/memory`、`PUT /api/memory/preference`；“我的”页编辑 | 同上；端到端 `http-energy-memory` |
| ⑧：能源智能（舒适范围、分时电价、估算负荷档位、舒适优先 / 节能模式） | `backend/app/energy/`、`PUT /api/spaces/{id}/energy-mode`；计划卡与空间页 | 同上 |
| ⑧：Harness 规划预检；协作过程展示（计划卡“查看协作过程”） | `backend/app/harness/policy.py`、`apps/mobile/features/agents/TraceView.tsx` | 同上 |
| ⑨：一键“准备演示”（重置数据 → 林悦 · 舒适优先 · 设备初始 80/26/100 · 清空对话 · 关闭证据面板 · 回到对话页） | `apps/mobile/features/shell/AppShell.tsx`、`features/me/MeScreen.tsx`、`useRestFlow.resetDemo` | 端到端 `http-prepare-demo` |
| ⑨：“场景”页“1+2 Agent 如何协作”说明卡（措辞与交接文档 0.4 一致；有计划时展示真实协作过程，否则引导去对话） | `apps/mobile/features/scenes/ScenesScreen.tsx` | 同上 |
| ⑨：信息类提示 3 秒自动淡出（警告、错误常驻）；空态改为大图标 + 引导语（对话、服务、设备、证据、场景时间线） | `features/shell/notices.ts`、`components/EmptyState.tsx` | `tests/notices.test.ts`；端到端 `http-prepare-demo` |
| ⑨：3 分钟演示讲稿 | `docs/demo-script.md` | — |
| ⑦：整晚安排（5 步：23:00 关灯、01:00 空调 +1°C、06:30 / 06:45 / 07:00 三步唤醒），Space Execution Agent 规则生成、Harness 预检、随休息计划确认 | `backend/app/rules/night_rule.py`、`agents/space_execution/agent.py` | `tests/test_night_service.py` |
| ⑦：模拟时钟推进 `POST /api/services/{id}/clock/advance`；锁内认领保证每步只执行一次；单服务单推进；停止取消剩余步骤；最后一步后服务 `completed` | `backend/app/services/rest_service.py::advance_clock` | 同上（10 项，含并发推进、推进中停止）；前端 Mock 同步 `tests/night.test.ts` |
| ⑦：App 运行条“快进 / 自动播放整晚”、计划卡整晚安排、空间页整晚时间线、对话系统消息；场景“起床渐进唤醒”改为已实现；场景时间线按触发来源归类动作 | `apps/mobile/features/night/`、`features/chat/ServiceStrip.tsx`、`features/scenes/timeline.ts` | 端到端 `http-night`、`mock-night`、`http-night-stop-phone`；`tests/conversation.test.ts` |
| D：三段网页版演示录屏（字幕标注网页版 / 虚拟设备 / 规则模式） | `apps/mobile/e2e/record_demo.py` | 已生成 `01-user-trigger`、`02-event-adjust`、`03-night-stop`（mp4，不入库；已放到用户 Mac 的 `Livingmind/演示打包/`） |
| D：汇报主张与证据对照表（23 条，逐条写明原型实际情况、证据、来源类型） | `scripts/build_evidence.py` → `docs/evidence.md`、PDF | 路径逐一核对存在；PDF 4 页 |
| D：平板安装说明与开发版配置（`eas.json`、`expo-dev-client`、包名 `com.livingmind.demo`、iOS 本地网络设置） | `docs/device-build.md`、`apps/mobile/eas.json`、`app.json` | **未实际构建**；网页端到端 19/19 在加入依赖后重跑通过 |
| 真实模型端到端脚本（后端：5 句话 → 计划 → 确认 → 回读 → 停止，延迟统计；浏览器：`--real-model`） | `backend/scripts/e2e_real_model.py`（含 `--eval`）、`apps/mobile/e2e/run_e2e.py --real-model` | 已用本地桩空跑通过；真实模型运行为**可选项**（开发环境无法访问 api.deepseek.com，需在用户 Mac 终端运行） |

## 步骤 4 的 7 项验证

| # | 内容 | 结果 |
|---|---|---|
| 1 | 创建计划不改变设备 | 自动化测试通过 |
| 2 | 确认后后端状态改变，App 能读回 | 自动化测试 + 浏览器点击（后端模式）通过 |
| 3 | A/B 人物计划不同 | 自动化测试 + 浏览器点击通过 |
| 4 | 重复确认不重复执行 | 自动化测试通过 |
| 5 | 停止后旧请求不再产生动作 | 自动化测试通过。B 之后：停止能在慢设备写入进行中立即返回，已开始的动作完成、其余跳过（`tests/test_concurrency.py`） |
| 6 | 非法人物 / 空间 / 账户 / 参数 / 过期 / 版本不符被拒绝 | 自动化测试通过 |
| 7 | 后端断开时 App 明确反馈 | 前端单元测试 + 端到端场景 `http-offline`（关掉后端后点确认，出现“无法连接后端，显示的状态可能已过期”，设备数值变灰，没有假装成功） |

浏览器端到端：`apps/mobile/e2e/run_e2e.py`（已入库，可复现）。用 Expo 网页导出，在 1180×820 和 390×844 两种尺寸下跑前端模拟与后端两种模式的完整流程，外加模型计划、超时降级、偏离降级、模拟模式降级、断网反馈，共 19 个场景（对话操作；含 PIN、证据面板、访客、场景库、1+2 Agent 协作、设备指令、节能模式、偏好编辑、准备演示、整晚服务），最近一次 19/19 通过，无页面错误。模型路径连的是本地桩，不是 DeepSeek。

## ⑤ 的验证情况

| 要求 | 结果 |
|---|---|
| 合法模型输出 → 计划，创建阶段不改设备 | 测试通过 |
| 模型计划确认后经同一执行器并回读 | 测试通过 |
| 模型超时 → 规则降级并标注 | 测试通过；本地 HTTP 桩 + 2 秒超时实测降级 2.07 秒 |
| 非法 JSON、越界、未知字段不能绕过校验 | 6 种输入参数化测试通过；另有偏离上限 4 例 |
| A/B 人物提示词各用自己的偏好 | 测试通过 |
| 规则模式完全不请求模型 | 测试通过 |
| 模型失败不影响停止、重复确认、过期 | 测试通过 |
| 日志与错误不含 API key | 测试通过 |
| **真实 DeepSeek 调用与 8 秒目标** | **Agent 层已验证**（用户 Mac，2026-09-17）：`deepseek-flash`，Agent 一次调用 **2035 ms**，输出通过结构校验（灯光 15%、空调 24°C、窗帘 0%，理由引用了“有点热”并相对基线下调 1°C）。单次样本。多次统计与评测集打分是可选项（脚本已就绪），汇报时引用单次结果并说明 |

本地 HTTP 桩只用于验证请求格式（`/chat/completions`、Bearer 头、`response_format: json_object`）、响应解析和超时路径，**不代表已连通 DeepSeek**。

## 未验证 / 限制

- **未在 iPad、安卓平板或手机真机上运行**，也未在 iOS 模拟器上运行；上面的界面验证来自网页版（react-native-web），真机效果需要团队用 Expo Go 确认。
- 数据全部在内存中，后端重启即重置。
- 身份只是演示账户，没有正式认证；后端不要部署到公网。
- 设备全部是虚拟的，不代表真实硬件接入。
- 模拟事件没有真实传感器；室温数值由按钮或 API 直接给出。
- 整晚服务跑在模拟时钟上，由按钮或“自动播放”（每 2.5 秒推进一步）驱动；后端没有真实定时器，也不读真实时间。
- 演示 PIN 不是认证；“我的”页上直接写出了演示 PIN，便于评审操作。
- 语音按钮是占位，点击只提示“后续接入”。
- Logo 来自 `KidMind-PPT/output/brand/livingmind-logo-primary-v2.png`（用户已同意在 App 中使用），为 PNG；正式发布前按品牌说明补 SVG 母版与商标检索。
- 所有人物、偏好、评测用例、室外温度与电价时段都是设计的模拟数据（见 `docs/test-data.md`）。
- 主 Agent 路由与 Space Execution Agent 的指令解析是规则实现；只有 Experience Agent 可调用模型。
- 能源负荷是规则估算，不是实测，也不代表节省比例。
- 演示身份下，谁能读哪份记忆由请求上下文决定，不是认证。
- 规则模式下输入文字只记录，不做语义理解。模型模式已验证一次真实调用；延迟只有单次样本。
- CI 配置写好了，但还没有在 GitHub 上跑过。

## 未开始

A 真机验收（有 iPad 时） · D 的设备部分（EAS 开发版构建、平板录屏） · P07 能源仿真证据补登（需团队提供仿真代码与输出） · 旧 HTML 前端清单（用户尚未提供旧文件）

## 下一步接口

- 下一步见 `AGENT-HANDOFF.md` 第 9 节。
- 若以后换成真实定时器：由定时器调用 `advance_clock`，认领与守卫逻辑不变。

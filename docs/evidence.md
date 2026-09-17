# 汇报主张与证据对照表

对照材料：`汇报演示/LivingMind_presentationV1（10 页）`。更新：2026-09-17。由 `scripts/build_evidence.py` 生成，改表请改脚本。

状态统计：已实现 10，部分实现 6，未接入 1，未实现 1，仓库外 1，外部数据 2，待验证 1，计划 1。

| 页 | 主张 | 状态 | 原型实际情况 | 证据 | 来源标注 |
|---|---|---|---|---|---|
| P01 | 面向居住空间的主动体验 Agent：持续理解居住者，主动组织空间服务 | 部分实现 | 家庭卧室原型：一句话 → 计划 → 确认 → 室温事件调整 → 整晚服务。“持续理解”目前是读取本人偏好，不从行为中学习 | backend/app/services/rest_service.py；录屏 01–03；网页端到端 19/19 | 后端规则 · 虚拟设备 · 模拟事件 / 时钟 |
| P01 / P03 | Home Living 为核心，Smart Stay 为延展 | 部分实现 | 只实现家庭场景：1 个空间（家 · 主卧），3 位成员 + 访客；酒店场景没有实现 | backend/app/demo/seed.py；docs/test-data.md | 设计的模拟数据 |
| P02 | 79% 重视互操作性；45% 仍主要用独立 App 控制设备 | 外部数据 | 只用于说明需求背景，不是原型证据 | 幻灯片标注：Deloitte 2023 Connected Consumer Study | 外部数据 |
| P03 | 同一条服务闭环：理解 → 规划 → 执行 → 反馈 → 调整 | 已实现（家庭） | 主 Agent 编排并记录协作过程；执行后回读设备；室温事件触发重新规划 | backend/app/agents/orchestrator/agent.py；tests/test_agents.py（33 项）；tests/test_events.py（10 项） | 后端规则（模型可选） |
| P03 | 多成员偏好 | 已实现 | 3 位成员偏好不同，同一句话得到不同计划；每人只能看到自己的偏好；访客不读取任何人的偏好 | backend/app/memory/service.py；tests/test_people_and_scenes.py（5 项）；端到端 *-pin-evidence、http-guest-scenes | 设计的模拟数据；演示 PIN 不是认证 |
| P03 | 用户信任与控制权 | 已实现 | 先确认后执行；随时可停止；停止后旧计划失效；重复确认不会重复执行 | backend/app/services/rest_service.py；tests/test_rest_flow.py（17 项） | 后端规则 |
| P04 | 一句话形成方案：柔和灯光、关闭窗帘、舒适温控、勿扰设置 | 部分实现 | 灯光、窗帘、空调已实现（家庭场景）；勿扰设置没有实现 | backend/app/rules/rest_rule.py；backend/app/agents/space_execution/agent.py；录屏 01 | 虚拟设备 |
| P04 | 状态变化后主动调整：室温变化 → 重新规划 → 调整空调 | 已实现 | 冷却 30 秒、最多 3 次、同一服务同时只有一个调整、不超出本人偏好 ±3°C、停止后忽略 | rest_service.py::inject_event；tests/test_events.py（10 项）；端到端 mock-event、http-event；录屏 02 | 模拟事件（没有真实传感器） |
| P04 | 体验确定舒适边界，能源策略在边界内选择运行方式 | 已实现（规则） | 舒适范围 = 体验目标 ±1°C；高峰电价时建议空调提高 0.5°C；“舒适优先”只建议，“节能模式”才应用 | backend/app/energy/rules.py；tests/test_agents.py；端到端 http-energy-memory | 规则估算，非实测；不显示节省比例或金额 |
| P05 | 拟接入 SpaceMind：任务路由、设备能力映射、权限、空间感知、结果回读、协议连接 | 未接入 | 幻灯片已注明尚未接入。原型里的本地对应：设备能力列表、执行器白名单与参数范围、写入后回读、演示上下文校验 | backend/app/adapters/virtual/devices.py；backend/app/harness/executor.py | 虚拟设备；接口待官方文档与联调 |
| P05 | Zigbee、Matter、Apple Home 等协议与平台 | 未实现 | 生态关系示意 | — | 示意 |
| P06 | 目标架构 1+2：一个主 Agent，两个专业 Agent | 已实现 | 主 Agent：规则路由与编排；Experience Agent：可调用大模型；Space Execution Agent：规则（设备能力、空间规则、指令解析、整晚安排）。不是三个大模型 Agent | backend/app/agents/；tests/test_agents.py（33 项）；tests/test_experience_agent.py（20 项）；“场景”页说明卡 | 只有 Experience Agent 调用模型 |
| P06 | Experience Agent 生成体验目标 | 已实现；真实调用验证 1 次 | 2026-09-17 在团队 Mac 上运行 scripts/try_model.py 成功（deepseek-flash，2035 ms，单次）。未配置、超时、网络、HTTP、非法 JSON、结构不符、超出偏离上限都会降级为规则并写明原因 | backend/app/services/planner.py；tests/test_experience_agent.py（测试替身）；端到端 http-model-paths（本地模型桩） | 真实模型仅单次样本；其余为测试替身 / 模型桩 |
| P06 | Context / Memory：当前情境 + 已授权偏好 + 历史反馈 | 部分实现 | 当前设备状态、本人偏好（可在“我的”页编辑）、空间规则已实现；历史反馈没有实现 | backend/app/memory/service.py；端到端 http-energy-memory | 设计的模拟数据 |
| P06 | Harness：权限、执行约束与异常处理 | 已实现（演示级） | 白名单与参数范围；每个动作前重查服务状态与代次；设备写入在锁外，停止可中途打断；统一错误格式。权限是演示上下文校验，不是登录认证 | backend/app/harness/；tests/test_concurrency.py（2 项）；tests/test_rest_flow.py | 后端规则 |
| P06 | 已支持空间设备虚拟执行与状态获取 | 已实现 | 有状态虚拟设备（灯光、空调、窗帘），写入后回读，版本号递增 | backend/app/adapters/virtual/devices.py；录屏 01 | 虚拟设备，不代表真实硬件 |
| P06 | 读取执行结果，基于结果重规划 | 部分实现 | 室温事件后的重新规划已实现；设备动作失败后的自动重规划没有实现（只记录并提示） | tests/test_events.py | 模拟事件 |
| 补充 | 一次表达，持续服务：整晚服务 | 已实现 | 一个服务贯穿整晚：23:00 关灯、01:00 空调调高 1°C、06:30–07:00 三步唤醒；每步只执行一次；停止取消剩余步骤；07:00 后服务结束 | rest_service.py::advance_clock；tests/test_night_service.py（10 项，含并发）；端到端 http-night、mock-night、http-night-stop-phone；录屏 03 | 模拟时钟（按钮或自动播放推进） |
| P07 | 24 小时家庭并网仿真：规则策略与 MATD3 对比；净运行成本 -$0.02；舒适违规 0 / 0 | 仓库外 | 本 App 仓库不包含这项仿真。App 里的能源模块是分时电价规则，不是 MATD3 | 待团队提供仿真代码、配置与输出文件后补登 | 仿真（幻灯片已注明单日、不外推） |
| P08 | 49.45% 消费者已使用智能家居；65% 酒店提及劳动力成本压力 | 外部数据 | 只用于说明市场背景，不证明付费意愿 | 幻灯片标注的来源（2025 年中国消费者数据；AHLA 2026，n=246） | 外部数据 |
| P08 | 一套能力，两种商业路径；拟收费单位 | 待验证 | 幻灯片已标“待验证” | — | 商业假设 |
| P10 | 下一步：官方接口联调、家庭样板、酒店试点、规模化推广 | 计划 | 尚未开始 | — | 计划 |
| 补充 | 平板 App | 部分实现 | Expo 应用，平板横竖屏布局；所有界面验证来自网页版；尚未在 iPad 或安卓平板上运行；开发版构建配置已入库 | apps/mobile/；docs/device-build.md | 网页版验证 |

## 录屏（网页版，`apps/mobile/e2e/record_demo.py` 生成）

| 文件 | 时长 | 内容 |
|---|---|---|
| 01-user-trigger.mp4 | 约 20 秒 | “我想休息” → 计划卡（协作过程、整晚安排）→ 确认 → 设备变化 |
| 02-event-adjust.mp4 | 约 23 秒 | 开始服务 → 模拟室温升高 3°C → 自动调整一次 → 冷却中再次触发被忽略 → 场景时间线 |
| 03-night-stop.mp4 | 约 47 秒 | 快进到 23:00 → 自动播放到 07:00，服务结束 → 空间页时间线 → 新的一晚执行一步后手动停止 |

每一帧顶部都有字幕：网页版录屏 · 后端虚拟设备 · 规则模式。不是平板真机录屏。

## 自动检查

| 检查 | 结果 | 位置 |
|---|---|---|
| 后端 pytest | 106 项 | backend/tests/ |
| 前端逻辑测试 + 类型检查 | 29 项 | apps/mobile/tests/ |
| 网页端到端（平板 / 手机尺寸，前端模拟与后端两种模式） | 19 个场景 | apps/mobile/e2e/run_e2e.py |
| 契约一致性（后端模型 → 前端类型） | 通过 | scripts/gen-api.sh |
| 干净副本 CI 模拟 | 通过 | .github/workflows/ |

## 来源标注说明

| 标注 | 含义 |
|---|---|
| 后端规则 | 后端固定规则生成，没有调用模型 |
| 真实模型 | DeepSeek 真实调用；目前只有 1 次成功样本（2035 ms） |
| 测试替身 / 模型桩 | 自动化测试里代替模型的本地程序，不是真实调用 |
| 虚拟设备 | 后端内存里的有状态设备，不代表真实硬件 |
| 模拟事件 / 模拟时钟 | 室温由按钮或接口给出；整晚时间由按钮推进，不是真实时间 |
| 设计的模拟数据 | 人物、偏好、室外温度、电价时段、评测用例都是设计的 |
| 网页版验证 | 界面测试和录屏来自 Expo 网页导出，不等于平板真机 |

## 使用建议

- 汇报时说“已实现”的，只用状态为“已实现”的行；“部分实现”要同时说清缺的部分。
- P07 的仿真结果需要团队补上仿真代码和输出文件，否则被问到时只能说明“在另一个仿真项目中完成，本原型未包含”。
- 外部数据只用于背景，不要用来证明 LivingMind 的效果或付费意愿。

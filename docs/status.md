# 实现状态

更新：2026-09-17 · 第一批（步骤 0–4）完成；B 并发修正完成；⑤ Experience Agent **已完成并验证真实调用**（2026-09-17 在用户 Mac 上运行 `scripts/try_model.py`，deepseek-flash，2035 ms）。评审修正 R1 完成。⑥ 起未开始。真机验收仍未做。

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
| 真实模型端到端脚本（后端：5 句话 → 计划 → 确认 → 回读 → 停止，延迟统计；浏览器：`--real-model`） | `backend/scripts/e2e_real_model.py`、`apps/mobile/e2e/run_e2e.py` | 已用本地桩空跑通过；**真实 DeepSeek 结果待用户在 Mac 上运行**（开发环境与 Mac 内的沙箱都无法访问 api.deepseek.com） |

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

浏览器端到端：`apps/mobile/e2e/run_e2e.py`（已入库，可复现）。用 Expo 网页导出，在 1180×820 和 390×844 两种尺寸下跑前端模拟与后端两种模式的完整流程，外加模型计划、超时降级、偏离降级、模拟模式降级、断网反馈，共 7 个场景，最近一次 7/7 通过，无页面错误。模型路径连的是本地桩，不是 DeepSeek。

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
| **真实 DeepSeek 调用与 8 秒目标** | **Agent 层已验证**（用户 Mac，2026-09-17）：`deepseek-flash`，Agent 一次调用 **2035 ms**，输出通过结构校验（灯光 15%、空调 24°C、窗帘 0%，理由引用了“有点热”并相对基线下调 1°C）。单次样本。多次统计与“提交到显示计划”的端到端计时，用 `scripts/e2e_real_model.py` 和 `run_e2e.py --real-model` 在 Mac 上测，结果待填 |

本地 HTTP 桩只用于验证请求格式（`/chat/completions`、Bearer 头、`response_format: json_object`）、响应解析和超时路径，**不代表已连通 DeepSeek**。

## 未验证 / 限制

- **未在 iPad、安卓平板或手机真机上运行**，也未在 iOS 模拟器上运行；上面的界面验证来自网页版（react-native-web），真机效果需要团队用 Expo Go 确认。
- 数据全部在内存中，后端重启即重置。
- 身份只是演示账户，没有正式认证；后端不要部署到公网。
- 设备全部是虚拟的，不代表真实硬件接入。
- 规则模式下输入文字只记录，不做语义理解。模型模式已验证一次真实调用；延迟只有单次样本。
- CI 配置写好了，但还没有在 GitHub 上跑过。

## 未开始

⑥ 一次事件调整 · C 视觉整理 · ⑦ 整晚服务 · ⑧ 主 Agent / 执行 Agent / 记忆 / 能源 · ⑨ 逐页迁移旧页面 · D 演示打包 · A 真机验收（有 iPad 时）

## 下一步接口

- ⑥：新增事件入口（如 `POST /api/spaces/{spaceId}/events`，来源标 `simulated`），调用 `RestService` 的重规划方法：检查服务 active、冷却时间、代次，再走 `Planner` → `_execute`（复用 guard 与 epoch）。事件类型先只做室温变化一种。
- 前端 ⑥：加“注入模拟事件”按钮和动态里的事件记录；不做视觉调整（留给 C）。

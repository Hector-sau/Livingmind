# 实现状态

更新：2026-09-17 · 第一批（步骤 0–4）完成，等待验收。第二批未开始。

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

## 步骤 4 的 7 项验证

| # | 内容 | 结果 |
|---|---|---|
| 1 | 创建计划不改变设备 | 自动化测试通过 |
| 2 | 确认后后端状态改变，App 能读回 | 自动化测试 + 浏览器点击（后端模式）通过 |
| 3 | A/B 人物计划不同 | 自动化测试 + 浏览器点击通过 |
| 4 | 重复确认不重复执行 | 自动化测试通过 |
| 5 | 停止后旧请求不再产生动作 | 自动化测试通过（含“执行中途停止，剩余动作跳过”） |
| 6 | 非法人物 / 空间 / 账户 / 参数 / 过期 / 版本不符被拒绝 | 自动化测试通过 |
| 7 | 后端断开时 App 明确反馈 | 前端单元测试 + 浏览器实测（关掉后端后点确认，出现“无法连接后端，显示的状态可能已过期”，设备数值变灰，没有假装成功） |

浏览器点击测试：用 Expo 导出的网页版，在 1180×820（平板横屏）和 390×844（手机竖屏）两种尺寸下，分别在前端模拟模式和后端模式跑完整流程，无控制台错误。

## 未验证 / 限制

- **未在 iPad、安卓平板或手机真机上运行**，也未在 iOS 模拟器上运行；上面的界面验证来自网页版（react-native-web），真机效果需要团队用 Expo Go 确认。
- 数据全部在内存中，后端重启即重置。
- 身份只是演示账户，没有正式认证；后端不要部署到公网。
- 设备全部是虚拟的，不代表真实硬件接入。
- 输入文字只记录，不做语义理解；计划来自固定规则，没有调用模型。
- CI 配置写好了，但还没有在 GitHub 上跑过。

## 未开始（第二批）

⑤ Experience Agent 真实模型调用 · ⑥ 一次事件调整 · ⑦ 整晚服务 · ⑧ 主 Agent / 执行 Agent / 记忆 / 能源 · ⑨ 逐页迁移旧页面

## 下一步接口

- 第二批 ⑤：在 `backend/app/agents/experience/` 生成 `Plan`（`source` 增加 `"model"`），仍交给 `harness/executor.py` 执行；前端 `PLAN_SOURCE_LABEL` 增加对应标签。
- 第二批 ⑥：事件入口调用 `RestService` 的新方法，复用 `_execute` 的 guard 与 epoch 检查。

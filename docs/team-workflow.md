# 团队协作工作流

这个仓库目前只有本地 Git，没有远程地址。建立 GitHub 仓库后，由项目负责人添加 `origin` 并推送；不要让自动化 Agent 自行创建公开仓库、推送或配置密钥。

## 模块边界

| 模块 | 可改范围 | 不可绕过的边界 |
|---|---|---|
| App 页面与体验 | `apps/mobile/features/`、`components/`、`theme/` | 页面只能调用 `services/`，不能直接修改设备状态 |
| App API / Mock | `apps/mobile/services/` | Mock 必须标注 `frontend_mock`，与后端可见规则保持一致 |
| API 契约 | `backend/app/contracts/`、`packages/api-client/` | 改契约后必须运行 `./scripts/gen-api.sh`；不得手改生成文件 |
| Agent / 业务服务 | `backend/app/agents/`、`services/`、`memory/`、`energy/` | Agent 只生成计划；所有写设备动作必须通过 Harness executor |
| 设备与接入 | `backend/app/adapters/`、`harness/` | 新厂商实现 `DeviceAdapter`，不允许页面或 Agent 绕过白名单、范围校验与回读 |
| 离线能源证据 | `simulation/home-energy/`、`backend/app/energy/simulation.py` | 只能读取给定结果；不写成实时控制、已重训或多智能体协作 |
| 文档与演示 | `docs/`、`AGENT-HANDOFF.md`、`README.md` | 每一项“已实现”必须有真实调用路径和测试 / 录屏证据 |

## 一项工作的最小交付

1. 只改一个模块边界内的内容；不要顺手重构无关目录。
2. 有 API 契约改动：生成类型，并提交生成的 `packages/api-client` 变更。
3. 补或更新最小测试，覆盖成功路径和一个失败 / 边界路径。
4. 运行与改动相称的检查：后端 `pytest`；前端 `npm run typecheck && npm test`；改界面或流程时再跑 `python e2e/run_e2e.py`。
5. 更新 `docs/status.md` 与 `AGENT-HANDOFF.md` 的完成度、限制和下一步；再创建一个聚焦提交。

## 合并前清单

```bash
./scripts/gen-api.sh                 # 改过 contracts 时
cd backend && pytest -q -p no:cacheprovider
cd ../apps/mobile && npm run typecheck && npm test
git status --short
```

GitHub CI 需要远程仓库才会实际运行；在此之前，上述本地检查才是当前的验收依据。

## 真实接入的后续顺序

1. 保持 App 请求不变，增加一个 `DeviceAdapter` 实现并先用集成测试验证写入 / 回读。
2. 让语音网关把转写结果转换为既有 assistant-message 请求；不要引入独立的设备控制旁路。
3. 真实定时器仅调用既有服务层，不复制夜间计划或执行器逻辑。
4. 真实身份、持久化和厂商凭据进入单独的安全评审；当前演示账户不得上线公网。

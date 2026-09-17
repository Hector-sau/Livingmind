## 做了什么

<!-- 一两句话。对应哪个步骤（例如：第二批 ⑤）？ -->

## 怎么验证

- [ ] `cd backend && pytest`
- [ ] `cd apps/mobile && npm run typecheck && npm test`
- [ ] 改了后端契约：已运行 `./scripts/gen-api.sh` 并提交生成文件
- [ ] 界面改动：附截图或录屏（平板横屏 + 手机竖屏）；可用 `python apps/mobile/e2e/run_e2e.py` 生成

## 边界自查

- [ ] 页面没有直接改设备状态（只经过 `services/`）
- [ ] 设备写入都经过执行器
- [ ] 改了后端业务规则（幂等、代次、过期、降级、偏离上限等）：前端 Mock（`apps/mobile/services/mock/`）与 `tests/mockApi.test.ts` 已同步
- [ ] 模拟 / 规则 / 模型调用在界面和记录里有明确标注
- [ ] 没有提交密钥、`.env`、`node_modules`、`.venv`
- [ ] `docs/status.md` 已更新（新增或完成的能力）

## 未验证 / 仍是模拟

<!-- 如实写。没有就写“无”。 -->

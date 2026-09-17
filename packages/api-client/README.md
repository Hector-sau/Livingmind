# @livingmind/api-client

由后端 Pydantic 契约生成的 TypeScript 类型。

- `openapi.json`：`backend/scripts/export_openapi.py` 导出，**不要手改**。
- `src/schema.ts`：`openapi-typescript` 生成，**不要手改**。
- `src/index.ts`：给 App 用的类型别名，可以手改（只放类型）。

重新生成：在仓库根目录运行 `./scripts/gen-api.sh`。CI 会重新生成并检查是否与提交内容一致。

说明：HTTP 调用代码目前放在 `apps/mobile/services/http/`，本包只提供类型，避免额外的打包配置。

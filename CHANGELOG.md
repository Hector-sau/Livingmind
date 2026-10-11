# Changelog

## [1.0.0] — 2026-10-11

First versioned source and demonstration release of LivingMind.

首个正式源码与演示版本。该版本集中发布既有工程成果，不新增真实硬件接入，也不改变核心业务流程。

### Product

- React Native / Expo 平板优先客户端，支持手机布局、对话、设备、场景和人物入口。
- 休息计划、用户确认、虚拟设备执行与回读、模拟入睡、环境调整、渐进唤醒和停止闭环。
- 人物偏好隔离、会话澄清、设备手动控制、短时撤销、动作历史与结果核对。
- 语音回合、播报与打断，以及尚待真机验收的设备端识别适配。

### Engineering

- 混合式 1+2 Agent；DeepSeek 结构化体验规划、规则降级、LangGraph 规划分支与 checkpoint。
- 模型规划与设备副作用分离；策略校验、有界授权、统一执行器、动作身份、回执与状态回读。
- PostgreSQL 持久化、并发约束与执行所有权，Redis 锁与冷却协调。
- 持久化 HTTP 虚拟网关；未知动作由后台 Worker 查询原回执，不盲目重新发送设备指令。
- PostgreSQL Transactional Outbox、事件重试、去重与按空间保序；未使用 Kafka。
- Docker Compose、数据库迁移、OpenAPI 生成前端契约、自动化后端/前端/浏览器回归。

### Energy

- 保留独立的固定 24 小时家庭能源仿真、MATD3 框架单智能体权重、给定结果和来源记录。
- App 只读展示离线结果；在线能源建议仍使用可解释规则，不执行强化学习模型。

### Release packaging

- 客户端、API 和契约包版本统一为 1.0.0。
- 增加正式发布说明、版本历史和归档过滤规则；交接文件及历史报告不进入整理后的源码发行包。
- 发行范围为本机/可信局域网中的可复现工程原型；未提供 APK / IPA、SpaceMind 实际联调或生产安全认证。

[1.0.0]: https://github.com/Hector-sau/Livingmind/releases/tag/v1.0.0

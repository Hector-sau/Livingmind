# 移动端依赖风险与处理记录

检查日期：2026-10-03。这是当前锁文件与上游公告的核对，不是安全认证。没有执行 `npm audit fix --force`，没有降级 Expo 或 React Native。

**One root advisory is fixed; two remain unresolved.**

原报告有 23 个受影响包，来自 3 个根公告。此次修复 `xcode → uuid` 后，复查剩余 16 个 high、0 个 moderate，来自另外 2 个根公告。受影响包数量包含依赖链传播，不能写成“修了 7 个独立漏洞”。原始对照保存在 `docs/evidence/npm-audit-2026-10-03.json` 与 `npm-audit-after-uuid-2026-10-03.json`。

## 已处理的 uuid

公告涉及 v3/v5/v6 方法指定输出 buffer 时缺少边界检查，11.1.1 列为修复版本。[上游公告](https://github.com/advisories/GHSA-w5hq-g745-h8pq)

本项目 `xcode@3.0.1` 在 `lib/pbxProject.js` 通过 CommonJS 调用 `uuid.v4()` 生成工程 ID，未在这个调用点使用上述方法或外部 buffer。仍通过局部 override 将该依赖锁到保留 CommonJS 导出的 11.1.1，不直接换到仅因版本号更大而选的版本。

`apps/mobile/tests/buildDependencies.test.ts` 验证实际 xcode 模块能加载、生成 100 个不重复的 24 位大写十六进制 ID，并检查解析到的 uuid 版本。前端类型、完整逻辑测试、iOS/Android JS/Hermes 导出也已通过；这些不代替 Xcode 原生编译或真机验收。后续升级 xcode 后，应检查是否能移除 override。

## 尚未解决的两项

| 根依赖 | 当前锁定与上游信息 | 本项目中的路径与判断 | 当前约束 |
|---|---|---|---|
| braces | 3.0.3；公告截至本次检查没有 patched version | Metro 文件匹配链使用 micromatch/braces，深度嵌套模式可能耗尽调用栈。没有证明来自 App 用户话术的可达路径，也没有完成所有构建输入审计 | 仅对可信项目与构建配置运行 Metro，不开放公共开发服务；等待兼容补丁并重新检查 |
| node-forge | 1.4.0；公告截至本次检查没有 patched version | Expo CLI / code-signing-certificates 涉及证书与签名；代码中存在 certificate.verify、publicKey.verify、csr.verify。不能因为属于工具链就断言不可达 | 不接收不可信签名/证书/构建项目，不将此原型当作已经完成生产 OTA 签名安全验收 |

上游依据：[braces 公告](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)、[node-forge 公告](https://github.com/advisories/GHSA-86w9-cpqp-85rv)。npm 的修复建议会把 Expo 退回 44、React Native 退回 0.72，不能直接当成可兼容解决方案。这里没有自行修改第三方密码学实现，也没有压制 audit 输出来换取“零漏洞”。

## 下一次怎样检查

1. 在 `apps/mobile/` 运行 `npm audit --json`，保存新的日期版本，不覆盖历史记录。
2. 核对公告 patched versions、npm 发布版本和 Expo 兼容要求；优先上游兼容更新。
3. 检查实际调用点和参数来源。可达性是要证明的事情，不是按 dependencies/devDependencies 标签猜测。
4. 修改锁文件后执行 `npm ci`、类型、逻辑测试、导出和浏览器回归；涉及原生构建工具时补 development build。

简历可讲“定位依赖风险、做兼容性修补和回归”，不能写“全部依赖漏洞已修复”。

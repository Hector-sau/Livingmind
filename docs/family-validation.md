# 家庭晚间模拟 · Validation notes

家庭模拟的设备写入、回读和故障注入均发生在虚拟网关。可选模型的解析约束使用替身验证。以下检查覆盖日常操作、浏览器表现、型号属性和本机进程恢复。真实硬件、家庭麦克风识别率和住户满意度仍需实测。

## 核对家庭行为、型号与恢复

从仓库根目录运行。下列 Python 用例使用标准库，SQLite 和 HTTP 用例会创建临时数据库、进程与回环端口。

```sh
(cd backend && PYTHONPATH=.:tests python3 -B -m unittest -v \
  test_family_evening test_family_execution test_family_storage \
  test_family_gateway_contract test_family_profile test_family_miot_spec)
node --test scripts/family_voice.test.cjs
```

| 场景 | 可以核对的结果 |
| --- | --- |
| 学习和观影同时发生 | 成员偏好与所在房间共同决定建议。重复信号、免打扰、临时例外与次日到期都有可重放用例。[家庭行为测试](../backend/tests/test_family_evening.py) |
| 加载两份型号属性 | 书桌灯绑定 `yeelink.light.lamp4` 的亮度，循环扇绑定 `dmaker.fan.p5` 的枚举档位。从初始状态确认学习建议，虚拟设备分别回读 75% 和 1 档。测试另行检查不支持的枚举值。[型号配置](../backend/examples/family-miot-two-models.json) · [型号测试](../backend/tests/test_family_miot_spec.py) |
| 确认中的设备回读被暂停 | 独立的状态读取可以看见已处理动作数及已提交回执。浏览器测试在第一次动作上暂停虚拟网关，直到发起端和观察端均显示 0/3，放行后观察端自动看到最终回执。打开编辑器时，后台刷新暂停并保留输入。[执行测试](../backend/tests/test_family_execution.py) · [双屏浏览器测试](../scripts/family-ui-regression.cjs) |
| 多进程同时确认同一建议 | 首个 HTTP 进程退出后，两个使用同一 SQLite 文件的本机服务器恢复同一条待确认建议。并发确认产生一次新结果与一次重放，两次返回相同的原始回执。[SQLite 与 HTTP 测试](../backend/tests/test_family_storage.py) |
| 设备动作处理中终止写入进程 | 到家方案的第一项灯光已确认，第二项窗帘正在执行，第三项空调尚未下发。恢复后逐项状态为 `confirmed`、`unknown`、`skipped`。重试同一确认返回这组三项原结果，写入日志没有第二次下发窗帘或补发空调。[中断与重放测试](../backend/tests/test_family_storage.py) |
| 转写尚未完成或切换说话人 | 语音适配使用模拟浏览器回调覆盖权限、打断和迟到结果。真实 Chromium 流程验证临时“确认”不能提交，切换人物会清空草稿。公开样本的声纹比对有独立实验。[语音接口测试](../scripts/family_voice.test.cjs) · [说话人实验](family-voice.md) |

要在界面重现型号示例，使用 [README 中的双型号启动命令](../README.md#运行模拟-app)。`--state-db` 和 `--miot-profile` 都是可选参数；恢复同一个数据库时须沿用原设备配置。上述故障恢复证据适用于同一台电脑上的 SQLite 和模拟设备。

## 核对视口

| 视口 | 布局 | 导出的单屏图像 |
| --- | --- | --- |
| 手机 390 × 844，3× | 一列服务流、底部导航、家庭成员纵向排列 | 1170 × 2532 |
| 手机 375 × 812，3× | 同一路径检查横向溢出、触控和滚动 | 验证，无单独发行图 |
| iPad 竖屏 820 × 1180，2× | 上下排列空间与建议，设备继续向下滚动 | 1640 × 2360 |
| 大屏 iPad 竖屏 1024 × 1366，2× | 触控设备保持上下排列，检查空间图与建议卡的实际位置 | 验证，无单独发行图 |
| iPad 横屏 1180 × 820，2× | 侧栏导航，空间与建议并排 | 2360 × 1640 |

视口单位为 CSS 像素，对应模拟设备的逻辑显示尺寸。原图固定截取单个视口，未使用整页长截图。脚本断言横向页面宽度、DPR 以及核心操作至少约 44 CSS px 的高度，并通过触摸完成确认与回执查看。

## 复现浏览器操作和媒体

QA 脚本使用 Node.js 和锁定版本的 Playwright。在仓库根目录执行下列命令安装测试依赖与 Chromium。

```sh
npm ci --prefix scripts
(cd scripts && npx --no-install playwright install chromium)
```

可用 `PLAYWRIGHT_MODULE` 指定已安装的模块入口，`CHROMIUM_PATH` 指定兼容的本地 Chromium。脚本每次创建独立的回环服务器与家庭状态，退出时关闭。浏览日常演示不需要这些录制依赖。

```sh
node scripts/family-ui-regression.cjs
node scripts/family-film/capture.cjs /tmp/livingmind-qa
node scripts/family-film/viewports.cjs /tmp/livingmind-screens
```

制作无声影片需要支持 H.264 与 GIF 编码的 FFmpeg、Python Pillow，以及可显示中文的字体。在 Linux 上，将 `CAPTION_FONT` 设为已安装的中文 TrueType 或 TTC 字体的完整路径，例如安装 Noto CJK 后可用 `fc-match -f '%{file}' 'Noto Sans CJK SC'` 查询。先用 `--film` 录制真实浏览器操作，再运行 `render`，合成底部中文说明和穿插在录屏中的架构图解、源码片段。

```sh
node scripts/family-film/capture.cjs /tmp/livingmind-film --film
python3 scripts/family-film/finish.py render /tmp/livingmind-film --media docs/media
node scripts/family-film/viewports.cjs docs/media
ffprobe -v error -select_streams v -show_entries stream=codec_name -of csv=p=0 docs/media/family-evening.mp4
ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 docs/media/family-evening.mp4
```

两条 `ffprobe` 命令分别检查视频流与音频流。第一条应输出一行 `h264`，第二条应为空。MP4 还含章节数据。打开展示页后，可从「架构章节」分别跳到规划、确认和回执图解，每个跳转取自随影片发布的 WebVTT。逐幕对照 App 的实际读数，可以检查修改后是否只执行所选设备，以及缺失回执是否保留为未知。[分镜文字稿](family-film.md) · [操作场景](../scripts/family-film/story.json)

独立展示页可直接用浏览器打开，也可作为静态站点展示影片与各设备原图。交互模拟 App 由 Python 服务提供。[展示页](index.html)

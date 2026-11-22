# Family evening simulator · 家庭晚间模拟 API

Run the App and its local API together from the repository root. Python 3.9+ is sufficient.

在仓库根目录运行下列命令，然后打开终端显示的本机地址。前端请求这个 Python 服务，刷新页面仍可看到同一次模拟。默认仅监听本机的 8765 端口。

```sh
python3 backend/family_demo.py
```

FastAPI also mounts the family API at `/api/family`, with interactive documentation at `/api/family/docs`. Both servers support an in-memory demo by default and an optional persistent household on one machine.

两个入口都可以用 `LIVINGMIND_FAMILY_STATE_DB` 指向同一份本地 SQLite 文件。标准库入口另提供 `--state-db`。默认内存模式下每个进程有独立家庭，重启恢复初始场景。

## Restartable household · 可恢复的家庭会话

```sh
python3 backend/family_demo.py --state-db /tmp/livingmind-review.sqlite3 \
  --miot-profile backend/examples/family-miot-two-models.json
```

Use the same file and profile after a restart. A second server on the same machine can share the household by adding `--port 8766` to the same command. The sample uses a temporary directory. Choose a persistent local folder to keep the household across system cleanups.

重启服务时使用相同的数据库路径和设备配置。另一终端在同一命令上加 `--port 8766` 即可让第二个本机进程看到同一家庭。数据库保存建议版本、当晚例外、模拟时钟、去重索引、设备值及回执。同目录的 `.writer.sqlite3` 用于协调写操作。运行中请保留两份文件。在 App 中选择“重置演示”会重置共享家庭。

During confirmation, `GET /state` returns a committed view with `lastOutcome: "executing"` and `execution` containing `suggestionId`, `memberId`, `completedActions` and `totalActions`. Other mutations are serialized. When all actions reach an outcome, `execution` becomes `null`.

确认时，系统先保存动作意图，再交给网关，每收到一份回执就保存进度。写进程退出后，下一次读取或写入会尝试接管。已完成的动作保留原回执，可能已经发出的动作标为 `unknown`，尚未发送的动作为 `skipped`。重试同一建议会拿到原结果。进度与回执仍可在另一常亮页面查看。可见页面默认约每 2.5 秒读取快照，编辑或语音弹窗打开时会保留用户草稿。[跨进程验证](../backend/tests/test_family_storage.py) · [执行测试](../backend/tests/test_family_execution.py)

## Routes · 请求

All successful responses return a complete state snapshot. All POST bodies are JSON objects. Error responses contain `error.code` and `error.message`.

每次成功调用都返回完整快照。字段包括家庭成员、空间、设备、待确认建议、当天时刻、最近一批执行结果，以及从新到旧的活动记录。成员选择是演示上下文，适用于本机家庭演示。

| Method | Path under `/api/family` | Body / behavior |
|---|---|---|
| GET | `/state` | Read the current household. 查看状态。 |
| POST | `/events` | Supply `eventId`, `type` and `memberId`. Types: `arrival`, `study`, `tv`, `sleep`, `unknown_arrival`. Identity may be omitted for `unknown_arrival`. Optional `source` identifies the panel (`simulated`), typed input (`resident-input`), sample transcript (`simulated-transcript`) or browser recognition (`browser-asr`). 学习默认在书房，也可传 `roomId: "living"`。 |
| POST | `/decision` | Supply current `suggestionId`, selected `memberId` and `decision`. Choose `confirm`, `edit`, `dismiss`, `snooze` (30 simulated minutes) or `mute` (tonight). 决策必须匹配建议所属成员。 |
| POST | `/devices` | Supply `deviceId` and `mode` (`online`, `offline`, `unknown`). Inject a virtual connection condition. |
| POST | `/next-day` | `{}` begins the next evening at 18:25. Clear tonight’s exceptions, silence settings and open proposal. Keep device values, connection conditions, preferences and history. |
| POST | `/reset` | `{}` restores every fixture and clears history. |

A unique event advances simulated time by five minutes. A duplicate ID with the same payload produces no second proposal or log entry. Reusing that ID with a different event returns 409. A real activity change can invalidate the previous proposal. A no-op signal from another member preserves a still-valid pending plan. Confirmations serialize device actions per household, expose partial progress to readers, and preserve the original outcome on retry. Matching device settings produce no extra action when the virtual readback is current. Terminal decisions include an immutable `decisionResult` with `suggestionId`, `memberId`, `decision`, `outcome` and per-action `receipts`. A retry sets `decisionReplayed` to true. The top-level snapshot still describes the household at response time.

每个新信号推进五分钟。重复信号不推进时间。下一条明确身份的活动会撤下已经过时的建议。建议在确认前不会写设备。跨到午夜会进入下一天的傍晚；也可用“下一晚”直接观察临时设置到期。

## Evening walkthrough · 可复现的一晚

Send the events in order, confirming each proposal before sending the next event.

按顺序注入事件，每步先确认，再推进到下一幕。以下动作均可在虚拟回读中核对。

| Type / member | Result from the fresh fixtures · 初始数据下的结果 |
|---|---|
| `arrival` / `mother` | Living light 45%, curtain opening 45%, AC 25°C. 妈妈到家后先看到建议。 |
| `study` / `child` | Desk lamp 75%, study fan level 1. 此时只需调整书房。若爸爸已开始观影且音量过高，学习建议也会包含客厅音量调整。 |
| `tv` / `father` | Living light 20%, volume 18%. 孩子正在学习，音量从独处观影目标 35% 限到 18%。 |
| `sleep` / `mother` | Bed light 8%, bedroom curtain closed, living volume 12%. 方案说明会降低客厅音量，确认后才执行。书桌保持 75%。 |

For a shared-room conflict, reset, send `study` with `memberId: "child"` and `roomId: "living"`, confirm, then send `tv` for `father`. The room light stays at 75%. Only the capped speaker volume is proposed.

让孩子先在客厅读书，再让爸爸在客厅观影，能看到系统保留共享灯光。身份不明的到家信号只记日志，不生成个性化建议。

## Tonight’s exception · 今晚的修改

```json
{"memberId":"mother","suggestionId":"use-current-id","decision":"edit","text":"我今晚还要看书，客厅亮一点，卧室先别动"}
```

From the initial 0% reading, this phrase proposes 65%. When the light is already at 80%, it proposes 90%. An unknown reading requires an explicit target before a relative adjustment can be proposed. “今晚只开客厅灯，空调先别开” retains only the proposed light target. “今晚只调客厅灯到 35%” specifies a numeric target. A structured alternative uses `onlyDeviceId` and optional `value`. Both forms may narrow the current proposal. An edit returns a new suggestion ID, and confirmation must use that new ID.

这里的语言理解来自有限规则。没理解的指令返回 `NOT_UNDERSTOOD`，未获支持的单位、设备和数值也会被拒绝。设备维持原值。以“这次”开头的修改只作用于当前计划；“今晚”的要求经确认才成为该成员在当晚该场景的约束。结构化编辑可指定 `scope` 为 `once` 或 `tonight`。家庭成员的长期偏好保持原值，下一晚按原偏好重新规划。

## MIoT mapping · 能力与回读

The default fixture maps eight virtual device instances to a room, a property, its access flags, range and step. Each `sim-*` device identifier and its instance numbers belong to this demonstration. A real product supplies its own IDs, supported properties and ranges. [Xiaomi MIoT Spec](https://iot.mi.com/v2/new/doc/introduction/knowledge/spec)

模拟设备包含客厅灯、客厅空调、客厅窗帘、客厅音箱、书桌灯、书房循环扇、床头灯和卧室窗帘。当前执行链没有厂商账号、实际网络传输或物理设备。真实接入还需由桥接层负责授权、发现设备并导入相应型号的属性能力。

```json
{
  "propertyRequest": {"did":"sim-living-light","siid":2,"piid":2,"value":35},
  "writeReply":      {"did":"sim-living-light","siid":2,"piid":2,"code":0},
  "readReply":       {"did":"sim-living-light","siid":2,"piid":2,"value":35,"code":0}
}
```

The execution layer checks readability of the returned address/value and agreement with the target. In the `unknown` fixture the write is acknowledged while the observation is missing. The result stays unknown and retains the last observed value. Offline skips the write. Duplicate action IDs return their prior receipt.

### 可替换的属性传输与离线地址映射

`MiotPropertyGateway(devices, transport)` 接收能力描述和属性传输对象。`write_property(packet)` 接收含目标值的属性请求，`read_property(address)` 读取刚写入的属性。两者各返回一条带地址、结果码的标准化回包。网关检查地址、回读值和动作编号。传输异常或回读缺失时，原动作保留待核对状态。同一网关实例收到相同动作编号时复用原回执。注入适配器的用法见[网关契约测试](../backend/tests/test_family_gateway_contract.py)。

在仓库根目录运行以下命令，可以用自选属性编号跑完整 App。示例只覆盖客厅灯与客厅窗帘的地址，其余设备沿用默认配置。两个入口也都接受环境变量 `LIVINGMIND_FAMILY_MIOT_PROFILE` 指向同一文件。地址配置在启动时校验，重置演示时保留。此模式继续使用内存传输，设备读数均为模拟值。[示例配置](../backend/examples/family-miot-profile.json)

```sh
python3 backend/family_demo.py --miot-profile backend/examples/family-miot-profile.json
```

模拟“妈妈到家”并确认后，`POST /api/family/decision` 返回的 `decisionResult.receipts` 中，客厅灯写入应为 `{"did":"demo-lamp-01","siid":3,"piid":7,"value":45}`，该灯回读为 45。请求只改变本地模拟家庭。连接真实环境还需要账户授权或已授权桥接、设备及型号发现、型号能力映射与真实传输。[功能清单与架构评审](family-architecture-review.md)

体验规则依据成员偏好和家人活动提出目标。空间执行规则检查设备是否具备可写属性、合法范围以及是否需要调整。主 Agent 处理身份、免打扰、建议有效性和用户确认。三个角色都使用确定性规则，可从 `plannerSource: "rule"`、建议轨迹和分设备结果中核对。

### Public model examples · 两份真实型号规范的离线用法

The example embeds selected properties from two public registry instances. Startup reads the local JSON. The imported metadata is visible in `devices[].modelSpec` and the bound control property in `devices[].capability`. The DIDs in this example address virtual devices.

选择“孩子学习”并确认，打开“设备执行回执”，展开每台设备的“设备协议详情”。演示配置中书桌灯从 20% 调到 75%，循环扇从 2 档调到 1 档。回执可查看型号、DID、SIID/PIID 及实际写入和读取的返回码。读写校验同时检查数值步长、离散枚举和设备访问权限，`notify` 表示型号声明的通知能力。观测值来自虚拟传输。[离线配置](../backend/examples/family-miot-two-models.json) · [导入器](../backend/app/family/miot_spec.py)

| Model / 型号 | 绑定的可写属性 | 演示回读 |
| --- | --- | --- |
| `yeelink.light.lamp4` | 书桌灯亮度，`siid=2, piid=2`，1–100%，步长 1 | 75% |
| `dmaker.fan.p5` | 书房风扇档位，`siid=2, piid=4`，允许 1、2、3、4 | 1 档 |

型号资料包含只读字段和带离散值的属性。家庭场景绑定其中的数值控制项。真实设备的上电状态、发现、账号授权与通知订阅仍需单独联调。小米官方集成的解析器使用相同的规范注册表。[台灯规范](https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:light:0000A001:yeelink-lamp4:1) · [风扇规范](https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:fan:0000A005:dmaker-p5:1) · [官方解析器](https://github.com/XiaoMi/ha_xiaomi_home/blob/main/custom_components/xiaomi_home/miot/miot_spec.py)

## Regression checks · 回归

```sh
cd backend
python3 -B -m unittest discover -s tests -p test_family_evening.py -v
```

Cases cover independent member preferences, co-located readers, noise limits, temporary scope, next evening, unrecognized text, simulated offline and lost observation, duplicate events and simultaneous confirmation.

用例覆盖三人偏好、共享空间冲突、今晚的例外设置、次日晚间恢复、未知输入、设备部分失败、去重及并发确认。

### Optional model-assisted edits · 可选模型解析

The default works offline. Set `LIVINGMIND_FAMILY_EDITOR=model` and configure the backend’s existing `DEEPSEEK_API_KEY` and model settings to interpret additional phrasings when the rule grammar cannot match. This path requires the existing backend dependencies. It sends the edit and the named virtual device’s capabilities to the configured provider. A validated edit carries `suggestion.editSource: "model"`; all scene planning remains rule-based.

默认离线演示只使用规则。可选模型仅用于补充理解语句中明确提到的一台候选设备。模型输出必须属于当前待确认方案，仍要检查数值范围、音量限制、成员身份与建议版本。模型无法理解、输出无效或请求含未识别的否定时，维持原建议。修改成功仍需用户确认。本次自动化验证使用模型替身。

### Repeated signals and session lifetime · 重复信号与会话范围

An exact event ID retry is idempotent. New event IDs for the same member, activity, room and unchanged household context are coalesced for ten simulated minutes. An open suggestion for that same context keeps its original confirmation ID, including any edits. A real change of activity triggers a fresh evaluation. The timeline records each distinct proposal or suppression; coalesced sensor noise does not add another notification.

同一信号的重试和短时间内代表同一活动的不同事件号会被合并。现有建议、临时修改和虚拟设备读数会保留。配置数据库后，重启和同机第二个进程都可使用同一组去重记录。经典休息服务另有 PostgreSQL 执行账本。

Optional speaker recognition has two additional endpoints: `GET /api/family/speaker/status` and `POST /api/family/speaker/identify`. These return attribution information and never authorize a device change. [Voice input and speaker recognition · 语音与说话人说明](family-voice.md)

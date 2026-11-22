"""Shared state machine for the isolated, single-household evening demonstration."""
from __future__ import annotations

from copy import deepcopy
import re
from threading import RLock
from uuid import uuid4

from .gateway import ROOMS, VirtualFamilyGateway, supports_value
from .agents import capability_actions, experience_targets
from .model_edit import configured_provider, interpret

ACTIVITIES = {"away": "未到家", "home": "在家", "study": "阅读学习", "tv": "看电视", "sleep": "准备休息"}
MEMBERS = [
    ("mother", "妈妈", "away", None, "回家喜欢柔和灯光，客厅 25°C"),
    ("father", "爸爸", "home", "living", "观影时客厅亮度 20%"),
    ("child", "孩子", "home", "study", "学习时书桌灯亮度 75%"),
]
EVENT_CONTEXT = {
    "arrival": ("home", "living"), "study": ("study", "study"),
    "tv": ("tv", "living"), "sleep": ("sleep", "bedroom"),
}
EVENT_TYPES = {*EVENT_CONTEXT, "unknown_arrival"}
EVENT_SOURCES = {
    "simulated": "模拟家庭事件面板",
    "resident-input": "成员键入的文字",
    "simulated-transcript": "模拟语音转写",
    "browser-asr": "浏览器语音识别转写",
}
AGENTS = ["主 Agent", "体验 Agent", "空间执行 Agent"]
ACTION_TEXT = {"confirmed": "虚拟回读一致", "unknown": "状态未知，保留上次读数", "offline": "设备离线，跳过", "rejected": "能力校验拒绝", "mismatch": "回读与目标不一致", "skipped": "中断前尚未发送"}

CHECKPOINT_FIELDS = (
    "members", "minutes", "day", "suggestion", "muted", "snooze_until",
    "events", "recent_signals", "decisions", "exceptions", "timeline", "receipts", "outcome",
)


class FamilyError(ValueError):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.payload = {"error": {"code": code, "message": message}}


def check(condition, message, *, status=422, code="INVALID_INPUT"):
    if not condition:
        raise FamilyError(status, code, message)


def text_field(data, key):
    value = data.get(key)
    check(isinstance(value, str) and 0 < len(value) <= 128 and value.strip() == value, f"{key} 需为 1–128 字符的非空文本")
    return value


class FamilyEvening:
    def __init__(self, gateway_factory=VirtualFamilyGateway, edit_provider=None, store=None):
        self.lock = RLock()
        self.view_lock = RLock()
        self.gateway_factory = gateway_factory
        self.edit_provider = edit_provider or configured_provider()
        self.store = store
        self.persistence_failed = False
        self._seed()
        checkpoint = store.load() if store is not None else None
        if checkpoint is None:
            self._publish()
        else:
            self._restore(checkpoint)

    def _seed(self):
        self.gateway = self.gateway_factory()
        self.members = {i: {"id": i, "name": n, "activity": a, "roomId": r, "activityLabel": ACTIVITIES[a],
                            "preference": p} for i, n, a, r, p in MEMBERS}
        self.minutes = 18 * 60 + 25
        self.day = 1
        self.suggestion = None
        self.muted = False
        self.snooze_until = None
        self.events = {}
        self.recent_signals = {}
        self.decisions = {}
        self.exceptions = {}
        self.timeline = []
        self.receipts = []
        self.outcome = "ready"
        self.execution = None
        self.log("reset", "家庭空间已就绪", "晚间模拟从 18:25 开始。所有空间信号和设备回读均为模拟。")

    def reset(self):
        with self.lock:
            self._seed()
            return self._publish()

    @property
    def time(self):
        return "%02d:%02d" % (self.minutes // 60 % 24, self.minutes % 60)

    def log(self, kind, title, detail, **fields):
        self.timeline.insert(0, {"id": uuid4().hex, "day": self.day, "time": self.time, "kind": kind, "title": title, "detail": detail, **fields})

    def state(self):
        # Published views never change. A read never competes with device I/O.
        with self.view_lock:
            view = self._view
        return deepcopy(view)

    def _publish(self, *, save=True):
        progress = None
        if self.execution is not None:
            progress = {"suggestionId": self.execution["suggestionId"], "memberId": self.execution["memberId"],
                        "completedActions": len(self.receipts), "totalActions": len(self.execution["actions"])}
        devices = self.gateway.snapshot()
        view = deepcopy({"plannerSource": "rule", "source": "simulation", "time": self.time, "day": self.day, "members": list(self.members.values()),
                         "rooms": ROOMS, "devices": devices, "suggestion": self.suggestion, "execution": progress,
                         "muted": self.muted, "snoozed": self.snooze_until is not None and self.minutes < self.snooze_until,
                         "receipts": self.receipts, "timeline": self.timeline, "lastOutcome": self.outcome})
        if self.store is not None and save:
            export = getattr(self.gateway, "export_state", None)
            try:
                self.store.save({
                    "version": 1, "view": view, "devices": devices,
                    "gateway": export() if callable(export) else None,
                    "execution": deepcopy(self.execution),
                    "state": deepcopy({k: getattr(self, k) for k in CHECKPOINT_FIELDS}),
                })
            except Exception as exc:
                # The last durable intent remains the authority. Do not dispatch more writes.
                self.persistence_failed = True
                raise FamilyError(503, "CHECKPOINT_UNAVAILABLE", "无法保存家庭状态，请恢复存储后重新载入。") from exc
        with self.view_lock:
            self._view = view
        return deepcopy(view)

    def _restore(self, checkpoint):
        if checkpoint["version"] != 1:
            raise ValueError("Unsupported family checkpoint version")
        for field in CHECKPOINT_FIELDS:
            setattr(self, field, deepcopy(checkpoint["state"][field]))
        if checkpoint["gateway"] is not None:
            self.gateway.restore_state(checkpoint["gateway"])
        elif self.gateway.snapshot() != checkpoint["devices"]:
            raise ValueError("Injected gateway must support restoring its saved device state")
        self.execution = deepcopy(checkpoint["execution"])
        if self.execution is None:
            self._publish(save=False)
            return
        sid, actor = self.execution["suggestionId"], self.execution["memberId"]
        for i in range(len(self.receipts), len(self.execution["actions"])):
            action = self.execution["actions"][i]
            status = "unknown" if i == self.execution["dispatching"] else "skipped"
            self.receipts.append(self._uncompleted_receipt(sid, action, status))
        self._finish_confirmation(sid, actor)
        self._publish()

    def _check_mutation_available(self):
        check(not self.persistence_failed, "家庭存储不可用，请重新载入。", status=503, code="CHECKPOINT_UNAVAILABLE")
        # Holding the mutator lock with an unfinished intent means a previous
        # writer exited unexpectedly. Only journal recovery can finalize it.
        check(self.execution is None, "家庭操作已中断，请重新载入。", status=503, code="RECOVERY_REQUIRED")

    def dispatch(self, method, path, data=None):
        """Serialize household commands while readers see the last committed progress."""
        if method == "GET" and path == "/state":
            return self.state()
        with self.lock:
            self._check_mutation_available()
            try:
                return self._dispatch(method, path, data)
            except FamilyError as error:
                if (self.edit_provider is None or path != "/decision"
                        or error.payload["error"]["code"] != "UNPARSED_EDIT"):
                    if error.payload["error"]["code"] == "UNPARSED_EDIT":
                        error.payload["error"]["code"] = "NOT_UNDERSTOOD"
                    raise
                allowed = {action["deviceId"] for action in self.suggestion["actions"]}
                devices = [d for d in self.gateway.snapshot() if d["id"] in allowed]
        parsed = interpret(self.edit_provider, data["text"], devices)
        check(parsed is not None, "未理解修改，请明确设备和目标。", code="NOT_UNDERSTOOD")
        with self.lock:
            self._check_mutation_available()
            # Recheck member, plan identity, range and family constraints after waiting.
            retry = {k: v for k, v in data.items() if k != "text"}
            if data["text"].strip().startswith("这次"):
                retry["scope"] = "once"
            elif "今晚" in data["text"] or "今夜" in data["text"]:
                retry["scope"] = "tonight"
            self.decide({**retry, **parsed})
            self.suggestion["editSource"] = "model"
            self.suggestion["trace"][1]["detail"] += "（模型辅助解析，规则校验通过）"
            return self._publish()

    def _dispatch(self, method, path, data):
        handlers = {"/events": self.event, "/decision": self.decide, "/devices": self.device}
        check(path in {*handlers, "/reset", "/next-day", "/state"}, "未找到路径", status=404, code="NOT_FOUND")
        check(method == "POST" and path != "/state", "此路径不支持该请求方法", status=405, code="METHOD")
        check(isinstance(data, dict), "请求内容应为 JSON 对象")
        if path == "/reset":
            return self.reset()
        if path == "/next-day":
            self.next_evening()
            return self._publish()
        result = handlers[path](data)
        snapshot = self.state() if result is not None and result[1] else self._publish()
        if path == "/decision" and result is not None:
            decision_result, replayed = result
            snapshot["decisionResult"] = deepcopy(decision_result)
            snapshot["decisionReplayed"] = replayed
        return snapshot


    def next_evening(self):
        self.day += 1
        self.minutes = 18 * 60 + 25
        self.muted = False
        self.snooze_until = None
        self.exceptions.clear()
        self.recent_signals.clear()
        self.suggestion = None
        self.receipts = []
        for mid, _, activity, room, _ in MEMBERS:
            self.members[mid].update(activity=activity, activityLabel=ACTIVITIES[activity], roomId=room)
        self.outcome = "next_day"
        self.log("next_day", f"第 {self.day} 天 · 新的傍晚", "昨晚临时设定已到期。保留长期偏好、虚拟设备当前值和活动记录。")

    def device(self, data):
        device_id, mode = text_field(data, "deviceId"), text_field(data, "mode")
        check(any(d["id"] == device_id for d in self.gateway.snapshot()), "未知设备")
        check(mode in ("online", "offline", "unknown"), "未知设备模拟状态")
        set_mode = getattr(self.gateway, "set_mode", None)
        check(callable(set_mode), "当前网关不支持模拟设备故障。", status=409, code="SIMULATION_ONLY")
        set_mode(device_id, mode)
        self.log("device_mode", "模拟设备状态已更改", f"{device_id} · {mode}")
        self.outcome = "device_mode"

    def event(self, data):
        event_id, typ = text_field(data, "eventId"), text_field(data, "type")
        check(typ in EVENT_TYPES, "未知家庭事件")
        member_id = data.get("memberId")
        source = data.get("source", "simulated")
        check(isinstance(source, str) and source in EVENT_SOURCES, "未知事件来源")
        check(isinstance(member_id, str) and member_id in self.members or (typ == "unknown_arrival" and member_id is None), "未知家庭成员")
        room = data.get("roomId", EVENT_CONTEXT.get(typ, (None, None))[1])
        check(room == EVENT_CONTEXT.get(typ, (None, None))[1] or (typ == "study" and room == "living"), "此事件不支持该空间")
        fingerprint = (typ, member_id, room, source)
        if event_id in self.events:
            check(self.events[event_id] == fingerprint, "同一个事件号不能用于另一条信号", status=409, code="EVENT_ID_REUSED")
            self.outcome = "duplicate"
            return
        self.events[event_id] = fingerprint
        self.minutes += 5
        if self.minutes >= 24 * 60:
            self.next_evening()
        if typ == "unknown_arrival":
            if self.minutes - self.recent_signals.get(("unknown",), -100) <= 10:
                self.outcome = "coalesced"
                return
            self.recent_signals[("unknown",)] = self.minutes
            self.outcome = "identity_uncertain"
            self.log("suppressed", "身份待确认", f"来自{EVENT_SOURCES[source]}。门口有活动，但无法确定是谁。保持设备现状，不调用个人偏好。", source=source, eventId=event_id)
            return
        member = self.members[member_id]
        activity = EVENT_CONTEXT[typ][0]
        same_activity = (member["activity"], member["roomId"]) == (activity, room)
        member.update(activity=activity, activityLabel=ACTIVITIES[activity], roomId=room)
        # New event IDs often describe the same situation. Keep an open edit and
        # its confirmation ID intact while the household context remains identical.
        context = tuple((m["activity"], m["roomId"]) for m in self.members.values())
        signal = (typ, member_id, room, context)
        quiet = self.muted or (self.snooze_until is not None and self.minutes < self.snooze_until)
        pending_same = (self.suggestion is not None and self.suggestion["memberId"] == member_id
                        and self.suggestion["eventType"] == typ and self.suggestion["roomId"] == room)
        if same_activity and not quiet and signal in self.recent_signals and (pending_same or self.minutes - self.recent_signals[signal] <= 10):
            self.outcome = "coalesced"
            return
        self.log("signal", f"{member['name']} · {ACTIVITIES[activity]}", f"来自{EVENT_SOURCES[source]}。", source=source, eventId=event_id)
        if self.suggestion and (not same_activity or quiet):
            self.log("superseded", "旧建议已撤下", "成员活动已变化，原建议不能再确认。")
            self.suggestion = None
        if quiet:
            self.outcome = "muted" if self.muted else "snoozed"
            self.log("suppressed", "保持安静", "当前处于免打扰时段，只记录空间状态。")
            return
        self.recent_signals[signal] = self.minutes
        self.plan(member_id, typ)

    def plan(self, member_id, typ):
        member = self.members[member_id]
        others = [m for m in self.members.values() if m["id"] != member_id]
        by_id = {d["id"]: d for d in self.gateway.snapshot()}
        title, reason, actions = experience_targets(member, others, typ, by_id)
        exception = self.exceptions.get((member_id, typ))
        if exception:
            revised = []
            for d, v in actions:
                if d != exception["deviceId"]:
                    continue
                override = exception["value"] if exception["value"] is not None else v
                if d == "living-speaker" and any(m["activity"] in ("study", "sleep") for m in self.members.values()):
                    override = min(override, v)
                revised.append((d, override))
            actions = revised
            reason += "已应用本成员今晚对此场景的限定。"
        # Suppress a no-op only with a known, current virtual reading.
        actions, skipped = capability_actions(actions, by_id)
        if skipped:
            reason += "跳过不支持的动作：" + "、".join(skipped) + "。"
        if not actions:
            self.outcome = "no_change"
            self.log("suppressed", "无需调整", reason + "当前无需新增动作。")
            return
        if self.suggestion:
            self.log("superseded", "旧建议已撤下", "新的可执行建议替换了原建议。")
        self.suggestion = {"id": uuid4().hex, "title": title, "reason": reason, "memberId": member_id,
                           "eventType": typ, "roomId": member["roomId"], "scope": "tonight", "plannerSource": "rule", "actions": [{"deviceId": d, "value": v} for d,v in actions],
                           "trace": [{"agent": AGENTS[0], "detail": f"识别{member['name']}的空间事件，核对免打扰和其他成员活动。"},
                                     {"agent": AGENTS[1], "detail": reason},
                                     {"agent": AGENTS[2], "detail": "按虚拟设备能力生成待确认动作：" + "、".join(by_id[d]["name"] for d,v in actions)}]}
        self.outcome = "suggested"
        self.log("suggested", title, reason)

    def decide(self, data):
        sid, decision = text_field(data, "suggestionId"), text_field(data, "decision")
        check(decision in ("confirm", "dismiss", "mute", "snooze", "edit"), "未知决策")
        check(decision == "edit" or not {"onlyDeviceId", "value", "text", "scope"}.intersection(data), "仅编辑请求可设置设备、值和作用时段")
        actor = text_field(data, "memberId")
        old = self.decisions.get(sid)
        owner = old["memberId"] if old else (self.suggestion or {}).get("memberId")
        if owner is not None:
            check(owner == actor, "当前建议属于另一位成员", status=403, code="WRONG_MEMBER")
        if old and old["decision"] == decision:
            return old, True
        suggestion = self.suggestion
        check(suggestion is not None and suggestion["id"] == sid, "建议已过期，请查看当前家庭状态", status=409, code="STALE_SUGGESTION")
        if decision == "edit":
            self.edit(suggestion, data)
            return
        if decision == "confirm":
            if suggestion["scope"] == "tonight" and "exception" in suggestion:
                self.exceptions[suggestion["memberId"], suggestion["eventType"]] = suggestion["exception"]
            self.receipts = []
            self.suggestion = None
            self.outcome = "executing"
            actions = suggestion["actions"]
            self.execution = {"suggestionId": sid, "memberId": actor, "actions": actions, "dispatching": None}
            for index, action in enumerate(actions):
                self.execution["dispatching"] = index
                self._publish()  # Persist intent before the transport can change a device.
                try:
                    receipt = self.gateway.submit(f"{sid}:{action['deviceId']}", action["deviceId"], action["value"])
                except Exception:
                    receipt = self._uncompleted_receipt(sid, action, "unknown")
                self.receipts.append(receipt)
                self.execution["dispatching"] = None
                self._publish()  # Make the observed result durable before admitting another action.
            return self._finish_confirmation(sid, actor), False
        self.outcome = {"dismiss": "dismissed", "mute": "muted", "snooze": "snoozed"}[decision]
        if decision == "mute":
            self.muted = True
        if decision == "snooze":
            self.snooze_until = self.minutes + 30
        labels = {"mute": "今晚免打扰", "dismiss": "已跳过这条建议", "snooze": "已暂停提醒 30 分钟"}
        self.log(self.outcome, labels[decision], "无设备写入。")
        self.suggestion = None
        return self._record_decision(sid, actor, decision), False

    def _uncompleted_receipt(self, sid, action, status):
        device_id = action["deviceId"]
        mark_unobserved = getattr(self.gateway, "mark_unobserved", None)
        if status == "unknown" and callable(mark_unobserved):
            mark_unobserved(device_id)
        return {"actionId": f"{sid}:{device_id}", "deviceId": device_id, "requested": action["value"],
                "status": status, "observed": None, "source": "execution-journal",
                "propertyRequest": None, "writeReply": None, "readReply": None}

    def _finish_confirmation(self, sid, actor):
        self.execution = None
        self.outcome = "confirmed" if all(r["status"] == "confirmed" for r in self.receipts) else "incomplete"
        names = {d["id"]: d["name"] for d in self.gateway.snapshot()}
        details = [f"{names[r['deviceId']]}：{ACTION_TEXT[r['status']]}" + (f"（{r['observed']}）" if r["observed"] is not None else "") for r in self.receipts]
        self.log(self.outcome, "已确认 · 设备执行结果", "；".join(details))
        return self._record_decision(sid, actor, "confirm")

    def _record_decision(self, sid, actor, decision):
        result = {
            "suggestionId": sid,
            "memberId": actor,
            "decision": decision,
            "outcome": self.outcome,
            "receipts": deepcopy(self.receipts) if decision == "confirm" else [],
        }
        self.decisions[sid] = result
        return result

    def edit(self, suggestion, data):
        scope = data.get("scope", suggestion["scope"])
        check(scope in ("once", "tonight"), "未知修改作用时段")
        if "text" in data:
            check(not {"onlyDeviceId", "value", "scope"}.intersection(data), "文字与结构化修改不能混用")
            command = re.sub(r"[\s，。！,!？?]", "", text_field(data, "text"))
            if command.startswith("这次"):
                scope = "once"
            elif "今晚" in command or "今夜" in command:
                scope = "tonight"
            command = re.sub(r"(?:其他|其它)(?:设备)?(?:都)?(?:保持不变|不要动|别动|不动)$", "", command)
            if re.fullmatch(r"(?:我)?今晚(?:还要|想|要)看书客厅亮一点卧室先别动", command):
                lamp = next((d for d in self.gateway.snapshot() if d["id"] == "living-light"), None)
                check(lamp is not None and lamp["mode"] == "online", "客厅灯缺少可靠读数，无法比较亮度。请指定一个目标百分比。", code="READBACK_UNAVAILABLE")
                if lamp["value"] >= lamp["capability"]["valueRange"][1]:
                    raise FamilyError(422, "ALREADY_AT_LIMIT", "客厅灯已达到最高亮度。原建议仍待确认。")
                brighter = min(lamp["capability"]["valueRange"][1], max(65, lamp["value"] + 10))
                command = f"今晚只调客厅灯到{brighter}%"
            elif re.fullmatch(r"今晚只(?:开|调)客厅灯空调(?:先)?(?:别开|不动|别动)", command):
                command = "今晚只调客厅灯"
            names = {d["name"]: d["id"] for d in self.gateway.snapshot()}
            terms = "|".join(map(re.escape, names))
            match = re.fullmatch(rf"(?:今晚|今夜|这次)?只(?:调|开|打开|调整|改|动)?({terms})(?:(?:到|至|为|调到|调至)([0-9]{{1,3}})(%|％|度|°C|档)?)?", command)
            check(match, "未理解本次修改。可说“今晚只调客厅灯到 35%”。原建议保持待确认。", code="UNPARSED_EDIT")
            device_id = names[match[1]]
            value = int(match[2]) if match[2] else None
            unit = match[3]
        else:
            device_id = text_field(data, "onlyDeviceId")
            value = data.get("value")
            unit = None
        actions = [dict(a) for a in suggestion["actions"] if a["deviceId"] == device_id]
        check(bool(actions), "只能缩小当前建议的设备范围")
        device = next(d for d in self.gateway.snapshot() if d["id"] == device_id)
        check(unit is None or {"度": "°C", "％": "%"}.get(unit, unit) == device["unit"], "单位与设备不符", code="NOT_UNDERSTOOD")
        if value is not None:
            bounds = device["capability"]["valueRange"]
            if all(type(bound) is int for bound in bounds):
                check(type(value) is int, "此设备只接受整数")
            check(supports_value(device["capability"], value), "数值超出设备支持范围")
            if device_id == "living-speaker" and any(m["activity"] in ("study", "sleep") for m in self.members.values()):
                limit = 12 if any(m["activity"] == "sleep" for m in self.members.values()) else 18
                check(value <= limit, f"家人正在学习或休息，当前音量上限为 {limit}%")
            actions[0]["value"] = value
        duration = "仅这次" if scope == "once" else "今晚此场景"
        detail = f"按要求{duration}只调{device['name']}到 {actions[0]['value']}{device['unit']}，保留长期偏好。"
        previous_scope = suggestion["scope"]
        suggestion.update(id=uuid4().hex, actions=actions, reason=detail, editSource="rule", scope=scope)
        if scope == "tonight":
            saved_value = value
            if saved_value is None:
                prior = suggestion.get("exception") or self.exceptions.get((suggestion["memberId"], suggestion["eventType"]))
                if previous_scope == "once":
                    # Extending a single-use target to tonight keeps the displayed number.
                    saved_value = actions[0]["value"]
                elif prior and prior["deviceId"] == device_id:
                    saved_value = prior["value"]
            suggestion["exception"] = {"deviceId": device_id, "value": saved_value}
        else:
            suggestion.pop("exception", None)
        suggestion["trace"][1]["detail"] = detail
        suggestion["trace"][2]["detail"] = f"仅{device['name']}待确认，其余设备没有待执行动作。"
        self.outcome = "edited"
        self.log("edited", "本次建议已修改" if scope == "once" else "今晚的建议已修改", detail)

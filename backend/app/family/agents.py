"""Deterministic experience planning and space capability mapping for the family simulator."""
PREFERENCES = {
    "mother": {"arrivalLight": 45, "arrivalTemp": 25, "studyLight": 65, "tvLight": 24, "sleepLight": 8},
    "father": {"arrivalLight": 55, "arrivalTemp": 24, "studyLight": 70, "tvLight": 20, "sleepLight": 10},
    "child": {"arrivalLight": 50, "arrivalTemp": 26, "studyLight": 75, "tvLight": 30, "sleepLight": 12},
}


def experience_targets(member, others, typ, by_id):
    pref = PREFERENCES[member["id"]]
    readers = [m["name"] for m in others if m["activity"] == "study"]
    living_readers = [m["name"] for m in others if m["activity"] == "study" and m["roomId"] == "living"]
    viewers = [m["name"] for m in others if m["activity"] == "tv"]
    sleepers = [m["name"] for m in others if m["activity"] == "sleep"]
    actions = []
    if typ == "arrival":
        title = "到家，要准备客厅吗？"
        reason = f"{member['name']}到家，通常喜欢客厅灯 {pref['arrivalLight']}%、空调 {pref['arrivalTemp']}°C。"
        if viewers or living_readers:
            reason += f"{'、'.join(viewers + living_readers)}正在使用客厅，保留灯光与窗帘。"
        else:
            actions.extend([("living-light", pref["arrivalLight"]), ("living-curtain", 45)])
        actions.append(("living-ac", pref["arrivalTemp"]))
    elif typ == "study":
        title = "为阅读调亮书桌灯？"
        in_living = member["roomId"] == "living"
        reason = f"{member['name']}在{'客厅' if in_living else '书房'}阅读，偏好亮度 {pref['studyLight']}%。"
        if viewers and in_living:
            reason += "客厅已有家人观影，不自动覆盖共享灯光。"
        elif in_living:
            actions = [("living-light", pref["studyLight"])]
        else:
            actions = [("desk-light", pref["studyLight"]), ("study-fan", 1)]
        if viewers and not in_living:
            reason += f"{'、'.join(viewers)}正在客厅看电视，保留客厅环境。"
    elif typ == "tv":
        title = "为观影调暗客厅灯？"
        reason = f"{member['name']}在客厅看电视，偏好观影亮度 {pref['tvLight']}%。"
        if living_readers:
            reason += f"{'、'.join(living_readers)}还在客厅读书，保留共享灯的亮度。"
        else:
            actions.append(("living-light", pref["tvLight"]))
        if readers and not living_readers:
            reason += f"{'、'.join(readers)}仍在书房学习，书桌灯保持原样。"
        volume = 12 if sleepers else 18 if readers else 35
        if sleepers or readers:
            reason += f"为减少打扰，客厅音量上限 {volume}%。"
        actions.append(("living-speaker", volume))
    else:
        title = "把卧室调到休息亮度？"
        reason = f"{member['name']}准备休息，偏好床头灯 {pref['sleepLight']}%。"
        if readers or viewers:
            reason += "其他家人仍在学习或观影，仅调整卧室。"
        actions = [("bed-light", pref["sleepLight"]), ("bed-curtain", 0)]
        if viewers and by_id["living-speaker"]["mode"] == "online" and by_id["living-speaker"]["value"] > 12:
            reason = reason.replace("仅调整卧室。", "书桌和客厅灯光保持原样。")
            reason += "若确认，同时将客厅音箱调至 12%，照顾准备休息的家人。"
            actions.append(("living-speaker", 12))
    return title, reason, actions

def capability_actions(targets, by_id):
    """Check supported writable properties, range and last reliable readback."""
    actions = []
    skipped = []
    for device_id, value in targets:
        device = by_id.get(device_id)
        if device is None or "write" not in device["capability"]["access"]:
            skipped.append(device_id)
            continue
        low, high, step = device["capability"]["valueRange"]
        if not low <= value <= high or (value - low) % step:
            skipped.append(device_id)
            continue
        if device["mode"] != "online" or device["value"] != value:
            actions.append((device_id, value))
    return actions, skipped

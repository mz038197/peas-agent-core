from __future__ import annotations

from peas_agent.lobby.protocol import MemberInfo, RoomConfig


def build_host_context(
    *,
    room_config: RoomConfig,
    members: list[MemberInfo],
    my_agent_id: str,
    my_display_name: str,
) -> str:
    names = "\n".join(
        f"- {m.display_name} ({m.agent_id})"
        + (" ← 你自己" if m.agent_id == my_agent_id else "")
        for m in members
    )
    return "\n".join(
        [
            f"你在聊天室 {room_config.room_id}，顯示名稱「{my_display_name}」（id: {my_agent_id}）。",
            f"【主題】{room_config.topic or '（未設定）'}",
            f"【規則】{room_config.rules or '請用 @display_name 點名；不需要發言回 [pass]。'}",
            "【可 @ 的成員】",
            names or "（尚無其他成員）",
            "點名請用 @display_name（例 @小明的 agent）。",
        ]
    )


def build_user_text(
    *,
    inbox: list[dict[str, str]],
    prompt_hint: str | None,
    max_messages: int = 20,
) -> str:
    recent = inbox[-max_messages:]
    lines = ["【最近聊天室訊息】"]
    if recent:
        for i, item in enumerate(recent, 1):
            lines.append(f"{i}. [{item['display_name']}] {item['text']}")
    else:
        lines.append("（尚無訊息）")
    lines.append("")
    lines.append("【現在輪到你】")
    lines.append(prompt_hint or "請針對以上討論發表看法。")
    return "\n".join(lines)

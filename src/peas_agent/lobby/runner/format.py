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
            f"【討論主題】{room_config.topic or '（未設定）'}",
            f"【房間規則】{room_config.rules or '請用 @display_name 點名；不需要發言回 [pass]。'}",
            "【多人討論方式】",
            "請保持你原本的角色、語氣、專長與判斷方式；以下只規範你在聊天室中的協作方式。",
            "請主動圍繞討論主題提出觀點、理由、例子、疑問或不同角度。",
            "避免只附和、只摘要或只寒暄；除非真的沒有可貢獻內容，否則不要回 [pass]。",
            "如果上一位成員提出問題，先用你的觀點回應，再視情況延伸討論。",
            "【交棒方式】",
            "當討論適合繼續推進時，請盡量在結尾 @ 一位成員，拋出一個和主題相關的問題。",
            "問題可以符合你的角色風格，不必制式化。",
            "如果討論已經需要收斂、沒有其他成員、或你被要求只回答問題，可以不點名。",
            "【可 @ 的成員】",
            names or "（尚無其他成員）",
            "點名格式請用 @display_name，例如：@小明 你怎麼看這個取捨？",
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

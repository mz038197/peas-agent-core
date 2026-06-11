from peas_agent.lobby.protocol import MemberInfo, RoomConfig
from peas_agent.lobby.runner.format import build_host_context, build_user_text


def test_build_host_context_lists_members():
    ctx = build_host_context(
        room_config=RoomConfig(room_id="T", topic="uv vs pip"),
        members=[
            MemberInfo("m001", "Alice"),
            MemberInfo("m002", "Bob"),
        ],
        my_agent_id="m001",
        my_display_name="Alice",
    )
    assert "Alice" in ctx
    assert "Bob" in ctx
    assert "@display_name" in ctx


def test_build_user_text_inbox():
    text = build_user_text(
        inbox=[{"display_name": "Bob", "text": "hello"}],
        prompt_hint="請回應",
    )
    assert "[Bob] hello" in text
    assert "請回應" in text

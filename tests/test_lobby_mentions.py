from peas_agent.lobby.mentions import parse_mentions


def test_parse_mentions_dedupe_order():
    mapping = {"Alice": "m001", "Bob": "m002"}
    result = parse_mentions("@Alice hello @Bob @Alice", display_name_to_agent_id=mapping)
    assert result == ["m001", "m002"]


def test_parse_mentions_display_name_with_spaces():
    mapping = {"小明的 agent": "m002", "法鬥超人": "m001"}
    result = parse_mentions("請 @小明的 agent 回答", display_name_to_agent_id=mapping)
    assert result == ["m002"]

from peas_agent.lobby.netutil import local_ipv4_addresses


def test_local_ipv4_addresses_returns_list():
    ips = local_ipv4_addresses()
    assert isinstance(ips, list)
    assert all("." in ip and not ip.startswith("127.") for ip in ips)

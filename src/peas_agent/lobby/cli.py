from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from peas_agent.lobby.netutil import local_ipv4_addresses
from peas_agent.lobby.paths import DEFAULT_LOBBY_WORKSPACE, resolve_lobby_workspace


def _print_serve_banner(*, host: str, port: int, workspace: Path) -> None:
    print(f"Lobby workspace: {workspace}")
    print(f"本機管理頁:     http://127.0.0.1:{port}/admin")
    print(f"本機 WebSocket: ws://127.0.0.1:{port}/ws")

    if host in ("0.0.0.0", "::"):
        ips = local_ipv4_addresses()
        if ips:
            print("區網位址（給學生 / 其他電腦）：")
            for ip in ips:
                print(f"  管理頁:     http://{ip}:{port}/admin")
                print(f"  WebSocket:  ws://{ip}:{port}/ws")
        else:
            print("（無法自動偵測區網 IP，請在本機執行 ipconfig 查 IPv4）")
    elif host not in ("127.0.0.1", "localhost"):
        print(f"管理頁:     http://{host}:{port}/admin")
        print(f"WebSocket:  ws://{host}:{port}/ws")

    print(
        "學生 join 範例："
        f" peas-agent lobby join --url ws://<上面IP>:{port}/ws --room ROOM --display-name 名稱"
    )
    print("")


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("請安裝 lobby extra：uv sync --extra lobby", file=sys.stderr)
        return 1

    from peas_agent.lobby.server.app import create_app

    workspace = resolve_lobby_workspace(args.lobby_workspace)
    app = create_app(workspace)
    _print_serve_banner(host=args.host, port=args.port, workspace=workspace)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _cmd_join(args: argparse.Namespace) -> int:
    from peas_agent.lobby.runner.client import LobbyRunner

    runner = LobbyRunner(
        ws_url=args.url,
        room_id=args.room,
        display_name=args.display_name,
        workspace=args.workspace,
    )
    return asyncio.run(runner.run())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PEAS Agent Lobby")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="啟動 lobby server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--lobby-workspace",
        default=str(DEFAULT_LOBBY_WORKSPACE),
        help=f"lobby 資料目錄（預設 {DEFAULT_LOBBY_WORKSPACE}）",
    )
    serve.set_defaults(func=_cmd_serve)

    join = sub.add_parser("join", help="加入聊天室（runner）")
    join.add_argument("--url", required=True, help="WebSocket URL，例 ws://localhost:8765/ws")
    join.add_argument("--room", required=True, help="room_id")
    join.add_argument("--display-name", required=True, dest="display_name")
    join.add_argument("-w", "--workspace", default=None, help="Agent workspace")
    join.set_defaults(func=_cmd_join)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

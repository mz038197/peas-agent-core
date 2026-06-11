"""PEAS Agent Workshop CLI entry point."""

from __future__ import annotations

import argparse
import sys

from peas_agent import Agent, get_config_path, get_token_budget


def _run_lobby(argv: list[str]) -> int:
    from peas_agent.lobby.cli import main as lobby_main

    return lobby_main(argv)


def _run_chat(args: argparse.Namespace) -> None:
    try:
        agent = Agent.create(
            workspace=args.workspace,
            session_name=args.session_name,
        )
    except (RuntimeError, ValueError) as e:
        print(e)
        return

    llm_cfg = agent.config.get("llm", {})
    model = llm_cfg.get("model", "gpt-5.4-mini") if isinstance(llm_cfg, dict) else "gpt-5.4-mini"
    base_url = (llm_cfg.get("base_url") or "").strip() if isinstance(llm_cfg, dict) else ""

    print("已讀到 API 金鑰設定（內容不顯示）；進入對話（串流 + 工具 + JSONL + 預算裁切 + WG-21 附圖）。")
    print(f"workspace: {agent.workspace}")
    print(f"config: {get_config_path()}")
    print(f"session: {agent.session_path}")
    print(f"model: {model}")
    if base_url:
        print(f"base_url: {base_url}")
    print(
        "（WG-21 附圖：先輸入 `/image 相對路徑`，再輸入本輪文字；"
        "或單行 `/image 路徑 問題`。）"
    )

    if agent.history:
        print(
            f"已從 {agent.session_path!r} 載入 {len(agent.history)} 則訊息（WG-16）；"
            f" last_consolidated={agent.last_consolidated}（WG-17）。"
        )
    else:
        print("尚無可載入歷史或檔不存在；自空 history 開始（WG-15 寫入）。")

    print(
        f"（WG-17 token_budget={get_token_budget()}，"
        f"WG-19 整併目標 ≤ {get_token_budget() // 2} 字元；以字元長度模擬 token。）"
    )

    pending_image: str | None = None

    while True:
        user_line = input("\n你：").strip()
        if user_line.lower() in ("quit", "exit", "q"):
            print("再見！")
            break
        if not user_line:
            continue

        image_rel: str | None = None
        user_text = user_line

        if user_line.startswith("/image "):
            rest = user_line[len("/image ") :].strip()
            if not rest:
                print(
                    "（用法：`/image 相對路徑`，下一行輸入文字；"
                    "或 `/image 路徑 問題`）"
                )
                continue
            parts = rest.split(maxsplit=1)
            image_rel = parts[0]
            if len(parts) > 1:
                user_text = parts[1].strip()
            else:
                pending_image = image_rel
                print(f"（已選附圖 {image_rel!r}，請輸入本輪文字）")
                continue
        elif pending_image is not None:
            image_rel = pending_image
            pending_image = None
            user_text = user_line

        if not user_text and not image_rel:
            continue

        print("\n助手：", end="", flush=True)
        agent.chat(user_text, image_path=image_rel)
        print()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "lobby":
        raise SystemExit(_run_lobby(sys.argv[2:]))

    parser = argparse.ArgumentParser(description="PEAS Agent Workshop CLI")
    parser.add_argument(
        "-w",
        "--workspace",
        help="Agent workspace 路徑（覆寫 config.json 與預設 ~/.peas-agent/workspace）",
    )
    parser.add_argument(
        "-s",
        "--session",
        dest="session_name",
        help="Session 檔名（置於 workspace/sessions/；省略則使用 session.jsonl）",
    )
    args = parser.parse_args()
    _run_chat(args)


if __name__ == "__main__":
    main()

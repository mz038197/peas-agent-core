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
            project_root=args.project_root,
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
    print(f"project_root: {agent.project_root}")
    print(f"config: {get_config_path()}")
    print(f"session: {agent.session_path}")
    print(f"model: {model}")
    if base_url:
        print(f"base_url: {base_url}")
    print(
        "（WG-21 附圖：先輸入 `/image 相對於 project root 的路徑`，再輸入本輪文字；"
        "或單行 `/image 路徑 問題`。workspace 內附圖請用絕對路徑。）"
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
        f"WG-19 歸檔目標 ≤ {get_token_budget() // 2} 字元；以字元長度模擬 token。）"
    )

    dream_cfg = agent.config.get("dream", {})
    if isinstance(dream_cfg, dict) and dream_cfg.get("enabled", True):
        from peas_agent.dream_scheduler import ensure_dream_scheduler

        scheduler = ensure_dream_scheduler(agent.workspace, agent.config)
        if scheduler:
            nxt = scheduler.next_run_at()
            if nxt:
                print(f"（Dream 背景排程已啟動；下次執行約 {nxt.strftime('%Y-%m-%d %H:%M')}。）")
        print(
            "（Dream 指令：/dream、/dream-log [sha]、/dream-restore [sha]、"
            "/memory-summary、/memory-pin <關鍵字>）"
        )

    pending_image: str | None = None

    while True:
        from peas_agent.dream_runner import poll_dream_message

        dream_msg = poll_dream_message(agent.workspace)
        if dream_msg:
            print(dream_msg)

        user_line = input("\n你：").strip()
        if user_line.lower() in ("quit", "exit", "q"):
            print("再見！")
            break
        if not user_line:
            continue

        if user_line == "/dream":
            ok = agent.dream()
            print(
                "（Dream 已開始背景執行…）"
                if ok
                else "（Dream：已在背景執行中或 workspace lock 被佔用。）"
            )
            continue
        if user_line.startswith("/dream-log"):
            parts = user_line.split(maxsplit=1)
            sha = parts[1].strip() if len(parts) > 1 else None
            print("\n" + agent.dream_log(sha))
            continue
        if user_line.startswith("/dream-restore"):
            parts = user_line.split(maxsplit=1)
            sha = parts[1].strip() if len(parts) > 1 else None
            print("\n" + agent.dream_restore(sha))
            continue
        if user_line == "/memory-summary":
            print("\n" + agent.memory_summary(refresh=True))
            continue
        if user_line.startswith("/memory-pin "):
            keyword = user_line[len("/memory-pin ") :].strip()
            if keyword:
                agent.memory_pin(keyword)
                print(f"（已釘選：{keyword!r}）")
            continue

        image_rel: str | None = None
        user_text = user_line

        if user_line.startswith("/image "):
            rest = user_line[len("/image ") :].strip()
            if not rest:
                print(
                    "（用法：`/image 相對於 project root 的路徑`，下一行輸入文字；"
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
        "--project-root",
        "--project",
        dest="project_root",
        help="Advanced override for the runtime project root; normally inferred from cwd and parent project markers.",
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

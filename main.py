"""Entry: GUI by default; pass a profile URL for headless CLI (stdout prints UID)."""

from __future__ import annotations

import argparse
import sys


def _is_profile_url(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _run_cli(query: str, cookie: str | None, http_only: bool) -> int:
    from extract import ExtractError
    from resolve import resolve_uid

    q = query.strip()
    try:
        if _is_profile_url(q):
            uid = resolve_uid(q, cookie, http_only=http_only)
        else:
            from short_id_lookup import lookup_uid_by_short_id

            uid = lookup_uid_by_short_id(q)
        sys.stdout.write(uid + "\n")
        sys.stdout.flush()
        return 0
    except ExtractError as e:
        print(str(e), file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="抖音号或主页 URL → 数字 UID（默认打开窗口；传入参数则无界面输出 UID）"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="抖音号或个人主页链接；省略则启动图形界面",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        metavar="STR",
        help="可选，浏览器 Cookie 整段字符串",
    )
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="仅用 HTTP 抓取（不做无头浏览器回退；动态页易失败）",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="强制打开图形界面（即使写了 url）",
    )
    args = parser.parse_args()

    if args.url and not args.gui:
        raise SystemExit(_run_cli(args.url, args.cookie, args.http_only))

    from app import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()

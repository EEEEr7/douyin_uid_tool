import json
import sys

import requests


def main() -> int:
    sec = sys.argv[1]
    url = (
        "https://www.douyin.com/aweme/v1/web/user/profile/"
        f"?sec_uid={sec}&device_platform=webapp&aid=6383"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Accept": "application/json, text/plain, */*",
    }
    r = requests.get(url, headers=headers, timeout=10)
    print("status=", r.status_code)
    print("head=", r.text[:200])
    try:
        data = r.json()
    except Exception:
        return 0
    # try common fields
    for path in [
        ("user", "uid"),
        ("user_info", "uid"),
        ("user", "id"),
    ]:
        cur = data
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            print("field", ".".join(path), "=", cur)
    print("keys=", list(data.keys())[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


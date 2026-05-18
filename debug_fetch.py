import re
import sys

from extract import fetch_html


def main() -> int:
    url = sys.argv[1]
    cookie = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    final, code, text = fetch_html(url, cookie=cookie, timeout=10)
    print("final=", final)
    print("code=", code, "len=", len(text))
    print("has_RENDER_DATA=", "RENDER_DATA" in text)
    login_hint = bool(re.search(r"(passport|login|验证码|安全验证|请登录)", text, re.I))
    print("login_hint=", login_hint)

    m = re.search(r"\"uid\"\s*:\s*\"(\d{5,})\"", text)
    print("uid_match=", m.group(1) if m else None)
    m = re.search(r"\"to_uid\"\s*:\s*(\d{5,})", text)
    print("to_uid_match=", m.group(1) if m else None)
    m = re.search(r"\\\"to_uid\\\"\s*:\s*(\d{5,})", text)
    print("escaped_to_uid_match=", m.group(1) if m else None)

    # Extra probes
    print("contains_known_uid=", "65204597181" in text)
    m = re.search(r"\b\d{11}\b", text)
    print("first_11_digits=", m.group(0) if m else None)
    m = re.search(r"sec_uid|secUid|SEC_UID", text)
    print("mentions_sec_uid=", bool(m))

    print("head=", text[:220].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""Fetch Douyin profile HTML and extract numeric to_uid.

Douyin pages may contain both `uid` (short display id) and `to_uid` (longer
target user id). This tool returns `to_uid` only.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any
from urllib.parse import urlparse, unquote

import requests


class ExtractError(Exception):
    """Recoverable extraction failure with user-facing message."""

    pass


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

LOGIN_HINT_RE = re.compile(
    r"(登录后可享|请登录|passport/login|验证码|安全验证)",
    re.IGNORECASE,
)

RENDER_DATA_RE = re.compile(
    r'<script\s+id=["\']RENDER_DATA["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

UID_REGEXES = [
    # Plain JSON: "uid":"65204597181"
    re.compile(r'"uid"\s*:\s*"(\d{5,})"'),
    # Numeric uid (some payloads omit quotes)
    re.compile(r'"uid"\s*:\s*(\d{8,13})\b'),
    # Escaped JSON fragments: \\\"uid\\\":\\\"652...\\\"
    re.compile(r'\\+"uid\\+"\s*:\s*\\+"(\d{5,})\\+"'),
    # Extra-heavy escaping seen in hydration strings
    re.compile(r'(?:\\)+"?uid(?:\\)+"\s*:\s*(?:\\)+"(\d{5,})(?:\\)+"'),
]

TO_UID_REGEXES = [
    # Plain JSON: "to_uid":435...
    re.compile(r'"to_uid"\s*:\s*(\d{5,})'),
    # Escaped JSON fragments with one or more backslashes before quotes:
    #   \\\"to_uid\\\":435...
    re.compile(r'\\+"to_uid\\+"\s*:\s*(\d{5,})'),
    # Nested escaping: \\\\\\\"to_uid\\\\\\\":435...
    re.compile(r'(?:\\)+"?to_uid(?:\\)+"\s*:\s*(\d{5,})'),
    # Some pages may include to_uid without surrounding quotes.
    re.compile(r'\bto_uid\b\D{0,24}(\d{5,})'),
]


def validate_profile_url(url: str) -> None:
    u = (url or "").strip()
    if not u:
        raise ExtractError("请输入抖音主页链接。")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise ExtractError("链接必须以 http:// 或 https:// 开头。")
    host = (parsed.hostname or "").lower()
    if "douyin.com" not in host:
        raise ExtractError("请输入有效的抖音域名链接（需包含 douyin.com）。")


def _pick_headers(cookie: str | None) -> dict[str, str]:
    h: dict[str, str] = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    if cookie and cookie.strip():
        h["Cookie"] = cookie.strip()
    return h


def fetch_html(url: str, cookie: str | None, timeout: float = 10.0) -> tuple[str, int, str]:
    """Return (final_url, status_code, text)."""
    validate_profile_url(url)
    try:
        resp = requests.get(
            url.strip(),
            headers=_pick_headers(cookie),
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        raise ExtractError("请求超时，请检查网络或稍后重试。") from None
    except requests.exceptions.ConnectionError:
        raise ExtractError("网络连接失败，请检查网络或代理设置。") from None
    except requests.exceptions.RequestException as e:
        raise ExtractError(f"请求失败：{e}") from e

    text = resp.text or ""
    final_url = resp.url or url
    code = resp.status_code

    if code != 200:
        raise ExtractError(f"服务器返回 HTTP {code}，无法读取页面。")

    low_final = final_url.lower()
    if "login" in low_final or "passport" in low_final:
        raise ExtractError(
            "页面被重定向到登录，请在 Cookie 栏粘贴浏览器 Cookie 后重试。"
        )

    if LOGIN_HINT_RE.search(text):
        raise ExtractError(
            "页面疑似登录或验证页。请在 Cookie 栏粘贴登录后的 Cookie 后重试。"
        )

    return final_url, code, text


def is_user_profile_url(url: str) -> bool:
    """True for /user/<sec_uid> or /@<unique_id> profile URLs."""
    try:
        path = (urlparse(url.strip()).path or "").lower()
        if "/user/" in path:
            return True
        if re.match(r"^/@[^/]+", path):
            return True
        return False
    except Exception:
        return False


def extract_unique_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url.strip()).path or ""
    m = re.match(r"^/@([^/?#]+)", path, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"^/user/@([^/?#]+)", path, re.I)
    if m:
        return m.group(1).strip()
    return None


def is_likely_dynamic_shell(html: str) -> bool:
    """Heuristic: HTML shell where UID lives only after JS runs (no SSR markers)."""
    if not html:
        return True
    if "RENDER_DATA" in html:
        return False
    if re.search(r"<body[^>]*>\s*</body>", html, re.I | re.DOTALL):
        return True
    # Observed Douyin bootstrap: VM prelude (SSR payload absent).
    if "_$jsvmprt" in html:
        return True
    return False


def _first_regex_any(regexes: list[re.Pattern[str]], html: str) -> str | None:
    for rx in regexes:
        m = rx.search(html)
        if m:
            return m.group(1)
    return None


def _looks_like_user_uid(v: str) -> bool:
    # Douyin numeric uid commonly ~9-12 digits; keep a safe window.
    return v.isdigit() and 8 <= len(v) <= 13


def _walk_find_to_uid(obj: Any) -> str | None:
    if isinstance(obj, dict):
        if "to_uid" in obj:
            v = obj["to_uid"]
            if isinstance(v, bool):
                return None
            if isinstance(v, int):
                return str(v)
            if isinstance(v, str) and v.isdigit():
                return v
        for val in obj.values():
            found = _walk_find_to_uid(val)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk_find_to_uid(item)
            if found:
                return found
    return None


def _walk_find_user_uid(obj: Any) -> str | None:
    """Find user-facing uid in nested dict/list (not short_id / not to_uid)."""
    if isinstance(obj, dict):
        for key in ("uid", "user_id", "userId"):
            if key in obj:
                v = obj[key]
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    s = str(v)
                    if _looks_like_user_uid(s):
                        return s
                elif isinstance(v, str) and v.isdigit() and _looks_like_user_uid(v):
                    return v
        for val in obj.values():
            found = _walk_find_user_uid(val)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk_find_user_uid(item)
            if found:
                return found
    return None


def extract_sec_uid_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/user/([^/?#\s]+)", url, re.I)
    if not m:
        return None
    val = m.group(1).strip()
    if not val or val.startswith("@"):
        return None
    # /user/84082679218 uses numeric uniqueId, not sec_uid.
    if val.isdigit():
        return None
    return val


def _user_blob(d: dict) -> dict:
    ui = d.get("user_info")
    if isinstance(ui, dict):
        return ui
    return d


def _to_uid_from_user_blob(d: dict) -> str | None:
    info = _user_blob(d)
    v = info.get("to_uid")
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str) and v.isdigit():
        return v
    return None


def _profile_blob_matches(info: dict, sec_uid: str | None, unique_id: str | None) -> bool:
    if sec_uid:
        for key in ("sec_uid", "secUid"):
            v = info.get(key)
            if v and str(v) == sec_uid:
                return True
    if unique_id:
        for key in ("unique_id", "uniqueId", "display_id"):
            v = info.get(key)
            if v and str(v).strip().lower() == unique_id.lower():
                return True
    return False


def _find_owner_to_uid_in_json(
    obj: Any, sec_uid: str | None, unique_id: str | None
) -> str | None:
    if isinstance(obj, dict):
        info = _user_blob(obj)
        if isinstance(info, dict) and _profile_blob_matches(info, sec_uid, unique_id):
            to_uid = _to_uid_from_user_blob(obj)
            if to_uid:
                return to_uid
        for val in obj.values():
            found = _find_owner_to_uid_in_json(val, sec_uid, unique_id)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_owner_to_uid_in_json(item, sec_uid, unique_id)
            if found:
                return found
    return None


# to_uid adjacent to sec_uid / unique_id in serialized page data
SEC_UID_TO_UID_RE = re.compile(
    r'sec_uid\\?"\s*:\s*\\?"(?P<sec>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'to_uid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.I,
)
SEC_UID_TO_UID_BARE_RE = re.compile(
    r'sec_uid\\?"\s*:\s*\\?"(?P<sec>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'to_uid\\?"\s*:\s*(?P<to_uid>\d{5,})\b',
    re.I,
)
UNIQUE_ID_TO_UID_RE = re.compile(
    r'uniqueId\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'to_uid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.I,
)
UNIQUE_ID_TO_UID_BARE_RE = re.compile(
    r'uniqueId\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'toUid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.I,
)
UNIQUE_TO_UID_RE = re.compile(
    r'unique_id\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'to_uid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.I,
)
UNIQUE_TO_UID_BARE_RE = re.compile(
    r'unique_id\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[\s\S]{0,4000}?'
    r'to_uid\\?"\s*:\s*(?P<to_uid>\d{5,})\b',
    re.I,
)


def _regex_owner_to_uid(
    text: str, sec_uid: str | None, unique_id: str | None
) -> str | None:
    if sec_uid:
        for rx in (SEC_UID_TO_UID_RE, SEC_UID_TO_UID_BARE_RE):
            for m in rx.finditer(text):
                if m.group("sec") == sec_uid:
                    return m.group("to_uid")
    if unique_id:
        tl = unique_id.lower()
        for rx in (
            UNIQUE_ID_TO_UID_RE,
            UNIQUE_ID_TO_UID_BARE_RE,
            UNIQUE_TO_UID_RE,
            UNIQUE_TO_UID_BARE_RE,
        ):
            for m in rx.finditer(text):
                if m.group("sid").lower() == tl:
                    return m.group("to_uid")
    return None


def _blocks_from_html(html_text: str) -> list[str]:
    blocks = [html_text]
    m = RENDER_DATA_RE.search(html_text)
    if m:
        raw = m.group(1).strip()
        blocks.append(raw)
        try:
            blocks.append(unquote(raw))
        except Exception:
            pass
    return blocks


def _extract_owner_to_uid(
    html_text: str,
    *,
    sec_uid: str | None = None,
    unique_id: str | None = None,
) -> str | None:
    """Return profile owner's to_uid (scoped by sec_uid / unique_id when known)."""
    if sec_uid or unique_id:
        for block in _blocks_from_html(html_text):
            to_uid = _regex_owner_to_uid(block, sec_uid, unique_id)
            if to_uid:
                return to_uid
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            to_uid = _find_owner_to_uid_in_json(data, sec_uid, unique_id)
            if to_uid:
                return to_uid

    if sec_uid and not unique_id:
        for block in _blocks_from_html(html_text):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            to_uid = _find_owner_to_uid_in_json(data, sec_uid, None)
            if to_uid:
                return to_uid

    return None


def extract_uid(
    html_text: str,
    *,
    page_url: str | None = None,
    unique_id: str | None = None,
) -> str:
    """
    Extract the profile owner's to_uid.

    When page_url or unique_id is known, only returns to_uid for that account.
    """
    sec_uid = extract_sec_uid_from_url(page_url)
    if not unique_id:
        unique_id = extract_unique_id_from_url(page_url)
    to_uid = _extract_owner_to_uid(
        html_text, sec_uid=sec_uid, unique_id=unique_id
    )
    if to_uid:
        return to_uid

    # Profile pages often embed to_uid without a sec_uid/unique_id pairing that
    # matches our scoped regex — fall back to page-wide search before failing.
    to_uid = _first_regex_any(TO_UID_REGEXES, html_text)
    if to_uid:
        return to_uid

    m = RENDER_DATA_RE.search(html_text)
    if m:
        raw_block = m.group(1).strip()
        try:
            decoded = unquote(raw_block)
        except Exception:
            decoded = raw_block
        to_uid2 = _first_regex_any(TO_UID_REGEXES, decoded)
        if to_uid2:
            return to_uid2
        try:
            parsed = _walk_find_to_uid(json.loads(decoded))
            if parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        to_uid3 = _first_regex_any(TO_UID_REGEXES, raw_block)
        if to_uid3:
            return to_uid3

    if sec_uid or unique_id:
        raise ExtractError(
            "未在页面中定位到该主页所属用户的 to_uid。"
            "请确认链接/抖音号正确，或页面需登录后再试。"
        )

    raise ExtractError("未在页面中找到 to_uid（可能是动态加载页或页面结构已变更）。")

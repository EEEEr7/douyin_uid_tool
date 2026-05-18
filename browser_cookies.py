"""Read Douyin cookies from locally installed Firefox, Edge, or Chrome."""

from __future__ import annotations

import http.cookiejar

from extract import ExtractError


def _jar_to_parts(jar: http.cookiejar.CookieJar) -> tuple[str, dict[str, str]]:
    parts: list[str] = []
    seen: set[str] = set()
    cookie_dict: dict[str, str] = {}
    for c in jar:
        if not c.name or c.name in seen:
            continue
        if c.value is None:
            continue
        domain = (c.domain or "").lower()
        if "douyin.com" not in domain:
            continue
        seen.add(c.name)
        parts.append(f"{c.name}={c.value}")
        cookie_dict[c.name] = c.value
    return "; ".join(parts), cookie_dict


def _try_browser(load_fn, label: str) -> tuple[str, dict[str, str]]:
    try:
        jar = load_fn(domain_name="douyin.com")
    except Exception as e:
        raise ExtractError(f"读取 {label} Cookie 失败：{e}") from e
    header, cookie_dict = _jar_to_parts(jar)
    if header:
        return header, cookie_dict
    raise ExtractError(f"{label} 中未找到 douyin.com 的 Cookie")


def get_douyin_cookie_bundle() -> tuple[str, dict[str, str]]:
    """
    Return (Cookie header string, name->value dict) for douyin.com.
    Tries Firefox, Edge, then Chrome.
    """
    import browser_cookie3

    errors: list[str] = []
    for load_fn, label in (
        (browser_cookie3.firefox, "Firefox"),
        (browser_cookie3.edge, "Edge"),
        (browser_cookie3.chrome, "Chrome"),
    ):
        try:
            return _try_browser(load_fn, label)
        except ExtractError as e:
            errors.append(str(e))

    detail = "\n".join(errors) if errors else ""
    raise ExtractError(
        "无法从本机浏览器读取抖音登录 Cookie。\n"
        "请先用 Firefox、Edge 或 Chrome 打开 douyin.com 并登录；查询前请关闭对应浏览器窗口。\n"
        + (detail if detail else "")
    )


def get_douyin_cookie_header() -> str:
    return get_douyin_cookie_bundle()[0]


def get_douyin_cookies_dict() -> dict[str, str]:
    return get_douyin_cookie_bundle()[1]

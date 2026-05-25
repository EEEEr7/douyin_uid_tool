"""Resolve Douyin numeric UID from short_id (抖音号) via search API + HTML/headless fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import requests

from browser_cookies import get_douyin_cookie_bundle
from extract import ExtractError, USER_AGENTS, extract_uid, is_likely_dynamic_shell

SEARCH_URLS = (
    "https://www.douyin.com/aweme/v1/web/discover/search/",
    "https://www.douyin.com/aweme/v1/web/search/query/",
)

PROFILE_OTHER_URL = "https://www.douyin.com/aweme/v1/web/user/profile/other/"

IESDOUYIN_INFO_URL = "https://www.iesdouyin.com/web/api/v2/user/info/"

# uniqueId (camelCase) near to_uid — numeric 抖音号 often uses this field name
HTML_UNIQUE_ID_TO_UID_RE = re.compile(
    r'uniqueId\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[^}]{0,1600}?'
    r'to_uid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.DOTALL | re.I,
)
HTML_UNIQUE_ID_TO_UID_BARE_RE = re.compile(
    r'uniqueId\\?"\s*:\s*\\?"(?P<sid>[^"\\]+)\\?"[^}]{0,1600}?'
    r'toUid\\?"\s*:\s*\\?"(?P<to_uid>\d{5,})\\?"',
    re.DOTALL | re.I,
)
PARAM_SETS: tuple[dict[str, str], ...] = (
    {
        "keyword": "",  # filled per request
        "search_channel": "aweme_user_fans",
        "type": "1",
        "device_platform": "webapp",
        "aid": "6383",
    },
    {
        "keyword": "",
        "search_channel": "aweme_user_web",
        "search_source": "normal_search",
        "query_correct_type": "1",
        "is_filter_search": "0",
        "type": "1",
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
    },
)

# Near unique_id in HTML: "unique_id":"xxx" ... "to_uid":123
HTML_TO_UID_NEAR_UNIQUE_RE = re.compile(
    r'"unique_id"\s*:\s*"(?P<sid>[^"]+)"[^}]{0,1200}?"to_uid"\s*:\s*"?(\d{5,})"?',
    re.DOTALL,
)
HTML_TO_UID_NEAR_UNIQUE_ESC_RE = re.compile(
    r'\\"unique_id\\"\s*:\s*\\"(?P<sid>[^\\]+)\\"[^}]{0,1600}?\\"to_uid\\"\s*:\s*\\"?(\d{5,})\\"?',
    re.DOTALL,
)
HTML_TO_UID_BEFORE_UNIQUE_RE = re.compile(
    r'"to_uid"\s*:\s*"?(\d{5,})"?[^}]{0,1200}?"unique_id"\s*:\s*"(?P<sid>[^"]+)"',
    re.DOTALL,
)


def _normalize_short_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ExtractError("请输入抖音号。")
    if s.startswith("@"):
        s = s[1:].strip()
    if "douyin.com" in s or s.startswith("http"):
        raise ExtractError("当前输入像是链接，请粘贴完整主页 URL，或只输入抖音号。")
    if len(s) > 64:
        raise ExtractError("抖音号过长，请检查输入。")
    return s


def _search_page_url(keyword: str) -> str:
    return f"https://www.douyin.com/search/{quote(keyword)}?type=user"


def _profile_page_urls(unique_id: str) -> tuple[str, ...]:
    """Douyin supports @unique_id and /user/{id} profile URLs."""
    safe = quote(unique_id, safe="")
    urls = (
        f"https://www.douyin.com/@{safe}",
        f"https://www.douyin.com/user/@{safe}",
        f"https://www.douyin.com/user/{safe}",
    )
    return urls


def _request_headers(cookie_header: str, referer: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENTS[0],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
        "Cookie": cookie_header,
    }


def _fetch_page(
    url: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    accept_html: bool = False,
    referer: str | None = None,
) -> tuple[str, int, str]:
    headers = _request_headers(cookie_header, referer or "https://www.douyin.com/")
    if accept_html:
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    try:
        resp = requests.get(
            url,
            headers=headers,
            cookies=cookie_dict,
            timeout=12,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        raise ExtractError("请求超时，请稍后重试。") from None
    except requests.exceptions.RequestException as e:
        raise ExtractError(f"请求失败：{e}") from e
    return resp.url or url, resp.status_code, resp.text or ""


def _enrich_params(base: dict[str, str], keyword: str, cookie_dict: dict[str, str]) -> dict[str, str]:
    params = {**base, "keyword": keyword}
    for key in ("msToken", "ttwid"):
        if key in cookie_dict and cookie_dict[key]:
            params.setdefault(key, cookie_dict[key])
    return params


def _pick_uid_from_user(user: dict) -> str | None:
    """Short display uid from API (used when to_uid absent)."""
    info = user.get("user_info") if isinstance(user.get("user_info"), dict) else user
    if not isinstance(info, dict):
        return None
    for key in ("uid", "user_id", "userId"):
        v = info.get(key)
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, int):
            return str(v)
        if isinstance(v, str) and v.isdigit():
            return v
    return None


def _pick_to_uid_from_user(user: dict) -> str | None:
    info = user.get("user_info") if isinstance(user.get("user_info"), dict) else user
    if not isinstance(info, dict):
        return None
    v = info.get("to_uid")
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str) and v.isdigit():
        return v
    return None


def _pick_sec_uid_from_user(user: dict) -> str | None:
    info = user.get("user_info") if isinstance(user.get("user_info"), dict) else user
    if not isinstance(info, dict):
        return None
    for key in ("sec_uid", "secUid"):
        v = info.get(key)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _to_uid_via_sec_uid(
    sec_uid: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    """API often returns sec_uid without to_uid — load /user/{sec_uid} for to_uid."""
    url = f"https://www.douyin.com/user/{sec_uid}"
    try:
        _final, code, text = _fetch_page(
            url,
            cookie_header,
            cookie_dict,
            accept_html=True,
            referer=url,
        )
    except ExtractError:
        return None
    if code != 200:
        return None
    if not is_likely_dynamic_shell(text):
        try:
            return extract_uid(text, page_url=url)
        except ExtractError:
            pass
    if http_only:
        return None
    try:
        from resolve import resolve_uid_headless_browser

        return resolve_uid_headless_browser(url, cookie_header, timeout_ms=75_000)
    except ExtractError:
        return None


def _to_uid_via_unique_id(
    unique_id: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
) -> str | None:
    for url in _profile_page_urls(unique_id):
        try:
            _final, code, text = _fetch_page(
                url,
                cookie_header,
                cookie_dict,
                accept_html=True,
                referer=f"https://www.douyin.com/@{unique_id}",
            )
        except ExtractError:
            continue
        if code != 200:
            continue
        if not is_likely_dynamic_shell(text):
            try:
                return extract_uid(text, unique_id=unique_id, page_url=url)
            except ExtractError:
                continue
    return None


def _resolve_to_uid_for_user(
    user: dict,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    to_uid = _pick_to_uid_from_user(user)
    if to_uid:
        return to_uid
    sec = _pick_sec_uid_from_user(user)
    if sec:
        return _to_uid_via_sec_uid(
            sec, cookie_header, cookie_dict, http_only=http_only
        )
    # API may return uid without to_uid — load @ profile for to_uid
    if _pick_uid_from_user(user):
        for sid in _short_id_candidates(user):
            found = _to_uid_via_unique_id(sid, cookie_header, cookie_dict)
            if found:
                return found
    return None


def _short_id_candidates(user: dict) -> list[str]:
    out: list[str] = []
    sources: list[dict] = []
    if isinstance(user, dict):
        sources.append(user)
        ui = user.get("user_info")
        if isinstance(ui, dict):
            sources.append(ui)
    for src in sources:
        for key in ("unique_id", "uniqueId", "short_id", "display_id"):
            v = src.get(key)
            if v is None:
                continue
            s = str(v).strip()
            if s and s not in out:
                out.append(s)
    return out


def _collect_user_lists(obj: Any, out: list[dict]) -> None:
    if isinstance(obj, dict):
        for key in ("user_list", "users"):
            ul = obj.get(key)
            if isinstance(ul, list):
                for item in ul:
                    if isinstance(item, dict):
                        out.append(item)
        data = obj.get("data")
        if isinstance(data, dict):
            for key in ("user_list", "users"):
                ul = data.get(key)
                if isinstance(ul, list):
                    for item in ul:
                        if isinstance(item, dict):
                            out.append(item)
        elif isinstance(data, list):
            for block in data:
                if isinstance(block, dict):
                    for key in ("user_list", "users"):
                        ul = block.get(key)
                        if isinstance(ul, list):
                            for item in ul:
                                if isinstance(item, dict):
                                    out.append(item)
        for val in obj.values():
            _collect_user_lists(val, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_user_lists(item, out)


def _match_uid_in_list(
    user_list: list[dict],
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    target_lower = target.lower()
    # Exact match
    for item in user_list:
        for sid in _short_id_candidates(item):
            if sid.lower() == target_lower:
                uid = _resolve_to_uid_for_user(
                    item, cookie_header, cookie_dict, http_only=http_only
                )
                if uid:
                    return uid
    # Substring match (second pass)
    for item in user_list:
        for sid in _short_id_candidates(item):
            if target_lower in sid.lower() or sid.lower() in target_lower:
                uid = _resolve_to_uid_for_user(
                    item, cookie_header, cookie_dict, http_only=http_only
                )
                if uid:
                    return uid
    return None


def _parse_api_response(
    data: dict,
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    status = data.get("status_code", data.get("status"))
    if status is not None and status != 0:
        msg = data.get("status_msg") or data.get("message") or "未知错误"
        if "login" in str(msg).lower() or status in (8,):
            raise ExtractError("Cookie 已过期或无效，请用浏览器重新登录 douyin.com 后再试。")
        # Non-fatal: try next param set / fallback
        return None

    user_list: list[dict] = []
    _collect_user_lists(data, user_list)
    if not user_list:
        return None
    return _match_uid_in_list(
        user_list, target, cookie_header, cookie_dict, http_only=http_only
    )


def _try_api_search(
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    referer = _search_page_url(target)
    headers = _request_headers(cookie_header, referer)

    last_http = 0
    for search_url in SEARCH_URLS:
        for param_base in PARAM_SETS:
            params = _enrich_params(param_base, target, cookie_dict)
            try:
                resp = requests.get(
                    search_url,
                    params=params,
                    headers=headers,
                    cookies=cookie_dict,
                    timeout=12,
                )
            except requests.exceptions.Timeout:
                raise ExtractError("搜索请求超时，请稍后重试。") from None
            except requests.exceptions.RequestException as e:
                raise ExtractError(f"搜索请求失败：{e}") from e

            last_http = resp.status_code
            if resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except json.JSONDecodeError:
                continue
            try:
                uid = _parse_api_response(
                    data, target, cookie_header, cookie_dict, http_only=http_only
                )
                if uid:
                    return uid
            except ExtractError:
                raise

    return None


def _uid_from_html_blob(
    html: str,
    target: str,
    *,
    profile_page: bool = False,
    page_url: str | None = None,
) -> str | None:
    target_lower = target.lower()
    for rx in (
        HTML_TO_UID_NEAR_UNIQUE_RE,
        HTML_TO_UID_NEAR_UNIQUE_ESC_RE,
        HTML_TO_UID_BEFORE_UNIQUE_RE,
        HTML_UNIQUE_ID_TO_UID_RE,
        HTML_UNIQUE_ID_TO_UID_BARE_RE,
    ):
        for m in rx.finditer(html):
            sid = m.group("sid")
            if sid.lower() == target_lower:
                return m.group(1)

    # Case-insensitive unique_id in page (profile / search)
    for pat in (
        f'"unique_id":"{target}"',
        f'"unique_id": "{target}"',
        f'"unique_id":"{target_lower}"',
        f'"uniqueId":"{target}"',
        f'"uniqueId": "{target}"',
        f'unique_id\\":\\"{target}\\"',
        f'uniqueId\\":\\"{target}\\"',
    ):
        if pat.lower() in html.lower():
            try:
                return extract_uid(html, unique_id=target, page_url=page_url)
            except ExtractError:
                break

    if profile_page or (page_url and "/search/" in page_url):
        try:
            return extract_uid(html, unique_id=target, page_url=page_url)
        except ExtractError:
            pass

    return None


def _parse_profile_other_json(
    data: dict,
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    user = data.get("user")
    if not isinstance(user, dict):
        user = data.get("user_info") if isinstance(data.get("user_info"), dict) else None
    if not user:
        return None
    for sid in _short_id_candidates({"user_info": user}):
        if sid.lower() == target.lower():
            return _resolve_to_uid_for_user(
                {"user_info": user},
                cookie_header,
                cookie_dict,
                http_only=http_only,
            )
    return None


def _try_profile_other_api(
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    params = {
        "unique_id": target,
        "device_platform": "webapp",
        "aid": "6383",
    }
    for key in ("msToken", "ttwid"):
        if key in cookie_dict:
            params[key] = cookie_dict[key]
    headers = _request_headers(cookie_header, f"https://www.douyin.com/@{target}")
    try:
        resp = requests.get(
            PROFILE_OTHER_URL,
            params=params,
            headers=headers,
            cookies=cookie_dict,
            timeout=12,
        )
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None
    status = data.get("status_code", data.get("status"))
    if status is not None and status != 0:
        return None
    return _parse_profile_other_json(
        data, target, cookie_header, cookie_dict, http_only=http_only
    )


def _try_iesdouyin_resolve(
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
    *,
    http_only: bool = False,
) -> str | None:
    """Resolve numeric/custom 抖音号 via iesdouyin user info → sec_uid → profile to_uid."""
    try:
        resp = requests.get(
            IESDOUYIN_INFO_URL,
            params={"unique_id": target},
            headers=_request_headers(
                cookie_header, f"https://www.douyin.com/user/{target}"
            ),
            cookies=cookie_dict,
            timeout=12,
        )
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None
    status = data.get("status_code")
    if status is not None and status != 0:
        return None
    user = data.get("user_info")
    if not isinstance(user, dict):
        return None
    for key in ("to_uid", "toUid"):
        v = user.get(key)
        if v is not None and str(v).isdigit():
            return str(v)
    sec = user.get("sec_uid") or user.get("secUid")
    if not sec or not isinstance(sec, str):
        return None
    return _to_uid_via_sec_uid(
        sec.strip(), cookie_header, cookie_dict, http_only=http_only
    )


def _try_direct_profile_pages(
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
) -> str | None:
    """Open https://www.douyin.com/@{抖音号} — works when search API returns empty."""
    for url in _profile_page_urls(target):
        try:
            final, code, text = _fetch_page(
                url,
                cookie_header,
                cookie_dict,
                accept_html=True,
                referer=f"https://www.douyin.com/@{target}",
            )
        except ExtractError:
            continue
        if code != 200:
            continue
        if "login" in (final or "").lower() or "passport" in (final or "").lower():
            raise ExtractError(
                "Cookie 已过期，请用浏览器重新登录 douyin.com 后再试。"
            )
        if not is_likely_dynamic_shell(text):
            uid = _uid_from_html_blob(
                text, target, profile_page=True, page_url=url
            )
            if uid:
                return uid
    return None


def _try_headless_profile(
    target: str,
    cookie_header: str,
    *,
    should_cancel: Callable[[], bool] | None = None,
) -> str | None:
    try:
        from resolve import resolve_uid_headless_browser
    except Exception:
        return None
    for url in _profile_page_urls(target):
        if should_cancel and should_cancel():
            raise ExtractError("已取消")
        try:
            uid = resolve_uid_headless_browser(
                url,
                cookie_header,
                timeout_ms=75_000,
                should_cancel=should_cancel,
            )
            if uid:
                return uid
        except ExtractError as e:
            if str(e) == "已取消":
                raise
            continue
    return None


def _try_html_fallback(
    target: str,
    cookie_header: str,
    cookie_dict: dict[str, str],
) -> str | None:
    url = _search_page_url(target)
    referer = url
    try:
        _final, code, text = _fetch_page(
            url,
            cookie_header,
            cookie_dict,
            accept_html=True,
            referer=referer,
        )
    except ExtractError:
        return None
    if code != 200:
        return None
    if "login" in (_final or "").lower() or "passport" in (_final or "").lower():
        raise ExtractError("Cookie 已过期，请用浏览器重新登录 douyin.com 后再试。")
    if is_likely_dynamic_shell(text):
        return None

    return _uid_from_html_blob(text, target, page_url=url)


def _try_headless_fallback(
    target: str,
    cookie_header: str,
    *,
    should_cancel: Callable[[], bool] | None = None,
) -> str | None:
    """Load search page in headless WebEngine; match UID to target short_id."""
    try:
        import sys

        from PySide6.QtCore import QEventLoop, Qt, QTimer, QUrl
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from web_shared import DOUYIN_ORIGIN, SCRIPT_DUMP_JS, inject_douyin_cookies
    except Exception:
        return None

    url = _search_page_url(target)
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(sys.argv)
        owns_app = True

    view = QWebEngineView()
    try:
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    except Exception:
        view.hide()
    view.resize(1, 1)
    view.hide()

    origin = QUrl(DOUYIN_ORIGIN)
    prof = view.page().profile()
    prof.setHttpUserAgent(USER_AGENTS[0])
    inject_douyin_cookies(prof, cookie_header, origin)

    loop = QEventLoop()
    state: dict[str, str | None] = {"uid": None, "err": None}
    attempt = [0]

    def finish_ok(uid: str) -> None:
        state["uid"] = uid
        loop.quit()

    def finish_fail() -> None:
        loop.quit()

    def try_extract() -> None:
        if should_cancel and should_cancel():
            state["err"] = "已取消"
            loop.quit()
            return
        if state["uid"]:
            return
        attempt[0] += 1
        if attempt[0] > 60:
            finish_fail()
            return

        def merge_and_parse(js_dump: object, html: str) -> None:
            blob = ((js_dump if isinstance(js_dump, str) else "") + "\n" + (html or "")).strip()
            uid = _uid_from_html_blob(blob, target, page_url=url)
            if uid:
                finish_ok(uid)
                return
            QTimer.singleShot(650, try_extract)

        def on_html(html: str) -> None:
            view.page().runJavaScript(SCRIPT_DUMP_JS, lambda jd: merge_and_parse(jd, html))

        view.page().toHtml(on_html)

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(finish_fail)
    deadline.start(90_000)

    def on_load_finished(ok: bool) -> None:
        if not ok:
            finish_fail()
            return
        QTimer.singleShot(1200, try_extract)

    view.loadFinished.connect(on_load_finished)
    view.load(QUrl(url))
    loop.exec()
    deadline.stop()
    view.deleteLater()
    if owns_app:
        app.processEvents()

    if state.get("err") == "已取消":
        raise ExtractError("已取消")
    return state["uid"]


def _short_id_not_found_error(target: str) -> ExtractError:
    return ExtractError(
        f"未找到抖音号为「{target}」的用户。\n"
        "请确认抖音号与 App 个人主页显示的完全一致（区分大小写）。\n"
        "抖音号查询需本机浏览器已登录 douyin.com；也可在工具里粘贴 Cookie。\n"
        "若浏览器能打开 https://www.douyin.com/@" + target
        + " ，也可直接粘贴该主页完整链接查询（往往更稳）。"
    )


def _is_auth_extract_error(exc: ExtractError) -> bool:
    msg = str(exc)
    return any(k in msg for k in ("Cookie", "过期", "登录"))


def lookup_uid_by_short_id_http(
    short_id: str, manual_cookie: str | None = None
) -> str:
    """HTTP/API only — safe to call from a QThread worker."""
    target = _normalize_short_id(short_id)
    cookie_header, cookie_dict = get_douyin_cookie_bundle(manual_cookie)

    uid = _try_iesdouyin_resolve(
        target, cookie_header, cookie_dict, http_only=True
    )
    if uid:
        return uid

    uid = _try_direct_profile_pages(target, cookie_header, cookie_dict)
    if uid:
        return uid

    uid = _try_profile_other_api(
        target, cookie_header, cookie_dict, http_only=True
    )
    if uid:
        return uid

    uid = _try_api_search(
        target, cookie_header, cookie_dict, http_only=True
    )
    if uid:
        return uid

    uid = _try_html_fallback(target, cookie_header, cookie_dict)
    if uid:
        return uid

    raise _short_id_not_found_error(target)


def lookup_uid_by_short_id_headless(
    short_id: str,
    manual_cookie: str | None = None,
    *,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    """Headless WebEngine only — must run on the GUI main thread."""
    if should_cancel and should_cancel():
        raise ExtractError("已取消")
    target = _normalize_short_id(short_id)
    cookie_header, _cookie_dict = get_douyin_cookie_bundle(manual_cookie)

    uid = _try_headless_profile(target, cookie_header, should_cancel=should_cancel)
    if uid:
        return uid
    if should_cancel and should_cancel():
        raise ExtractError("已取消")

    uid = _try_headless_fallback(target, cookie_header, should_cancel=should_cancel)
    if uid:
        return uid

    raise _short_id_not_found_error(target)


def lookup_uid_by_short_id(
    short_id: str, manual_cookie: str | None = None
) -> str:
    """Look up numeric UID by Douyin short_id (抖音号). CLI: HTTP then headless."""
    try:
        return lookup_uid_by_short_id_http(short_id, manual_cookie)
    except ExtractError as e:
        if _is_auth_extract_error(e):
            raise
    return lookup_uid_by_short_id_headless(short_id, manual_cookie)

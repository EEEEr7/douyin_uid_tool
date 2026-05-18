"""Resolve Douyin numeric UID: HTTP first, then headless Qt WebEngine if needed."""

from __future__ import annotations

import sys

from extract import (
    ExtractError,
    extract_uid,
    fetch_html,
    is_likely_dynamic_shell,
    is_user_profile_url,
)


def resolve_uid(url: str, cookie: str | None, *, http_only: bool = False) -> str:
    """Return UID string. Raises ExtractError on failure."""
    url = url.strip()
    _final, _code, text = fetch_html(url, cookie)

    if not http_only and is_likely_dynamic_shell(text):
        return _resolve_uid_webengine(url, cookie)

    try:
        return extract_uid(text, page_url=url)
    except ExtractError:
        if http_only:
            raise
        if text and is_user_profile_url(url):
            return _resolve_uid_webengine(url, cookie)
        raise


def _resolve_uid_webengine(url: str, cookie: str | None, *, timeout_ms: int = 120_000) -> str:
    try:
        from PySide6.QtCore import QEventLoop, Qt, QTimer, QUrl
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except Exception as e:  # pragma: no cover
        raise ExtractError(f"无界面解析需要 Qt WebEngine：{e}") from e

    from web_shared import DOUYIN_ORIGIN, SCRIPT_DUMP_JS, inject_douyin_cookies

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
    prof.setHttpUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    inject_douyin_cookies(prof, cookie, origin)

    loop = QEventLoop()
    state: dict[str, str | None] = {"uid": None, "err": None}
    attempt = [0]
    max_attempts = 80

    def finish_fail(msg: str) -> None:
        if state["err"] is None:
            state["err"] = msg
        loop.quit()

    def finish_ok(uid: str) -> None:
        state["uid"] = uid
        loop.quit()

    def try_extract() -> None:
        if state["uid"] or state["err"]:
            return
        attempt[0] += 1
        if attempt[0] > max_attempts:
            finish_fail("多次尝试仍未提取到 UID（请检查网络或稍后再试）")
            return

        def merge_and_parse(js_dump: object, html: str) -> None:
            dump = js_dump if isinstance(js_dump, str) else ""
            blob = (dump + "\n" + (html or "")).strip()
            try:
                finish_ok(extract_uid(blob, page_url=url))
            except ExtractError:
                QTimer.singleShot(650, try_extract)
            except Exception as e:
                finish_fail(f"解析异常：{e}")

        def on_html(html: str) -> None:
            view.page().runJavaScript(SCRIPT_DUMP_JS, lambda jd: merge_and_parse(jd, html))

        view.page().toHtml(on_html)

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(lambda: finish_fail(f"整体超时（{timeout_ms // 1000}s），请检查网络后重试"))
    deadline.start(timeout_ms)

    def on_load_finished(ok: bool) -> None:
        if not ok:
            finish_fail("内置浏览器加载页面失败")
            return
        QTimer.singleShot(1200, try_extract)

    view.loadFinished.connect(on_load_finished)
    view.load(QUrl(url))

    loop.exec()
    deadline.stop()

    view.deleteLater()
    if owns_app:
        app.processEvents()

    if state["err"]:
        raise ExtractError(state["err"])
    uid = state["uid"]
    if uid:
        return uid
    raise ExtractError("无界面解析未返回 UID")


def resolve_uid_headless_browser(url: str, cookie: str | None = None, *, timeout_ms: int = 120_000) -> str:
    """Public alias used by GUI (main-thread headless WebEngine)."""
    return _resolve_uid_webengine(url, cookie, timeout_ms=timeout_ms)

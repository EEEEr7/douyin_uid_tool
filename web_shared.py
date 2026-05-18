"""Shared Qt WebEngine helpers (GUI + CLI headless)."""

from __future__ import annotations

from PySide6.QtNetwork import QNetworkCookie

DOUYIN_ORIGIN = "https://www.douyin.com"

SCRIPT_DUMP_JS = r"""
(function () {
  try {
    var html = document.documentElement ? document.documentElement.outerHTML : "";
    var buf = [];
    var els = document.querySelectorAll("script");
    for (var i = 0; i < els.length; i++) {
      var t = els[i].textContent || els[i].innerHTML || "";
      if (t) buf.push(t);
    }
    return html + "\n___SCRIPT_TEXT_DUMP___\n" + buf.join("\n");
  } catch (e) {
    return "JS_DUMP_ERROR:" + String(e);
  }
})();
"""


def inject_douyin_cookies(profile, cookie_header: str | None, origin) -> None:
    """Apply `Cookie` header pairs to QtWebEngine for douyin.com."""
    if not cookie_header or not str(cookie_header).strip():
        return
    store = profile.cookieStore()
    for part in str(cookie_header).split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        c = QNetworkCookie(name.encode("utf-8", errors="ignore"), value.encode("utf-8", errors="ignore"))
        c.setDomain(".douyin.com")
        c.setPath("/")
        c.setSecure(True)
        store.setCookie(c, origin)

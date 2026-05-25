"""PySide6 GUI: Douyin profile URL → numeric UID (minimal layout).

Fast path uses HTTP; dynamic pages fall back to headless Qt WebEngine on the GUI thread.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QClipboard, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from extract import (
    ExtractError,
    extract_uid,
    fetch_html,
    is_likely_dynamic_shell,
    is_user_profile_url,
)


# Rose palette (UI UX Pro Max); layout kept minimal
DS_PRIMARY = "#E11D48"
DS_SECONDARY = "#FB7185"
DS_CTA = "#2563EB"
DS_BG = "#FFF1F2"
DS_TEXT = "#881337"
DS_TEXT_MUTED = "#9F1239"
DS_CARD = "#FFFFFF"
DS_BORDER = "#FECDD3"
DS_RESULT_BG = "#FFF5F5"

APP_STYLE = f"""
QMainWindow {{
    background-color: {DS_BG};
}}
QWidget#card {{
    background-color: {DS_CARD};
    border-radius: 12px;
    border: 1px solid {DS_BORDER};
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 700;
    color: {DS_TEXT};
}}
QLabel#subtitle {{
    font-size: 12px;
    color: {DS_TEXT_MUTED};
}}
QLabel#sectionLabel {{
    font-size: 12px;
    color: {DS_TEXT_MUTED};
}}
QLabel#hint {{
    font-size: 12px;
    color: {DS_TEXT_MUTED};
    margin-top: 6px;
}}
QLabel#hint[status="loading"] {{
    color: {DS_CTA};
}}
QLabel#hint[status="ok"] {{
    color: #047857;
}}
QLabel#hint[status="err"] {{
    color: #B91C1C;
}}
QLineEdit {{
    padding: 10px 12px;
    border: 1px solid {DS_BORDER};
    border-radius: 8px;
    font-size: 13px;
    background: {DS_RESULT_BG};
    color: {DS_TEXT};
    selection-background-color: {DS_SECONDARY};
}}
QLineEdit:focus {{
    border-color: {DS_PRIMARY};
    background: #FFFFFF;
}}
QPushButton#primary {{
    background-color: {DS_PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 9px 22px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: #BE123C; }}
QPushButton#primary:disabled {{ background-color: #FDA4AF; }}
QPushButton#secondary {{
    background-color: #FFFFFF;
    color: {DS_TEXT};
    border: 1px solid {DS_BORDER};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}}
QPushButton#secondary:hover {{
    border-color: {DS_SECONDARY};
    background-color: #FFF5F5;
}}
QPushButton#secondary:disabled {{ color: #FDA4AF; }}
QTextEdit#resultBox {{
    border: 1px solid {DS_BORDER};
    border-radius: 8px;
    padding: 12px 14px;
    background-color: {DS_RESULT_BG};
    font-size: 18px;
    font-weight: 600;
    color: {DS_TEXT};
    selection-background-color: {DS_PRIMARY};
}}
"""


def _pick_font(
    families: tuple[str, ...],
    size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    available = set(QFontDatabase.families())
    for name in families:
        if name in available:
            font = QFont(name, size)
            font.setWeight(weight)
            return font
    font = QFont("Segoe UI", size)
    font.setWeight(weight)
    return font


def _apply_typography(app: QApplication, window: QMainWindow) -> None:
    body_font = _pick_font(("Segoe UI", "Microsoft YaHei UI"), 13)
    mono_font = _pick_font(
        ("Consolas", "Cascadia Mono", "JetBrains Mono"),
        18,
        QFont.Weight.Bold,
    )
    app.setFont(body_font)
    if getattr(window, "result_box", None) is not None:
        window.result_box.setFont(mono_font)


def _is_profile_url(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("http://") or t.startswith("https://")


APP_USER_MODEL_ID = "DouyinUIDExtractor.DouyinUIDTool.1"


def _init_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def _apply_windows_hwnd_icon(window: QMainWindow, icon_path: Path) -> None:
    if sys.platform != "win32" or not icon_path.is_file():
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        if hwnd == 0:
            return
        path = str(icon_path.resolve())
        lr_loadfromfile = 0x0010
        image_icon = 1
        wm_seticon = 0x0080
        load = ctypes.windll.user32.LoadImageW
        send = ctypes.windll.user32.SendMessageW
        for size, kind in ((16, 0), (32, 0), (48, 1), (256, 1)):
            handle = load(None, path, image_icon, size, size, lr_loadfromfile)
            if handle:
                send(hwnd, wm_seticon, 0 if size <= 32 else 1, handle)
    except (AttributeError, OSError, ValueError):
        pass


def _app_icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for name in ("app_icon.ico", "app_icon.png"):
        path = base / name
        if path.is_file():
            return path
    return base / "app_icon.ico"


def _apply_app_icon(app: QApplication, window: QMainWindow | None = None) -> None:
    icon_path = _app_icon_path()
    if not icon_path.is_file():
        return
    icon = QIcon(str(icon_path))
    app.setWindowIcon(icon)
    if window is not None:
        window.setWindowIcon(icon)
        QTimer.singleShot(0, partial(_apply_windows_hwnd_icon, window, icon_path))


class Worker(QObject):
    finished_ok = Signal(str)
    finished_err = Signal(str)
    need_browser = Signal(str)
    need_headless_short_id = Signal(str)

    def __init__(self, query: str) -> None:
        super().__init__()
        self._query = query.strip()

    def _cookie_header(self) -> str | None:
        try:
            from browser_cookies import get_douyin_cookie_bundle

            return get_douyin_cookie_bundle(None)[0]
        except ExtractError:
            return None

    @Slot()
    def run(self) -> None:
        if not _is_profile_url(self._query):
            try:
                from short_id_lookup import (
                    _is_auth_extract_error,
                    lookup_uid_by_short_id_http,
                )

                uid = lookup_uid_by_short_id_http(self._query)
                self.finished_ok.emit(uid)
            except ExtractError as e:
                if _is_auth_extract_error(e):
                    self.finished_err.emit(str(e))
                    return
                self.need_headless_short_id.emit(self._query)
            except Exception as e:  # pragma: no cover
                self.finished_err.emit(f"发生意外错误：{e}")
            return

        url = self._query
        text = ""
        cookie = self._cookie_header()
        try:
            _final, _code, text = fetch_html(url, cookie)
            if is_likely_dynamic_shell(text):
                self.need_browser.emit(url)
                return
            uid = extract_uid(text, page_url=url)
            self.finished_ok.emit(uid)
        except ExtractError as e:
            if text and is_user_profile_url(url):
                self.need_browser.emit(url)
                return
            self.finished_err.emit(str(e))
        except Exception as e:  # pragma: no cover
            self.finished_err.emit(f"发生意外错误：{e}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("抖音 UID 提取")
        self.setMinimumSize(640, 400)
        self.resize(760, 480)

        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._cancel_requested = False
        self._pending_headless_url: str | None = None
        self._pending_headless_short_id: str | None = None
        self._parse_elapsed_sec = 0
        self._parse_timer = QTimer(self)
        self._parse_timer.setInterval(1000)
        self._parse_timer.timeout.connect(self._tick_parse_timer)

        shell = QWidget(self)
        self.setCentralWidget(shell)
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        card = QWidget()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(12)

        self.title_label = QLabel("抖音 UID 提取")
        self.title_label.setObjectName("title")
        self.sub_label = QLabel(
            "输入抖音号或主页链接。查抖音号需已登录 douyin.com；失败时可粘贴主页链接。"
        )
        self.sub_label.setObjectName("subtitle")
        self.sub_label.setWordWrap(True)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("抖音号或主页链接 https://www.douyin.com/user/...")
        self.url_edit.returnPressed.connect(self._on_query)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.query_btn = QPushButton("查询")
        self.query_btn.setObjectName("primary")
        self.cancel_btn = QPushButton("取消查询")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setEnabled(False)
        self.copy_btn = QPushButton("复制结果")
        self.copy_btn.setObjectName("secondary")
        self.copy_btn.setEnabled(False)
        row.addWidget(self.query_btn)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()

        self.result_label = QLabel("to_uid")
        self.result_label.setObjectName("sectionLabel")

        self.result_box = QTextEdit()
        self.result_box.setObjectName("resultBox")
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("查询成功后在此显示")
        self.result_box.setMinimumHeight(100)
        self.result_box.setMaximumHeight(200)
        self.result_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("hint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setMinimumHeight(22)

        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.sub_label)
        card_layout.addWidget(self.url_edit)
        card_layout.addLayout(row)
        card_layout.addWidget(self.result_label)
        card_layout.addWidget(self.result_box)
        card_layout.addWidget(self.hint_label)

        outer.addWidget(card)
        outer.addStretch()

        shell.setStyleSheet(APP_STYLE)

        self.query_btn.clicked.connect(self._on_query)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.copy_btn.clicked.connect(self._on_copy)
        self._set_hint("就绪", "ok")

    def _set_hint(self, text: str, status: str = "") -> None:
        self.hint_label.setText(text)
        if status:
            self.hint_label.setProperty("status", status)
        else:
            self.hint_label.setProperty("status", "")
        self.hint_label.style().unpolish(self.hint_label)
        self.hint_label.style().polish(self.hint_label)

    def _format_elapsed(self) -> str:
        minutes, seconds = divmod(self._parse_elapsed_sec, 60)
        return f"{minutes}:{seconds:02d}"

    def _update_parsing_hint(self) -> None:
        self._set_hint(f"解析中 {self._format_elapsed()}", "loading")

    def _start_parse_timer(self) -> None:
        self._parse_elapsed_sec = 0
        self._update_parsing_hint()
        self._parse_timer.start()

    def _ensure_parse_timer(self) -> None:
        if not self._parse_timer.isActive():
            self._update_parsing_hint()
        self._parse_timer.start()

    def _stop_parse_timer(self) -> str:
        self._parse_timer.stop()
        return self._format_elapsed()

    @Slot()
    def _tick_parse_timer(self) -> None:
        self._parse_elapsed_sec += 1
        self._update_parsing_hint()

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def _set_busy(self, busy: bool) -> None:
        self.query_btn.setEnabled(not busy)
        self.url_edit.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        if busy:
            self.copy_btn.setEnabled(False)
        else:
            self.copy_btn.setEnabled(bool(self.result_box.toPlainText().strip()))

    def _disconnect_worker(self) -> None:
        worker = self._worker
        thread = self._thread
        if worker is None:
            return
        for signal, slot in (
            (worker.finished_ok, self._on_success),
            (worker.finished_err, self._on_error),
            (worker.need_browser, self._remember_headless_url),
            (worker.need_headless_short_id, self._remember_headless_short_id),
        ):
            try:
                signal.disconnect(slot)
            except RuntimeError:
                pass
        if thread is not None:
            for signal in (
                worker.finished_ok,
                worker.finished_err,
                worker.need_browser,
                worker.need_headless_short_id,
            ):
                try:
                    signal.disconnect(thread.quit)
                except RuntimeError:
                    pass

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
            self._worker = None

    @Slot()
    def _on_cancel(self) -> None:
        self._cancel_requested = True
        self._pending_headless_url = None
        self._pending_headless_short_id = None
        self._disconnect_worker()
        self._cleanup_thread()
        self._stop_parse_timer()
        self._set_busy(False)
        self._set_hint("已取消", "")

    @Slot()
    def _on_query(self) -> None:
        self._cancel_requested = False
        self._cleanup_thread()
        query = self.url_edit.text().strip()
        if not query:
            self._set_hint("请先输入抖音号或主页链接", "err")
            return

        self.result_box.clear()
        self.copy_btn.setEnabled(False)
        self._start_parse_timer()
        self._set_busy(True)

        self._thread = QThread()
        self._worker = Worker(query)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.finished_err.connect(self._on_error)
        self._worker.need_browser.connect(self._remember_headless_url)
        self._worker.need_headless_short_id.connect(self._remember_headless_short_id)
        self._worker.finished_ok.connect(self._thread.quit)
        self._worker.finished_err.connect(self._thread.quit)
        self._worker.need_browser.connect(self._thread.quit)
        self._worker.need_headless_short_id.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    @Slot(str)
    def _on_success(self, uid: str) -> None:
        if self._cancel_requested:
            return
        elapsed = self._stop_parse_timer()
        self.result_box.setPlainText(uid)
        self._set_busy(False)
        self._set_hint(f"查询完成（用时 {elapsed}）", "ok")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        if self._cancel_requested:
            return
        self._stop_parse_timer()
        self._set_busy(False)
        self._set_hint(message, "err")
        if message != "已取消":
            QMessageBox.warning(self, "查询失败", message)

    @Slot(str)
    def _remember_headless_url(self, url: str) -> None:
        self._pending_headless_url = url

    @Slot(str)
    def _remember_headless_short_id(self, short_id: str) -> None:
        self._pending_headless_short_id = short_id

    @Slot()
    def _on_thread_finished(self) -> None:
        if self._cancel_requested:
            self._pending_headless_url = None
            self._pending_headless_short_id = None
            self._thread = None
            self._worker = None
            return

        pending_url = self._pending_headless_url
        pending_short_id = self._pending_headless_short_id
        self._pending_headless_url = None
        self._pending_headless_short_id = None
        self._thread = None
        self._worker = None

        if pending_url or pending_short_id:
            self.result_box.clear()
            self.copy_btn.setEnabled(False)
            self._ensure_parse_timer()
            self._set_busy(True)
            if pending_url:
                QTimer.singleShot(0, partial(self._run_headless_resolve, pending_url))
            else:
                assert pending_short_id is not None
                QTimer.singleShot(
                    0, partial(self._run_headless_short_id, pending_short_id)
                )
            return

        self._set_busy(False)

    def _cookie_for_headless(self) -> str | None:
        from browser_cookies import get_douyin_cookie_bundle

        try:
            cookie, _cd = get_douyin_cookie_bundle(None)
            return cookie
        except ExtractError:
            return None

    def _run_headless_resolve(self, url: str) -> None:
        if self._cancel_requested:
            self._stop_parse_timer()
            self._set_busy(False)
            return
        self._set_busy(True)
        try:
            from resolve import resolve_uid_headless_browser

            uid = resolve_uid_headless_browser(
                url, self._cookie_for_headless(), should_cancel=self._is_cancelled
            )
            if self._cancel_requested:
                return
            elapsed = self._stop_parse_timer()
            self.result_box.setPlainText(uid)
            self._set_busy(False)
            self._set_hint(f"查询完成（用时 {elapsed}）", "ok")
        except ExtractError as e:
            if self._cancel_requested or str(e) == "已取消":
                self._stop_parse_timer()
                self._set_busy(False)
                self._set_hint("已取消", "")
                return
            self._stop_parse_timer()
            self._set_busy(False)
            self._set_hint(str(e), "err")
            QMessageBox.warning(self, "查询失败", str(e))
        finally:
            if self._cancel_requested:
                self._stop_parse_timer()
                self._set_busy(False)

    def _run_headless_short_id(self, short_id: str) -> None:
        if self._cancel_requested:
            self._stop_parse_timer()
            self._set_busy(False)
            return
        self._set_busy(True)
        try:
            from short_id_lookup import lookup_uid_by_short_id_headless

            uid = lookup_uid_by_short_id_headless(
                short_id, should_cancel=self._is_cancelled
            )
            if self._cancel_requested:
                return
            elapsed = self._stop_parse_timer()
            self.result_box.setPlainText(uid)
            self._set_busy(False)
            self._set_hint(f"查询完成（用时 {elapsed}）", "ok")
        except ExtractError as e:
            if self._cancel_requested or str(e) == "已取消":
                self._stop_parse_timer()
                self._set_busy(False)
                self._set_hint("已取消", "")
                return
            self._stop_parse_timer()
            self._set_busy(False)
            self._set_hint(str(e), "err")
            QMessageBox.warning(self, "查询失败", str(e))
        finally:
            if self._cancel_requested:
                self._stop_parse_timer()
                self._set_busy(False)

    @Slot()
    def _on_copy(self) -> None:
        text = self.result_box.toPlainText().strip()
        if not text:
            self._set_hint("暂无可复制内容", "err")
            return
        clip = QApplication.clipboard()
        assert clip is not None
        clip.setText(text, QClipboard.Clipboard)
        self._set_hint("已复制到剪贴板", "ok")

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        icon_path = _app_icon_path()
        if icon_path.is_file():
            _apply_windows_hwnd_icon(self, icon_path)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._parse_timer.stop()
        self._cleanup_thread()
        super().closeEvent(event)


def main() -> None:
    _init_windows_app_user_model_id()
    app = QApplication(sys.argv)
    win = MainWindow()
    _apply_typography(app, win)
    _apply_app_icon(app, win)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""PySide6 GUI: Douyin profile URL → numeric UID (minimal layout).

Fast path uses HTTP; dynamic pages fall back to headless Qt WebEngine on the GUI thread.
"""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QClipboard, QFont
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


APP_STYLE = """
QMainWindow { background-color: #eef2f7; }
QWidget#card {
    background-color: #ffffff;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
}
QLabel#title {
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#subtitle {
    font-size: 12px;
    color: #64748b;
}
QLabel#hint {
    font-size: 12px;
    color: #64748b;
    margin-top: 10px;
    padding-top: 2px;
}
QLineEdit {
    padding: 11px 14px;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    font-size: 13px;
    background: #f8fafc;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus {
    border-color: #3b82f6;
    background: #ffffff;
}
QPushButton#primary {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 26px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #1d4ed8; }
QPushButton#primary:pressed { background-color: #1e40af; }
QPushButton#primary:disabled { background-color: #93c5fd; color: #e2e8f0; }
QPushButton#secondary {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#secondary:hover { background-color: #f1f5f9; }
QPushButton#secondary:disabled { color: #94a3b8; border-color: #e2e8f0; }
QTextEdit {
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 14px 16px;
    background-color: #f8fafc;
    font-size: 20px;
    font-weight: 600;
    color: #0f172a;
}
"""


def _is_profile_url(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("http://") or t.startswith("https://")


class Worker(QObject):
    finished_ok = Signal(str)
    finished_err = Signal(str)
    need_browser = Signal(str)

    def __init__(self, query: str) -> None:
        super().__init__()
        self._query = query.strip()

    @Slot()
    def run(self) -> None:
        if not _is_profile_url(self._query):
            try:
                from short_id_lookup import lookup_uid_by_short_id

                uid = lookup_uid_by_short_id(self._query)
                self.finished_ok.emit(uid)
            except ExtractError as e:
                self.finished_err.emit(str(e))
            except Exception as e:  # pragma: no cover
                self.finished_err.emit(f"发生意外错误：{e}")
            return

        url = self._query
        text = ""
        try:
            _final, _code, text = fetch_html(url, None)
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
        self._pending_headless_url: str | None = None

        shell = QWidget(self)
        self.setCentralWidget(shell)
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(0)

        card = QWidget()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        title = QLabel("抖音 UID 提取")
        title.setObjectName("title")
        sub = QLabel("输入抖音号或粘贴个人主页链接，点击查询即可")
        sub.setObjectName("subtitle")

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("抖音号（如 abc123）或主页链接 https://www.douyin.com/user/...")
        self.url_edit.returnPressed.connect(self._on_query)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.query_btn = QPushButton("查询")
        self.query_btn.setObjectName("primary")
        self.copy_btn = QPushButton("复制结果")
        self.copy_btn.setObjectName("secondary")
        self.copy_btn.setEnabled(False)
        row.addWidget(self.query_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()

        out_lab = QLabel("to_uid")
        out_lab.setObjectName("subtitle")

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("查询成功后在此显示")
        # Avoid stretch stealing vertical space: shrinking window used to crush hint_label,
        # making status text overlap / look misaligned with the UID box.
        self.result_box.setMinimumHeight(108)
        self.result_box.setMaximumHeight(220)
        self.result_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("hint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setMinimumHeight(26)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        card_layout.addWidget(title)
        card_layout.addWidget(sub)
        card_layout.addWidget(self.url_edit)
        card_layout.addLayout(row)
        card_layout.addWidget(out_lab)
        card_layout.addWidget(self.result_box)
        card_layout.addWidget(self.hint_label)

        outer.addWidget(card)
        outer.addStretch()

        shell.setStyleSheet(APP_STYLE)

        mono = QFont("Segoe UI", 16)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setBold(True)
        self.result_box.setFont(mono)

        self.query_btn.clicked.connect(self._on_query)
        self.copy_btn.clicked.connect(self._on_copy)
        self.hint_label.setText("就绪")

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
            self._worker = None

    @Slot()
    def _on_query(self) -> None:
        self._cleanup_thread()
        query = self.url_edit.text().strip()
        if not query:
            self.hint_label.setText("请先输入抖音号或主页链接")
            return

        self.result_box.clear()
        self.copy_btn.setEnabled(False)
        self.hint_label.setText("解析中")
        self.query_btn.setEnabled(False)
        self.url_edit.setEnabled(False)

        self._thread = QThread()
        self._worker = Worker(query)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.finished_err.connect(self._on_error)
        self._worker.need_browser.connect(self._remember_headless)
        self._worker.finished_ok.connect(self._thread.quit)
        self._worker.finished_err.connect(self._thread.quit)
        self._worker.need_browser.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    @Slot(str)
    def _on_success(self, uid: str) -> None:
        self.result_box.setPlainText(uid)
        self.copy_btn.setEnabled(True)
        self.hint_label.setText("完成")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.hint_label.setText(message)
        QMessageBox.warning(self, "查询失败", message)

    @Slot(str)
    def _remember_headless(self, url: str) -> None:
        self._pending_headless_url = url

    @Slot()
    def _on_thread_finished(self) -> None:
        pending = self._pending_headless_url
        self._pending_headless_url = None
        self.query_btn.setEnabled(True)
        self.url_edit.setEnabled(True)
        self._thread = None
        self._worker = None
        if pending:
            self.result_box.clear()
            self.copy_btn.setEnabled(False)
            self.hint_label.setText("解析中")
            QTimer.singleShot(0, partial(self._run_headless_resolve, pending))

    def _run_headless_resolve(self, url: str) -> None:
        self.query_btn.setEnabled(False)
        self.url_edit.setEnabled(False)
        try:
            from resolve import resolve_uid_headless_browser

            uid = resolve_uid_headless_browser(url, None)
            self.result_box.setPlainText(uid)
            self.copy_btn.setEnabled(True)
            self.hint_label.setText("完成")
        except ExtractError as e:
            self.hint_label.setText(str(e))
            QMessageBox.warning(self, "查询失败", str(e))
        finally:
            self.query_btn.setEnabled(True)
            self.url_edit.setEnabled(True)

    @Slot()
    def _on_copy(self) -> None:
        text = self.result_box.toPlainText().strip()
        if not text:
            self.hint_label.setText("暂无可复制内容")
            return
        clip = QApplication.clipboard()
        assert clip is not None
        clip.setText(text, QClipboard.Clipboard)
        self.hint_label.setText("已复制到剪贴板")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._cleanup_thread()
        super().closeEvent(event)


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

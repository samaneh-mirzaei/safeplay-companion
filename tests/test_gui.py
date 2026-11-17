"""Regression checks for the redesigned controls, without player or network IO."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox, QPushButton, QMessageBox
from safeplay.storage import Store
import sqlite3
from safeplay.gui import MainWindow, MpvWorker
from safeplay.models import Movie, Scene


def application():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    for name in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
    return app


def test_scene_controls_and_episode_change(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "ui.db")
    try:
        window.movie = Movie("Episode", 2025, "test", 600, "test", [
            Scene("one", 30, 40, "violence", "test", "verified")])
        window.store.save_guide(window.movie)
        window.duration = 600
        window.confirmed = True
        window.filter_boxes["violence"].setChecked(True)
        window.auto_skip.setChecked(True)
        window._save_settings()
        assert "ready" in window.skip_label.text()
        assert window.worker.engine.enabled
        assert window.scene_table.item(0, 6).text() == "Yes"
        window.scene_table.item(0, 5).setCheckState(Qt.Unchecked)
        assert not window.store.load_guide("test").scenes[0].enabled
        assert window.scene_table.item(0, 6).text() == "No"
        window.media_type.setCurrentIndex(1)
        assert window.season.isEnabled() and window.episode.isEnabled()
        assert window.movie is None and not window.confirmed
    finally:
        window.close()


def test_compact_layout_keeps_controls_reachable(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "ui.db")
    try:
        window.resize(600, 760)
        window.show()
        app.processEvents()
        app.processEvents()
        assert window.width() == 600
        for index in (0, 2):
            window.tabs.setCurrentIndex(index)
            app.processEvents()
            area = window.tabs.widget(index)
            assert area.horizontalScrollBar().maximum() == 0
            assert area.verticalScrollBar().maximum() > 0
    finally:
        window.close()


def test_desktop_dashboard_fits_viewport(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "desktop.db")
    try:
        window.resize(1180, 800)
        window.show()
        for _ in range(4): app.processEvents()
        area = window.tabs.widget(0)
        assert area.horizontalScrollBar().maximum() == 0
        assert area.verticalScrollBar().maximum() == 0
        window._status("Disconnected: No reachable mpv IPC pipe. Restart mpv to load mpv.conf, or enable a shared IPC pipe in Syncplay Player Arguments.")
        window.movie_label.setText("Movie: Eşref Rüya — S01E03 (2025)")
        window.guide_label.setText("Guide: 24 scenes; 18 with usable times; edition confirmation required")
        window.media_type.setCurrentIndex(1)
        for _ in range(4): app.processEvents()
        assert area.verticalScrollBar().maximum() == 0
        for control in (window.title, window.year, window.search, window.media_type,
                        window.season, window.episode, window.confirm, window.all_filters,
                        *window.filter_boxes.values()):
            point = control.mapTo(area.viewport(), QPoint(0, 0))
            assert point.x() >= 0 and point.y() >= 0
            assert point.x() + control.width() <= area.viewport().width()
            assert point.y() + control.height() <= area.viewport().height()
        assert window.attribution.isVisible()
        assert window.attribution.openExternalLinks()
        assert 'href="https://www.doesthedogdie.com"' in window.attribution.text()
        assert "Powered by DoesTheDogDie.com" in window.attribution.text()
    finally:
        window.close()


def test_desktop_settings_fit_and_attribution_remains_visible(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "settings.db")
    try:
        window.resize(1180, 800)
        window.show()
        window.tabs.setCurrentIndex(2)
        for _ in range(4): app.processEvents()
        area = window.tabs.widget(2)
        assert area.horizontalScrollBar().maximum() == 0
        assert area.verticalScrollBar().maximum() == 0
        for control in (window.pipe, window.api_key, window.auto_connect,
                        window.auto_skip, window.margin, window.language, window.startup,
                        window.saved_label):
            point = control.mapTo(area.viewport(), QPoint(0, 0))
            assert point.x() >= 0 and point.y() >= 0
            assert point.x() + control.width() <= area.viewport().width()
            assert point.y() + control.height() <= area.viewport().height()
        for index in (0, 1, 2, 3):
            window.tabs.setCurrentIndex(index)
            app.processEvents()
            assert window.attribution.isVisible()
    finally:
        window.close()


def test_activity_preserves_plain_event_content(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "activity.db")
    try:
        detail = 'A <movie> & a file\nSecond line with "quotes"'
        window._log("error", detail)
        timestamp = window.store.recent()[0][0]
        rendered = window.log_box.toPlainText()
        assert detail in rendered
        assert timestamp in rendered
        assert "Error" in rendered
        assert window.activity_empty.isHidden()
    finally:
        window.close()


def test_numeric_clicks_startup_selection_and_restart(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    path = tmp_path / "settings-restart.db"
    window = MainWindow(path)
    window.show(); app.processEvents()
    try:
        window.media_type.setCurrentIndex(1)
        for control, tab in ((window.year, 0), (window.season, 0), (window.episode, 0), (window.margin, 2)):
            window.tabs.setCurrentIndex(tab); app.processEvents()
            initial = control.value()
            option = QStyleOptionSpinBox(); control.initStyleOption(option)
            for part, direction in ((QStyle.SC_SpinBoxUp, 1), (QStyle.SC_SpinBoxDown, -1)):
                rect = control.style().subControlRect(QStyle.CC_SpinBox, option, part, control)
                QTest.mouseClick(control, Qt.LeftButton, pos=rect.center())
                assert control.value() > initial if direction == 1 else abs(control.value() - initial) < .001
        window.startup.setFocus()
        QTest.keyClick(window.startup, Qt.Key_Down)
        assert window.startup.currentIndex() == 1
        save = next(b for b in window.findChildren(QPushButton) if b.text() == "Save settings")
        QTest.mouseClick(save, Qt.LeftButton)
        assert window.store.preference("startup") == 1
    finally:
        window.close()
    reopened = MainWindow(path)
    try:
        assert reopened.startup.currentIndex() == 1
        reopened.show_startup_window(); app.processEvents()
        assert reopened.isMinimized()
        reopened.startup.setCurrentIndex(0); reopened._save_settings()
    finally:
        reopened.close()
    normal = MainWindow(path)
    try:
        normal.show_startup_window(); app.processEvents()
        assert not normal.isMinimized()
    finally:
        normal.close()
    for invalid in (-1, 99, "bad", None):
        store = Store(path); store.set_preference("startup", invalid); store.close()
        safe = MainWindow(path)
        try: assert safe.startup.currentIndex() == 0
        finally: safe.close()


def test_window_mode_mouse_selection_applies_and_saves_immediately(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    path = tmp_path / "immediate-window.db"
    window = MainWindow(path)
    try:
        window.show(); window.tabs.setCurrentIndex(2); app.processEvents()
        window.margin.setValue(2.0)  # Other unsaved fields must stay unsaved.
        QTest.mouseClick(window.startup, Qt.LeftButton)
        app.processEvents()
        view = window.startup.view()
        index = window.startup.model().index(1, 0)
        QTest.mouseMove(view.viewport(), view.visualRect(index).center())
        QTest.qWait(QApplication.doubleClickInterval())
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
        app.processEvents()
        assert window.isMinimized()
        assert window.store.preference("startup") == 1
        assert window.store.preference("margin") == .5
        window.showNormal(); app.processEvents()
        QTest.mouseClick(window.startup, Qt.LeftButton)
        app.processEvents()
        index = window.startup.model().index(0, 0)
        QTest.mouseMove(view.viewport(), view.visualRect(index).center())
        QTest.qWait(QApplication.doubleClickInterval())
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
        app.processEvents()
        assert not window.isMinimized()
        assert window.store.preference("startup") == 0
        def fail(*args): raise sqlite3.OperationalError("test read-only database")
        monkeypatch.setattr(window.store, "set_preference", fail)
        window.startup.setCurrentIndex(1)
        window.startup.activated.emit(1); app.processEvents()
        assert not window.isMinimized()
        assert window.startup.currentIndex() == 0
        assert "Couldn’t save" in window.saved_label.text()
    finally:
        window.close()


def test_clear_log_persists_and_new_events_work(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    path = tmp_path / "clear.db"
    window = MainWindow(path)
    try:
        window.show(); window.tabs.setCurrentIndex(3); app.processEvents()
        for number in range(3):
            window._log("guide", f"Old event {number}")
        assert len(window.store.recent()) == 3
        assert window.refresh_button.text() == "Refresh log"
        assert window.clear_button.text() == "Clear log"
        window._activity_events = []
        window.log_box.clear()
        QTest.mouseClick(window.refresh_button, Qt.LeftButton); app.processEvents()
        assert len(window.store.recent()) == 3
        assert "Old event 2" in window.log_box.toPlainText()
        assert "3 events" in window.refresh_status.text()
        window.store.log("skip", "Fourth event")
        QTest.mouseClick(window.refresh_button, Qt.LeftButton); app.processEvents()
        assert "Fourth event" in window.log_box.toPlainText()
        assert len(window.store.recent()) == 4
        monkeypatch.setattr(window, "_confirm_clear_log", lambda: False)
        QTest.mouseClick(window.clear_button, Qt.LeftButton)
        assert len(window.store.recent()) == 4
        monkeypatch.setattr(window, "_confirm_clear_log", lambda: True)
        QTest.mouseClick(window.clear_button, Qt.LeftButton); app.processEvents()
        assert window.store.recent() == []
        assert window.log_box.toPlainText() == ""
        assert window.activity_empty.isVisible()
        assert "0 events" in window.refresh_status.text()
        window.tabs.setCurrentIndex(0); window.tabs.setCurrentIndex(3)
        assert window.log_box.toPlainText() == ""
    finally:
        window.close()
    reopened = MainWindow(path)
    try:
        reopened.show(); reopened.tabs.setCurrentIndex(3); app.processEvents()
        assert reopened.store.recent() == []
        assert reopened.activity_empty.isVisible()
        reopened._log("connection", "New connection")
        assert len(reopened.store.recent()) == 1
        assert "New connection" in reopened.log_box.toPlainText()
        assert "Old event" not in reopened.log_box.toPlainText()
        QTest.mouseClick(reopened.refresh_button, Qt.LeftButton); app.processEvents()
        assert len(reopened.store.recent()) == 1
        assert "New connection" in reopened.log_box.toPlainText()
    finally:
        reopened.close()


def test_clear_log_preserves_display_on_database_error(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "clear-error.db")
    try:
        window._log("guide", "Keep this event")
        window.show(); window.tabs.setCurrentIndex(3); app.processEvents()
        def fail(): raise sqlite3.OperationalError("database unavailable")
        monkeypatch.setattr(window.store, "clear_activity", fail)
        monkeypatch.setattr(window, "_confirm_clear_log", lambda: True)
        QTest.mouseClick(window.clear_button, Qt.LeftButton); app.processEvents()
        assert "Keep this event" in window.log_box.toPlainText()
        assert len(window.store.recent()) == 1
        assert "Couldn’t clear" in window.refresh_status.text()
        assert window.clear_button.isEnabled()
    finally:
        window.close()


def test_clear_confirmation_dialog_has_cancel_and_destructive_action(tmp_path, monkeypatch):
    app = application()
    monkeypatch.setattr(MpvWorker, "start", lambda self: None)
    window = MainWindow(tmp_path / "confirm.db")
    try:
        window.show(); window.tabs.setCurrentIndex(3); app.processEvents()
        for choice, expected in (("Cancel", False), ("Clear log", True)):
            def choose():
                dialog = app.activeModalWidget()
                assert isinstance(dialog, QMessageBox)
                assert "permanently delete" in dialog.informativeText()
                button = next(b for b in dialog.buttons() if b.text() == choice)
                QTest.mouseClick(button, Qt.LeftButton)
            QTimer.singleShot(0, choose)
            assert window._confirm_clear_log() is expected
    finally:
        window.close()

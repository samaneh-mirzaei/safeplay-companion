from __future__ import annotations

import os
import sqlite3
from datetime import datetime
import threading
import time
from uuid import uuid4
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView,
)

from .theme import STYLE, AdaptiveColumns, CueArtwork, CinemaIllustration, ticket_panel, label, panel, scroll
from .controls import IntegerInput as QSpinBox, DecimalInput as QDoubleSpinBox, ChoiceInput as QComboBox
from .engine import SkipEngine
from .secondary import STYLE as SECONDARY_STYLE, SETTINGS_STYLE, SceneLabels, empty_state, activity_html
from PySide6.QtGui import QFont
from .models import CATEGORIES, Movie, Scene, identify_media, runtime_warning
from .mpv import MpvClient, MpvError, syncplay_pipes
from .provider import DoesTheDogDie, ProviderError, fallback_providers
from .storage import Store


def clock(seconds):
    if seconds is None:
        return "—"
    n = int(seconds)
    return f"{n // 3600:02}:{n // 60 % 60:02}:{n % 60:02}"


class MpvWorker(QThread):
    snapshot = Signal(dict)
    status = Signal(str)
    skipped = Signal(float, list)
    warning = Signal(str)

    def __init__(self, pipe):
        super().__init__()
        self.pipe = pipe
        self.client = None
        self.engine = SkipEngine()
        self.lock = threading.RLock()
        self.active = True
        self.auto_connect = True
        self.current_path = None
        self.connected_pipe = None

    def _connect(self):
        errors = []
        for endpoint in [self.pipe]:
            client = MpvClient(endpoint)
            try:
                snap = client.snapshot()
                self.client = client
                self.connected_pipe = endpoint
                return snap
            except (MpvError, OSError) as exc:
                errors.append((endpoint, str(exc)))
                client.close()
        available = []
        for endpoint in syncplay_pipes():
            if endpoint == self.pipe:
                continue
            client = MpvClient(endpoint)
            try:
                available.append((endpoint, client, client.snapshot()))
            except (MpvError, OSError) as exc:
                errors.append((endpoint, str(exc)))
                client.close()
        if len(available) == 1:
            self.connected_pipe, self.client, snap = available[0]
            return snap
        for _, client, _ in available:
            client.close()
        if len(available) > 1:
            raise MpvError("Multiple Syncplay mpv pipes found. Enter the correct IPC pipe in Settings.")
        if any("Permission denied" in error or "Access is denied" in error
               for _, error in errors):
            raise MpvError("Syncplay mpv pipe is access denied. Run SafePlay and Syncplay at the same Windows privilege level, then reconnect.")
        raise MpvError("No reachable mpv IPC pipe. Restart mpv to load mpv.conf, or enable a shared IPC pipe in Syncplay Player Arguments.")

    def configure(self, scenes=None, duration=None, confirmed=None, enabled=None,
                  filters=None, margin=None, pipe=None, auto_connect=None):
        with self.lock:
            if pipe is not None and pipe != self.pipe:
                self.pipe = pipe
                if self.client:
                    self.client.close()
                    self.client = None
                self.current_path = None
                self.connected_pipe = None
                self.engine.load([], None, False)
            if scenes is not None:
                self.engine.load(scenes, duration, bool(confirmed))
            elif confirmed is not None:
                self.engine.confirmed = confirmed
            if enabled is not None:
                self.engine.enabled = enabled
            if filters is not None:
                self.engine.filters = dict(filters)
            if margin is not None:
                self.engine.margin = margin
            if auto_connect is not None:
                self.auto_connect = auto_connect
            if confirmed:
                self.engine.resume_after_conflict()

    def run(self):
        was_connected = False
        reported_missing = False
        while self.active:
            if not self.auto_connect:
                if self.client:
                    self.client.close()
                    self.client = None
                self.msleep(500)
                continue
            try:
                with self.lock:
                    snap = self._connect() if self.client is None else self.client.snapshot()
                    if snap["path"] != self.current_path:
                        self.current_path = snap["path"]
                        self.engine.load([], snap.get("duration"), False)
                    self.engine.duration = snap.get("duration")
                    if not was_connected:
                        self.status.emit("Connected to mpv via " + self.connected_pipe)
                        was_connected = True
                        reported_missing = False
                    self.snapshot.emit(snap)
                    if not snap.get("path"):
                        self.msleep(250)
                        continue
                    decision = self.engine.tick(snap.get("time-pos"), bool(snap.get("pause")))
                    if self.engine.suspended:
                        self.warning.emit("Syncplay or another controller reversed the seek. Automatic skipping is suspended until you reconfirm.")
                    if decision:
                        target, keys = decision
                        try:
                            self.client.seek(target)
                            self.skipped.emit(target, keys)
                        except MpvError:
                            self.engine.seek_failed(keys)
                            raise
            except (MpvError, OSError) as exc:
                if was_connected or not reported_missing:
                    self.status.emit("Disconnected: " + str(exc))
                    reported_missing = True
                was_connected = False
                with self.lock:
                    if self.client:
                        self.client.close()
                        self.client = None
                    self.connected_pipe = None
                self.msleep(1500)
            self.msleep(250)
        if self.client:
            self.client.close()


class FetchWorker(QThread):
    done = Signal(object, object)

    def __init__(self, key, title, year, media_type):
        super().__init__()
        self.key, self.title, self.year, self.media_type = key, title, year, media_type

    def run(self):
        try:
            provider = DoesTheDogDie(self.key)
            matches = provider.find(self.title, self.year, self.media_type)
            self.done.emit(matches, None)
        except Exception as exc:
            self.done.emit(None, str(exc))


class GuideWorker(QThread):
    done = Signal(object, object)

    def __init__(self, key, item, season=None, episode=None):
        super().__init__()
        self.key, self.item, self.season, self.episode = key, item, season, episode

    def run(self):
        try:
            self.done.emit(DoesTheDogDie(self.key).guide(self.item, self.season, self.episode), None)
        except Exception as exc:
            self.done.emit(None, str(exc))


class SceneSourceWorker(QThread):
    done = Signal(object, object)

    def __init__(self, title, year, providers):
        super().__init__()
        self.title, self.year = title, year
        self.providers = providers

    def run(self):
        scenes = []
        errors = []
        for provider in self.providers:
            try:
                scenes.extend(provider().scenes(self.title, self.year))
            except Exception as exc:
                errors.append(str(exc))
        self.done.emit(scenes, "; ".join(errors) if errors and not scenes else None)


class SceneDialog(QDialog):
    def __init__(self, scene: Scene, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review scene interval")
        self.setMinimumWidth(440)
        form = QFormLayout(self)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(16)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.addRow(label("Review the interval", "pageTitle"))
        form.addRow(label("Use seconds from the exact file you’re watching"))
        self.start = QDoubleSpinBox(); self.start.setRange(0, 100000); self.start.setDecimals(1)
        self.end = QDoubleSpinBox(); self.end.setRange(0, 100000); self.end.setDecimals(1)
        self.start.setValue(scene.start or 0); self.end.setValue(scene.end or 0)
        self.category = QComboBox()
        for key, title in CATEGORIES.items():
            self.category.addItem(title, key)
        self.category.setCurrentIndex(list(CATEGORIES).index(scene.category))
        self.enabled = QCheckBox("Enable this scene"); self.enabled.setChecked(scene.enabled)
        self.note = QLineEdit(scene.note)
        form.addRow("Start (seconds)", self.start)
        form.addRow("Safe resume (seconds)", self.end)
        form.addRow("Category", self.category)
        form.addRow("Note", self.note)
        form.addRow(self.enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply(self, scene: Scene):
        scene.start = self.start.value()
        scene.end = self.end.value()
        scene.category = self.category.currentData()
        scene.enabled = self.enabled.isChecked()
        scene.note = self.note.text().strip()


class MainWindow(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.store = Store(db_path)
        self.movie: Movie | None = None
        self.media_path = ""
        self.duration = None
        self.fetcher = None
        self.guide_worker = None
        self.scene_fetcher = None
        self.scene_fetchers = []
        self.scene_fetch_context = None
        self.fetch_context = None
        self.guide_context = None
        self.confirmed = False
        self.suspended = False
        self.setWindowTitle("SafePlay Companion")
        self.resize(1180, 800)
        self.setMinimumSize(560, 480)
        self.setStyleSheet(STYLE)
        shell = QWidget(); shell.setObjectName("shell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(20, 12, 20, 12)
        shell_layout.setSpacing(8)
        masthead = QHBoxLayout()
        masthead.addWidget(label("SafePlay", "brand"))
        masthead.addWidget(label("Companion / mpv + Syncplay\nYour viewing. Your boundaries.", "subtitle"))
        self.attribution = QLabel('<a href="https://www.doesthedogdie.com" style="color:#20201e;text-decoration:none">Powered by DoesTheDogDie.com</a>')
        self.attribution.setObjectName("providerAttribution")
        self.attribution.setOpenExternalLinks(True)
        self.attribution.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.attribution.setFocusPolicy(Qt.StrongFocus)
        self.attribution.setAccessibleName("Powered by DoesTheDogDie.com, opens website")
        shell_layout.addLayout(masthead)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        shell_layout.addWidget(self.tabs)
        shell_layout.addWidget(self.attribution, 0, Qt.AlignRight)
        self.setCentralWidget(shell)
        self.tabs.addTab(scroll(self._dashboard()), "Dashboard")
        self.tabs.addTab(self._scene_page(), "Scenes")
        self.tabs.addTab(scroll(self._settings_page()), "Settings")
        self.tabs.addTab(self._log_page(), "Activity")
        self.worker = MpvWorker(self.pipe.text())
        self.worker.snapshot.connect(self._snapshot)
        self.worker.status.connect(self._status)
        self.worker.skipped.connect(self._skipped)
        self.worker.warning.connect(self._warning)
        self._apply_settings()
        self.worker.start()
        self._refresh_log()

    def _page(self, title, description):
        page = QWidget(); page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 24, 8, 12)
        layout.setSpacing(20)
        title_row = QHBoxLayout(); title_row.setSpacing(16)
        title_row.addWidget(label(title, "pageTitle"), 1)
        variant = {"Set the scene": 0, "The cut list": 1,
                   "Make the connection": 2, "Playback journal": 3}.get(title, 0)
        title_row.addWidget(CueArtwork(variant))
        layout.addLayout(title_row)
        layout.addWidget(label(description))
        return page, layout

    def _dashboard(self):
        page = QWidget(); page.setObjectName("dashboard")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 8, 8); layout.setSpacing(8)
        intro = QHBoxLayout(); intro.setSpacing(24)
        intro.addWidget(label("Your movie. Your rules.", "pageTitle"), 1)
        intro.addWidget(label("Find a guide, choose filters, confirm your edition."))
        layout.addLayout(intro)
        playback, playback_layout = ticket_panel("Now playing", "01", "playbackPanel")
        self.movie_label = label("No media loaded", "movie")
        self.position_label = label("Playback: —", "timecode")
        self.status_label = label("Connecting to mpv…")
        self.guide_label = label("Guide: not loaded")
        self.skip_label = label("Automatic skipping: OFF", "skipState")
        readout = QWidget(); readout_layout = QVBoxLayout(readout)
        readout_layout.setContentsMargins(0, 0, 0, 0); readout_layout.setSpacing(4)
        for item in (self.movie_label, self.position_label, self.status_label, self.guide_label):
            readout_layout.addWidget(item)
        picture = CinemaIllustration()
        playback_row = QHBoxLayout(); playback_row.setSpacing(24)
        playback_row.addWidget(readout, 1); playback_row.addWidget(picture)
        playback_layout.addLayout(playback_row)
        playback_layout.addWidget(self.skip_label)
        layout.addWidget(playback)

        guide, guide_layout = ticket_panel("Find your guide", "02", "guidePanel", "guide")
        self.title = QLineEdit(); self.title.setPlaceholderText("Movie or series title")
        self.title.setAccessibleName("Movie or series title")
        self.title.returnPressed.connect(self._search)
        guide_layout.addWidget(self.title)
        row = QHBoxLayout(); row.setSpacing(12)
        self.year = QSpinBox(); self.year.setRange(0, 2100); self.year.setSpecialValueText("Year unknown")
        self.year.setAccessibleName("Release year")
        self.search = QPushButton("Find guide"); self.search.setProperty("primary", True)
        self.search.clicked.connect(self._search)
        row.addWidget(self.year); row.addWidget(self.search)
        guide_layout.addLayout(row)
        episode_row = QHBoxLayout(); episode_row.setSpacing(8)
        self.media_type = QComboBox()
        self.media_type.addItem("Movie", "movie"); self.media_type.addItem("TV show", "tv show")
        self.media_type.setAccessibleName("Media type")
        self.season = QSpinBox(); self.season.setRange(1, 100); self.season.setPrefix("Season ")
        self.episode = QSpinBox(); self.episode.setRange(1, 1000); self.episode.setPrefix("Episode ")
        self.season.setAccessibleName("Season"); self.episode.setAccessibleName("Episode")
        self.media_type.currentIndexChanged.connect(self._kind_changed)
        self.season.valueChanged.connect(self._selection_changed)
        self.episode.valueChanged.connect(self._selection_changed)
        for item in (self.media_type, self.season, self.episode): episode_row.addWidget(item)
        guide_layout.addLayout(episode_row)
        guide_layout.addWidget(label("TV shows: select a season and episode"))
        self.confirm = QPushButton("Review and confirm movie edition")
        self.confirm.setObjectName("confirmEdition")
        self.confirm.clicked.connect(self._confirm_edition)
        guide_layout.addWidget(self.confirm)
        guide_layout.addWidget(label("Confirm this file’s edition before skipping"))
        guide_layout.addStretch()
        self._kind_changed()

        filters, filter_layout = ticket_panel("Content filters", "03", "filtersPanel", "filters")
        self.all_filters = QCheckBox("Enable all content filters")
        self.all_filters.stateChanged.connect(self._toggle_all)
        filter_layout.addWidget(self.all_filters)
        self.filter_boxes = {}
        for key, title in CATEGORIES.items():
            box = QCheckBox(title.replace("&", "&&")); box.setChecked(self.store.preference("filter_" + key, False))
            box.setProperty("filterRow", True); box.setProperty("category", key)
            box.toggled.connect(lambda value, k=key: self._filter_changed(k, value))
            filter_layout.addWidget(box); self.filter_boxes[key] = box
        self.all_filters.blockSignals(True)
        self.all_filters.setChecked(all(b.isChecked() for b in self.filter_boxes.values()))
        self.all_filters.blockSignals(False)
        filter_layout.addWidget(label("Choose scenes in Scenes. Enable skipping in Settings."))
        filter_layout.addStretch()
        layout.addWidget(AdaptiveColumns(guide, filters))
        return page

    def _scene_page(self):
        page, layout = self._page("The cut list", "Review scene times and choose what to skip")
        page.setObjectName("secondary"); page.setStyleSheet(SECONDARY_STYLE)
        layout.setContentsMargins(4, 8, 8, 8); layout.setSpacing(12)
        sheet, sheet_layout = ticket_panel("Scene intervals", "01", "secondaryPanel")
        self.scene_table = QTableWidget(0, 8)
        self.scene_table.setItemDelegate(SceneLabels(self.scene_table))
        self.scene_table.setHorizontalHeaderLabels(["Start", "End", "Category", "Source", "Reliability", "Skip this scene", "Ready now?", "Topic"])
        self.scene_table.horizontalHeader().setStretchLastSection(True)
        self.scene_table.horizontalHeader().setMinimumSectionSize(88)
        for i, width in enumerate((88, 88, 184, 160, 104, 116, 96, 220)):
            self.scene_table.setColumnWidth(i, width)
        self.scene_table.verticalHeader().setVisible(False)
        self.scene_table.verticalHeader().setDefaultSectionSize(48)
        self.scene_table.setAlternatingRowColors(True)
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scene_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.scene_table.setAccessibleName("Scene intervals")
        self.scene_table.itemChanged.connect(self._scene_check_changed)
        self.scene_empty_panel, self.scene_empty = empty_state("Your cut list starts here", "Find a movie or episode on Dashboard to see its scene intervals")
        sheet_layout.addWidget(self.scene_empty_panel)
        sheet_layout.addWidget(self.scene_table, 1)
        layout.addWidget(sheet, 1)
        row = QHBoxLayout(); row.setSpacing(12)
        edit = QPushButton("Edit selected scene"); edit.setProperty("primary", True); edit.clicked.connect(self._edit_scene)
        add = QPushButton("Add manual scene"); add.clicked.connect(self._add_scene)
        row.addWidget(edit); row.addWidget(add); row.addStretch(); layout.addLayout(row)
        self.scene_info = label("No guide loaded")
        layout.addWidget(self.scene_info)
        layout.addWidget(label("Missing times cannot skip. Verify intervals against your file."))
        return page

    def _settings_page(self):
        page = QWidget(); page.setObjectName("settings")
        page.setStyleSheet(SETTINGS_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 8, 8); layout.setSpacing(12)
        intro = QHBoxLayout(); intro.setSpacing(24)
        intro.addWidget(label("Make the connection", "pageTitle"), 1)
        intro.addWidget(label("Configure mpv, your guide source,\nand automatic skipping"))
        layout.addLayout(intro)
        connection, connection_layout = ticket_panel("Player & guide", "01", "settingsConnection", "guide")
        form = QFormLayout(); form.setSpacing(8)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.pipe = QLineEdit(self.store.preference("pipe", r"\\.\pipe\safeplay-mpv"))
        self.api_key = QLineEdit(os.environ.get("SAFEPLAY_DDD_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.auto_connect = QCheckBox("Connect to mpv automatically"); self.auto_connect.setChecked(self.store.preference("auto_connect", True))
        self.auto_skip = QCheckBox("Enable automatic skipping"); self.auto_skip.setChecked(self.store.preference("auto_skip", False))
        self.margin = QDoubleSpinBox(); self.margin.setRange(0, 5); self.margin.setSingleStep(.1)
        self.margin.setValue(self.store.preference("margin", .5)); self.margin.setSuffix(" seconds")
        self.language = QComboBox(); self.language.addItem("English", "en")
        self.startup = QComboBox(); self.startup.addItems(["Normal window", "Minimized"])
        startup = self.store.preference("startup", 0)
        self.startup.setCurrentIndex(startup if type(startup) is int and startup in (0, 1) else 0)
        self._saved_startup = self.startup.currentIndex()
        self.startup.setToolTip("Applies immediately and is saved for future launches")
        self.startup.activated.connect(self._window_mode_changed)
        form.addRow("mpv IPC pipe", self.pipe)
        form.addRow("DoesTheDogDie API key (session only)", self.api_key)
        form.addRow(self.auto_connect)
        connection_layout.addLayout(form)
        connection_layout.addWidget(label("Match your mpv IPC pipe. Syncplay pipes are detected automatically."))
        connection_layout.addWidget(label("Session only. Set SAFEPLAY_DDD_API_KEY to reuse your key."))
        preferences, preferences_layout = ticket_panel("Playback preferences", "02", "settingsBehavior", "filters")
        behavior = QFormLayout(); behavior.setSpacing(8); behavior.setRowWrapPolicy(QFormLayout.WrapAllRows)
        behavior.addRow(self.auto_skip)
        behavior.addRow("Safety margin", self.margin)
        behavior.addRow("Language", self.language)
        behavior.addRow("SafePlay window mode", self.startup)
        preferences_layout.addLayout(behavior)
        preferences_layout.addWidget(label("Requires selected filters, valid times, and a confirmed edition."))
        layout.addWidget(AdaptiveColumns(connection, preferences))
        save = QPushButton("Save settings"); save.setProperty("primary", True)
        save.clicked.connect(self._save_settings)
        self.saved_label = label("Save to apply changes")
        footer = QHBoxLayout(); footer.setSpacing(16)
        footer.addWidget(save); footer.addWidget(self.saved_label, 1)
        layout.addLayout(footer)
        layout.addStretch()
        return page

    def _save_settings(self):
        self._apply_settings()
        if self.pipe.text().strip().startswith("\\\\.\\pipe\\"):
            self.saved_label.setText("Settings saved")

    def _window_mode_changed(self, index):
        """A user selection applies now, independently of other unsaved settings."""
        try:
            self.store.set_preference("startup", index)
        except sqlite3.Error:
            self.startup.setCurrentIndex(self._saved_startup)
            self.saved_label.setText("Couldn’t save window mode. Try again.")
            return
        self._saved_startup = index
        self.saved_label.setText("Window mode saved · Applies now and at startup")
        # Let the native dropdown close before changing the top-level window state.
        QTimer.singleShot(0, self.show_startup_window)

    def _log_page(self):
        page, layout = self._page("Playback journal", "Connection changes, guide lookups, and every automatic skip")
        page.setObjectName("secondary"); page.setStyleSheet(SECONDARY_STYLE)
        layout.setContentsMargins(4, 8, 8, 8); layout.setSpacing(12)
        journal, journal_layout = ticket_panel("Recent events", "01", "secondaryPanel")
        self.activity_empty, _ = empty_state("No activity yet", "New playback and connection events will appear here")
        journal_layout.addWidget(self.activity_empty)
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setAccessibleName("Playback activity log")
        journal_layout.addWidget(self.log_box, 1)
        layout.addWidget(journal, 1)
        self.refresh_button = QPushButton("Refresh log")
        self.refresh_button.clicked.connect(self._request_refresh)
        self.clear_button = QPushButton("Clear log")
        self.clear_button.setProperty("destructive", True)
        self.clear_button.clicked.connect(self._clear_log)
        self.refresh_status = label("Latest 200 events · Stored on this computer")
        self._activity_events = None
        refresh_row = QHBoxLayout(); refresh_row.setSpacing(16)
        refresh_row.addWidget(self.refresh_button)
        refresh_row.addWidget(self.clear_button)
        refresh_row.addWidget(self.refresh_status, 1)
        layout.addLayout(refresh_row)
        return page

    def _log(self, kind, message):
        self.store.log(kind, message)
        self._refresh_log()

    def _request_refresh(self):
        self.refresh_button.setEnabled(False)
        self.refresh_status.setText("Refreshing…")
        QTimer.singleShot(0, self._refresh_log)

    def _confirm_clear_log(self):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Clear activity log?")
        dialog.setText("Clear activity log?")
        dialog.setInformativeText("This will permanently delete all recorded activity events. This action cannot be undone.")
        dialog.addButton("Cancel", QMessageBox.RejectRole)
        clear = dialog.addButton("Clear log", QMessageBox.DestructiveRole)
        dialog.setDefaultButton(dialog.buttons()[0])
        dialog.exec()
        return dialog.clickedButton() is clear

    def _clear_log(self):
        if not self._confirm_clear_log():
            return
        self.clear_button.setEnabled(False)
        try:
            self.store.clear_activity()
        except sqlite3.Error as exc:
            self.refresh_status.setText("Couldn’t clear activity. Try again.")
            self.refresh_status.setToolTip(str(exc))
        else:
            self._activity_events = []
            self.log_box.clear()
            self.activity_empty.setVisible(True)
            self.refresh_status.setText("Log cleared · 0 events")
            self.refresh_status.setToolTip("")
        finally:
            self.clear_button.setEnabled(True)

    def _refresh_log(self):
        try:
            events = self.store.recent()
            self.activity_empty.setVisible(not events)
            self.log_box.setHtml(activity_html(events))
            self._activity_events = events
            self.refresh_status.setText(f"Updated {datetime.now():%H:%M:%S} · {len(events)} events · Newest first")
        except sqlite3.Error as exc:
            self.refresh_status.setText("Couldn’t refresh activity. Try again.")
            self.refresh_status.setToolTip(str(exc))
        else:
            self.refresh_status.setToolTip("")
        finally:
            self.refresh_button.setEnabled(True)

    def _status(self, status):
        self.status_label.setText("mpv: " + status)
        self._log("connection", status)

    def _kind_changed(self):
        is_series = self.media_type.currentData() == "tv show"
        self.season.setEnabled(is_series)
        self.episode.setEnabled(is_series)
        self.confirm.setText("Review and confirm episode edition" if is_series
                             else "Review and confirm movie edition")
        self._selection_changed()

    def _selection_changed(self):
        if self.movie is None:
            return
        self.movie = None
        self.confirmed = False
        self.suspended = False
        self.worker.configure(scenes=[], duration=self.duration, confirmed=False)
        self.guide_label.setText("Guide: selection changed; click Find guide")
        self._render_scenes()
        self._update_skip_label()

    def _search_context(self):
        return (self.media_path, self.title.text().strip(), self.year.value() or None,
                self.media_type.currentData(),
                self.season.value() if self.media_type.currentData() == "tv show" else None,
                self.episode.value() if self.media_type.currentData() == "tv show" else None)

    def _warning(self, message):
        if not self.suspended:
            self.suspended = True
            self._update_skip_label()
            self._log("warning", message)
            QMessageBox.warning(self, "Playback correction detected", message)

    def _snapshot(self, snap):
        path = snap.get("path") or ""
        previous_duration = self.duration
        self.duration = snap.get("duration")
        self.position_label.setText(f"Playback: {clock(snap.get('time-pos'))} / {clock(self.duration)}" +
                                    (" (paused)" if snap.get("pause") else ""))
        if path != self.media_path:
            self.media_path = path
            if not path:
                self.movie = None; self.confirmed = False; self.suspended = False
                self.movie_label.setText("Movie: no media loaded")
                self.guide_label.setText("Guide: not loaded")
                self.worker.configure(scenes=[], duration=self.duration, confirmed=False)
                self._render_scenes()
                self._update_skip_label()
                return
            title, year, season, episode = identify_media(path)
            self.title.setText(title)
            self.year.setValue(year or 0)
            self.media_type.setCurrentIndex(1 if season is not None else 0)
            if season is not None:
                self.season.setValue(season)
                self.episode.setValue(episode)
            self.movie = None; self.confirmed = False; self.suspended = False
            self.worker.configure(scenes=[], duration=self.duration, confirmed=False)
            self.movie_label.setText(f"Movie: {title} ({year or 'year unknown'})")
            self.guide_label.setText("Guide: searching…" if self.api_key.text() else "Guide: API key required")
            self._render_scenes(); self._update_skip_label()
            self._log("movie", f"Detected {title} ({year or 'unknown'})")
            if self.api_key.text():
                self._search()
        elif self.movie and previous_duration != self.duration:
            self._render_scenes()
            self._update_skip_label()

    def _search(self):
        if self.fetcher and self.fetcher.isRunning():
            return
        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Movie title", "Enter a movie title first."); return
        self.guide_label.setText("Guide: searching…")
        self.fetcher = FetchWorker(self.api_key.text(), title, self.year.value() or None,
                                   self.media_type.currentData())
        self.fetch_context = self._search_context()
        self.fetcher.done.connect(self._found)
        self.fetcher.start()

    def _found(self, matches, error):
        if self.fetch_context != self._search_context():
            if self.api_key.text() and self.media_path:
                QTimer.singleShot(100, self._search)
            return
        if error:
            self.guide_label.setText("Guide: unavailable")
            self._log("error", error); return
        if not matches:
            self.guide_label.setText("Guide: no matching title")
            self._log("guide", "No matching movie or TV show; check type, title and year")
            return
        wanted = self.title.text().strip().casefold()
        year = self.year.value() or None
        exact = [m for m in matches if m.get("name", "").casefold() == wanted and (year is None or m.get("releaseYear") == year)]
        if len(exact) == 1:
            item = exact[0]
        else:
            dialog = QDialog(self); dialog.setWindowTitle("Choose the correct title")
            layout = QVBoxLayout(dialog); listing = QListWidget()
            for m in matches:
                listing.addItem(f"{m.get('name')} ({m.get('releaseYear', '?')}) — ID {m.get('id')}")
            layout.addWidget(listing)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() != QDialog.Accepted or listing.currentRow() < 0:
                self.guide_label.setText("Guide: selection required"); return
            item = matches[listing.currentRow()]
        is_series = self.media_type.currentData() == "tv show"
        season = self.season.value() if is_series else None
        episode = self.episode.value() if is_series else None
        guide_id = f"{item['id']}:S{season}E{episode}" if is_series else str(item["id"])
        cached = self.store.load_guide(guide_id)
        if cached:
            self._guide_ready(cached, None, from_cache=True); return
        self.guide_label.setText("Guide: downloading…")
        self.guide_worker = GuideWorker(self.api_key.text(), item, season, episode)
        self.guide_context = self._search_context()
        self.guide_worker.done.connect(self._guide_ready)
        self.guide_worker.start()

    def _guide_ready(self, movie, error, from_cache=False):
        if not from_cache and self.guide_context != self._search_context():
            if self.api_key.text() and self.media_path:
                QTimer.singleShot(100, self._search)
            return
        if error:
            self.guide_label.setText("Guide: unavailable")
            self._log("error", error); return
        if not isinstance(movie, Movie):
            return
        if not from_cache:
            self.store.save_guide(movie)
        self.movie = self.store.load_guide(movie.external_id)
        if self.duration and any(s.end is not None and s.end > self.duration + 2 for s in self.movie.scenes):
            self.movie.warnings.append("At least one scene exceeds the current file runtime and cannot skip.")
        self.confirmed = False
        self.worker.configure(scenes=self.movie.scenes, duration=self.duration, confirmed=False)
        self.movie_label.setText(f"Movie: {movie.title} ({movie.year or 'year unknown'})")
        timed = sum(s.valid(self.duration) for s in self.movie.scenes)
        self.guide_label.setText(f"Guide: {len(self.movie.scenes)} scenes; {timed} with usable times; edition confirmation required")
        self._log("guide", f"Loaded {movie.title}; {len(movie.scenes)} scenes. " + " ".join(movie.warnings))
        self._render_scenes()
        self._update_skip_label()
        providers = fallback_providers(self.movie.scenes) if self.movie.source == "doesthedogdie" else []
        if providers:
            self.scene_fetch_context = (self.media_path, self.movie.external_id)
            self.scene_fetcher = SceneSourceWorker(self.movie.title, self.movie.year, providers)
            self.scene_fetcher.done.connect(self._cleanstream_ready)
            self.scene_fetchers.append(self.scene_fetcher)
            self.scene_fetcher.finished.connect(lambda worker=self.scene_fetcher: self.scene_fetchers.remove(worker) if worker in self.scene_fetchers else None)
            self.scene_fetcher.start()

    def _cleanstream_ready(self, scenes, error):
        if not self.movie or self.scene_fetch_context != (self.media_path, self.movie.external_id):
            return
        if error:
            self._log("guide", error)
            return
        if not scenes:
            self._log("guide", "No matching timestamped scenes from CleanStream or CringeMDb for this title and year")
            return
        keys = {s.key for s in self.movie.scenes}
        self.movie.scenes.extend(s for s in scenes if s.key not in keys)
        self.store.save_guide(self.movie)
        self.movie = self.store.load_guide(self.movie.external_id, allow_stale=True)
        self.worker.configure(scenes=self.movie.scenes, duration=self.duration, confirmed=self.confirmed)
        self._render_scenes(); self._update_skip_label()
        self._log("guide", f"Added {len(scenes)} timestamped scenes from external guides")

    def _confirm_edition(self):
        if not self.movie:
            QMessageBox.warning(self, "Guide", "Load a guide first."); return
        reference_minutes, accepted = QInputDialog.getDouble(
            self, "Reference edition runtime",
            "Reference edition runtime in minutes (0 if unknown):", 0, 0, 1000, 1)
        if not accepted:
            return
        self.movie.runtime = reference_minutes * 60 if reference_minutes else None
        details = (f"Guide: {self.movie.title} ({self.movie.year or 'unknown year'})\n"
                   f"Current file: {Path(self.media_path).name}\n"
                   f"Player runtime: {clock(self.duration)}\n"
                   f"{runtime_warning(self.duration, self.movie.runtime) or 'Runtime appears compatible.'}\n"
                   "Confirm this exact file and every interval before enabling automatic skips.\n"
                   "External seeks may conflict with Syncplay; test with your viewing room.")
        if QMessageBox.question(self, "Confirm movie edition", details,
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.confirmed = True
            self.suspended = False
            self.worker.configure(confirmed=True)
            self._log("guide", "User confirmed movie edition and reviewed runtime warning")
            self._render_scenes()
            self._apply_settings()

    def _render_scenes(self):
        selected_row = self.scene_table.currentRow()
        scenes = self.movie.scenes if self.movie else []
        self.scene_empty_panel.setVisible(not scenes)
        self.scene_empty.setText("No scenes submitted for this guide\nTry another episode or add a reviewed interval" if self.movie else "No guide loaded\nFind a movie or episode on Dashboard to see its scene intervals")
        if self.movie:
            timed = sum(s.valid(self.duration) for s in scenes)
            state = "edition confirmed" if self.confirmed else "edition confirmation required"
            self.guide_label.setText(f"Guide: {len(scenes)} scenes; {timed} with usable times; {state}")
        self.scene_table.blockSignals(True)
        self.scene_table.setRowCount(len(scenes))
        for i, s in enumerate(scenes):
            skip = s.can_skip(self.duration, self.confirmed) and self.auto_skip.isChecked() and self.filter_boxes[s.category].isChecked()
            values = [clock(s.start) if s.start is not None else "Missing",
                      clock(s.end) if s.end is not None else "Missing",
                      CATEGORIES[s.category], s.source, s.reliability,
                      "", "Yes" if skip else "No", s.topic or s.note]
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if j in (0, 1):
                    item.setFont(QFont("Consolas", 10))
                if j == 5:
                    item.setFlags((item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                    item.setCheckState(Qt.Checked if s.enabled else Qt.Unchecked)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.scene_table.setItem(i, j, item)
        self.scene_table.blockSignals(False)
        if 0 <= selected_row < len(scenes):
            self.scene_table.selectRow(selected_row)
        missing = sum(s.start is None or s.end is None for s in scenes)
        self.scene_info.setText(f"{len(scenes)} scenes · {missing} missing times")

    def _selected_scene(self):
        row = self.scene_table.currentRow()
        return self.movie.scenes[row] if self.movie and 0 <= row < len(self.movie.scenes) else None

    def _edit_scene(self):
        scene = self._selected_scene()
        if not scene: return
        dialog = SceneDialog(scene, self)
        if dialog.exec() != QDialog.Accepted: return
        candidate = Scene(**{**scene.__dict__})
        dialog.apply(candidate)
        if not candidate.valid(self.duration):
            QMessageBox.warning(self, "Invalid interval", "Start must precede end and fit within playback duration."); return
        if QMessageBox.question(self, "Confirm interval",
                                "I checked this scene and its safe resume time against this exact movie edition.",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.store.save_edit(self.movie.external_id, candidate, reviewed=True)
        self.movie = self.store.load_guide(self.movie.external_id, allow_stale=True)
        self.worker.configure(scenes=self.movie.scenes, duration=self.duration, confirmed=self.confirmed)
        self._render_scenes(); self._update_skip_label(); self._log("scene", f"Reviewed and edited {candidate.key}")

    def _add_scene(self):
        if not self.movie:
            QMessageBox.warning(self, "Guide", "Load a guide first."); return
        scene = Scene(key="manual:" + uuid4().hex, start=0, end=0,
                      category="violence", source="user", reliability="unreliable")
        dialog = SceneDialog(scene, self)
        if dialog.exec() != QDialog.Accepted: return
        dialog.apply(scene)
        if not scene.valid(self.duration):
            QMessageBox.warning(self, "Invalid interval", "Start must precede end and fit within playback duration."); return
        if QMessageBox.question(self, "Confirm interval",
                                "I checked this scene and its safe resume time against this exact movie edition.",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.store.save_edit(self.movie.external_id, scene, reviewed=True)
        self.movie = self.store.load_guide(self.movie.external_id, allow_stale=True)
        self.worker.configure(scenes=self.movie.scenes, duration=self.duration, confirmed=self.confirmed)
        self._render_scenes(); self._update_skip_label(); self._log("scene", f"Added manual scene {scene.key}")

    def _scene_check_changed(self, item):
        if item.column() != 5 or not self.movie:
            return
        scene = self.movie.scenes[item.row()]
        scene.enabled = item.checkState() == Qt.Checked
        self.store.save_edit(self.movie.external_id, scene)
        self.worker.configure(scenes=self.movie.scenes, duration=self.duration, confirmed=self.confirmed)
        self._render_scenes(); self._update_skip_label(); self._log("scene", f"{'Enabled' if scene.enabled else 'Disabled'} {scene.key}")

    def _toggle_all(self, state):
        for box in self.filter_boxes.values():
            box.setChecked(bool(state))

    def _filter_changed(self, key, value):
        self.store.set_preference("filter_" + key, value)
        self.all_filters.blockSignals(True)
        self.all_filters.setChecked(all(b.isChecked() for b in self.filter_boxes.values()))
        self.all_filters.blockSignals(False)
        self.worker.configure(filters={k: b.isChecked() for k, b in self.filter_boxes.items()})
        self._render_scenes()
        self._update_skip_label()

    def _update_skip_label(self):
        if not self.auto_skip.isChecked():
            detail = "OFF"
        elif self.suspended:
            detail = "SUSPENDED — review and reconfirm the movie edition"
        elif not self.movie:
            detail = "ON — waiting for a guide"
        elif not self.confirmed:
            detail = "ON — confirm movie edition"
        elif not any(s.can_skip(self.duration, True) and self.filter_boxes[s.category].isChecked()
                     for s in self.movie.scenes):
            detail = "ON — no selected scenes with verified times"
        else:
            detail = "ON — ready"
        self.skip_label.setText("Automatic skipping: " + detail)

    def _apply_settings(self):
        pipe = self.pipe.text().strip()
        if not pipe.startswith("\\\\.\\pipe\\"):
            QMessageBox.warning(self, "IPC pipe", "Use a path beginning with \\\\.\\pipe\\")
            return
        for key, value in {"pipe": pipe, "auto_connect": self.auto_connect.isChecked(),
                           "auto_skip": self.auto_skip.isChecked(), "margin": self.margin.value(),
                           "startup": self.startup.currentIndex()}.items():
            self.store.set_preference(key, value)
        self.worker.configure(pipe=pipe, auto_connect=self.auto_connect.isChecked(),
                              enabled=self.auto_skip.isChecked(), margin=self.margin.value(),
                              filters={k: b.isChecked() for k, b in self.filter_boxes.items()})
        self._update_skip_label()
        self._render_scenes()

    def _skipped(self, target, keys):
        self._log("skip", f"Sought to {clock(target)} for {', '.join(keys)}")

    def show_startup_window(self):
        if self.startup.currentIndex() == 1:
            self.showMinimized()
        else:
            self.showNormal()

    def closeEvent(self, event):
        self.worker.active = False
        self.worker.wait(5000)
        for worker in self.scene_fetchers:
            worker.wait(22000)
        self.store.close()
        super().closeEvent(event)


def launch():
    app = QApplication([])
    app.setStyle("Fusion")
    home = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SafePlayCompanion"
    window = MainWindow(home / "safeplay.db")
    window.show_startup_window()
    return app.exec()

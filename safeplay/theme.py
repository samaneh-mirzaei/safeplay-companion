"""SafePlay's cue-sheet visual system. Presentation only; no playback state."""
from PySide6.QtCore import Qt, QSize, QPointF, QByteArray
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QLabel, QScrollArea, QVBoxLayout,
    QWidget, QBoxLayout, QSizePolicy, QLayout, QHBoxLayout,
)
from PySide6.QtSvgWidgets import QSvgWidget

INK = '#20201e'
PAPER = '#faf9f6'
ACCENT = '#e8bd42'
PINK = '#f4bfd0'
CYAN = '#8cdee8'
CORAL = '#f27b69'
GREEN = '#a7d9ad'

STYLE = """
QWidget { color: #20201e; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow, QDialog, QScrollArea, QWidget#page, QWidget#shell, QWidget#dashboard, QWidget#settings { background: #faf9f6; }
QLabel { background: transparent; }
QLabel#brand { font-size: 36px; font-weight: 800; }
QLabel#subtitle, QLabel#caption { color: #595951; }
QLabel#providerAttribution { color: #20201e; background: #fff3d7; border-bottom: 2px solid #8cdee8; padding: 1px 4px; font-size: 12px; }
QLabel#pageTitle { font-size: 40px; font-weight: 800; }
QLabel#sectionTitle { font-size: 20px; font-weight: 700; }
QLabel#cue { font-family: 'Consolas'; font-size: 12px; color: #595951; }
QLabel#movie { font-size: 24px; font-weight: 700; }
QLabel#timecode { font-family: 'Consolas'; font-size: 20px; }
QLabel#skipState { background: #faf9f6; border: 2px solid #20201e; border-left: 8px solid #e8bd42; padding: 12px; font-weight: 600; }
QFrame#panel { background: #ffffff; border: 2px solid #20201e; }
QFrame#filterPanel { background: #fff0f3; border: 2px solid #20201e; }
QTabWidget::pane { border: 0; border-top: 2px solid #20201e; }
QTabBar::tab { background: #ffffff; border: 2px solid #20201e; border-bottom: 0; padding: 12px 24px; margin-right: 4px; font-weight: 600; }
QTabBar::tab:selected { background: #8cdee8; }
QTabBar::tab:hover { background: #fffef9; }
QTabBar::tab:selected:hover { background: #b0e8ef; }
QPushButton { background: #fffef9; border: 2px solid #20201e; border-radius: 0; padding: 6px 12px; border-right: 4px solid #20201e; border-bottom: 5px solid #20201e; font-weight: 600; min-height: 20px; }
QPushButton[primary="true"] { background: #e8bd42; }
QPushButton:hover { background: #e6e5dd; }
QPushButton[primary="true"]:hover { background: #ffe76c; }
QPushButton[destructive="true"] { background: #f9d4cd; }
QPushButton[destructive="true"]:hover { background: #f27b69; }
QPushButton:pressed { background: #20201e; color: #fffef9; }
QPushButton:focus { border-style: dashed; }
QPushButton:disabled { color: #77776f; border-color: #aaa99f; background: #e6e5dd; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #fffef9; border: 2px solid #7c7c72; border-radius: 0; padding: 6px 8px; min-height: 20px; selection-background-color: #f5d747; selection-color: #20201e; }

QSpinBox, QDoubleSpinBox { padding-right: 28px; }
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit { border: 0; padding: 0; min-height: 0; background: transparent; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 24px; height: 18px; border-left: 1px solid #7c7c72; background: #eeede6; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 24px; height: 18px; border-left: 1px solid #7c7c72; background: #eeede6; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #ccedf2; }
QSpinBox::up-arrow, QSpinBox::down-arrow, QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox { padding-right: 28px; }
QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right; width: 24px; border-left: 1px solid #7c7c72; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #20201e; background: #fffbed; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background: #e6e5dd; color: #77776f; border-color: #b7b7ad; }
QComboBox QAbstractItemView { background: #fffef9; color: #20201e; selection-background-color: #f5d747; selection-color: #20201e; }
QCheckBox { spacing: 12px; padding: 8px 0; }
QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #20201e; background: #fffef9; }
QCheckBox::indicator:checked { background: #20201e; image: none; border: 5px solid #a7d9ad; }
QTableWidget::indicator { width: 16px; height: 16px; border: 2px solid #20201e; background: #fffef9; }
QTableWidget::indicator:checked { background: #20201e; border: 4px solid #a7d9ad; }
QCheckBox::indicator:hover { border-color: #8a7314; }
QCheckBox:focus { background: #f5d747; }
QTableWidget, QTextEdit, QListWidget { background: #fffef9; alternate-background-color: #eeede6; border: 2px solid #20201e; border-radius: 0; selection-background-color: #f5d747; selection-color: #20201e; padding: 4px; gridline-color: #d6d5cb; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:focus { border: 1px dashed #20201e; }
QHeaderView::section { background: #20201e; color: #fffef9; border: 0; border-right: 1px solid #77776f; padding: 12px 8px; font-weight: 600; }
QTextEdit { font-family: 'Consolas'; font-size: 13px; padding: 16px; }
QScrollArea { border: 0; }
QScrollBar:vertical { width: 12px; background: #e6e5dd; }
QScrollBar:horizontal { height: 12px; background: #e6e5dd; }
QScrollBar::handle { background: #77776f; min-height: 28px; min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background: #20201e; color: #fffef9; border: 1px solid #20201e; padding: 8px; }
QWidget#dashboard QLabel#sectionTitle { font-size: 23px; font-weight: 800; }
QWidget#dashboard QLabel#pageTitle { font-size: 32px; }
QWidget#dashboard QLabel#movie { font-size: 25px; }
QWidget#dashboard QLabel#timecode { font-size: 22px; }
QWidget#dashboard QLabel#caption { font-size: 12px; }
QWidget#dashboard QLabel#ticketNumber { background: #20201e; color: #faf9f6; font-family: 'Consolas'; font-size: 18px; font-weight: 700; padding: 4px 8px; }
QWidget#dashboard QFrame#playbackPanel { background: #e3f3f1; border: 2px solid #20201e; }
QWidget#dashboard QFrame#guidePanel { background: #fff3d7; border: 2px solid #20201e; }
QWidget#dashboard QFrame#filtersPanel { background: #f9dce5; border: 2px solid #20201e; }
QWidget#dashboard QCheckBox[filterRow="true"] { border: 2px solid #20201e; padding: 6px 12px; background: #faf9f6; }
QWidget#dashboard QCheckBox[category="sexual"] { background: #fff0f4; }
QWidget#dashboard QCheckBox[category="violence"] { background: #ffd4c9; }
QWidget#dashboard QCheckBox[category="language"] { background: #ccedf2; }
QWidget#dashboard QCheckBox[category="substances"] { background: #d2e9ba; }
QWidget#dashboard QCheckBox[filterRow="true"]:hover { background: #ffffff; }
QWidget#dashboard QCheckBox[filterRow="true"]:focus { border: 2px dashed #20201e; }
QWidget#dashboard QPushButton#confirmEdition { background: #b8dba0; }
QWidget#dashboard QPushButton#confirmEdition:hover { background: #d2e9ba; }
QWidget#dashboard QLabel#skipState { padding: 6px 10px; }
QWidget#settings QLabel#pageTitle { font-size: 32px; }
QWidget#settings QLabel#sectionTitle { font-size: 23px; font-weight: 800; }
QWidget#settings QLabel#ticketNumber { background: #20201e; color: #faf9f6; font-family: 'Consolas'; font-size: 18px; font-weight: 700; padding: 4px 8px; }
QWidget#settings QFrame#settingsConnection { background: #fff3d7; border: 2px solid #20201e; }
QWidget#settings QFrame#settingsBehavior { background: #e3f3f1; border: 2px solid #20201e; }
"""


class CinemaIllustration(QSvgWidget):
    """Inline vector artwork, bundled as code so frozen builds remain portable."""
    def __init__(self, kind='projector'):
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        if kind == 'projector':
            self.setFixedSize(176, 112)
            drawing = '''<defs><pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#20201e"/></pattern></defs>
            <path d="M140 72 L221 35 L218 126 L142 107Z" fill="#fff3d7" stroke="none"/>
            <path d="M5 97H49V146H5Z" fill="url(#dots)" stroke="none"/>
            <g stroke="#20201e" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round">
            <path d="M60 128L50 148M121 129L134 148M52 149H142" fill="none"/>
            <path d="M40 63L139 59L143 127L39 131Z" fill="#20201e"/>
            <path d="M35 58L134 55L138 122L34 126Z" fill="#f4bfd0"/>
            <circle cx="57" cy="37" r="27" fill="#e8bd42"/><circle cx="113" cy="34" r="25" fill="#a7d9ad"/>
            <g fill="#faf9f6"><circle cx="57" cy="23" r="6"/><circle cx="44" cy="42" r="6"/><circle cx="68" cy="45" r="6"/>
            <circle cx="113" cy="21" r="5"/><circle cx="102" cy="40" r="5"/><circle cx="124" cy="40" r="5"/></g>
            <path d="M134 77L155 68L157 108L137 101Z" fill="#8cdee8"/>
            <path d="M70 78L70 105L92 91Z" fill="#faf9f6"/>
            <path d="M43 114L61 113M102 112L124 111" fill="none"/>
            <path d="M185 10L190 23L204 25L193 33L194 47L183 39L170 43L175 30L167 19L181 21Z" fill="#f27b69"/>
            <path d="M204 130L216 142M216 130L204 142" fill="none"/>
            <circle cx="18" cy="72" r="5" fill="#8cdee8"/>
            </g>'''
            box = '0 0 232 152'
        else:
            self.setFixedSize(64, 40)
            drawing = ('''<g stroke="#20201e" stroke-width="2" stroke-linejoin="round"><path d="M7 8L44 5L48 32L10 36Z" fill="#faf9f6"/><path d="M15 15L35 13M17 23L31 21"/><circle cx="43" cy="22" r="10" fill="#8cdee8"/><path d="M50 30L60 38" stroke-width="5"/></g>''' if kind == 'guide' else
                       '''<g stroke="#20201e" stroke-width="2" stroke-linecap="round"><path d="M8 8L55 9M8 20L55 21M8 32L55 33"/><circle cx="22" cy="8" r="6" fill="#e8bd42"/><circle cx="43" cy="21" r="6" fill="#8cdee8"/><circle cx="29" cy="33" r="6" fill="#a7d9ad"/></g>''')
            box = '0 0 64 40'
        self.load(QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">{drawing}</svg>'.encode()))


def ticket_panel(title, number, name, illustration=None):
    frame = QFrame(); frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 8, 16, 12); layout.setSpacing(8)
    heading = QHBoxLayout(); heading.setSpacing(12)
    badge = label(number, 'ticketNumber'); badge.setFixedSize(44, 36)
    heading.addWidget(badge); heading.addWidget(label(title, 'sectionTitle'), 1)
    if illustration: heading.addWidget(CinemaIllustration(illustration))
    layout.addLayout(heading)
    shadow = QGraphicsDropShadowEffect(frame)
    shadow.setBlurRadius(0); shadow.setOffset(4, 4); shadow.setColor(QColor(INK))
    frame.setGraphicsEffect(shadow)
    return frame, layout


class CueArtwork(QWidget):
    """Small, static print illustration; dots never sit behind readable content."""
    def __init__(self, variant=0):
        super().__init__()
        self.variant = variant
        self.setFixedSize(112, 64)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(INK))
        for x in range(60, 108, 8):
            for y in range(8, 60, 8):
                painter.drawEllipse(QPointF(x, y), 0.8, 0.8)
        painter.setPen(QPen(QColor(INK), 2))
        painter.setBrush(QColor((PINK, CYAN, GREEN, ACCENT)[self.variant % 4]))
        painter.drawRect(10, 12, 58, 40)
        painter.setBrush(QColor(INK))
        painter.drawPolygon(QPolygonF([QPointF(32, 22), QPointF(32, 42), QPointF(49, 32)]))
        painter.setBrush(QColor(CORAL))
        painter.drawEllipse(QPointF(80, 42), 13, 13)
        painter.end()


def label(text, role='caption'):
    item = QLabel(text)
    item.setObjectName(role)
    item.setWordWrap(True)
    item.setTextFormat(Qt.PlainText)
    item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return item


def panel(title, cue, filters=False):
    frame = QFrame()
    frame.setObjectName('filterPanel' if filters else 'panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(12)
    layout.addWidget(label(cue, 'cue'))
    layout.addWidget(label(title, 'sectionTitle'))
    shadow = QGraphicsDropShadowEffect(frame)
    shadow.setBlurRadius(0)
    shadow.setOffset(5, 5)
    shadow.setColor(QColor(INK))
    frame.setGraphicsEffect(shadow)
    return frame, layout


def scroll(page):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(page)
    return area


class AdaptiveColumns(QWidget):
    """Stack the same controls when the viewport cannot fit two columns."""
    def __init__(self, first, second):
        super().__init__()
        self.columns = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.columns.setSizeConstraint(QLayout.SetNoConstraint)
        self.columns.setContentsMargins(0, 0, 8, 8)
        self.columns.setSpacing(24)
        self.columns.addWidget(first, 3)
        self.columns.addWidget(second, 2)

    def minimumSizeHint(self):
        # Let the viewport narrow this container before the columns reflow.
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        self.columns.setDirection(QBoxLayout.TopToBottom if self.width() < 820 else QBoxLayout.LeftToRight)
        super().resizeEvent(event)

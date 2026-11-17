"""Restrained secondary views built from the Dashboard's existing tokens."""
from html import escape
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from .theme import INK, PAPER, label, ticket_panel

STYLE = '''
QWidget#secondary { background: #faf9f6; }
QWidget#secondary QLabel#pageTitle { font-size: 32px; }
QWidget#secondary QLabel#sectionTitle { font-size: 22px; font-weight: 800; }
QWidget#secondary QLabel#ticketNumber { background: #20201e; color: #faf9f6; font-family: 'Consolas'; font-size: 18px; padding: 4px 8px; }
QFrame#secondaryPanel { background: #ffffff; border: 2px solid #20201e; }
QFrame#emptyPanel { background: #fff3d7; border: 2px solid #20201e; }
QWidget#secondary QTableWidget { background: #ffffff; alternate-background-color: #f0f8f4; selection-background-color: #b4e6ec; selection-color: #20201e; padding: 0; border: 0; gridline-color: #d7e2db; }
QWidget#secondary QHeaderView::section { background: #fff3d7; color: #20201e; border-bottom: 2px solid #20201e; border-right: 1px solid #d7d2c5; padding: 10px 8px; }
QWidget#secondary QTextEdit { background: #ffffff; border: 0; font-family: 'Segoe UI'; font-size: 14px; padding: 4px; }
'''

SETTINGS_STYLE = '''
QWidget#settings QCheckBox { background: #faf9f6; border: 1px solid #b5beb5; padding: 8px; }
QWidget#settings QCheckBox:focus { border: 2px dashed #20201e; }
QWidget#settings QLineEdit:focus, QWidget#settings QComboBox:focus, QWidget#settings QDoubleSpinBox:focus { border-color: #20201e; background: #fffbed; }
'''


def empty_state(title, description):
    frame, layout = ticket_panel(title, '—', 'emptyPanel', 'guide')
    text = label(description)
    layout.addWidget(text)
    return frame, text


class SceneLabels(QStyledItemDelegate):
    """Paint labels while retaining native selection, focus and checkbox behavior."""
    def paint(self, painter, option, index):
        text = str(index.data() or '')
        fills = {
            'Sexual Content & Nudity': '#f9dce5', 'Violence & Gore': '#ffd4c9',
            'Profanity & Language': '#ccedf2', 'Drugs & Alcohol': '#d2e9ba',
            'Yes': '#d2e9ba', 'No': '#eeede6', 'Missing': '#ffd4c9',
        }
        if index.column() not in (0, 1, 2, 6) or text not in fills:
            return super().paint(painter, option, index)
        base = QStyleOptionViewItem(option)
        self.initStyleOption(base, index)
        base.text = ''
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, base, painter, option.widget)
        painter.save()
        font = QFont(option.font); font.setPixelSize(12); font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        width = min(painter.fontMetrics().horizontalAdvance(text) + 16, option.rect.width() - 12)
        rect = QRect(option.rect.x() + 6, option.rect.y() + 10, width, option.rect.height() - 20)
        painter.setPen(QPen(QColor(INK), 1)); painter.setBrush(QColor(fills[text]))
        painter.drawRect(rect)
        painter.drawText(rect.adjusted(6, 0, -6, 0), Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(text, Qt.ElideRight, rect.width() - 12))
        painter.restore()


def activity_html(events):
    """Escape all external content; keep full timestamps and event details copyable."""
    titles = {'connection': 'Player connection', 'guide': 'Guide update', 'skip': 'Scene skipped',
              'scene': 'Scene edited', 'movie': 'Media detected', 'warning': 'Playback warning', 'error': 'Error'}
    rows = []
    for at, kind, detail in events:
        color = {'skip': '#d2e9ba', 'error': '#ffd4c9', 'warning': '#fff3d7',
                 'guide': '#ccedf2'}.get(kind, '#eeede6')
        background = {'skip': '#f0f8f4', 'error': '#fff2ee', 'warning': '#fff9e9'}.get(kind, '#ffffff')
        timestamp = escape(str(at))
        rows.append(f'''<tr bgcolor="{background}"><td width="12" bgcolor="{color}"></td>
        <td style="padding:12px"><b>{escape(titles.get(kind, str(kind)))}</b>
        <span style="color:#595951"> · {escape(str(kind))}</span><br>
        <span style="font-family:Consolas;font-size:11px;color:#595951">{timestamp}</span><br>
        <span>{escape(str(detail)).replace(chr(10), '<br>')}</span></td></tr>''')
    return '<table width="100%" bgcolor="#deded5" cellspacing="1" cellpadding="8">' + ''.join(rows) + '</table>'

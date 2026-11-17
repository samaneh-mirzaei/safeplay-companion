"""Native Qt controls with explicit, reliably visible arrow glyphs."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPolygonF
from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QComboBox, QStyle, QStyleOptionSpinBox, QStyleOptionComboBox


def arrow(widget, rect, up=False, enabled=True):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor('#20201e' if enabled else '#92928a'))
    x, y = rect.center().x(), rect.center().y()
    direction = -1 if up else 1
    painter.drawPolygon(QPolygonF([QPointF(x - 4, y - direction * 2),
                                  QPointF(x + 4, y - direction * 2),
                                  QPointF(x, y + direction * 3)]))
    painter.end()


class SpinArrows:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lineEdit().setTextMargins(8, 0, 4, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox(); self.initStyleOption(option)
        for control, up, available in (
            (QStyle.SC_SpinBoxUp, True, self.value() < self.maximum()),
            (QStyle.SC_SpinBoxDown, False, self.value() > self.minimum()),
        ):
            rect = self.style().subControlRect(QStyle.CC_SpinBox, option, control, self)
            arrow(self, rect, up, self.isEnabled() and available)
        painter = QPainter(self)
        painter.setPen(QColor('#20201e' if self.hasFocus() else '#7c7c72' if self.isEnabled() else '#b7b7ad'))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.end()


class IntegerInput(SpinArrows, QSpinBox):
    pass


class DecimalInput(SpinArrows, QDoubleSpinBox):
    pass


class ChoiceInput(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox(); self.initStyleOption(option)
        rect = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)
        arrow(self, rect, enabled=self.isEnabled())

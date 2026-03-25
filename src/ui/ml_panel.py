from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui.styles import DIMMED_TEXT, FONT_FAMILY


class MLPanel(QWidget):
    """Grayed-out placeholder panel for future ML arrival predictions."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            "MLPanel { background-color: #1f1f1f; border-radius: 8px; }"
        )
        self.setFixedHeight(50)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        label = QLabel("ML Arrival Prediction [Coming Soon]")
        label.setFont(QFont(FONT_FAMILY, 13))
        label.setStyleSheet(f"color: {DIMMED_TEXT};")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

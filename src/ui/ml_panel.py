from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.config import ML_MIN_COMPLETED_RUNS
from src.ui.styles import DIMMED_TEXT, FONT_FAMILY, WHITE

_MAX_PREDICTION_ROWS = 4
_ROUTE_COLORS: dict[str, str] = {"Red": "#c60c30", "P": "#522398"}


class MLPanel(QWidget):
    """Live panel showing CNN+LSTM arrival predictions compared to CTA
    estimates.  Updates every poll cycle once the model has been trained."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "MLPanel { background-color: #1f1f1f; border-radius: 8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("ML Arrival Prediction")
        title.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {WHITE};")
        header.addWidget(title)

        self._status = QLabel()
        self._status.setFont(QFont(FONT_FAMILY, 11))
        self._status.setStyleSheet(f"color: {DIMMED_TEXT};")
        self._status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addWidget(self._status, 1)
        layout.addLayout(header)

        self._rows: list[_PredictionRow] = []
        for _ in range(_MAX_PREDICTION_ROWS):
            row = _PredictionRow()
            row.hide()
            layout.addWidget(row)
            self._rows.append(row)

        self._empty = QLabel("Collecting train data\u2026")
        self._empty.setFont(QFont(FONT_FAMILY, 12))
        self._empty.setStyleSheet(f"color: {DIMMED_TEXT};")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        self.set_status("Waiting for data", 0, 0)

    def set_status(self, phase: str, completed: int, active: int) -> None:
        parts = [phase]
        if completed > 0:
            parts.append(f"{completed} runs learned")
        if active > 0:
            parts.append(f"{active} tracked")
        self._status.setText(" \u00b7 ".join(parts))

    def update_predictions(self, predictions: list) -> None:
        has = bool(predictions)
        self._empty.setVisible(not has)

        if not has:
            self._empty.setText("Collecting train data\u2026")

        for i, row in enumerate(self._rows):
            if i < len(predictions):
                p = predictions[i]
                row.render(
                    p.route,
                    p.destination,
                    p.cta_minutes,
                    p.predicted_minutes,
                    p.confidence,
                )
                row.show()
            else:
                row.hide()


class _PredictionRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        layout.addWidget(self._dot)

        self._dest = QLabel()
        self._dest.setFont(QFont(FONT_FAMILY, 12))
        self._dest.setStyleSheet(f"color: {WHITE};")
        layout.addWidget(self._dest, 1)

        self._cta = QLabel()
        self._cta.setFont(QFont(FONT_FAMILY, 12))
        self._cta.setStyleSheet(f"color: {DIMMED_TEXT};")
        layout.addWidget(self._cta)

        self._ml = QLabel()
        self._ml.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        layout.addWidget(self._ml)

        self._delta = QLabel()
        self._delta.setFont(QFont(FONT_FAMILY, 11))
        self._delta.setFixedWidth(50)
        self._delta.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._delta)

    def render(
        self,
        route: str,
        destination: str,
        cta_min: float,
        ml_min: float,
        confidence: float,
    ) -> None:
        color = _ROUTE_COLORS.get(route, DIMMED_TEXT)
        self._dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )
        self._dest.setText(destination)
        self._cta.setText(f"CTA: {int(cta_min)} min")

        alpha = max(0.4, confidence)
        self._ml.setText(f"ML: {int(ml_min)} min")
        self._ml.setStyleSheet(f"color: rgba(255,255,255,{alpha});")

        diff = ml_min - cta_min
        if abs(diff) < 0.5:
            self._delta.setText("=")
            self._delta.setStyleSheet(f"color: {DIMMED_TEXT};")
        elif diff > 0:
            self._delta.setText(f"+{int(diff)}")
            self._delta.setStyleSheet("color: #ff6b6b;")
        else:
            self._delta.setText(f"{int(diff)}")
            self._delta.setStyleSheet("color: #69db7c;")

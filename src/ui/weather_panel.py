from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.services.weather_service import WeatherForecast
from src.ui.styles import BG_COLOR, DIMMED_TEXT, FONT_FAMILY, WHITE


class WeatherPanel(QWidget):
    """Displays Chicago weather from Earth2Studio forecast output."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            f"WeatherPanel {{ background-color: #252525; border-radius: 8px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Chicago Weather (Earth2Studio)")
        title.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {WHITE};")
        layout.addWidget(title)

        self._current_row = QWidget()
        current_layout = QHBoxLayout(self._current_row)
        current_layout.setContentsMargins(0, 0, 0, 0)
        current_layout.setSpacing(20)

        self._temp_label = QLabel()
        self._temp_label.setFont(QFont(FONT_FAMILY, 22, QFont.Weight.Bold))
        self._temp_label.setStyleSheet(f"color: {WHITE};")

        self._wind_label = QLabel()
        self._wind_label.setFont(QFont(FONT_FAMILY, 13))
        self._wind_label.setStyleSheet(f"color: rgba(255,255,255,0.8);")

        current_layout.addWidget(self._temp_label)
        current_layout.addWidget(self._wind_label)
        current_layout.addStretch()
        layout.addWidget(self._current_row)

        self._forecast_label = QLabel()
        self._forecast_label.setFont(QFont(FONT_FAMILY, 12))
        self._forecast_label.setStyleSheet(f"color: rgba(255,255,255,0.6);")
        self._forecast_label.setWordWrap(True)
        layout.addWidget(self._forecast_label)

        self._unavailable_label = QLabel("Weather forecast unavailable")
        self._unavailable_label.setFont(QFont(FONT_FAMILY, 13))
        self._unavailable_label.setStyleSheet(f"color: {DIMMED_TEXT};")
        self._unavailable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._unavailable_label)

        self._show_unavailable()

    def update_forecast(self, forecast: WeatherForecast | None) -> None:
        if forecast is None or not forecast.steps:
            self._show_unavailable()
            return

        self._current_row.show()
        self._forecast_label.show()
        self._unavailable_label.hide()

        current = forecast.steps[0]
        self._temp_label.setText(f"{current.temperature_f:.0f}\u00b0F")
        self._wind_label.setText(
            f"Wind {current.wind_speed_mph:.0f} mph {current.wind_direction}"
        )

        if len(forecast.steps) > 1:
            parts: list[str] = []
            for step in forecast.steps[1:]:
                hour_label = step.valid_time.strftime("%-I%p").lower()
                parts.append(f"{hour_label}: {step.temperature_f:.0f}\u00b0F")
            self._forecast_label.setText("6h forecast: " + "  \u2022  ".join(parts))
        else:
            self._forecast_label.setText("")

    def _show_unavailable(self) -> None:
        self._current_row.hide()
        self._forecast_label.hide()
        self._unavailable_label.show()

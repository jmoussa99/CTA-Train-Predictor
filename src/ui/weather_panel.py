from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.services.weather_service import WeatherForecast
from src.ui.styles import BG_COLOR, DIMMED_TEXT, FONT_FAMILY, WHITE

_MAX_HOURS = 12


class WeatherPanel(QWidget):
    """Displays Chicago hourly weather from Open-Meteo."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            "WeatherPanel { background-color: #252525; border-radius: 8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Chicago Weather")
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

        self._precip_label = QLabel()
        self._precip_label.setFont(QFont(FONT_FAMILY, 13))
        self._precip_label.setStyleSheet("color: rgba(255,255,255,0.8);")

        current_layout.addWidget(self._temp_label)
        current_layout.addWidget(self._precip_label)
        current_layout.addStretch()
        layout.addWidget(self._current_row)

        self._hourly_grid = QWidget()
        grid = QGridLayout(self._hourly_grid)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setSpacing(4)

        self._hour_labels: list[QLabel] = []
        self._hour_emojis: list[QLabel] = []
        self._hour_temps: list[QLabel] = []
        self._hour_precips: list[QLabel] = []

        header_font = QFont(FONT_FAMILY, 10, QFont.Weight.Bold)
        value_font = QFont(FONT_FAMILY, 10)
        emoji_font = QFont(FONT_FAMILY, 14)

        for col in range(_MAX_HOURS):
            hour_lbl = QLabel()
            hour_lbl.setFont(header_font)
            hour_lbl.setStyleSheet("color: rgba(255,255,255,0.5);")
            hour_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(hour_lbl, 0, col)
            self._hour_labels.append(hour_lbl)

            emoji_lbl = QLabel()
            emoji_lbl.setFont(emoji_font)
            emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(emoji_lbl, 1, col)
            self._hour_emojis.append(emoji_lbl)

            temp_lbl = QLabel()
            temp_lbl.setFont(value_font)
            temp_lbl.setStyleSheet(f"color: {WHITE};")
            temp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(temp_lbl, 2, col)
            self._hour_temps.append(temp_lbl)

            precip_lbl = QLabel()
            precip_lbl.setFont(value_font)
            precip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(precip_lbl, 3, col)
            self._hour_precips.append(precip_lbl)

        layout.addWidget(self._hourly_grid)

        self._unavailable_label = QLabel("Weather forecast unavailable")
        self._unavailable_label.setFont(QFont(FONT_FAMILY, 13))
        self._unavailable_label.setStyleSheet(f"color: {DIMMED_TEXT};")
        self._unavailable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._unavailable_label)

        self._show_unavailable()

    def update_forecast(self, forecast: WeatherForecast | None) -> None:
        if forecast is None or (not forecast.current and not forecast.steps):
            self._show_unavailable()
            return

        self._current_row.show()
        self._hourly_grid.show()
        self._unavailable_label.hide()

        if forecast.current:
            cur = forecast.current
            self._temp_label.setText(f"{cur.emoji} {cur.temperature_c:.0f}\u00b0C")
            self._precip_label.setText(
                f"\U0001f4a7 precip: {cur.precipitation_mm:.1f} mm"
                if cur.precipitation_mm > 0
                else ""
            )
        elif forecast.steps:
            step = forecast.steps[0]
            self._temp_label.setText(f"{step.emoji} {step.temperature_c:.0f}\u00b0C")
            self._precip_label.setText("")

        upcoming = forecast.steps[: _MAX_HOURS]
        for i in range(_MAX_HOURS):
            if i < len(upcoming):
                step = upcoming[i]
                self._hour_labels[i].setText(step.valid_time.strftime("%-I%p").lower())
                self._hour_emojis[i].setText(step.emoji)
                self._hour_temps[i].setText(f"{step.temperature_c:.0f}\u00b0")
                prob = step.precipitation_probability
                self._hour_precips[i].setText(f"{prob}%")
                self._hour_precips[i].setStyleSheet(
                    f"color: {'#4fc3f7' if prob >= 50 else 'rgba(255,255,255,0.5)'};"
                )
                self._hour_labels[i].show()
                self._hour_emojis[i].show()
                self._hour_temps[i].show()
                self._hour_precips[i].show()
            else:
                self._hour_labels[i].hide()
                self._hour_emojis[i].hide()
                self._hour_temps[i].hide()
                self._hour_precips[i].hide()

    def _show_unavailable(self) -> None:
        self._current_row.hide()
        self._hourly_grid.hide()
        self._unavailable_label.show()

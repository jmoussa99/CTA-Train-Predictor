from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from src.config import BG_COLOR, POLL_INTERVAL_SEC
from src.services.cta_api import CTAClient, TrainETA
from src.services.transfer_calculator import LindenConnection, TransferCalculator
from src.services.weather_service import WeatherForecast, WeatherService
from src.ui.ml_panel import MLPanel
from src.ui.styles import DIMMED_TEXT, FONT_FAMILY, MAIN_STYLESHEET
from src.ui.train_panel import TrainPanel
from src.ui.weather_panel import WeatherPanel

logger = logging.getLogger(__name__)


class _CTAPollSignals(QObject):
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)


class _CTAPollWorker(QRunnable):
    def __init__(self, client: CTAClient, calculator: TransferCalculator):
        super().__init__()
        self.signals = _CTAPollSignals()
        self._client = client
        self._calculator = calculator

    @pyqtSlot()
    def run(self):
        try:
            red_trains = self._client.fetch_sheridan_red()
            purple_trains = self._client.fetch_wilson_purple_linden()

            howard_trains = [t for t in red_trains if t.destination == "Howard"]
            connections = self._calculator.compute_connections(
                howard_trains, purple_trains
            )

            self.signals.finished.emit(red_trains, connections)
        except Exception as exc:
            logger.exception("CTA poll failed")
            self.signals.error.emit(str(exc))


class _WeatherSignals(QObject):
    finished = pyqtSignal(object)


class _WeatherWorker(QRunnable):
    def __init__(self, service: WeatherService):
        super().__init__()
        self.signals = _WeatherSignals()
        self._service = service

    @pyqtSlot()
    def run(self):
        forecast = self._service.get_forecast(force_refresh=True)
        self.signals.finished.emit(forecast)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CTA Sheridan Train Tracker")
        self.setMinimumSize(900, 500)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._client = CTAClient()
        self._calculator = TransferCalculator()
        self._weather_service = WeatherService()
        self._thread_pool = QThreadPool()

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._train_panel = TrainPanel()
        layout.addWidget(self._train_panel)

        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(12, 0, 12, 8)
        bottom_layout.setSpacing(8)

        self._weather_panel = WeatherPanel()
        bottom_layout.addWidget(self._weather_panel)

        self._ml_panel = MLPanel()
        bottom_layout.addWidget(self._ml_panel)

        self._status_label = QLabel()
        self._status_label.setObjectName("status")
        self._status_label.setFont(QFont(FONT_FAMILY, 11))
        self._status_label.setStyleSheet(f"color: {DIMMED_TEXT};")
        bottom_layout.addWidget(self._status_label)

        layout.addWidget(bottom_container)
        layout.addStretch()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_SEC * 1000)
        self._poll_timer.timeout.connect(self._poll_cta)

        self._poll_cta()
        self._poll_timer.start()

        self._start_weather_fetch()

    def _poll_cta(self) -> None:
        worker = _CTAPollWorker(self._client, self._calculator)
        worker.signals.finished.connect(self._on_cta_data)
        worker.signals.error.connect(self._on_cta_error)
        self._thread_pool.start(worker)

    def _on_cta_data(
        self,
        red_trains: list[TrainETA],
        connections: list[LindenConnection],
    ) -> None:
        self._train_panel.update_data(red_trains, connections)
        now_str = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(f"Last updated: {now_str} CT")

    def _on_cta_error(self, message: str) -> None:
        now_str = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(
            f"Service info unavailable \u2022 Last attempt: {now_str} CT"
        )

    def _start_weather_fetch(self) -> None:
        worker = _WeatherWorker(self._weather_service)
        worker.signals.finished.connect(self._on_weather_ready)
        self._thread_pool.start(worker)

    def _on_weather_ready(self, forecast: WeatherForecast | None) -> None:
        self._weather_panel.update_forecast(forecast)

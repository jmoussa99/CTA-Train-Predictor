from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from src.config import BG_COLOR, ML_MIN_COMPLETED_RUNS, POLL_INTERVAL_SEC
from src.models.data_buffer import ObservationBuffer
from src.models.ml_predictor import ArrivalPredictor
from src.services.cta_api import CTAClient, TrainETA
from src.services.transfer_calculator import LindenConnection, TransferCalculator
from src.services.weather_service import CurrentWeather, WeatherForecast, WeatherService
from src.ui.ml_panel import MLPanel
from src.ui.styles import DIMMED_TEXT, FONT_FAMILY, MAIN_STYLESHEET
from src.ui.train_panel import TrainPanel
from src.ui.weather_panel import WeatherPanel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class _CTAPollSignals(QObject):
    finished = pyqtSignal(list, list, list)
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

            self.signals.finished.emit(red_trains, connections, purple_trains)
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


class _MLSignals(QObject):
    finished = pyqtSignal(object)


class _MLWorker(QRunnable):
    """Runs model training (when new data is available) and inference
    in a background thread so the UI stays responsive."""

    def __init__(
        self,
        predictor: ArrivalPredictor,
        training_data: tuple | None,
        sequences: dict,
        active_runs: dict,
    ):
        super().__init__()
        self.signals = _MLSignals()
        self._predictor = predictor
        self._training_data = training_data
        self._sequences = sequences
        self._active_runs = active_runs

    @pyqtSlot()
    def run(self):
        if self._training_data is not None:
            X, y = self._training_data
            self._predictor.train(X, y)

        preds = self._predictor.predict(self._sequences, self._active_runs)

        self.signals.finished.emit(
            {
                "predictions": preds,
                "is_trained": self._predictor.is_trained,
                "rounds": self._predictor.rounds,
                "loss": self._predictor.last_loss,
            }
        )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

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

        self._ml_buffer = ObservationBuffer()
        self._ml_predictor = ArrivalPredictor()
        self._ml_running = False
        self._current_weather: CurrentWeather | None = None

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

    # ---- CTA polling -------------------------------------------------------

    def _poll_cta(self) -> None:
        worker = _CTAPollWorker(self._client, self._calculator)
        worker.signals.finished.connect(self._on_cta_data)
        worker.signals.error.connect(self._on_cta_error)
        self._thread_pool.start(worker)

    def _on_cta_data(
        self,
        red_trains: list[TrainETA],
        connections: list[LindenConnection],
        purple_trains: list[TrainETA],
    ) -> None:
        self._train_panel.update_data(red_trains, connections)
        now_str = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(f"Last updated: {now_str} CT")

        self._feed_ml(red_trains, purple_trains)

    def _on_cta_error(self, message: str) -> None:
        now_str = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(
            f"Service info unavailable \u2022 Last attempt: {now_str} CT"
        )

    # ---- Weather ------------------------------------------------------------

    def _start_weather_fetch(self) -> None:
        worker = _WeatherWorker(self._weather_service)
        worker.signals.finished.connect(self._on_weather_ready)
        self._thread_pool.start(worker)

    def _on_weather_ready(self, forecast: WeatherForecast | None) -> None:
        self._weather_panel.update_forecast(forecast)
        if forecast and forecast.current:
            self._current_weather = forecast.current

    # ---- ML pipeline --------------------------------------------------------

    def _feed_ml(
        self,
        red_trains: list[TrainETA],
        purple_trains: list[TrainETA],
    ) -> None:
        cw = self._current_weather
        self._ml_buffer.record(
            red_trains + purple_trains,
            weather_temp=cw.temperature_c if cw else 20.0,
            weather_precip=cw.precipitation_mm if cw else 0.0,
            weather_code=cw.weather_code if cw else 0,
        )

        buf = self._ml_buffer
        if buf.is_ready():
            phase = "Active" if self._ml_predictor.is_trained else "Training\u2026"
        else:
            phase = f"Collecting ({buf.completed_count}/{ML_MIN_COMPLETED_RUNS})"
        self._ml_panel.set_status(phase, buf.completed_count, buf.active_count)

        if not self._ml_running:
            self._dispatch_ml()

    def _dispatch_ml(self) -> None:
        buf = self._ml_buffer

        training_data = None
        if buf.is_ready() and buf.new_completions > 0:
            training_data = buf.build_training_data()
            buf.reset_completion_counter()

        if training_data is None and not self._ml_predictor.is_trained:
            return

        sequences = buf.get_active_sequences()
        if not sequences and training_data is None:
            return

        active_snapshot = {k: list(v) for k, v in buf.active_runs.items()}

        self._ml_running = True
        worker = _MLWorker(
            self._ml_predictor, training_data, sequences, active_snapshot
        )
        worker.signals.finished.connect(self._on_ml_done)
        self._thread_pool.start(worker)

    def _on_ml_done(self, result: dict) -> None:
        self._ml_running = False

        if result["is_trained"]:
            r = result["rounds"]
            loss = result["loss"]
            self._ml_panel.set_status(
                f"Active \u00b7 round {r} \u00b7 loss {loss:.3f}",
                self._ml_buffer.completed_count,
                self._ml_buffer.active_count,
            )
            self._ml_panel.update_predictions(result["predictions"])

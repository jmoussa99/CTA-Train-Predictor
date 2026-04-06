from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.config import PURPLE_COLOR, RED_COLOR, WALK_TO_SHERIDAN_MIN
from src.services.cta_api import TrainETA
from src.services.transfer_calculator import LindenConnection
from src.ui.styles import (
    FONT_FAMILY,
    FONT_HEADER_SIZE,
    FONT_METADATA_SIZE,
    HEADER_STYLESHEET,
    WHITE,
)
from src.ui.train_box import TrainBox, TrainDisplayData

_MISSED_THRESHOLD = -1.0


def _catchable(trains: list[TrainETA]) -> list[TrainETA]:
    return [t for t in trains if t.leave_home_in >= _MISSED_THRESHOLD]


def _eta_to_display(train: TrainETA, line_prefix: str) -> TrainDisplayData:
    lh = train.leave_home_in
    return TrainDisplayData(
        line_label=f"{line_prefix} #{train.run_number} to",
        destination=train.destination,
        leave_home_min=lh,
        is_due=lh <= 1,
        is_delayed=train.is_delayed,
        is_scheduled=train.is_scheduled,
    )


def _conn_to_display(conn: LindenConnection) -> TrainDisplayData:
    wait_text = f"{int(conn.wait_at_wilson_min)} min wait at Wilson"
    return TrainDisplayData(
        line_label=f"Purple Line (Red #{conn.red_run} \u2192 Prp #{conn.purple_run})",
        destination="Linden",
        leave_home_min=conn.leave_home_in,
        is_due=conn.leave_home_in <= 1,
        is_delayed=conn.is_delayed,
        is_scheduled=False,
        subtitle=wait_text,
    )


class TrainPanel(QWidget):
    """Vertically stacked TrainBox rows for Howard, 95th, and Linden
    destinations, styled like a CTA display board."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header.setStyleSheet(HEADER_STYLESHEET)
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        station_label = QLabel("Next 'L' services from Sheridan")
        station_label.setObjectName("headerStation")
        station_label.setFont(QFont(FONT_FAMILY, FONT_HEADER_SIZE, QFont.Weight.Bold))
        station_label.setStyleSheet(f"color: {WHITE};")

        header_layout.addWidget(station_label)
        header_layout.addStretch()

        if WALK_TO_SHERIDAN_MIN > 0:
            walk_label = QLabel(f"{WALK_TO_SHERIDAN_MIN} min walk")
            walk_label.setObjectName("headerWalk")
            walk_label.setFont(QFont(FONT_FAMILY, FONT_METADATA_SIZE))
            walk_label.setStyleSheet(f"color: #999999;")
            walk_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(walk_label)

        root_layout.addWidget(header)

        self._howard_box = TrainBox(1, RED_COLOR)
        self._95th_box = TrainBox(2, RED_COLOR)
        self._linden_box = TrainBox(3, PURPLE_COLOR)

        root_layout.addWidget(self._howard_box)
        root_layout.addWidget(self._95th_box)
        root_layout.addWidget(self._linden_box)

    def update_data(
        self,
        red_trains: list[TrainETA],
        linden_connections: list[LindenConnection],
    ) -> None:
        howard = _catchable(
            sorted(
                [t for t in red_trains if t.destination == "Howard"],
                key=lambda t: t.leave_home_in,
            )
        )
        ninety_fifth = _catchable(
            sorted(
                [t for t in red_trains if t.destination != "Howard"],
                key=lambda t: t.leave_home_in,
            )
        )

        howard_display = [_eta_to_display(t, "Red Line") for t in howard[:2]]
        ninety_fifth_display = [_eta_to_display(t, "Red Line") for t in ninety_fifth[:2]]

        catchable_linden = [c for c in linden_connections if c.leave_home_in >= _MISSED_THRESHOLD]
        linden_display = [_conn_to_display(c) for c in catchable_linden[:2]]

        self._howard_box.set_trains(howard_display)
        self._95th_box.set_trains(ninety_fifth_display)
        self._linden_box.set_trains(linden_display)

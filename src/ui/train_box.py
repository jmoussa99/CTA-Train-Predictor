from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.config import FADE_DURATION_MS, ROTATION_INTERVAL_SEC
from src.ui.styles import (
    AMBER_COLOR,
    DIMMED_TEXT,
    FONT_DESTINATION_SIZE,
    FONT_FAMILY,
    FONT_METADATA_SIZE,
    FONT_MINUTES_SIZE,
    WHITE,
)

_LABEL_TRANSPARENT = "background: transparent;"


@dataclass
class TrainDisplayData:
    line_label: str
    destination: str
    leave_home_min: float
    is_due: bool
    is_delayed: bool
    is_scheduled: bool
    subtitle: str | None = None


class TrainBox(QFrame):
    """A full-width color-coded row that displays one train at a time and
    optionally rotates between two trains with a fade transition.

    Layout mirrors the CTA display board:
        [#]  Line info (small)
             Destination (large)        XX min
             subtitle
    """

    def __init__(
        self,
        row_number: int,
        background_color: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._bg_color = background_color
        self._trains: list[TrainDisplayData] = []
        self._current_index = 0

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(90)

        self._content = QWidget(self)
        self._content.setStyleSheet("background: transparent;")

        row_layout = QHBoxLayout(self._content)
        row_layout.setContentsMargins(16, 8, 24, 8)
        row_layout.setSpacing(16)

        self._row_number_label = QLabel(str(row_number))
        self._row_number_label.setFont(
            QFont(FONT_FAMILY, FONT_METADATA_SIZE + 2, QFont.Weight.Bold)
        )
        self._row_number_label.setStyleSheet(
            f"color: rgba(255,255,255,0.6); {_LABEL_TRANSPARENT}"
        )
        self._row_number_label.setFixedWidth(24)
        self._row_number_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        row_layout.addWidget(self._row_number_label)

        text_column = QVBoxLayout()
        text_column.setSpacing(0)
        text_column.setContentsMargins(0, 0, 0, 0)

        self._line_label = QLabel()
        self._line_label.setFont(QFont(FONT_FAMILY, FONT_METADATA_SIZE))
        self._line_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")

        self._destination_label = QLabel()
        self._destination_label.setFont(
            QFont(FONT_FAMILY, FONT_DESTINATION_SIZE, QFont.Weight.Bold)
        )
        self._destination_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")

        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)
        sub_row.setContentsMargins(0, 0, 0, 0)

        self._subtitle_label = QLabel()
        self._subtitle_label.setFont(QFont(FONT_FAMILY, FONT_METADATA_SIZE - 1))
        self._subtitle_label.setStyleSheet(
            f"color: rgba(255,255,255,0.7); {_LABEL_TRANSPARENT}"
        )

        self._delayed_label = QLabel("Delayed")
        self._delayed_label.setFont(
            QFont(FONT_FAMILY, FONT_METADATA_SIZE - 1, QFont.Weight.Bold)
        )
        self._delayed_label.setStyleSheet(
            f"color: {WHITE}; background-color: {AMBER_COLOR}; "
            f"padding: 1px 6px; border-radius: 3px;"
        )
        self._delayed_label.hide()

        sub_row.addWidget(self._subtitle_label)
        sub_row.addWidget(self._delayed_label)
        sub_row.addStretch()

        text_column.addWidget(self._line_label)
        text_column.addWidget(self._destination_label)
        text_column.addLayout(sub_row)

        row_layout.addLayout(text_column, 1)

        self._minutes_label = QLabel()
        self._minutes_label.setFont(
            QFont(FONT_FAMILY, FONT_MINUTES_SIZE, QFont.Weight.Bold)
        )
        self._minutes_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")
        self._minutes_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_layout.addWidget(self._minutes_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._content)

        self._opacity_effect = QGraphicsOpacityEffect(self._content)
        self._opacity_effect.setOpacity(1.0)
        self._content.setGraphicsEffect(self._opacity_effect)

        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out_anim.setDuration(FADE_DURATION_MS // 2)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.finished.connect(self._on_fade_out_done)

        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in_anim.setDuration(FADE_DURATION_MS // 2)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)

        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(ROTATION_INTERVAL_SEC * 1000)
        self._rotation_timer.timeout.connect(self._start_rotation)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(800)
        self._pulse_visible = True
        self._pulse_timer.timeout.connect(self._toggle_pulse)

        self._apply_background()
        self._show_empty()

    def _apply_background(self) -> None:
        self.setObjectName("trainRow")
        self.setStyleSheet(
            f"QFrame#trainRow {{ background-color: {self._bg_color};"
            f" border: none; border-bottom: 2px solid #000000; }}"
        )

    def set_trains(self, trains: list[TrainDisplayData]) -> None:
        self._trains = trains[:2]
        self._current_index = 0
        self._rotation_timer.stop()
        self._pulse_timer.stop()

        if not self._trains:
            self._show_empty()
            return

        self._render_train(self._trains[0])

        if len(self._trains) == 2:
            self._rotation_timer.start()

    def _show_empty(self) -> None:
        self._line_label.setText("")
        self._destination_label.setText("No upcoming service")
        self._destination_label.setStyleSheet(f"color: {DIMMED_TEXT}; {_LABEL_TRANSPARENT}")
        self._minutes_label.setText("")
        self._subtitle_label.setText("")
        self._delayed_label.hide()

    def _render_train(self, train: TrainDisplayData) -> None:
        self._line_label.setText(train.line_label)
        self._destination_label.setText(train.destination)
        self._destination_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")

        if train.is_due:
            self._minutes_label.setText("Due")
            self._minutes_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")
            self._pulse_timer.start()
            self._pulse_visible = True
        else:
            mins = int(train.leave_home_min)
            self._minutes_label.setText(f"{mins} min")
            self._minutes_label.setStyleSheet(f"color: {WHITE}; {_LABEL_TRANSPARENT}")
            self._pulse_timer.stop()
            self._minutes_label.setVisible(True)

        sched_tag = " (sched)" if train.is_scheduled else ""
        self._subtitle_label.setText((train.subtitle or "") + sched_tag)

        if train.is_delayed:
            self._delayed_label.show()
        else:
            self._delayed_label.hide()

    def _toggle_pulse(self) -> None:
        self._pulse_visible = not self._pulse_visible
        self._minutes_label.setVisible(self._pulse_visible)

    def _start_rotation(self) -> None:
        if len(self._trains) < 2:
            return
        self._fade_out_anim.start()

    def _on_fade_out_done(self) -> None:
        self._current_index = (self._current_index + 1) % len(self._trains)
        self._render_train(self._trains[self._current_index])
        self._fade_in_anim.start()

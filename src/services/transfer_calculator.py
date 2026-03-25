from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.config import SHERIDAN_TO_WILSON_MIN, WALK_TO_SHERIDAN_MIN
from src.services.cta_api import TrainETA


@dataclass
class LindenConnection:
    leave_home_in: float
    red_run: str
    purple_run: str
    wait_at_wilson_min: float
    is_delayed: bool


class TransferCalculator:
    """Matches Red Line Howard-bound trains at Sheridan to Purple Line
    Linden-bound trains at Wilson to find viable Sheridan-to-Linden
    transfer connections."""

    def compute_connections(
        self,
        red_howard_trains: list[TrainETA],
        purple_linden_trains: list[TrainETA],
        now: datetime | None = None,
    ) -> list[LindenConnection]:
        if not red_howard_trains or not purple_linden_trains:
            return []

        if now is None:
            now = datetime.now()

        travel_delta = timedelta(minutes=SHERIDAN_TO_WILSON_MIN)
        sorted_reds = sorted(red_howard_trains, key=lambda t: t.arrival_time)

        connections: list[LindenConnection] = []

        for purple in purple_linden_trains:
            best_red: TrainETA | None = None

            for red in sorted_reds:
                red_arrives_wilson = red.arrival_time + travel_delta
                if red_arrives_wilson <= purple.arrival_time:
                    leave_home = (red.arrival_time - now).total_seconds() / 60.0 - WALK_TO_SHERIDAN_MIN
                    if leave_home >= -1:
                        best_red = red

            if best_red is None:
                continue

            red_arrives_wilson = best_red.arrival_time + travel_delta
            leave_home = (best_red.arrival_time - now).total_seconds() / 60.0 - WALK_TO_SHERIDAN_MIN
            wait = (purple.arrival_time - red_arrives_wilson).total_seconds() / 60.0

            connections.append(
                LindenConnection(
                    leave_home_in=round(leave_home, 1),
                    red_run=best_red.run_number,
                    purple_run=purple.run_number,
                    wait_at_wilson_min=round(wait, 1),
                    is_delayed=best_red.is_delayed or purple.is_delayed,
                )
            )

        connections.sort(key=lambda c: c.leave_home_in)
        return connections

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from src.config import ML_FEATURE_DIM, ML_MAX_BUFFER_RUNS, ML_MIN_COMPLETED_RUNS, ML_SEQUENCE_LENGTH


@dataclass
class RunObservation:
    timestamp: float
    station_minutes: float
    is_delayed: bool
    is_scheduled: bool
    is_approaching: bool
    route: str
    destination: str
    hour: int
    minute: int
    day_of_week: int
    temperature_c: float
    precipitation_mm: float
    weather_code: int


@dataclass
class CompletedRun:
    observations: list[RunObservation]
    arrived_at: float


def encode_observation(
    obs: RunObservation,
    prev_station_min: float | None = None,
) -> np.ndarray:
    h = 2 * math.pi * obs.hour / 24
    d = 2 * math.pi * obs.day_of_week / 7
    delta = 0.0
    if prev_station_min is not None:
        delta = (obs.station_minutes - prev_station_min) / 10.0

    return np.array(
        [
            math.sin(h),
            math.cos(h),
            math.sin(d),
            math.cos(d),
            obs.station_minutes / 30.0,
            float(obs.is_delayed),
            float(obs.is_scheduled),
            float(obs.is_approaching),
            0.0 if obs.route == "Red" else 1.0,
            obs.temperature_c / 40.0,
            obs.precipitation_mm / 10.0,
            obs.weather_code / 100.0,
            delta,
        ],
        dtype=np.float32,
    )


class ObservationBuffer:
    """In-memory rolling buffer that tracks active and completed train runs.

    Each CTA poll feeds new observations into `record()`. When a run_number
    vanishes between consecutive polls the run is considered *arrived* and
    moved to the completed ring-buffer, providing ground-truth labels for
    supervised training without ever writing to disk.
    """

    def __init__(self) -> None:
        self._active: dict[str, list[RunObservation]] = {}
        self._completed: deque[CompletedRun] = deque(maxlen=ML_MAX_BUFFER_RUNS)
        self._prev_ids: set[str] = set()
        self._new_completions = 0

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def new_completions(self) -> int:
        return self._new_completions

    def reset_completion_counter(self) -> None:
        self._new_completions = 0

    def is_ready(self) -> bool:
        return len(self._completed) >= ML_MIN_COMPLETED_RUNS

    def record(
        self,
        trains: list,
        weather_temp: float = 20.0,
        weather_precip: float = 0.0,
        weather_code: int = 0,
    ) -> None:
        now = time.time()
        lt = time.localtime(now)
        current_ids: set[str] = set()

        for t in trains:
            rid = f"{t.route}_{t.run_number}"
            current_ids.add(rid)

            obs = RunObservation(
                timestamp=now,
                station_minutes=t.station_minutes,
                is_delayed=t.is_delayed,
                is_scheduled=t.is_scheduled,
                is_approaching=t.is_approaching,
                route=t.route,
                destination=t.destination,
                hour=lt.tm_hour,
                minute=lt.tm_min,
                day_of_week=lt.tm_wday,
                temperature_c=weather_temp,
                precipitation_mm=weather_precip,
                weather_code=weather_code,
            )

            if rid not in self._active:
                self._active[rid] = []
            self._active[rid].append(obs)

        departed = self._prev_ids - current_ids
        for rid in departed:
            obs_list = self._active.pop(rid, None)
            if obs_list and len(obs_list) >= 2:
                self._completed.append(CompletedRun(obs_list, now))
                self._new_completions += 1

        self._prev_ids = current_ids

    def build_training_data(self) -> tuple[np.ndarray, np.ndarray] | None:
        if not self.is_ready():
            return None

        xs: list[np.ndarray] = []
        ys: list[float] = []

        for run in self._completed:
            obs_list = run.observations
            arrival_t = run.arrived_at

            for start in range(len(obs_list) - ML_SEQUENCE_LENGTH + 1):
                window = obs_list[start : start + ML_SEQUENCE_LENGTH]
                feats = []
                for i, obs in enumerate(window):
                    prev = window[i - 1].station_minutes if i > 0 else None
                    feats.append(encode_observation(obs, prev))

                xs.append(np.stack(feats))

                actual_remaining = max((arrival_t - window[-1].timestamp) / 60.0, 0.0)
                ys.append(actual_remaining)

        if not xs:
            return None

        return np.stack(xs), np.array(ys, dtype=np.float32)

    def get_active_sequences(self) -> dict[str, np.ndarray]:
        result: dict[str, np.ndarray] = {}

        for rid, obs_list in self._active.items():
            if len(obs_list) < 2:
                continue

            recent = obs_list[-ML_SEQUENCE_LENGTH:]
            feats = []
            for i, obs in enumerate(recent):
                prev = recent[i - 1].station_minutes if i > 0 else None
                feats.append(encode_observation(obs, prev))

            seq = np.stack(feats)

            if seq.shape[0] < ML_SEQUENCE_LENGTH:
                pad = np.zeros(
                    (ML_SEQUENCE_LENGTH - seq.shape[0], ML_FEATURE_DIM),
                    dtype=np.float32,
                )
                seq = np.concatenate([pad, seq], axis=0)

            result[rid] = seq

        return result

    @property
    def active_runs(self) -> dict[str, list[RunObservation]]:
        return self._active

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from src.config import CHICAGO_LAT, CHICAGO_LON

logger = logging.getLogger(__name__)

_CACHE_HOURS = 6


@dataclass
class WeatherStep:
    valid_time: datetime
    temperature_k: float
    wind_u_ms: float
    wind_v_ms: float

    @property
    def temperature_f(self) -> float:
        return (self.temperature_k - 273.15) * 9.0 / 5.0 + 32.0

    @property
    def wind_speed_mph(self) -> float:
        return math.sqrt(self.wind_u_ms**2 + self.wind_v_ms**2) * 2.237

    @property
    def wind_direction(self) -> str:
        angle = (math.degrees(math.atan2(-self.wind_u_ms, -self.wind_v_ms)) + 360) % 360
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = int((angle + 22.5) / 45.0) % 8
        return dirs[idx]


@dataclass
class WeatherForecast:
    generated_at: datetime
    steps: list[WeatherStep] = field(default_factory=list)


class WeatherService:
    """Runs NVIDIA Earth2Studio FCN3 to produce a Chicago weather forecast.
    Results are cached for 6 hours to avoid expensive repeated inference."""

    def __init__(self) -> None:
        self._cache: WeatherForecast | None = None
        self._last_run: datetime | None = None

    def get_forecast(self, force_refresh: bool = False) -> WeatherForecast | None:
        if not force_refresh and self._cache is not None and self._last_run is not None:
            age_hours = (datetime.now() - self._last_run).total_seconds() / 3600.0
            if age_hours < _CACHE_HOURS:
                return self._cache

        try:
            forecast = self._run_model()
            self._cache = forecast
            self._last_run = datetime.now()
            return forecast
        except Exception:
            logger.exception("Earth2Studio forecast failed")
            return self._cache

    def _run_model(self) -> WeatherForecast:
        from earth2studio.data import GFS
        from earth2studio.io import ZarrBackend
        from earth2studio.models.px import FCN3
        from earth2studio.run import deterministic as run

        model = FCN3.load_model(FCN3.load_default_package())
        data = GFS()
        io = ZarrBackend("outputs/chicago_forecast.zarr")

        now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        init_hour = (now_utc.hour // 6) * 6
        init_time = now_utc.replace(hour=init_hour)
        init_str = init_time.strftime("%Y-%m-%dT%H:%M:%S")

        nsteps = 10
        run([init_str], nsteps, model, data, io)

        ds = io.root
        lats = np.array(ds["lat"])
        lons = np.array(ds["lon"])

        lat_idx = int(np.argmin(np.abs(lats - CHICAGO_LAT)))
        lon_target = CHICAGO_LON % 360 if np.all(lons >= 0) else CHICAGO_LON
        lon_idx = int(np.argmin(np.abs(lons - lon_target)))

        steps: list[WeatherStep] = []
        lead_times = ds["lead_time"]

        for i in range(len(lead_times)):
            valid_time = init_time + timedelta(hours=float(lead_times[i]))

            t2m = float(ds["t2m"][0, i, lat_idx, lon_idx])
            u10 = float(ds["u10m"][0, i, lat_idx, lon_idx])
            v10 = float(ds["v10m"][0, i, lat_idx, lon_idx])

            steps.append(
                WeatherStep(
                    valid_time=valid_time,
                    temperature_k=t2m,
                    wind_u_ms=u10,
                    wind_v_ms=v10,
                )
            )

        return WeatherForecast(generated_at=datetime.now(), steps=steps)

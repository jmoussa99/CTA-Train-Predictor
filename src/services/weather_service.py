from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from src.config import CHICAGO_LAT, CHICAGO_LON

logger = logging.getLogger(__name__)

_CACHE_HOURS = 1
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


_WMO_EMOJI: dict[int, str] = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️",
    56: "🌧️", 57: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "🌧️",
    66: "🌧️", 67: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "🌨️", 77: "🌨️",
    80: "🌦️", 81: "🌧️", 82: "🌧️",
    85: "🌨️", 86: "🌨️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}

_WMO_NIGHT: dict[int, str] = {
    0: "🌙", 1: "🌙", 2: "⛅", 3: "☁️",
}


@dataclass
class WeatherStep:
    valid_time: datetime
    temperature_c: float
    precipitation_mm: float
    precipitation_probability: int
    weather_code: int

    @property
    def emoji(self) -> str:
        hour = self.valid_time.hour
        is_night = hour < 6 or hour >= 20
        if is_night and self.weather_code in _WMO_NIGHT:
            return _WMO_NIGHT[self.weather_code]
        return _WMO_EMOJI.get(self.weather_code, "🌡️")


@dataclass
class CurrentWeather:
    temperature_c: float
    precipitation_mm: float
    weather_code: int
    time: datetime

    @property
    def emoji(self) -> str:
        is_night = self.time.hour < 6 or self.time.hour >= 20
        if is_night and self.weather_code in _WMO_NIGHT:
            return _WMO_NIGHT[self.weather_code]
        return _WMO_EMOJI.get(self.weather_code, "🌡️")


@dataclass
class WeatherForecast:
    generated_at: datetime
    current: CurrentWeather | None = None
    steps: list[WeatherStep] = field(default_factory=list)


class WeatherService:
    """Fetches hourly Chicago weather from the Open-Meteo API.
    Results are cached for 1 hour."""

    def __init__(self) -> None:
        self._cache: WeatherForecast | None = None
        self._last_run: datetime | None = None

    def get_forecast(self, force_refresh: bool = False) -> WeatherForecast | None:
        if not force_refresh and self._cache is not None and self._last_run is not None:
            age_hours = (datetime.now() - self._last_run).total_seconds() / 3600.0
            if age_hours < _CACHE_HOURS:
                return self._cache

        try:
            forecast = self._fetch_forecast()
            self._cache = forecast
            self._last_run = datetime.now()
            return forecast
        except Exception:
            logger.exception("Open-Meteo forecast fetch failed")
            return self._cache

    def _fetch_forecast(self) -> WeatherForecast:
        params = {
            "latitude": CHICAGO_LAT,
            "longitude": CHICAGO_LON,
            "current": "temperature_2m,precipitation,weather_code",
            "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "timezone": "America/Chicago",
            "forecast_days": 1,
        }

        resp = httpx.get(_OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        cur = data["current"]
        current = CurrentWeather(
            temperature_c=cur["temperature_2m"],
            precipitation_mm=cur["precipitation"],
            weather_code=cur["weather_code"],
            time=datetime.fromisoformat(cur["time"]),
        )

        hourly = data["hourly"]
        times = hourly["time"]
        temps = hourly["temperature_2m"]
        precip_probs = hourly["precipitation_probability"]
        precip_amounts = hourly["precipitation"]
        weather_codes = hourly["weather_code"]

        now = datetime.now()

        steps: list[WeatherStep] = []
        for i, iso_time in enumerate(times):
            valid_time = datetime.fromisoformat(iso_time)
            if valid_time < now.replace(minute=0, second=0, microsecond=0):
                continue
            steps.append(
                WeatherStep(
                    valid_time=valid_time,
                    temperature_c=temps[i],
                    precipitation_mm=precip_amounts[i],
                    precipitation_probability=precip_probs[i],
                    weather_code=weather_codes[i],
                )
            )

        return WeatherForecast(generated_at=now, current=current, steps=steps)

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests

from src.config import (
    CTA_API_BASE,
    CTA_API_KEY,
    SHERIDAN_MAP_ID,
    WALK_TO_SHERIDAN_MIN,
    WILSON_LINDEN_STOP_ID,
)

logger = logging.getLogger(__name__)

_CTA_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"


@dataclass
class TrainETA:
    run_number: str
    route: str
    destination: str
    prediction_time: datetime
    arrival_time: datetime
    is_approaching: bool
    is_delayed: bool
    is_scheduled: bool
    station_minutes: float

    @property
    def leave_home_in(self) -> float:
        return self.station_minutes - WALK_TO_SHERIDAN_MIN


def _parse_eta(eta: dict, now: datetime) -> TrainETA:
    prediction_time = datetime.strptime(eta["prdt"], _CTA_DATETIME_FMT)
    arrival_time = datetime.strptime(eta["arrT"], _CTA_DATETIME_FMT)
    station_minutes = (arrival_time - now).total_seconds() / 60.0

    return TrainETA(
        run_number=eta["rn"],
        route=eta["rt"],
        destination=eta["destNm"],
        prediction_time=prediction_time,
        arrival_time=arrival_time,
        is_approaching=eta.get("isApp", "0") == "1",
        is_delayed=eta.get("isDly", "0") == "1",
        is_scheduled=eta.get("isSch", "0") == "1",
        station_minutes=station_minutes,
    )


class CTAClient:
    def __init__(self, api_key: str = CTA_API_KEY, timeout: int = 5):
        self._api_key = api_key
        self._timeout = timeout
        if not (self._api_key or "").strip():
            logger.warning(
                "CTA_API_KEY is not set. Use env CTA_API_KEY or copy "
                "src/config_secrets.example.py to src/config_secrets.py."
            )

    def _fetch(self, params: dict) -> list[TrainETA]:
        params = {**params, "key": self._api_key, "outputType": "JSON"}
        now = datetime.now()
        try:
            resp = requests.get(CTA_API_BASE, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("CTA API request failed: %s", exc)
            return []

        ctatt = data.get("ctatt", {})
        err_cd = ctatt.get("errCd", "0")
        if err_cd != "0":
            logger.warning(
                "CTA API error %s: %s", err_cd, ctatt.get("errNm", "unknown")
            )
            return []

        raw_etas = ctatt.get("eta", [])
        if isinstance(raw_etas, dict):
            raw_etas = [raw_etas]

        results: list[TrainETA] = []
        for eta in raw_etas:
            try:
                results.append(_parse_eta(eta, now))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed ETA: %s", exc)
        return results

    def fetch_sheridan_red(self) -> list[TrainETA]:
        return self._fetch({"mapid": SHERIDAN_MAP_ID, "rt": "Red"})

    def fetch_wilson_purple_linden(self) -> list[TrainETA]:
        etas = self._fetch({"stpid": WILSON_LINDEN_STOP_ID, "rt": "P"})
        return [e for e in etas if e.destination == "Linden"]

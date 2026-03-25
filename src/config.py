import os


def _resolve_cta_api_key() -> str:
    env = os.environ.get("CTA_API_KEY", "").strip()
    if env:
        return env
    try:
        from src import config_secrets

        local = getattr(config_secrets, "CTA_API_KEY", "").strip()
        if local:
            return local
    except ImportError:
        pass
    return ""


CTA_API_KEY = _resolve_cta_api_key()
CTA_API_BASE = "http://lapi.transitchicago.com/api/1.0/ttarrivals.aspx"

SHERIDAN_MAP_ID = 40080
WILSON_LINDEN_STOP_ID = 30386

WALK_TO_SHERIDAN_MIN = 9
SHERIDAN_TO_WILSON_MIN = 4

POLL_INTERVAL_SEC = 10
ROTATION_INTERVAL_SEC = 15
FADE_DURATION_MS = 500

RED_COLOR = "#c60c30"
PURPLE_COLOR = "#522398"
BG_COLOR = "#1a1a1a"
HEADER_BG = "#333333"

CHICAGO_LAT = 41.88
CHICAGO_LON = -87.63

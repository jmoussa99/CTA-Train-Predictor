# Engineering Tickets -- CTA Sheridan Train Tracker

All tickets reference the [spec](/.cursor/plans/cta_train_tracker_spec_d8e756a4.plan.md). Each is independently mergeable against `main` (except where a dependency is noted).

---

## Ticket 1: Project Scaffold and Configuration

**Branch:** `scaffold`
**Depends on:** nothing
**Files:**

- `requirements.txt`
- `.gitignore`
- `src/__init__.py`
- `src/config.py`
- `src/main.py` (minimal entry point that prints "CTA Train Tracker starting...")
- `src/services/__init__.py`
- `src/ui/__init__.py`
- `src/models/__init__.py`
- move existing CSV into `data/`

**What to build:**

`config.py` must define all constants from the spec:

```python
CTA_API_KEY = "45eba1098fbd48ec925d80888223b776"
CTA_API_BASE = "http://lapi.transitchicago.com/api/1.0/ttarrivals.aspx"

SHERIDAN_MAP_ID = 40080        # Red Line
WILSON_LINDEN_STOP_ID = 30386  # Purple Line Linden-bound at Wilson

WALK_TO_SHERIDAN_MIN = 9
SHERIDAN_TO_WILSON_MIN = 4

POLL_INTERVAL_SEC = 30
ROTATION_INTERVAL_SEC = 15
FADE_DURATION_MS = 500

RED_COLOR = "#c60c30"
PURPLE_COLOR = "#522398"
BG_COLOR = "#1a1a1a"
HEADER_BG = "#333333"

CHICAGO_LAT = 41.88
CHICAGO_LON = -87.63
```

`requirements.txt`:

```
PyQt6
requests
earth2studio
torch
zarr
xarray
numpy
scikit-learn
```

`.gitignore` must ignore `__pycache__/`, `*.pyc`, `.env`, `outputs/`, `*.zarr`, `.venv/`.

**Acceptance checks:**

```bash
# 1. Create venv and install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Config imports cleanly
python -c "from src.config import CTA_API_KEY, WALK_TO_SHERIDAN_MIN, SHERIDAN_TO_WILSON_MIN; print('OK')"
# expect: OK

# 3. Entry point runs
python -m src.main
# expect: prints "CTA Train Tracker starting..."

# 4. Directory structure exists
ls src/services/__init__.py src/ui/__init__.py src/models/__init__.py
# expect: all three listed with no errors
```

---

## Ticket 2: CTA API Client

**Branch:** `cta-api-client`
**Depends on:** Ticket 1 (config.py)
**Files:**

- `src/services/cta_api.py`

**What to build:**

A `CTAClient` class with two public methods:

```python
class CTAClient:
    def fetch_sheridan_red(self) -> list[TrainETA]:
        """GET mapid=40080&rt=Red&outputType=JSON. Returns parsed list."""

    def fetch_wilson_purple_linden(self) -> list[TrainETA]:
        """GET stpid=30386&rt=P&outputType=JSON. Returns parsed list."""
```

`TrainETA` dataclass:

```python
@dataclass
class TrainETA:
    run_number: str       # rn
    route: str            # rt ("Red" or "P")
    destination: str      # destNm ("Howard", "95th/Dan Ryan", "Linden")
    prediction_time: datetime  # prdt
    arrival_time: datetime     # arrT
    is_approaching: bool  # isApp == "1"
    is_delayed: bool      # isDly == "1"
    is_scheduled: bool    # isSch == "1"
    station_minutes: float  # (arrT - now) in minutes

    @property
    def leave_home_in(self) -> float:
        """station_minutes - WALK_TO_SHERIDAN_MIN"""
```

Handle: HTTP errors (timeout=5s, retry once), JSON parse errors, empty eta lists, CTA error codes (errCd != "0"). On failure return empty list and log warning.

Parse datetime strings in format `"2015-04-30T20:23:32"`.

**Acceptance checks:**

```bash
# 1. Smoke test against live API
python -c "
from src.services.cta_api import CTAClient
c = CTAClient()
reds = c.fetch_sheridan_red()
print(f'Red Line trains: {len(reds)}')
for t in reds[:2]:
    print(f'  #{t.run_number} -> {t.destination} in {t.station_minutes:.0f} min (leave home: {t.leave_home_in:.0f} min)')
"
# expect: at least 1 train printed (during service hours), no exceptions

# 2. Purple Line fetch
python -c "
from src.services.cta_api import CTAClient
c = CTAClient()
purps = c.fetch_wilson_purple_linden()
print(f'Purple Linden trains at Wilson: {len(purps)}')
for t in purps[:2]:
    print(f'  #{t.run_number} -> {t.destination} in {t.station_minutes:.0f} min')
"
# expect: 0+ trains (Purple runs limited hours), no exceptions

# 3. Error handling -- bad API key
python -c "
from src.services.cta_api import CTAClient
c = CTAClient(api_key='invalid')
result = c.fetch_sheridan_red()
print(f'Returned {len(result)} trains (expected 0)')
"
# expect: prints "Returned 0 trains (expected 0)", no unhandled exception
```

---

## Ticket 3: Transfer Calculator

**Branch:** `transfer-calculator`
**Depends on:** Ticket 2 (TrainETA dataclass)
**Files:**

- `src/services/transfer_calculator.py`

**What to build:**

```python
@dataclass
class LindenConnection:
    leave_home_in: float        # minutes until user leaves home
    red_run: str                # Red Line run number (Sheridan -> Wilson)
    purple_run: str             # Purple Line run number (Wilson -> Linden)
    wait_at_wilson_min: float   # idle minutes at Wilson platform
    is_delayed: bool            # True if either leg is delayed

class TransferCalculator:
    def compute_connections(
        self,
        red_howard_trains: list[TrainETA],
        purple_linden_trains: list[TrainETA],
        now: datetime | None = None
    ) -> list[LindenConnection]:
        """
        For each Purple Line train at Wilson, find the LATEST Red Line
        Howard-bound train at Sheridan that still gets to Wilson in time.
        
        Connection valid when:
          red_train.arrival_time + SHERIDAN_TO_WILSON_MIN <= purple_train.arrival_time
        
        Filter out connections where leave_home_in < -1 (missed).
        Return sorted by leave_home_in ascending.
        """
```

Algorithm from spec section 5. The `now` parameter enables deterministic testing.

**Acceptance checks:**

```bash
# 1. Unit test with fixed data
python -c "
from datetime import datetime, timedelta
from src.services.cta_api import TrainETA
from src.services.transfer_calculator import TransferCalculator

now = datetime(2026, 3, 24, 14, 0, 0)

red_trains = [
    TrainETA('914', 'Red', 'Howard', now, now + timedelta(minutes=11),
             False, False, False, 11),
    TrainETA('920', 'Red', 'Howard', now, now + timedelta(minutes=20),
             False, False, False, 20),
]
purple_trains = [
    TrainETA('601', 'P', 'Linden', now, now + timedelta(minutes=16),
             False, False, False, 16),
    TrainETA('605', 'P', 'Linden', now, now + timedelta(minutes=26),
             False, False, False, 26),
]

calc = TransferCalculator()
conns = calc.compute_connections(red_trains, purple_trains, now=now)

assert len(conns) == 2, f'Expected 2 connections, got {len(conns)}'

# Connection 1: Red 914 (11 min) -> arrives Wilson 15 min -> Purple 601 (16 min)
# leave_home = 11 - 9 = 2, wait = 16 - 15 = 1
assert conns[0].red_run == '914'
assert conns[0].purple_run == '601'
assert abs(conns[0].leave_home_in - 2.0) < 0.1
assert abs(conns[0].wait_at_wilson_min - 1.0) < 0.1

# Connection 2: Red 920 (20 min) -> arrives Wilson 24 min -> Purple 605 (26 min)
# leave_home = 20 - 9 = 11, wait = 26 - 24 = 2
assert conns[1].red_run == '920'
assert conns[1].purple_run == '605'
assert abs(conns[1].leave_home_in - 11.0) < 0.1
assert abs(conns[1].wait_at_wilson_min - 2.0) < 0.1

print('All assertions passed')
"
# expect: "All assertions passed"

# 2. Missed-train filtering
python -c "
from datetime import datetime, timedelta
from src.services.cta_api import TrainETA
from src.services.transfer_calculator import TransferCalculator

now = datetime(2026, 3, 24, 14, 0, 0)

red_trains = [
    TrainETA('900', 'Red', 'Howard', now, now + timedelta(minutes=3),
             True, False, False, 3),  # arrives in 3 min, leave_home = -6 -> missed
]
purple_trains = [
    TrainETA('601', 'P', 'Linden', now, now + timedelta(minutes=8),
             False, False, False, 8),
]

calc = TransferCalculator()
conns = calc.compute_connections(red_trains, purple_trains, now=now)
assert len(conns) == 0, f'Expected 0 (missed), got {len(conns)}'
print('Missed-train filtering passed')
"
# expect: "Missed-train filtering passed"

# 3. Empty input handling
python -c "
from src.services.transfer_calculator import TransferCalculator
calc = TransferCalculator()
assert calc.compute_connections([], []) == []
print('Empty input OK')
"
# expect: "Empty input OK"
```

---

## Ticket 4: UI Styles and Train Box Widget

**Branch:** `train-box-widget`
**Depends on:** Ticket 1 (config.py, PyQt6 in requirements)
**Files:**

- `src/ui/styles.py`
- `src/ui/train_box.py`

**What to build:**

`styles.py` -- shared theme constants:

```python
from src.config import RED_COLOR, PURPLE_COLOR, BG_COLOR, HEADER_BG, FADE_DURATION_MS

FONT_DESTINATION = ("Helvetica Neue", 28)
FONT_METADATA = ("Helvetica Neue", 14)
FONT_MINUTES = ("Helvetica Neue", 32)
AMBER_COLOR = "#ff9500"
DIMMED_TEXT = "#666666"
```

`train_box.py` -- a single destination box:

```python
class TrainBox(QWidget):
    """
    A single color-coded box displaying one train at a time.
    Holds up to 2 TrainDisplayData items and fades between them
    every ROTATION_INTERVAL_SEC (15s) with FADE_DURATION_MS (500ms).
    """

    def set_trains(self, trains: list[TrainDisplayData]) -> None:
        """Update the box with 0, 1, or 2 trains. Resets rotation."""

    def _fade_to_next(self) -> None:
        """QPropertyAnimation on opacity: 1.0 -> 0.0 -> swap content -> 0.0 -> 1.0"""
```

`TrainDisplayData`:

```python
@dataclass
class TrainDisplayData:
    line_label: str          # "Red Line #914 to" or "Purple Line to"
    destination: str         # "Howard", "95th/Dan Ryan", "Linden"
    leave_home_min: float    # countdown to display
    is_due: bool             # leave_home_min <= 1
    is_delayed: bool
    is_scheduled: bool
    subtitle: str | None     # e.g. "2 min wait at Wilson" (Linden only)
```

Display states:
- `is_due` -> show "Due" in large text, pulsing
- `is_delayed` -> amber "Delayed" badge
- `leave_home_min > 1` -> show "{N} min"
- 0 trains -> "No upcoming service" dimmed
- 1 train -> static, no rotation timer

**Acceptance checks:**

```bash
# 1. Widget renders with mock data (visual check)
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.train_box import TrainBox, TrainDisplayData

app = QApplication(sys.argv)
box = TrainBox(background_color='#c60c30')
box.set_trains([
    TrainDisplayData('Red Line #914 to', 'Howard', 2.0, False, False, False, None),
    TrainDisplayData('Red Line #920 to', 'Howard', 11.0, False, False, False, None),
])
box.setFixedSize(280, 180)
box.show()
app.exec()
"
# expect: red box appears with "Howard" and "2 min". After 15s, fades to "Howard" "11 min".

# 2. Due state renders
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.train_box import TrainBox, TrainDisplayData

app = QApplication(sys.argv)
box = TrainBox(background_color='#c60c30')
box.set_trains([
    TrainDisplayData('Red Line #914 to', 'Howard', 0.5, True, False, False, None),
])
box.setFixedSize(280, 180)
box.show()
app.exec()
"
# expect: red box appears with "Howard" and "Due" (pulsing). No rotation (only 1 train).

# 3. Empty state renders
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.train_box import TrainBox, TrainDisplayData

app = QApplication(sys.argv)
box = TrainBox(background_color='#522398')
box.set_trains([])
box.setFixedSize(280, 180)
box.show()
app.exec()
"
# expect: purple box appears with "No upcoming service" in dimmed text.
```

---

## Ticket 5: Train Panel (3-Box Layout)

**Branch:** `train-panel`
**Depends on:** Tickets 2, 3, 4 (CTAClient, TransferCalculator, TrainBox)
**Files:**

- `src/ui/train_panel.py`

**What to build:**

```python
class TrainPanel(QWidget):
    """
    Contains 3 TrainBox widgets laid out horizontally:
      [Howard box]  [95th box]  [Linden box]
    
    Plus a header bar: "Next 'L' services from Sheridan  |  9 min walk"
    """

    def __init__(self):
        # Create 3 TrainBox instances:
        #   howard_box  (RED_COLOR)
        #   ninetyFifth_box (RED_COLOR)
        #   linden_box (PURPLE_COLOR)

    def update_data(
        self,
        red_trains: list[TrainETA],
        linden_connections: list[LindenConnection]
    ) -> None:
        """
        1. Split red_trains by destination ("Howard" vs "95th/Dan Ryan").
        2. Filter to catchable only (leave_home_in > -1).
        3. Take first 2 of each, convert to TrainDisplayData.
        4. Convert first 2 LindenConnection to TrainDisplayData.
        5. Call set_trains() on each box.
        """
```

**Acceptance checks:**

```bash
# 1. Panel renders with mock data (visual check)
python -c "
import sys
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QApplication
from src.services.cta_api import TrainETA
from src.services.transfer_calculator import LindenConnection
from src.ui.train_panel import TrainPanel

app = QApplication(sys.argv)
panel = TrainPanel()

now = datetime.now()
reds = [
    TrainETA('914', 'Red', 'Howard', now, now + timedelta(minutes=11), False, False, False, 11),
    TrainETA('918', 'Red', 'Howard', now, now + timedelta(minutes=22), False, False, False, 22),
    TrainETA('920', 'Red', '95th/Dan Ryan', now, now + timedelta(minutes=14), False, False, False, 14),
    TrainETA('924', 'Red', '95th/Dan Ryan', now, now + timedelta(minutes=25), False, False, False, 25),
]
lindens = [
    LindenConnection(leave_home_in=2.0, red_run='914', purple_run='601', wait_at_wilson_min=1.0, is_delayed=False),
    LindenConnection(leave_home_in=13.0, red_run='918', purple_run='605', wait_at_wilson_min=2.0, is_delayed=False),
]

panel.update_data(reds, lindens)
panel.show()
app.exec()
"
# expect: 3 boxes shown side by side -- 2 red (Howard, 95th), 1 purple (Linden). Each rotates every 15s.

# 2. Header text visible
# expect: top bar reads "Next 'L' services from Sheridan" with "9 min walk" right-aligned
```

---

## Ticket 6: Earth2Studio Weather Service

**Branch:** `weather-service`
**Depends on:** Ticket 1 (config.py)
**Files:**

- `src/services/weather_service.py`

**What to build:**

```python
class WeatherService:
    """Runs NVIDIA Earth2Studio FCN3 model to produce a Chicago weather forecast."""

    def __init__(self):
        self._cache: WeatherForecast | None = None
        self._last_run: datetime | None = None

    def get_forecast(self, force_refresh: bool = False) -> WeatherForecast:
        """
        Returns cached forecast if < 6 hours old, otherwise runs model.
        Uses earth2studio.run.deterministic with FCN3 + GFS data source.
        Extracts Chicago grid point (~41.88, -87.63) from Zarr output.
        """

    def _run_model(self) -> WeatherForecast:
        """
        1. Load FCN3 model + GFS data source
        2. Run deterministic forecast (10 steps = 60h at 6h/step)
        3. Open output Zarr, find nearest lat/lon to Chicago
        4. Extract t2m, u10m, v10m for each time step
        5. Return WeatherForecast dataclass
        """

@dataclass
class WeatherForecast:
    generated_at: datetime
    steps: list[WeatherStep]  # one per 6h forecast step

@dataclass
class WeatherStep:
    valid_time: datetime
    temperature_k: float   # Kelvin (convert to F in UI)
    wind_u_ms: float       # m/s (east-west component)
    wind_v_ms: float       # m/s (north-south component)
```

Run model inference in a background thread so the UI is not blocked. Catch model load failures and return a "forecast unavailable" state.

**Acceptance checks:**

```bash
# 1. Forecast runs (requires GPU + earth2studio installed)
python -c "
from src.services.weather_service import WeatherService
ws = WeatherService()
fc = ws.get_forecast(force_refresh=True)
print(f'Forecast generated at: {fc.generated_at}')
print(f'Steps: {len(fc.steps)}')
for s in fc.steps[:3]:
    temp_f = (s.temperature_k - 273.15) * 9/5 + 32
    print(f'  {s.valid_time}: {temp_f:.1f}F')
"
# expect: prints forecast times and temperatures for Chicago, no exceptions

# 2. Caching works
python -c "
from src.services.weather_service import WeatherService
ws = WeatherService()
f1 = ws.get_forecast(force_refresh=True)
f2 = ws.get_forecast()  # should use cache
assert f1.generated_at == f2.generated_at, 'Cache miss'
print('Cache hit OK')
"
# expect: "Cache hit OK" (second call returns instantly)

# 3. Graceful failure without GPU
python -c "
from src.services.weather_service import WeatherService
ws = WeatherService()
try:
    fc = ws.get_forecast()
    print(f'Got forecast: {len(fc.steps)} steps')
except Exception as e:
    print(f'Handled gracefully: {type(e).__name__}')
"
# expect: either prints forecast or a handled exception, never a raw traceback
```

---

## Ticket 7: Weather Panel UI

**Branch:** `weather-panel`
**Depends on:** Tickets 1 and 6 (WeatherForecast dataclass, styles)
**Files:**

- `src/ui/weather_panel.py`

**What to build:**

```python
class WeatherPanel(QWidget):
    """
    Displays Chicago weather from Earth2Studio output.
    
    Layout:
      [Current temp F]  [Wind speed mph + direction]
      [6h-step forecast row: 42F, 38F, 35F, ...]
      or "Weather forecast unavailable" if no data
    """

    def update_forecast(self, forecast: WeatherForecast | None) -> None:
        """Refresh display with new forecast data or show unavailable state."""
```

Convert Kelvin to Fahrenheit. Compute wind speed from u/v components: `speed = sqrt(u^2 + v^2) * 2.237` (m/s to mph). Compute cardinal direction from atan2.

Dark background consistent with train panel. White text, same font family.

**Acceptance checks:**

```bash
# 1. Panel renders with mock data
python -c "
import sys
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QApplication
from src.services.weather_service import WeatherForecast, WeatherStep
from src.ui.weather_panel import WeatherPanel

app = QApplication(sys.argv)
panel = WeatherPanel()

fc = WeatherForecast(
    generated_at=datetime.now(),
    steps=[
        WeatherStep(datetime.now() + timedelta(hours=i*6), 280.0 - i, 3.0, -2.0)
        for i in range(8)
    ]
)
panel.update_forecast(fc)
panel.show()
app.exec()
"
# expect: dark panel showing current temp (~44F), wind speed/direction, and 6h-step forecast row

# 2. Unavailable state
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.weather_panel import WeatherPanel

app = QApplication(sys.argv)
panel = WeatherPanel()
panel.update_forecast(None)
panel.show()
app.exec()
"
# expect: panel shows "Weather forecast unavailable" in dimmed text
```

---

## Ticket 8: ML Prediction Stub

**Branch:** `ml-stub`
**Depends on:** Ticket 1 (config.py)
**Files:**

- `src/models/ml_predictor.py`
- `src/ui/ml_panel.py`

**What to build:**

`ml_predictor.py`:

```python
class RandomForestPredictor:
    """
    Placeholder for future Random Forest arrival predictor.
    
    Planned features:
    - Train on historical CTA arrival data (log API responses over time)
    - Features: time of day, day of week, weather, line, direction, delay flags
    - Target: actual arrival delta vs CTA predicted arrival
    """

    def predict(self, *args, **kwargs):
        raise NotImplementedError(
            "Random Forest predictor is not yet implemented. "
            "See TICKETS.md Ticket 8 for planned feature description."
        )
```

`ml_panel.py`:

```python
class MLPanel(QWidget):
    """Grayed-out placeholder panel for future ML predictions."""
    # Shows: "ML Arrival Prediction [Coming Soon]"
    # Dark background, dimmed text, consistent with overall theme
```

**Acceptance checks:**

```bash
# 1. Stub raises correctly
python -c "
from src.models.ml_predictor import RandomForestPredictor
p = RandomForestPredictor()
try:
    p.predict()
except NotImplementedError as e:
    print(f'Correct: {e}')
"
# expect: prints NotImplementedError message

# 2. Panel renders
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.ml_panel import MLPanel

app = QApplication(sys.argv)
panel = MLPanel()
panel.show()
app.exec()
"
# expect: dark panel with "ML Arrival Prediction [Coming Soon]" in dimmed/gray text
```

---

## Ticket 9: Main Window Assembly and Polling

**Branch:** `main-window`
**Depends on:** Tickets 2-8 (all components)
**Files:**

- `src/ui/main_window.py`
- `src/main.py` (update from stub to real entry point)

**What to build:**

```python
class MainWindow(QMainWindow):
    """
    Full app window. Layout (vertical):
      [TrainPanel]        -- 3 destination boxes
      [WeatherPanel]      -- Earth2Studio forecast
      [MLPanel]           -- Coming soon stub
      [StatusBar]         -- "Last updated: HH:MM:SS CT"
    """

    def __init__(self):
        # Instantiate: CTAClient, TransferCalculator, WeatherService
        # Build layout with TrainPanel, WeatherPanel, MLPanel
        # Start QTimer for 30s CTA polling
        # Start weather forecast in background thread

    def _poll_cta(self) -> None:
        """
        Called every 30s by QTimer.
        1. CTAClient.fetch_sheridan_red()
        2. CTAClient.fetch_wilson_purple_linden()
        3. TransferCalculator.compute_connections(howard_trains, purple_trains)
        4. TrainPanel.update_data(red_trains, linden_connections)
        5. Update status bar timestamp
        Run API calls in QThread/QRunnable to avoid blocking UI.
        """

    def _on_weather_ready(self, forecast: WeatherForecast) -> None:
        """Signal handler: update WeatherPanel when forecast completes."""
```

`src/main.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

**Acceptance checks:**

```bash
# 1. App launches and shows all panels
python -m src.main
# expect: window opens with:
#   - header "Next 'L' services from Sheridan | 9 min walk"
#   - 3 train boxes (Howard, 95th, Linden) with live data (or "No upcoming service" if off-hours)
#   - weather panel (forecast or "unavailable" if no GPU)
#   - ML panel "Coming Soon"
#   - status bar with timestamp

# 2. Auto-refresh (wait 35 seconds)
# expect: status bar timestamp updates, train countdowns change

# 3. Box rotation (wait 15 seconds)
# expect: at least one box fades to its second train and back

# 4. Close window
# expect: app exits cleanly, no errors in terminal
```

---

## Ticket Dependency Graph

```
Ticket 1 (Scaffold)
├── Ticket 2 (CTA API Client)
│   ├── Ticket 3 (Transfer Calculator)
│   └── Ticket 5 (Train Panel) ← also needs 3, 4
├── Ticket 4 (Train Box Widget)
│   └── Ticket 5 (Train Panel)
├── Ticket 6 (Weather Service)
│   └── Ticket 7 (Weather Panel)
├── Ticket 8 (ML Stub)
└── Ticket 9 (Main Window) ← needs all of 2-8
```

Tickets 2, 4, 6, and 8 can all be worked in parallel after Ticket 1 merges. Ticket 9 is the final integration.

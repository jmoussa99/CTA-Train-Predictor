# CTA Train Predictor

Desktop app (Python + PyQt6) that shows **Red Line** arrivals at Sheridan (Howard and 95th/Dan Ryan) and **Purple Line** connections to Linden via Wilson, with walk time to the station baked in. Includes a Chicago weather panel via Open-Meteo and a **CNN+LSTM model** that learns to predict actual arrival times in real time.

## Run

```bash
uv sync
cp src/config_secrets.example.py src/config_secrets.py
# Edit config_secrets.py and set CTA_API_KEY (or export CTA_API_KEY instead)
uv run python -m src.main
```

## Config

Station IDs, walk time, poll interval, colors, and ML hyperparameters are in `src/config.py`.

The **CTA Train Tracker API key** is not stored in the repo. Set it via:

- Environment variable `CTA_API_KEY`, or
- `src/config_secrets.py` (gitignored; start from `src/config_secrets.example.py`)

## ML Arrival Prediction

A CNN+LSTM model predicts actual minutes-to-arrival, learning from how CTA predictions drift over time. Everything runs in memory — no data is saved to disk.

**How it works:**

1. Every 10-second poll, observations (CTA prediction, delay flags, weather, time features) are recorded in an in-memory buffer.
2. When a train disappears from the API (it arrived), the buffer gets ground-truth labels: for each past observation of that run, the actual remaining time is known.
3. After 3 completed runs, the model trains on sliding windows of these sequences and begins predicting for active trains.
4. The ML panel shows each tracked train with CTA's estimate vs. the model's prediction and a delta indicator.

**Architecture:**

- Two 1D-CNN layers (BatchNorm + ReLU) extract local temporal features from the observation sequence.
- A 2-layer LSTM captures longer-range dependencies across the window.
- A fully-connected head outputs predicted minutes remaining.
- 13 input features per timestep: cyclical time encoding, station_minutes, delay/schedule/approaching flags, route, weather conditions, and prediction delta.

The model improves throughout each session as more trains complete their runs. Training and inference run in a background thread so the UI stays responsive.

## Notes

- Weather data comes from the free [Open-Meteo API](https://open-meteo.com/) and requires no API key.
- CTA data comes from the [Train Tracker API](https://www.transitchicago.com/developers/ttdocs/).

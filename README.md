# CTA Train Predictor

Desktop app (Python + PyQt6) that shows **Red Line** arrivals at Sheridan (Howard and 95th/Dan Ryan) and **Purple Line** connections to Linden via Wilson, with walk time to the station baked in. Includes a Chicago weather panel (NVIDIA Earth2Studio when available) and a placeholder for future ML predictions.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp src/config_secrets.example.py src/config_secrets.py
# Edit config_secrets.py and set CTA_API_KEY (or export CTA_API_KEY instead)
python -m src.main
```

## Config

Station IDs, walk time, poll interval, and colors are in `src/config.py`.

The **CTA Train Tracker API key** is not stored in the repo. Set it via:

- Environment variable `CTA_API_KEY`, or
- `src/config_secrets.py` (gitignored; start from `src/config_secrets.example.py`)

## Notes

- Weather needs `earth2studio` and a GPU-friendly setup; if that fails, the app still runs and shows trains.
- CTA data comes from the [Train Tracker API](https://www.transitchicago.com/developers/ttdocs/).

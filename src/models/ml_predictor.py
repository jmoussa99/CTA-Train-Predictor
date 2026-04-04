from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.config import (
    ML_CNN_CHANNELS,
    ML_FEATURE_DIM,
    ML_LEARNING_RATE,
    ML_LSTM_HIDDEN,
    ML_LSTM_LAYERS,
    ML_TRAIN_EPOCHS,
)

logger = logging.getLogger(__name__)


class ArrivalCNNLSTM(nn.Module):
    """1-D CNN extracts local temporal features from the observation sequence,
    then an LSTM captures longer-range dependencies across the window.
    A small fully-connected head maps the final hidden state to a scalar
    prediction of *actual* minutes remaining until the train arrives.
    """

    def __init__(
        self,
        input_dim: int = ML_FEATURE_DIM,
        cnn_channels: int = ML_CNN_CHANNELS,
        lstm_hidden: int = ML_LSTM_HIDDEN,
        lstm_layers: int = ML_LSTM_LAYERS,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        self.cnn = nn.Sequential(
            nn.Conv1d(input_dim, cnn_channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(cnn_channels),
            nn.Conv1d(cnn_channels, cnn_channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(cnn_channels),
        )

        self.lstm = nn.LSTM(
            input_size=cnn_channels,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )

        self.head = nn.Sequential(
            nn.Linear(lstm_hidden, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, features)
        c = self.cnn(x.permute(0, 2, 1))  # -> (batch, channels, seq_len)
        c = c.permute(0, 2, 1)  # -> (batch, seq_len, channels)
        out, _ = self.lstm(c)  # -> (batch, seq_len, hidden)
        return self.head(out[:, -1, :]).squeeze(-1)  # -> (batch,)


@dataclass
class Prediction:
    run_id: str
    route: str
    destination: str
    cta_minutes: float
    predicted_minutes: float
    confidence: float


class ArrivalPredictor:
    """Manages online training and inference for the CNN+LSTM model.

    All state lives in memory; nothing is persisted to disk.
    Call `train()` with numpy arrays produced by `ObservationBuffer`,
    then `predict()` with active-run sequences.
    """

    def __init__(self) -> None:
        self._device = torch.device("cpu")
        self._model = ArrivalCNNLSTM().to(self._device)
        self._optimizer = torch.optim.Adam(
            self._model.parameters(), lr=ML_LEARNING_RATE
        )
        self._criterion = nn.HuberLoss()
        self._trained = False
        self._loss = float("inf")
        self._rounds = 0

    @property
    def is_trained(self) -> bool:
        return self._trained

    @property
    def last_loss(self) -> float:
        return self._loss

    @property
    def rounds(self) -> int:
        return self._rounds

    def train(self, X: np.ndarray, y: np.ndarray) -> float:
        self._model.train()

        X_t = torch.tensor(X, dtype=torch.float32, device=self._device)
        y_t = torch.tensor(y, dtype=torch.float32, device=self._device)

        ds = TensorDataset(X_t, y_t)
        loader = DataLoader(ds, batch_size=min(32, len(X)), shuffle=True)

        loss_val = 0.0
        for _ in range(ML_TRAIN_EPOCHS):
            epoch_loss = 0.0
            for xb, yb in loader:
                self._optimizer.zero_grad()
                pred = self._model(xb)
                loss = self._criterion(pred, yb)
                loss.backward()
                self._optimizer.step()
                epoch_loss += loss.item()
            loss_val = epoch_loss / len(loader)

        self._trained = True
        self._loss = loss_val
        self._rounds += 1
        logger.info(
            "ML train round %d  loss=%.4f  samples=%d",
            self._rounds,
            loss_val,
            len(X),
        )
        return loss_val

    def predict(
        self,
        sequences: dict[str, np.ndarray],
        active_runs: dict,
    ) -> list[Prediction]:
        if not self._trained or not sequences:
            return []

        self._model.eval()
        preds: list[Prediction] = []

        with torch.no_grad():
            for rid, seq in sequences.items():
                x = torch.tensor(
                    seq, dtype=torch.float32, device=self._device
                ).unsqueeze(0)
                mins = max(self._model(x).item(), 0.0)

                obs_list = active_runs.get(rid)
                if not obs_list:
                    continue

                last = obs_list[-1]
                conf = min(self._rounds / 10.0, 1.0) * max(
                    0.0, 1.0 - self._loss
                )
                conf = max(0.0, min(1.0, conf))

                preds.append(
                    Prediction(
                        run_id=rid,
                        route=last.route,
                        destination=last.destination,
                        cta_minutes=last.station_minutes,
                        predicted_minutes=mins,
                        confidence=conf,
                    )
                )

        preds.sort(key=lambda p: p.cta_minutes)
        return preds

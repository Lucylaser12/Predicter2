"""
features.py
Builds technical-indicator features from raw OHLCV candle data.

These are the model's inputs. All features are computed using only
PAST data relative to each row (no lookahead), which is essential for
an honest backtest.
"""

import numpy as np
import pandas as pd


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(series, period=20, num_std=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    width = (upper - lower) / sma.replace(0, np.nan)
    return pct_b.fillna(0.5), width.fillna(0)


def _atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def build_features(df):
    """
    df: DataFrame with columns open_time, open, high, low, close, volume,
        num_trades, taker_buy_base, taker_buy_quote (as produced by data_fetch.py)

    Returns a new DataFrame with engineered features + the original close price,
    plus the target column 'target_up' (1 if NEXT candle closes higher, else 0).
    """
    out = df.copy().reset_index(drop=True)
    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]

    # --- Returns / momentum ---
    out["ret_1"] = close.pct_change(1)
    out["ret_3"] = close.pct_change(3)
    out["ret_6"] = close.pct_change(6)
    out["ret_12"] = close.pct_change(12)

    # --- Moving averages (relative distance, not absolute price -> stationarity) ---
    for window in [5, 10, 20, 50]:
        sma = close.rolling(window).mean()
        out[f"dist_sma_{window}"] = (close - sma) / sma

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    out["dist_ema_12"] = (close - ema_12) / ema_12
    out["dist_ema_26"] = (close - ema_26) / ema_26

    # --- RSI ---
    out["rsi_14"] = _rsi(close, 14)

    # --- MACD ---
    macd_line, signal_line, hist = _macd(close)
    out["macd_hist"] = hist
    out["macd_norm"] = macd_line / close

    # --- Bollinger Bands ---
    pct_b, bb_width = _bollinger(close)
    out["bb_pct_b"] = pct_b
    out["bb_width"] = bb_width

    # --- Volatility ---
    out["volatility_10"] = out["ret_1"].rolling(10).std()
    out["volatility_30"] = out["ret_1"].rolling(30).std()
    out["atr_14"] = _atr(out, 14) / close  # normalized

    # --- Volume features ---
    out["volume_chg"] = volume.pct_change(1)
    out["volume_z_20"] = (volume - volume.rolling(20).mean()) / volume.rolling(20).std()
    out["taker_buy_ratio"] = out["taker_buy_base"] / out["volume"].replace(0, np.nan)

    # --- Candle structure ---
    out["body_pct"] = (close - out["open"]) / out["open"]
    out["upper_wick"] = (high - close.where(close > out["open"], out["open"])) / close
    out["lower_wick"] = (close.where(close < out["open"], out["open"]) - low) / close
    out["high_low_range"] = (high - low) / close

    # --- Time-of-day cyclical features (captures intraday seasonality) ---
    hour = out["open_time"].dt.hour + out["open_time"].dt.minute / 60.0
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["day_of_week"] = out["open_time"].dt.dayofweek

    # --- TARGET: did the NEXT candle close higher than this candle's close? ---
    out["target_up"] = (close.shift(-1) > close).astype(int)

    feature_cols = [
        "ret_1", "ret_3", "ret_6", "ret_12",
        "dist_sma_5", "dist_sma_10", "dist_sma_20", "dist_sma_50",
        "dist_ema_12", "dist_ema_26",
        "rsi_14", "macd_hist", "macd_norm",
        "bb_pct_b", "bb_width",
        "volatility_10", "volatility_30", "atr_14",
        "volume_chg", "volume_z_20", "taker_buy_ratio",
        "body_pct", "upper_wick", "lower_wick", "high_low_range",
        "hour_sin", "hour_cos", "day_of_week",
    ]

    # Drop rows with NaNs from rolling windows / shifts (start and end of series)
    model_df = out.dropna(subset=feature_cols + ["target_up"]).reset_index(drop=True)

    return model_df, feature_cols


if __name__ == "__main__":
    raw = pd.read_csv("btc_15m_raw.csv", parse_dates=["open_time", "close_time"])
    model_df, feature_cols = build_features(raw)
    print(f"Built {len(feature_cols)} features over {len(model_df)} rows")
    print(f"Target balance: {model_df['target_up'].mean():.3f} fraction 'up'")
    model_df.to_csv("btc_15m_features.csv", index=False)
    print("Saved to btc_15m_features.csv")

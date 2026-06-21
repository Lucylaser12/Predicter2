"""
data_fetch.py
Pulls historical BTC price/volume data from CoinGecko's free public API.

IMPORTANT: Pehle hum Binance API use kar rahe the, lekin Binance kuch
regions/servers (jaise GitHub Actions ke US/EU data centers) ko geo-block
kar deta hai (HTTP 451 error). CoinGecko ka free API geo-block nahi karta
aur isiliye GitHub Actions pe reliably chalta hai.

TRADE-OFF: CoinGecko ka free /market_chart endpoint sirf price + volume
deta hai (Binance jaisa full open/high/low/close OHLC candle nahi).
Isliye humne resampling ke through pseudo-OHLC banaya hai (neeche dekho).
Ye real exchange OHLC se kam rich hai, lekin price-direction prediction
ke liye phir bhi kaam karta hai.
"""

import requests
import pandas as pd
import time
from datetime import datetime, timezone

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

# CoinGecko free plan granularity rule (automatic, can't be chosen directly):
#   1-2 days   -> ~5 minute data points
#   3-90 days  -> hourly data points
#   91+ days   -> daily data points
# Isliye "15m" jaisa exact interval nahi maang sakte -- jo bhi granularity
# CoinGecko de, usi pe kaam karte hain. Fine-grained candles ke liye hum
# sirf "days=1" ya "days=2" maangte hain (~5 min spacing), phir use
# 15-min blocks me resample karte hain.


def fetch_market_chart(days=2, vs_currency="usd"):
    """
    Fetch raw price + volume time series from CoinGecko.
    Returns a DataFrame with columns: timestamp, price, volume
    """
    params = {"vs_currency": vs_currency, "days": days}
    resp = requests.get(COINGECKO_BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    df_price = pd.DataFrame(prices, columns=["timestamp", "price"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])

    df = pd.merge(df_price, df_vol, on="timestamp", how="left")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def resample_to_candles(df, interval_minutes=15):
    """
    CoinGecko humein sirf price points deta hai (OHLC nahi), isliye hum
    unhe resample karke pseudo-candles banate hain:
      - open  = period ke pehle price point
      - high  = period ka max price
      - low   = period ka min price
      - close = period ke aakhri price point
      - volume = period ke volume points ka sum
    """
    df = df.set_index("timestamp")
    rule = f"{interval_minutes}min"

    ohlc = df["price"].resample(rule).ohlc()
    vol = df["volume"].resample(rule).sum()

    out = ohlc.join(vol)
    out = out.dropna(subset=["open", "high", "low", "close"]).reset_index()
    out = out.rename(columns={"timestamp": "open_time"})

    # Derived columns taaki features.py ka schema match ho jaaye
    out["close_time"] = out["open_time"] + pd.Timedelta(minutes=interval_minutes) - pd.Timedelta(milliseconds=1)
    out["num_trades"] = 0  # CoinGecko free plan me trade count nahi milta
    out["taker_buy_base"] = out["volume"] * 0.5  # estimate, real buy/sell split nahi milta
    out["taker_buy_quote"] = out["taker_buy_base"] * out["close"]

    keep_cols = ["open_time", "open", "high", "low", "close", "volume",
                 "close_time", "num_trades", "taker_buy_base", "taker_buy_quote"]
    return out[keep_cols]


def fetch_historical(symbol="BTCUSDT", interval="15m", total_candles=6000, min_required=400):
    """
    Same function signature jo pehle Binance wali file me thi, taaki
    predict_and_save.py me kuch badalna na pade.

    IMPORTANT: CoinGecko free plan ki granularity automatic hai aur
    days parameter ke hisaab se badalti hai:
      - days=1-2  -> ~5 min spacing
      - days=3-90 -> ~1 hour spacing
      - days=91+  -> ~1 day spacing

    Agar hum chote "days" (jisme fine 5-min spacing milti hai) use karein,
    to total history bahut kam milti hai (~190 candles @ 15m). Agar zyada
    "days" use karein taaki zyada history mile, to underlying granularity
    coarser (hourly) ho jaati hai -- aur use 15-min blocks me resample
    karne se data LOSS hota hai (zyada NaN gaps), kam candles, behtar nahi.

    Isliye yahaan hum candle interval ko CoinGecko ki di hui granularity
    ke hisaab se khud adapt karte hain: jitne din maange, utni hi
    "natural" granularity pe candles banate hain (chote din = 15m candles,
    bade din = 1h candles). Requested `interval` sirf ek hint hai jab
    granularity fine ho.
    """
    requested_minutes = 15
    if interval.endswith("m"):
        requested_minutes = int(interval[:-1])
    elif interval.endswith("h"):
        requested_minutes = int(interval[:-1]) * 60

    # (days, natural granularity in minutes) pairs -- jitna zyada din,
    # CoinGecko utni coarser granularity deta hai
    attempts = [
        (2, requested_minutes),     # fine data, requested interval try karo
        (7, 60),                    # hourly granularity
        (30, 60),
        (90, 60),
        (180, 24 * 60),             # daily granularity (bahut zyada history)
    ]

    candles = None
    for days, candle_minutes in attempts:
        print(f"CoinGecko se data fetch ho raha hai (days={days}, candle={candle_minutes}min)...")
        try:
            raw = fetch_market_chart(days=days)
        except requests.exceptions.HTTPError as e:
            print(f"  days={days} fail hua ({e}), agla try karte hain...")
            time.sleep(1)
            continue

        time.sleep(1)  # CoinGecko free tier rate limit ka respect

        candidate = resample_to_candles(raw, interval_minutes=candle_minutes)
        print(f"  -> {len(candidate)} candles mile is granularity pe")

        if len(candidate) >= min_required:
            candles = candidate
            break
        if candles is None or len(candidate) > len(candles):
            candles = candidate  # sabse best jo mila ho rakh lo

    if candles is None or len(candles) < 50:
        raise RuntimeError(
            f"Itna data nahi mil paya CoinGecko se. Sirf {0 if candles is None else len(candles)} "
            "candles mile. API status ya network check karo."
        )

    if len(candles) > total_candles:
        candles = candles.tail(total_candles).reset_index(drop=True)

    # Actual interval candle timestamps se detect karte hain (taaki JSON
    # output me sahi interval dikhe, requested wala nahi)
    if len(candles) >= 2:
        actual_minutes = int((candles["open_time"].iloc[1] - candles["open_time"].iloc[0]).total_seconds() / 60)
    else:
        actual_minutes = requested_minutes

    print(f"Final: {len(candles)} candles use ho rahe hain (~{actual_minutes} min interval).")
    candles.attrs["interval_minutes"] = actual_minutes
    return candles


if __name__ == "__main__":
    print(f"Fetching BTC data from CoinGecko... ({datetime.now(timezone.utc).isoformat()})")
    df = fetch_historical(interval="15m", total_candles=6000)
    print(f"Fetched {len(df)} candles from {df['open_time'].min()} to {df['open_time'].max()}")
    df.to_csv("btc_15m_raw.csv", index=False)
    print("Saved to btc_15m_raw.csv")

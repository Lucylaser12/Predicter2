"""
predict_and_save.py

Ye script poora pipeline ek saath chalata hai:
1. Binance se naya BTC data fetch karta hai
2. Features banata hai
3. Model train karta hai (walk-forward validation ke saath)
4. NEXT candle ka prediction nikalta hai
5. Sab kuch ek prediction.json file me save karta hai

Ye file website padhega -- isliye iska format simple JSON rakha hai.

GitHub Actions ye script har ghante automatic chalayega.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    from sklearn.ensemble import GradientBoostingClassifier

from data_fetch import fetch_historical
from features import build_features


def make_gbm():
    if HAS_LGBM:
        return LGBMClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8,
            class_weight="balanced", verbosity=-1,
        )
    return GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.05)


def make_logreg():
    return LogisticRegression(max_iter=1000, C=0.5, class_weight="balanced")


def walk_forward_accuracy(X, y, n_splits=5, min_train_frac=0.6, test_frac=0.08, min_test_size=20):
    """Honest out-of-sample accuracy check -- sirf yeh batane ke liye ki
    model abhi kitna reliable hai (ya nahi hai).

    min_test_size ko purposely chota rakha hai (20) kyunki CoinGecko se
    kabhi-kabhi limited history milti hai -- chote dataset par bhi kam se
    kam kuch fold mil sakein, taaki validation completely skip na ho."""
    n = len(X)
    min_train = max(30, int(n * min_train_frac))
    test_size = max(min_test_size, int(n * test_frac))

    if n < min_train + min_test_size:
        print(f"  Warning: sirf {n} rows hain, walk-forward validation ke liye kam hai. Skip kar rahe hain.")
        return []

    accs = []
    start_test = min_train
    for _ in range(n_splits):
        train_end = start_test
        test_end = min(start_test + test_size, n)
        if test_end <= train_end or (test_end - train_end) < min_test_size // 2:
            break
        X_train, y_train = X[:train_end], y[:train_end]
        X_test, y_test = X[train_end:test_end], y[train_end:test_end]

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = make_logreg()
        model.fit(X_train_s, y_train)
        pred = model.predict(X_test_s)
        accs.append(accuracy_score(y_test, pred))

        start_test = test_end

    return accs


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Pipeline shuru ho raha hai...")

    # Step 1: Data fetch
    print("Step 1: BTC data fetch ho raha hai CoinGecko se...")
    raw = fetch_historical(symbol="BTCUSDT", interval="15m", total_candles=6000)
    actual_interval_minutes = raw.attrs.get("interval_minutes", 15)
    print(f"  {len(raw)} candles mile, {raw['open_time'].min()} se {raw['open_time'].max()} tak "
          f"(~{actual_interval_minutes} min interval)")

    # Step 2: Features
    print("Step 2: Features ban rahe hain...")
    df, feature_cols = build_features(raw)
    print(f"  {len(feature_cols)} features, {len(df)} usable rows")

    X = df[feature_cols].values
    y = df["target_up"].values

    # Step 3: Honest accuracy check (walk-forward) -- isse pata chalega
    # ki model abhi kitna trustworthy hai
    print("Step 3: Walk-forward validation se honest accuracy check ho raha hai...")
    fold_accs = walk_forward_accuracy(X, y)
    avg_acc = float(np.mean(fold_accs)) if fold_accs else 0.5
    print(f"  Average out-of-sample accuracy: {avg_acc:.4f} (folds: {[round(a, 4) for a in fold_accs]})")

    # Step 4: Final model -- saare data pe train, taaki latest prediction sabse accurate ho
    print("Step 4: Final model training ho raha hai (saare available data pe)...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = make_gbm()
    model.fit(X, y)  # tree models ko scaling ki zaroorat nahi

    # Step 5: Sabse latest row se NEXT candle ka prediction
    latest_row = X[-1:].copy()
    prob_up = float(model.predict_proba(latest_row)[0][1])
    prediction = "up" if prob_up >= 0.5 else "down"

    latest_close = float(df["close"].iloc[-1])
    latest_time = df["open_time"].iloc[-1].isoformat()

    # Step 6: Result ko JSON me save karna -- website ye padhegi
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": "BTCUSDT",
        "interval": f"{actual_interval_minutes}m",
        "data_source": "CoinGecko (pseudo-OHLC, resampled from price points)",
        "latest_candle_time": latest_time,
        "latest_close_price": latest_close,
        "prediction": prediction,
        "probability_up": round(prob_up, 4),
        "confidence_pct": round(abs(prob_up - 0.5) * 200, 2),  # 0-100 scale, 0 = pure coin flip
        "model_type": "lightgbm" if HAS_LGBM else "gradient_boosting",
        "walk_forward_accuracy": round(avg_acc, 4),
        "walk_forward_folds": [round(a, 4) for a in fold_accs],
        "rows_used": len(df),
        "disclaimer": (
            "Ye sirf educational/portfolio project hai. Out-of-sample accuracy "
            "coin-flip (50%) ke kareeb hai. Fees ke baad shayad profitable na ho. "
            "Real money trading ke liye use na karein."
        ),
    }

    with open("prediction.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n--- Result ---")
    print(json.dumps(result, indent=2))
    print("\nSaved to prediction.json")


if __name__ == "__main__":
    main()

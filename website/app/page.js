"use client";

import { useEffect, useState } from "react";

export default function HomePage() {
  const [prediction, setPrediction] = useState(null);
  const [livePrice, setLivePrice] = useState(null);
  const [priceChange, setPriceChange] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // prediction.json hamari apni site se aata hai (GitHub Actions ne banaya)
    fetch("/prediction.json")
      .then((res) => res.json())
      .then(setPrediction)
      .catch(() => setError("Prediction file load nahi ho payi"));

    // Live price CoinGecko ke public API se (CORS-friendly)
    fetch(
      "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
    )
      .then((res) => res.json())
      .then((data) => {
        setLivePrice(data.bitcoin.usd);
        setPriceChange(data.bitcoin.usd_24h_change);
      })
      .catch(() => {
        /* live price fail ho jaaye to bhi prediction dikhti rahegi */
      });
  }, []);

  if (error) {
    return <div style={styles.page}><p>{error}</p></div>;
  }

  if (!prediction) {
    return (
      <div style={styles.page}>
        <p style={{ color: "#888" }}>Loading prediction...</p>
      </div>
    );
  }

  const isUp = prediction.prediction === "up";
  const confidenceColor = isUp ? "#3B5BA5" : "#A8453B";

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <h1 style={styles.title}>BTC direction predictor</h1>
        <p style={styles.subtitle}>
          Educational demo &mdash; not financial advice
        </p>

        <div style={styles.priceRow}>
          <span style={styles.priceVal}>
            {livePrice ? `$${livePrice.toLocaleString()}` : "loading..."}
          </span>
          {priceChange !== null && (
            <span
              style={{
                ...styles.priceChange,
                color: priceChange >= 0 ? "#3B5BA5" : "#A8453B",
              }}
            >
              {priceChange >= 0 ? "+" : ""}
              {priceChange.toFixed(2)}% (24h)
            </span>
          )}
        </div>

        <div style={styles.card}>
          <p style={styles.cardLabel}>Next 15m candle, model says</p>
          <div style={{ ...styles.predictionBig, color: confidenceColor }}>
            {prediction.prediction.toUpperCase()}
          </div>
          <p style={styles.confidenceText}>
            Confidence: {prediction.confidence_pct}% above coin-flip
            (probability up: {(prediction.probability_up * 100).toFixed(1)}%)
          </p>
        </div>

        <div style={styles.statsGrid}>
          <div style={styles.statBox}>
            <p style={styles.statLabel}>Walk-forward accuracy</p>
            <p style={styles.statValue}>
              {(prediction.walk_forward_accuracy * 100).toFixed(1)}%
            </p>
          </div>
          <div style={styles.statBox}>
            <p style={styles.statLabel}>Candle interval</p>
            <p style={styles.statValue}>{prediction.interval}</p>
          </div>
          <div style={styles.statBox}>
            <p style={styles.statLabel}>Last updated</p>
            <p style={styles.statValue}>
              {new Date(prediction.generated_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div style={styles.disclaimer}>{prediction.disclaimer}</div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#F7F5F0",
    display: "flex",
    justifyContent: "center",
    padding: "40px 16px",
    fontFamily: "system-ui, sans-serif",
    color: "#1C1B19",
  },
  container: {
    width: "100%",
    maxWidth: 480,
  },
  title: {
    fontSize: 24,
    fontWeight: 600,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: "#777",
    marginBottom: 24,
  },
  priceRow: {
    display: "flex",
    alignItems: "baseline",
    gap: 10,
    marginBottom: 24,
  },
  priceVal: {
    fontSize: 28,
    fontWeight: 600,
    fontFamily: "monospace",
  },
  priceChange: {
    fontSize: 14,
    fontFamily: "monospace",
  },
  card: {
    background: "#FFFFFF",
    border: "1px solid #E5E2D9",
    borderRadius: 16,
    padding: "24px",
    textAlign: "center",
    marginBottom: 20,
  },
  cardLabel: {
    fontSize: 13,
    color: "#777",
    marginBottom: 12,
  },
  predictionBig: {
    fontSize: 42,
    fontWeight: 700,
    letterSpacing: 1,
    marginBottom: 8,
  },
  confidenceText: {
    fontSize: 13,
    color: "#555",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 10,
    marginBottom: 20,
  },
  statBox: {
    background: "#EFEDE5",
    borderRadius: 10,
    padding: "12px 10px",
    textAlign: "center",
  },
  statLabel: {
    fontSize: 11,
    color: "#777",
    marginBottom: 4,
  },
  statValue: {
    fontSize: 13,
    fontWeight: 600,
  },
  disclaimer: {
    fontSize: 12,
    color: "#8A5A1E",
    background: "#FBF0DC",
    borderRadius: 10,
    padding: "12px 14px",
    lineHeight: 1.6,
  },
};

import os
import math
import requests
import pandas as pd
import numpy as np
from io import StringIO

STOOQ_SYMBOL = "SPY.US"

# --- Capital config (edit defaults or override via GitHub Action env vars) ---
SPY_CORE_VALUE = float(os.getenv("SPY_CORE_VALUE", "127000"))   # informational
ADD_CAPITAL = float(os.getenv("ADD_CAPITAL", "30000"))          # capital earmarked for dip buys

# Tier sizing (fractions of ADD_CAPITAL)
TIER1_ALLOC = float(os.getenv("TIER1_ALLOC", "0.10"))  # 10%
TIER2_ALLOC = float(os.getenv("TIER2_ALLOC", "0.25"))  # 25%
TIER3_ALLOC = float(os.getenv("TIER3_ALLOC", "0.40"))  # 40%

# Thresholds
PULLBACK_WITHIN_PCT = float(os.getenv("PULLBACK_WITHIN_PCT", "0.005"))  # 0.5%
STABILIZE_DAYS = int(os.getenv("STABILIZE_DAYS", "3"))
STABILIZE_RANGE_PCT = float(os.getenv("STABILIZE_RANGE_PCT", "0.02"))  # 2%

def fetch_stooq(symbol: str) -> pd.DataFrame:
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}&i=d"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing (EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)  # neutral fallback

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["RSI14"] = rsi(df["Close"], 14)
    return df

def within(x: float, target: float, pct: float) -> bool:
    # "touched or within pct above" target
    return x <= target * (1 + pct)

def sma200_rising(df: pd.DataFrame, lookback: int = 20) -> bool:
    if len(df) < 200 + lookback:
        return False
    a = df["SMA200"].iloc[-1]
    b = df["SMA200"].iloc[-(lookback+1)]
    if np.isnan(a) or np.isnan(b):
        return False
    return a > b

def stabilization(df: pd.DataFrame, days: int, range_pct: float) -> bool:
    # last N closes in a tight range (max/min - 1 <= range_pct)
    closes = df["Close"].iloc[-days:]
    mx = closes.max()
    mn = closes.min()
    if mn <= 0:
        return False
    return (mx / mn - 1) <= range_pct

def tier1_signal(row, trend_ok: bool) -> bool:
    # Tier 1:
    # - Bull trend: Close > SMA50, EMA20 > SMA50, SMA200 rising
    # - Pullback to EMA20: Low touches or within 0.5% of EMA20
    # - RSI 40–50
    # - Bullish day: Close > Open
    return (
        trend_ok
        and (row["Close"] > row["SMA50"])
        and (row["EMA20"] > row["SMA50"])
        and within(row["Low"], row["EMA20"], PULLBACK_WITHIN_PCT)
        and (40 <= row["RSI14"] <= 50)
        and (row["Close"] > row["Open"])
    )

def tier2_signal(row, prev_row) -> bool:
    # Tier 2:
    # - Above SMA200 (still in long-term up regime)
    # - Touch/undercut near SMA50
    # - RSI 30–40
    # - Strong green reclaim: Close > Open AND (Close > SMA50 OR Close > EMA20)
    return (
        (row["Close"] > row["SMA200"])
        and within(row["Low"], row["SMA50"], PULLBACK_WITHIN_PCT)
        and (30 <= row["RSI14"] <= 40)
        and (row["Close"] > row["Open"])
        and ((row["Close"] > row["SMA50"]) or (row["Close"] > row["EMA20"]))
        and (row["Close"] > prev_row["High"])  # adds "strength returning" flavor
    )

def tier3_signal(df: pd.DataFrame, row, prev_row) -> bool:
    # Tier 3:
    # - RSI <= 30
    # - Stabilization for N days
    # - Strong reclaim day: Close > Open AND Close > prev High
    return (
        (row["RSI14"] <= 30)
        and stabilization(df.iloc[:-1], STABILIZE_DAYS, STABILIZE_RANGE_PCT)  # stabilize BEFORE today
        and (row["Close"] > row["Open"])
        and (row["Close"] > prev_row["High"])
    )

def recommend_amount(tier: int) -> float:
    if tier == 1:
        return ADD_CAPITAL * TIER1_ALLOC
    if tier == 2:
        return ADD_CAPITAL * TIER2_ALLOC
    if tier == 3:
        return ADD_CAPITAL * TIER3_ALLOC
    return 0.0

def fmt_money(x: float) -> str:
    return f"${x:,.2f}"

def main():
    df = fetch_stooq(STOOQ_SYMBOL)
    df = compute_indicators(df)

    if len(df) < 220:
        raise SystemExit("Not enough history to compute SMA200 + lookbacks reliably.")

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_ok = sma200_rising(df, lookback=20) and (last["Close"] > last["SMA200"])

    t1 = tier1_signal(last, trend_ok)
    t2 = tier2_signal(last, prev)
    t3 = tier3_signal(df, last, prev)

    triggered_tier = 0
    if t3:
        triggered_tier = 3
    elif t2:
        triggered_tier = 2
    elif t1:
        triggered_tier = 1

    close = float(last["Close"])
    rec_amt = recommend_amount(triggered_tier)
    approx_shares = int(math.floor(rec_amt / close)) if rec_amt > 0 else 0

    # Build report
    lines = []
    lines.append("SPY Dip Buy Scan (Stooq)")
    lines.append("--------------------------------")
    lines.append(f"Date: {str(last['Date'].date())}")
    lines.append(f"SPY Close: {close:.2f}")
    lines.append(f"EMA20: {float(last['EMA20']):.2f} | SMA50: {float(last['SMA50']):.2f} | SMA200: {float(last['SMA200']):.2f}")
    lines.append(f"RSI14: {float(last['RSI14']):.2f}")
    lines.append("")
    lines.append(f"Core SPY Value (info): {fmt_money(SPY_CORE_VALUE)}")
    lines.append(f"Dip Add Capital Pool: {fmt_money(ADD_CAPITAL)}")
    lines.append("")

    if triggered_tier == 0:
        lines.append("Signal: ❌ No Tier buy signal today.")
    else:
        lines.append(f"Signal: ✅ TIER {triggered_tier} BUY THE DIP")
        lines.append(f"Recommended Buy Amount: {fmt_money(rec_amt)}")
        lines.append(f"Approx Shares @ close: {approx_shares} (approx; use your execution rules)")
        lines.append("")
        if triggered_tier == 1:
            lines.append("Tier 1 rationale: bull trend + pullback to EMA20 + RSI 40–50 + bullish day.")
        elif triggered_tier == 2:
            lines.append("Tier 2 rationale: above SMA200 + touch SMA50 + RSI 30–40 + strong reclaim day.")
        else:
            lines.append("Tier 3 rationale: RSI <= 30 + stabilization + strong reclaim day.")
        lines.append("")
        lines.append("Execution note: Prefer buying near the trigger zone (EMA20/50) rather than chasing a gap up.")

    report = "\n".join(lines)
    print(report)

    # Write report.md for artifact upload or commit (optional)
    with open("report.md", "w", encoding="utf-8") as f:
        f.write(report + "\n")

    # Export for GitHub Actions step outputs
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"tier={triggered_tier}\n")
            f.write(f"recommended_amount={rec_amt}\n")

if __name__ == "__main__":
    main()
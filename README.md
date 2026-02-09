SPY Dip Buy Scan (GitHub Action)

This repository contains a rule-based, automated buy-the-dip system for SPY designed for long-term investors who want to add to a core position during statistically favorable pullbacks, without selling the core prematurely.

The system runs automatically every morning and evaluates whether current market conditions qualify as a Tier 1, Tier 2, or Tier 3 dip-buy opportunity, then recommends how much capital to deploy.

⸻

What This Action Does

Each morning, the GitHub Action:
	1.	Pulls daily SPY OHLCV data from Stooq
	•	Source: https://stooq.com/q/d/l/?s=SPY.US&i=d
	2.	Computes key technical indicators
	•	20-day EMA
	•	50-day SMA
	•	200-day SMA
	•	RSI(14)
	3.	Evaluates three dip-buy tiers

🟢 Tier 1 — Shallow Dip in a Bull Trend

Triggered when:
	•	SPY is above the 50 SMA
	•	20 EMA is above the 50 SMA
	•	200 SMA is rising
	•	Price pulls back to the 20 EMA (within 0.5%)
	•	RSI(14) is between 40–50
	•	The day closes bullish (close > open)

Action:
	•	Buy ~10% of your predefined “dip-buy capital”

⸻

🟡 Tier 2 — Meaningful Pullback

Triggered when:
	•	SPY remains above the 200 SMA
	•	Price touches or slightly undercuts the 50 SMA
	•	RSI(14) is between 30–40
	•	Strong bullish reclaim day (close > open and reclaims EMA20 or SMA50)

Action:
	•	Buy ~25% of your dip-buy capital

⸻

🔴 Tier 3 — Deep Fear / High-Conviction Dip

Triggered when:
	•	RSI(14) ≤ 30
	•	Price stabilizes for multiple days in a tight range
	•	Strong bullish reversal day (close > open and > prior high)

Action:
	•	Buy ~40% of your dip-buy capital

⸻

	4.	Generates a clear daily report
	•	Current SPY price
	•	EMA/SMA levels
	•	RSI value
	•	Triggered tier (if any)
	•	Recommended dollar amount to buy
	•	Approximate share count
	5.	Publishes results
	•	Prints the report in GitHub Actions logs
	•	Writes a report.md artifact
	•	Automatically creates a GitHub Issue if a Tier 1, 2, or 3 signal is triggered (so you receive a notification)

⸻

Configuration

All key values are configurable via environment variables in the GitHub Action:

Variable	Description	Example
SPY_CORE_VALUE	Current value of your SPY core (informational)	127000
ADD_CAPITAL	Capital reserved for dip buying	30000
TIER1_ALLOC	Fraction of add capital for Tier 1	0.10
TIER2_ALLOC	Fraction of add capital for Tier 2	0.25
TIER3_ALLOC	Fraction of add capital for Tier 3	0.40
PULLBACK_WITHIN_PCT	Pullback tolerance	0.005
STABILIZE_DAYS	Days required for stabilization (Tier 3)	3
STABILIZE_RANGE_PCT	Max price range during stabilization	0.02

You can adjust these to be more conservative or aggressive without changing code.

⸻

Schedule

The workflow runs every morning at 4:00 AM local time (America/Los_Angeles).

Because GitHub Actions uses UTC, the workflow includes two cron entries to automatically handle daylight savings time:

on:
  schedule:
    # 4:00 AM Los Angeles
    - cron: "0 12 * * *"  # PDT
    - cron: "0 13 * * *"  # PST

You can also run the scan manually at any time using Actions → Run workflow.

⸻

What This Is (and Is Not)

This is:
	•	A long-term accumulation tool
	•	A volatility-harvesting system
	•	A rules-based way to buy fear

This is not:
	•	A day-trading system
	•	A market-timing top caller
	•	A replacement for risk management

The intent is to compound a core SPY position faster over time by deploying capital only when probabilities improve.

⸻

Typical Usage
	•	Let the action run automatically each morning
	•	Only act when a Tier 1/2/3 signal is triggered
	•	Use limit orders near the trigger zone (EMA20 / SMA50)
	•	Do nothing on most days — inactivity is a feature

⸻

License / Disclaimer

This project is for educational and personal-use purposes only.
It does not constitute financial advice.
You are responsible for all trading and investment decisions.

⸻

If you later want to add:
	•	cooldown rules
	•	monthly capital caps
	•	SPY sell/trim logic
	•	email or Slack notifications

…the system is intentionally designed to be extended cleanly.
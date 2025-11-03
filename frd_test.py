import pandas as pd
import numpy as np
from fraud_engine import FraudEngine

# Step 1: Read CSV
df = pd.read_csv("fraudulent_transactions.csv")

# Step 2: Normalize column names
df.columns = [c.strip().lower() for c in df.columns]

# Step 3: Rename `date` → `timestamp`
if "date" in df.columns:
    df = df.rename(columns={"date": "timestamp"})

# Step 4: Parse timestamps safely
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

# Step 5: Drop any invalid or missing dates
invalid_dates = df["timestamp"].isna().sum()
if invalid_dates > 0:
    print(f"⚠️  Found {invalid_dates} invalid date(s). Dropping them.")
    df = df.dropna(subset=["timestamp"])

# Step 6: Ensure timestamps are sorted
df = df.sort_values("timestamp").reset_index(drop=True)

# Step 7: Run your fraud detection engine
engine = FraudEngine(df)
flags = engine.detect_fraud()

# Step 8: Display results
for f in flags:
    print(
        f"{f['transaction']['timestamp']} | "
        f"{f['transaction']['merchant']} | "
        f"Risk Score: {f['risk_score']:.1f} | "
        f"Rules: {[r['name'] for r in f['triggered_rules']]}"
    )

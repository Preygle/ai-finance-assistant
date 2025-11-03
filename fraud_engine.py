import pandas as pd
import numpy as np
from datetime import timedelta


class FraudEngine:
    def __init__(self, user_transactions):
        """
        user_transactions: list of dicts or a DataFrame with (at least)
         - date or timestamp (ISO string)
         - amount (string or number, may contain ₹,+, commas)
         - merchant
         - category
         - transaction_type OR 'direction' (optional) : "credit" or "debit"
         - source (csv/plaid) optional
        """
        if isinstance(user_transactions, pd.DataFrame):
            self.df = user_transactions.copy()
        else:
            self.df = pd.DataFrame(user_transactions)
        self._preprocess_data()

    def _preprocess_data(self):
        # Parse timestamp
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        elif 'date' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['date'])
        else:
            raise ValueError("No date/timestamp column found.")

        # Clean amount strings -> numeric
        def parse_amount(x):
            if pd.isna(x):
                return np.nan
            s = str(x).replace('₹', '').replace(',', '').strip()
            # keep leading + or - if present
            s = s.replace('+', '')
            try:
                return float(s)
            except:
                # fallback: extract digits
                import re
                m = re.search(r'-?\d+(\.\d+)?', s)
                return float(m.group(0)) if m else np.nan

        self.df['amount_raw'] = self.df['amount']
        self.df['amount'] = self.df['amount'].apply(parse_amount).astype(float)

        # Determine sign/direction:
        # Prefer explicit transaction_type/direction if present
        def signed_amount(row):
            amt = row['amount']
            if 'transaction_type' in row and pd.notna(row['transaction_type']):
                typ = str(row['transaction_type']).lower()
                if typ in ('credit', 'deposit', 'in'):
                    return +abs(amt)
                elif typ in ('debit', 'withdrawal', 'out'):
                    return -abs(amt)
            if 'direction' in row and pd.notna(row['direction']):
                d = str(row['direction']).lower()
                if d in ('credit', 'in'):
                    return +abs(amt)
                else:
                    return -abs(amt)
            # fallback heuristic: if amount string had leading '-' treat negative else assume debit as negative
            s_raw = str(row['amount_raw'])
            if s_raw.strip().startswith('-'):
                return float(row['amount'])
            # assume CSV shows debits as positive — adapt if your data is opposite
            # Here we will treat "debit" semantics: positive amounts are debits -> negative in signed_amount
            # If you'd rather use positive for debits, invert this logic
            return -abs(amt)

        self.df['amount_signed'] = self.df.apply(signed_amount, axis=1)

        # sort
        self.df = self.df.sort_values(by='timestamp').reset_index(drop=True)

        # set timestamp index for rolling time windows
        self.df = self.df.set_index('timestamp')

        # rolling / window features (time-based)
        # 7-day and 14-day rolling mean up to each transaction
        self.df['rolling_avg_7d'] = self.df['amount_signed'].rolling(
            '7D').mean()
        self.df['rolling_std_7d'] = self.df['amount_signed'].rolling(
            '7D').std()
        self.df['rolling_avg_14d'] = self.df['amount_signed'].rolling(
            '14D').mean()

        # txn counts in windows (vectorized)
        # For counts we compute a rolling count over 1h, 24h and 2m windows by using resample + rolling,
        # but an easier approach is to compute via searchsorted for index values
        timestamps = self.df.index.values

        # helper to compute counts quickly
        def counts_within(window_timedelta):
            # returns series of counts for each index row (inclusive)
            import numpy as _np
            ts = _np.array(timestamps, dtype='datetime64[ns]')
            counts = []
            for i, t in enumerate(ts):
                start = t - _np.timedelta64(window_timedelta.seconds,
                                            's') if window_timedelta.days == 0 else t - _np.timedelta64(window_timedelta, 's')
                # fallback use boolean slice (simple and fine for <= 100k rows)
                # simpler: use mask
                mask = (ts > (t - window_timedelta)) & (ts <= t)
                counts.append(int(mask.sum()))
            return pd.Series(counts, index=self.df.index)

        # For simplicity and reliability on small datasets, use boolean masks:
        self.df['txn_count_1h'] = [int(self.df.loc[(self.df.index > (
            t - timedelta(hours=1))) & (self.df.index <= t)].shape[0]) for t in self.df.index]
        self.df['txn_count_24h'] = [int(self.df.loc[(self.df.index > (
            t - timedelta(days=1))) & (self.df.index <= t)].shape[0]) for t in self.df.index]
        self.df['txn_count_2m'] = [int(self.df.loc[(self.df.index > (
            t - timedelta(minutes=2))) & (self.df.index <= t)].shape[0]) for t in self.df.index]

        # merchant first seen relative to user
        self.df['merchant_first_seen'] = ~self.df['merchant'].duplicated(
            keep='first')

        # ratio to 7-day avg (avoid div zero)
        self.df['ratio_to_7d_avg'] = self.df['amount_signed'].abs(
        ) / (self.df['rolling_avg_7d'].abs().replace(0, np.nan) + 1e-9)

        # reset index to keep later templating simple
        self.df = self.df.reset_index()

    # ---------- rule implementations (use per-row features) ----------
    def detect_fraud(self):
        fraud_flags = []
        # iterate rows (ok for moderate sizes); rules are vectorized where possible but keep logic per-row
        for idx, row in self.df.iterrows():
            triggered_rules = []
            # pass df and idx for windowed checks
            r = self._apply_rules(row, idx)
            triggered_rules.extend(r)

            total_weight = sum(
                [r['weight'] for r in triggered_rules]) if triggered_rules else 0
            # simpler scoring: cap at 10
            risk_score = min(10, total_weight)

            fraud_flags.append({
                'transaction': row.to_dict(),
                'triggered_rules': triggered_rules,
                'risk_score': float(risk_score)
            })
        return fraud_flags

    def _apply_rules(self, row, idx):
        rules = []

        # convenience helpers
        amt = row['amount_signed']
        abs_amt = abs(amt)
        # subset of transactions up to current time (exclusive of future)
        current_time = row['timestamp']
        past_window_7d = self.df[(self.df['timestamp'] > current_time -
                                  timedelta(days=7)) & (self.df['timestamp'] <= current_time)]
        past_window_14d = self.df[(self.df['timestamp'] > current_time -
                                   timedelta(days=14)) & (self.df['timestamp'] <= current_time)]

        # ---------- High Value Outlier ----------
        user_avg = self.df['amount_signed'].abs().mean()
        user_std = self.df['amount_signed'].abs().std()
        if not np.isnan(user_avg) and (abs_amt > user_avg + 3 * (user_std if not np.isnan(user_std) else 0) or abs_amt > 50000):
            rules.append({'name': 'High-Value Outlier', 'weight': 5,
                         'reason': f"Amount ₹{abs_amt:.2f} >> user avg ₹{user_avg:.2f}"})

        # ---------- Relative Spike vs 14d behavior ----------
        if len(past_window_14d) >= 5:
            avg_14d = past_window_14d['amount_signed'].abs().mean()
            if avg_14d > 0 and abs_amt > 5 * avg_14d:
                rules.append({'name': 'Relative Spike vs Recent Behavior', 'weight': 4,
                             'reason': f"₹{abs_amt:.2f} > 5x 14d avg ₹{avg_14d:.2f}"})

        # ---------- New Merchant (avoid firing if too little history) ----------
        # consider merchant new if merchant_first_seen True and we have at least 20 transactions history
        if row['merchant_first_seen'] and len(self.df) >= 20:
            rules.append({'name': 'New Merchant', 'weight': 1,
                         'reason': f"First transaction with merchant '{row.get('merchant')}'"})

        # ---------- Unusual Category ----------
        if 'category' in row and pd.notna(row['category']):
            cat = row['category']
            total_cat_count = self.df[self.df['category'] == cat].shape[0]
            if len(self.df) >= 20 and total_cat_count / max(1, len(self.df)) < 0.05:
                rules.append({'name': 'Unusual Category for User', 'weight': 2,
                             'reason': f"Category '{cat}' is <5% of user history."})

        # ---------- Rapid-Fire (2m window) ----------
        recent_2m = self.df[(self.df['timestamp'] > current_time -
                             timedelta(minutes=2)) & (self.df['timestamp'] <= current_time)]
        if recent_2m.shape[0] > 5 and (recent_2m['amount_signed'].abs() > 1000).all():
            rules.append({'name': 'High-Frequency Transactions', 'weight': 4,
                         'reason': f"{recent_2m.shape[0]} txns > ₹1000 in last 2 mins"})

        # ---------- Duplicate/Near-Duplicate within 2 minutes (lookback) ----------
        lookback = self.df[(self.df['timestamp'] >= current_time -
                            timedelta(minutes=2)) & (self.df['timestamp'] < current_time)]
        # merchant match and amount within epsilon
        dup_mask = (lookback['merchant'] == row['merchant']) & (
            np.isclose(lookback['amount_signed'], row['amount_signed'], atol=1.0))
        if dup_mask.any():
            rules.append({'name': 'Duplicate / Near-Duplicate', 'weight': 3,
                         'reason': 'Duplicate transaction detected within 2 minutes.'})

        # ---------- Odd Hour (midnight-4am) but only for sizeable transactions ----------
        median_amt = self.df['amount_signed'].abs().median()
        if row['timestamp'].hour in [0, 1, 2, 3, 4] and abs_amt > max(3 * (median_amt if not np.isnan(median_amt) else 0), 1000):
            rules.append({'name': 'Odd-Hour Transaction', 'weight': 2,
                         'reason': 'Transaction at midnight-4am with high amount.'})

        # ---------- Time-window amount threshold (24h) ----------
        window_24h = self.df[(self.df['timestamp'] > current_time -
                              timedelta(days=1)) & (self.df['timestamp'] <= current_time)]
        sum_24h = window_24h['amount_signed'].abs().sum()
        if len(self.df) >= 10 and sum_24h > 5 * self.df['amount_signed'].abs().mean() * max(1, window_24h.shape[0]):
            rules.append({'name': 'Time-Window Amount Threshold', 'weight': 4,
                         'reason': f"Spent ₹{sum_24h:.2f} in prior 24h."})

        # ---------- Round Number Testing ----------
        if abs_amt > 5000 and (abs_amt % 500) == 0:
            rules.append({'name': 'Round-number Testing',
                         'weight': 2, 'reason': 'Round-number > ₹5000.'})

        # ---------- Category-value correlation ----------
        if 'category' in row:
            cat_df = self.df[self.df['category'] == row['category']]
            if cat_df.shape[0] > 10:
                p99 = cat_df['amount_signed'].abs().quantile(0.99)
                if abs_amt > p99:
                    rules.append({'name': 'Category-Value Correlation', 'weight': 2,
                                 'reason': f"Amount in 99th percentile for category {row['category']}."})

        # ---------- Round-trip / Rapid refund detection ----------
        # look for immediate refund/credit related patterns in prior 30 minutes
        prior_30m = self.df[(self.df['timestamp'] >= current_time -
                             timedelta(minutes=30)) & (self.df['timestamp'] < current_time)]
        # round-trip: prior credit ~ current debit (or vice versa)
        if amt < 0 and not prior_30m.empty:
            possible = prior_30m[(prior_30m['amount_signed'] > 0) & (
                np.isclose(prior_30m['amount_signed'], abs_amt, atol=100))]
            if not possible.empty:
                rules.append({'name': 'Round-Trip Transaction', 'weight': 3,
                             'reason': 'Large credit followed by nearly equal debit within 30 minutes.'})
        if amt > 0 and not prior_30m.empty:
            possible = prior_30m[(prior_30m['amount_signed'] < 0) & (
                np.isclose(abs(possible['amount_signed']), amt, atol=1))]
            if not possible.empty:
                rules.append({'name': 'Rapid Refund / Reversal', 'weight': 3,
                             'reason': 'Refund within 1 hour of original txn.'})

        # ---------- Historical risk amplifier: look at previous flags (simplified) ----------
        # This requires access to prior risk flags; skip inside this stateless function or pass history externally.
        # We'll skip here to keep stateless.

        return rules

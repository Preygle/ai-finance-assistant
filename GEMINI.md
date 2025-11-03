csrf_token() is wrong format, always go for csrf_token

Make sure before applying any changes, there are no inconsistencies in styling
1. Authentication & Session (FR1)

User Access:

Register/login via web app.

Passwords hashed with bcrypt.

Sessions:

JWT tokens (30-min timeout, refreshed on activity).

CSRF protection for form submissions.

Re-auth:

Auto-expire after inactivity → user must re-login.

2. Transaction Ingestion (FR2)

CSV Upload:

Validate schema: (date, merchant, amount, category).

Preview → confirm → process (but not stored).

Bank API (optional):

OAuth with Plaid/Yodlee/OpenBanking.

Scheduled sync into normalized schema (in-memory / transient).

⚠️ Note: Transactions are used immediately for categorization, fraud detection, budgeting — then discarded after blockchain logging.

3. Data Persistence (DB Layer)

Stores only:

ML models (categorization, forecasting, fraud detection).

Blockchain proofs (txn hash + Ethereum txHash).

No raw transaction data stored.

4. AI Categorization (FR3)

Pipeline:

Text preprocessing: regex cleaning + merchant normalization.

Feature extraction: TF-IDF.

Model: Logistic Regression / Random Forest.

Output:

Category + confidence score.

If low confidence → flagged to user for manual confirmation (not stored).

5. Fraud Detection (FR3 Extension)

Techniques:

Isolation Forest or Autoencoder.

Detection targets:

Abnormally high spend.

New merchants.

Frequency anomalies.

Outcome:

Suspicious transactions flagged on-the-fly.

6. Budgeting & Suggestions (FR4)

Budget Input: User sets category limits.

Processing:

In-memory spend aggregation (pandas/SQL window functions).

Time-series forecasting (Prophet/ARIMA) for spend prediction.

Suggestions:

Rule-based + ML-driven recommendations.

Results shown to user immediately (not persisted).

7. Blockchain Integrity Logging (FR5)

On transaction finalization:

Compute SHA-256 hash (txnID + date + amount + merchant + category).

Submit to Ethereum smart contract (Web3.py).

Receive txHash → stored in DB.

Privacy preserved: Only the hash is on-chain + in DB.

Ensures tamper-proof audit trail without storing transaction data.

8. Authenticity Verification (FR5)

On demand:

Recompute transaction hash locally.

Fetch stored proof (on-chain + DB).

Compare:

Match → Verified (with blockchain link).

Mismatch → Integrity Error.


MAKE SURE YOU ARE NOT  COMPLETLKY CHANGING THE OLD FUNCTIONLAITIES BY COMPLETLY OVERWRITING THE NEW ONES. BASED ONT HE WORKFLOW I PROVIDED, I WILL BE GIVING YOU VARIOUS ELEMNTS OF MY PROJECT TO IMPLEMENT ONE A TIME, SO GENERATE ACCORDINGLY.
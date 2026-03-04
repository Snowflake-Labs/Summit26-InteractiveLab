# Summit 2026 Interactive Lab
## Real-Time Arcade Score Streaming with Snowpipe Streaming + Interactive Tables

Stream thousands of arcade game scores from across the globe into Snowflake
in real time, materialise them into an **Interactive Table**, and query with an
**Interactive Warehouse** — experiencing sub-second latency at scale.

---

## Architecture

```
 Python Generator
 ─────────────────
  Arcade Score Events          Snowpipe Streaming SDK
  (50 rows/sec)        ──────► StreamingIngestClient
  20 games                      ├─ Channel 0
  45 cities                     ├─ Channel 1      ──► ARCADE_SCORES
  500 players                   ├─ Channel 2          (Interactive Table)
                                └─ Channel 3          CLUSTER BY (GAME_ENDED_AT)
                                                            │
                                                            ▼
                                                     SUMMIT_INT_WH
                                                  (Interactive Warehouse, XS)
                                                  Always-on · ms-latency queries
```

Snowpipe Streaming uses the **channel API**, not SQL DML, so it writes rows
directly into the Interactive Table — no intermediate landing table needed.

### Warehouse design

| Warehouse | Type | Purpose |
|---|---|---|
| `SUMMIT_TRAD_WH` | Standard XS | Traditional warehouse for comparison benchmarks |
| `SUMMIT_INT_WH` | **Interactive XS** | All lab queries; always-on for instant low-latency responses |

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.9 – 3.13 |
| Snowflake account | In a [supported region](https://docs.snowflake.com/en/user-guide/interactive#region-availability) for Interactive Tables/Warehouses |
| Role | ACCOUNTADMIN (or CREATE WAREHOUSE + CREATE DATABASE privileges) |
| OpenSSL | For RSA key-pair generation |
| JMeter | For concurrency testing (optional) |

### Supported regions (Interactive Tables GA)

AWS: `us-east-1`, `us-west-2`, `us-east-2`, `ca-central-1`, `ap-northeast-1`, `ap-southeast-2`, `eu-central-1`, `eu-west-1`, `eu-west-2`
GCP: `us-central1`, `us-east4`, `europe-west2/3/4`, `australia-southeast2`
Azure: All Azure regions

---

## Lab Setup

### 1 — Run the Snowflake setup script

Open **`sql/01_setup.sql`** in Snowsight and run it using a **standard warehouse** session.

### 2 — Register the RSA public key for the service user

```bash
bash sql/02_service_auth.sh
```

Generates `rsa_key.p8` / `rsa_key.pub` if they don't exist, then prints the `ALTER USER` statement. Paste it into Snowsight and run it as `ACCOUNTADMIN`.

> `rsa_key.p8` is in `.gitignore` and must never be committed.

The script provisions (in order):
1. Service user + role + RSA auth policy
2. `ARCADE_DB` database + `SUMMIT_TRAD_WH` standard warehouse
3. `ARCADE_SCORES` **Interactive Table** (`CLUSTER BY (GAME_ENDED_AT)`, initially empty)
4. `SUMMIT_INT_WH` **Interactive Warehouse** (XS, resumed automatically)
5. Grants for streaming role and lab-reader role

### 3 — Create `profile.json`

```bash
cp profile.json.example profile.json
```

Edit with your account identifier (the part before `.snowflakecomputing.com`):

```json
{
    "user":             "ARCADE_STREAMING_USER",
    "account":          "xy12345",
    "url":              "https://xy12345.snowflakecomputing.com:443",
    "private_key_file": "rsa_key.p8",
    "role":             "ARCADE_STREAMING_ROLE"
}
```

### 4 — Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5 — Start the arcade streamer

```bash
cd python
python arcade_streamer.py
```

```
============================================================
 Summit 2026 – Arcade Scores Snowpipe Streamer
============================================================
  Account   : xy12345
  Database  : ARCADE_DB.PUBLIC
  Pipe      : ARCADE_SCORES-STREAMING
  Channels  : 4
  Target    : 50 rows/sec
============================================================

  [14:22:05]  rows:      250  |  50.0 rows/sec  |  errors: 0  |  elapsed:    5s
  [14:22:10]  rows:      500  |  50.0 rows/sec  |  errors: 0  |  elapsed:   10s
```

### 6 — Wait for cache warm-up

The `SUMMIT_INT_WH` Interactive Warehouse starts warming its local SSD cache
as soon as it resumes. Wait **2–3 minutes** after the streamer starts before
running interactive queries — the first few queries after
resume will be slower while the cache populates.

---

## Lab Exercises

Open **`sql/03_lab_queries.sql`** in Snowsight while the streamer is running.

> **Tip:** Use `SUMMIT_INT_WH` for exercises marked ⚡ and `SUMMIT_TRAD_WH`
> for exercises marked 🔧. Each `USE WAREHOUSE` statement is already in the
> query file.

### ⚡ Exercise 1 — Pipeline freshness

Watch row counts grow in real time and measure live ingest throughput (rows/sec).

### ⚡ Exercise 2 — End-to-end latency

Each row carries `GAME_ENDED_AT` (when the game ended on the client) and
`INGEST_AT` (when the row was submitted to the SDK). The P50/P90/P99
millisecond breakdown shows how quickly Snowpipe Streaming moves data from
the edge into a queryable Interactive Table.

### ⚡ Exercise 3 — Global leaderboard (Interactive Warehouse)

Top 20 scores of the last 24 hours. Notice how the `CLUSTER BY (GAME_ENDED_AT)`
clustering key allows the Interactive Warehouse to skip irrelevant partitions
and return results in milliseconds.

### ⚡ Exercise 4 — Per-game top 5 (window function)

Uses `QUALIFY ROW_NUMBER()` scoped to the last hour. Stays well within the
interactive warehouse 5-second query limit.

### ⚡ Exercise 5 — Country heat map

Which countries are playing most right now? Japan and South Korea should
dominate — the data generator weights cities by real gaming culture.

### ⚡ Exercise 6 — Game popularity

Pac-Man and Tetris lead; Joust and Tron are rare finds.

### ⚡ Exercise 7 — Platform breakdown

Arcade cabinets are most common for classic titles; Tetris goes mobile.

### ⚡ Exercise 8 — Live score feed

Re-run this every few seconds. Each execution hits data that arrived within the
last 5 minutes — demonstrating end-to-end freshness from generator to
Interactive Table.

### 🔧 Exercise 9 — Achievement rarity

Shows how rare badges ("Pacifist", "Triple Threat") require specific skill tier
+ game mode + score conditions — rarely seen in thousands of rows.

### ⚡ Exercise 10 — Interactive vs Traditional warehouse speed comparison

Run the identical GROUP BY on both warehouses and compare in Query History.
The Interactive Warehouse wins at high concurrency thanks to local SSD caching
and pre-computed index metadata.

### ⚡ Exercise 11 — Concurrency demo (JMeter load test)

Use the JMeter load testing tool to simulate 50 concurrent users hitting the
warehouse. See [Concurrency Testing with JMeter](#concurrency-testing-with-jmeter) below.

### ⚡ Bonus A — Time Travel on an Interactive Table

```sql
SELECT COUNT(*) FROM ARCADE_SCORES AT(OFFSET => -300);
```

Interactive Tables support Time Travel even with streaming ingestion.

---

## Streamlit Dashboard (Optional)

After completing the lab exercises, deploy a live dashboard against the same `ARCADE_SCORES` data.

See **[STREAMLIT.md](STREAMLIT.md)** for full setup instructions — install the Snowflake CLI and Cortex CLI, generate a PAT via `sql/04_generate_pat.sql`, and deploy the dashboard.

---

## Concurrency Testing with JMeter (Optional)

The `jmeter/` directory contains a load test plan that simulates concurrent users
querying the warehouse. This demonstrates the Interactive Warehouse's ability
to handle high concurrency without queuing.

### Install JMeter

**macOS:**
```bash
brew install jmeter
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install jmeter
```

**Windows or manual install:**
Download from https://jmeter.apache.org/download_jmeter.cgi

### Download Snowflake JDBC driver

Download the driver and install it to JMeter's lib directory:

```bash
cd jmeter

# Download the driver
curl -L -o snowflake-jdbc.jar https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.16.1/snowflake-jdbc-3.16.1.jar

# Copy to JMeter lib directory (macOS with Homebrew)
cp snowflake-jdbc.jar $(brew --prefix)/Cellar/jmeter/*/libexec/lib/

# Or for manual JMeter installation
# cp snowflake-jdbc.jar $JMETER_HOME/lib/
```

The test runner script will attempt to install the driver automatically, but manual installation ensures it works correctly.

### Run the concurrency test

**Set up environment variables:**

```bash
export SNOWFLAKE_ACCOUNT=xy12345
export SNOWFLAKE_PRIVATE_KEY_FILE=/path/to/rsa_key.p8

# Optional - defaults to ARCADE_STREAMING_USER from setup
# export SNOWFLAKE_USER=ARCADE_STREAMING_USER
```

> **Note:** The test uses the `ARCADE_STREAMING_USER` created in the setup script with RSA key authentication.

**Example for this lab:**

```bash
export SNOWFLAKE_ACCOUNT=SFPRODUCTSTRATEGY-SC_ZBMCPJGOXU
export SNOWFLAKE_PRIVATE_KEY_FILE=/Users/bculberson/projects/Summit26-InteractiveLab/rsa_key.p8
```

**Test Interactive Warehouse (SUMMIT_INT_WH):**

```bash
cd jmeter
./run_concurrency_test.sh SUMMIT_INT_WH
```

**Test Traditional Warehouse (SUMMIT_TRAD_WH):**

```bash
cd jmeter
./run_concurrency_test.sh SUMMIT_TRAD_WH
```

The script will:
1. Run 50 concurrent threads for 30 seconds
2. Execute 5 different queries randomly
3. Generate an HTML report in `results_WAREHOUSE_TIMESTAMP/`
4. Display summary statistics

**View the HTML report:**
```bash
open results_SUMMIT_INT_WH_*/index.html
```

### Expected results

| Metric | SUMMIT_INT_WH (Interactive) | SUMMIT_TRAD_WH (Traditional) |
|---|---|---|
| Throughput | ~60-80 queries/sec | ~20-25 queries/sec |
| Avg Latency | ~200-300 ms | ~1000-1200 ms |
| Min Latency | ~100-150 ms | ~200-300 ms |
| Concurrency | Handles 50 concurrent users smoothly | Queue delays with high concurrency |

The Interactive Warehouse achieves **3-4x higher throughput and 4-5x lower latency** because
it uses a shared SSD cache and pre-computed indexes optimized for the
associated Interactive Tables.

### Customize the test

Edit `jmeter/concurrency_test.jmx` to adjust:
- Thread count: `ThreadGroup.num_threads` (default 50)
- Test duration: `ThreadGroup.duration` (default 30 seconds)
- Queries: Add or modify `JDBCSampler` elements

### Troubleshooting

**Connection errors:**
- Verify RSA key path is correct
- Ensure `ARCADE_STREAMING_USER` has been created (run `sql/01_setup.sql`)
- Confirm RSA public key is set on the user (see setup step 1)

**JDBC driver not found:**
- Download the driver: `cd jmeter && curl -L -o snowflake-jdbc.jar https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.16.1/snowflake-jdbc-3.16.1.jar`

**No data returned:**
- Ensure the arcade streamer is running (`python/arcade_streamer.py`)
- Verify data exists: `SELECT COUNT(*) FROM ARCADE_DB.PUBLIC.ARCADE_SCORES`

---

## Interactive Warehouse Key Facts

| Property | Value |
|---|---|
| Query timeout (SELECT) | 5 seconds (cannot be increased) |
| Auto-suspend | No — runs continuously |
| Cache warm-up | Required after resume (2–5 min for small tables) |
| Compatible table types | Interactive Tables only |
| Sizing guidance | XS = working set < 500 GB |
| Billing | Minimum 1 hour; per-second after that |

---

## Streamer Options

```bash
# Default: 50 rows/sec, 4 channels, runs until Ctrl-C
python arcade_streamer.py

# High-throughput demo (200 rows/sec, 8 channels)
python arcade_streamer.py --rate 200 --channels 8

# Insert exactly 10,000 rows then stop
python arcade_streamer.py --rows 10000

# Preview generated data without connecting to Snowflake
python arcade_streamer.py --dry-run --rows 5
```

---

## Data Model

### `ARCADE_SCORES` (Interactive Table)


| Column | Type | Notes |
|---|---|---|
| `SCORE_ID` | VARCHAR(36) | Session UUID |
| `PLAYER_ID` | VARCHAR(36) | Stable player UUID (500-player pool) |
| `PLAYER_NAME` | VARCHAR(64) | Display name |
| `PLAYER_COUNTRY` / `PLAYER_CITY` | VARCHAR | Geographic origin |
| `LATITUDE` / `LONGITUDE` | FLOAT | GPS coordinates |
| `GAME_NAME` | VARCHAR(64) | One of 20 classic arcade titles |
| `GAME_MODE` | VARCHAR(32) | classic (50%) · tournament · co-op · survival · speed-run |
| `PLATFORM` | VARCHAR(32) | arcade · console · mobile · pc (game-specific weights) |
| `SCORE` | NUMBER(12,0) | Power-law distributed by skill tier |
| `LEVEL_REACHED` | NUMBER(4,0) | Correlated with score |
| `DURATION_SECONDS` | NUMBER(6,0) | Correlated with level |
| `LIVES_REMAINING` | NUMBER(2,0) | Inversely correlated with score |
| `ACCURACY_PCT` | FLOAT | Nullable; correlated with skill tier |
| `ACHIEVEMENT` | VARCHAR(64) | Rare contextual badge (nullable) |
| `GAME_ENDED_AT` | TIMESTAMP_NTZ | Client-side end time **(clustering key)** |
| `INGEST_AT` | TIMESTAMP_NTZ | Snowflake commit timestamp |

---

## Cleanup

Open **`sql/05_cleanup.sql`** in Snowsight and run it.

Drops both warehouses, the database (and all tables/pipes), and the service user.

---

## File Structure

```
Summit26-InteractiveLab/
├── README.md
├── requirements.txt                 Snowpipe Streaming SDK dep
├── profile.json.example
├── .gitignore
├── sql/
│   ├── 01_setup.sql                 Full Snowflake provisioning
│   ├── 02_service_auth.sh           Outputs ALTER USER RSA key SQL
│   ├── 03_lab_queries.sql           11 exercises + bonus queries
│   ├── 04_generate_pat.sql          Generate PAT + snow connection add command
│   └── 05_cleanup.sql               Teardown
├── python/
│   ├── config.py                    Game catalogue, cities, skill tiers
│   ├── generator.py                 Realistic score generator
│   └── arcade_streamer.py           Snowpipe Streaming SDK ingest
└── jmeter/
    ├── concurrency_test.jmx         JMeter test plan
    └── run_concurrency_test.sh      Test runner script
```

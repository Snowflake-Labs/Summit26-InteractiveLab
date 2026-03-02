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
                                                     SUMMIT_LAB_WH
                                                  (Interactive Warehouse, XS)
                                                  Always-on · ms-latency queries
```

Snowpipe Streaming uses the **channel API**, not SQL DML, so it writes rows
directly into the Interactive Table — no intermediate landing table needed.

### Warehouse design

| Warehouse | Type | Purpose |
|---|---|---|
| `SUMMIT_SETUP_WH` | Standard XS | Setup script only; Snowpipe Streaming does not consume warehouse credits |
| `SUMMIT_LAB_WH` | **Interactive XS** | All lab queries; always-on for instant low-latency responses |

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.9 – 3.13 |
| Snowflake account | In a [supported region](https://docs.snowflake.com/en/user-guide/interactive#region-availability) for Interactive Tables/Warehouses |
| Role | ACCOUNTADMIN (or CREATE WAREHOUSE + CREATE DATABASE privileges) |
| OpenSSL | For RSA key-pair generation |

### Supported regions (Interactive Tables GA)

AWS: `us-east-1`, `us-west-2`, `us-east-2`, `ca-central-1`, `ap-northeast-1`, `ap-southeast-2`, `eu-central-1`, `eu-west-1`, `eu-west-2`
GCP: `us-central1`, `us-east4`, `europe-west2/3/4`, `australia-southeast2`
Azure: All Azure regions

---

## Lab Setup (Instructor)

### 1 — Generate RSA key pair

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Format for ALTER USER
PUBK=$(grep -v 'KEY-' rsa_key.pub | tr -d '\n')
echo "ALTER USER ARCADE_STREAMING_USER SET RSA_PUBLIC_KEY='$PUBK';"
```

> `rsa_key.p8` is in `.gitignore` and must never be committed.

### 2 — Run the Snowflake setup script

Execute **`sql/01_setup.sql`** using a **standard warehouse** session
(Snowsight, SnowSQL, or Snowflake CLI):

```bash
snow sql -f sql/01_setup.sql --connection <your-connection>
```

Then immediately paste and run the `ALTER USER` statement from Step 1.

The script provisions (in order):
1. Service user + role + RSA auth policy
2. `ARCADE_DB` database + `SUMMIT_SETUP_WH` standard warehouse (setup only)
3. `ARCADE_SCORES` **Interactive Table** (`CLUSTER BY (GAME_ENDED_AT)`, initially empty)
4. `ARCADE_SCORES_PIPE` streaming pipe
5. `SUMMIT_LAB_WH` **Interactive Warehouse** (XS, resumed automatically)
6. Grants for streaming role and lab-reader role

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
  Pipe      : ARCADE_SCORES_PIPE  →  ARCADE_SCORES_RAW
  Channels  : 4
  Target    : 50 rows/sec
============================================================

  [14:22:05]  rows:      250  |  50.0 rows/sec  |  errors: 0  |  elapsed:    5s
  [14:22:10]  rows:      500  |  50.0 rows/sec  |  errors: 0  |  elapsed:   10s
```

### 6 — Let the Interactive Table warm up

The `SUMMIT_LAB_WH` Interactive Warehouse starts warming its local SSD cache
as soon as it resumes. Wait **2–3 minutes** after the streamer starts before
asking attendees to run interactive queries — the first few queries after
resume will be slower while the cache populates.

---

## Lab Exercises (Attendees)

Open **`sql/02_lab_queries.sql`** in Snowsight while the streamer is running.

> **Tip:** Use `SUMMIT_LAB_WH` for exercises marked ⚡ and `SUMMIT_SETUP_WH`
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

### ⚡ Exercise 10 — Interactive vs Standard warehouse speed comparison

Run the identical GROUP BY on both warehouses and compare in Query History.
The Interactive Warehouse wins at high concurrency thanks to local SSD caching
and pre-computed index metadata.

### ⚡ Exercise 11 — Interactive vs Standard warehouse speed comparison

Run the identical GROUP BY query on both warehouses and compare execution times
in Query History. The Interactive Warehouse wins at high concurrency.

### ⚡ Exercise 12 — Concurrency demo

Open the same worksheet in multiple browser tabs simultaneously and hit Run in
all of them at once. The Interactive Warehouse serves them all without queuing.

### ⚡ Bonus A — Time Travel on an Interactive Table

```sql
SELECT COUNT(*) FROM ARCADE_SCORES AT(OFFSET => -300);
```

Interactive Tables support Time Travel even with streaming ingestion.

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

```bash
snow sql -f sql/03_cleanup.sql --connection <your-connection>
```

Drops both warehouses, the database (and all tables/pipe), and the service user.

---

## File Structure

```
Summit26-InteractiveLab/
├── README.md
├── requirements.txt
├── profile.json.example
├── .gitignore
├── sql/
│   ├── 01_setup.sql        Full Snowflake provisioning (raw table → interactive table → interactive warehouse)
│   ├── 02_lab_queries.sql  12 exercises + 3 bonus queries, warehouse-annotated
│   └── 03_cleanup.sql      Teardown
└── python/
    ├── config.py           Game catalogue, cities, skill tiers, tuning knobs
    ├── generator.py        Realistic score generator (tier-based, weighted distributions)
    └── arcade_streamer.py  Snowpipe Streaming SDK ingest (multi-channel, threaded)
```

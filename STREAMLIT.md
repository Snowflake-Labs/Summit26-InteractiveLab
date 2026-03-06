# Streamlit Dashboard Setup Guide

## Prerequisites

### 1. Install Snowflake CLI

```bash
# macOS (Homebrew)
brew install snowflake-cli

# or pip (into your active venv)
pip install snowflake-cli
```

Verify:
```bash
snow --version
```

### 2. Install Cortex CLI

**macOS/Linux:**
```bash
curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh
```

**Windows (PowerShell):**
```powershell
iwr https://ai.snowflake.com/static/cc-scripts/install.ps1 -useb | iex
```

Verify:
```bash
cortex --version
```

### 3. Generate a PAT for the Cortex CLI and register the snow CLI connection

The Cortex CLI uses `snow` under the hood to deploy the Streamlit app. `snow` requires a **Programmatic Access Token (PAT)** — this is only needed for Cortex CLI deployment and is separate from the RSA key pair used by the Python streamer.

Open **`sql/04_generate_pat.sql`** in Snowsight and run it as the user who will deploy the dashboard.

Copy the `SETUP_COMMAND` result and run it in your terminal — it registers the `snow` connection in one step.

Verify:
```bash
snow connection test
```

---

## Generate the Streamlit Dashboard with Cortex

Run Cortex from the project root with all tool calls enabled so it can read files, write the app, and deploy it:

```bash
cortex --dangerously-allow-all-tool-calls
```

Then send the following prompt:

Use skill `developing-with-streamlit` to create a real-time arcade scores dashboard with the following requirements:

**Data Source:**
 - Table: `ARCADE_DB.PUBLIC.ARCADE_SCORES`
 - Warehouse: `SUMMIT_INT_WH` (Interactive Warehouse)
 - Connection: Use default connection with programmatic token
 - Columns: All columns and tables are uppercase in Snowflake

 **Deployment:**
 - Deploy as Streamlit in Snowflake named `ARCADE_SCORES_DASHBOARD` in `ARCADE_DB.PUBLIC`
 - Use compute pool `ARCADE_REPORTING_POOL` (already provisioned)
 - Add external access integration and network rule for PyPI access

 **Dashboard Features:**
 1. **Global Leaderboard** - Highest scores in last 24 hours
 2. **Top Players by Game** - Top 5 players per game in last hour
 3. **Geographic Heatmap** - Country-level plays over last hour
 4. **Game Popularity** - Session and player counts by game (last hour)
 5. **Platform Breakdown** - Session and player counts by platform (last hour)
 6. **Recent Activity** - Last 30 scores
 7. **Achievements** - All earned achievements (where ACHIEVEMENT IS NOT NULL) with counts
 8. **Active Cities** - Most active cities in last minute
 9. **Pipeline Health** - Operational metrics page with:
    - Total games played (all time)
    - Current data freshness in decimal seconds: `DATEDIFF('millisecond', MAX(GAME_ENDED_AT), CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ) / 1000.0` — how many seconds ago was the most recent row committed
    - Freshness over last hour as a time-series line chart: freshness per minute bucketed with `DATE_TRUNC('minute', GAME_ENDED_AT)`
    - Rows/sec over last hour: count of rows per minute bucket (filtered by `GAME_ENDED_AT`) divided by 60, shown as a time-series line chart
# Streamlit Dashboard Setup Guide

## Prerequisites

### 1. Install Cortex CLI

Download and install the Cortex CLI for your platform:

**macOS/Linux:**
```bash
curl -sL https://sfc-cli-installer.s3.amazonaws.com/cortex/install.sh | bash
```

**Windows (PowerShell):**
```powershell
iwr https://sfc-cli-installer.s3.amazonaws.com/cortex/install.ps1 -useb | iex
```

Verify installation:
```bash
cortex --version
```

### 2. Setup Snowflake Connection

Create a default connection for programmatic token authentication:

```bash
cortex connection add default \
  --account <your-account> \
  --user <your-username> \
  --authenticator externalbrowser
```

Test the connection:
```bash
cortex connection test default
```

---

## Prompt to Generate Streamlit Dashboard

Use skill `developing-with-streamlit` to create a real-time arcade scores dashboard with the following requirements:

**Data Source:**
- Table: `ARCADE_DB.PUBLIC.ARCADE_SCORES`
- Warehouse: `SUMMIT_INT_WH` (Interactive Warehouse)
- Connection: Use default connection with programmatic token

**Deployment:**
- Deploy as Streamlit in Snowflake on compute pool
- Instance family: `CPU_X64_XS`
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
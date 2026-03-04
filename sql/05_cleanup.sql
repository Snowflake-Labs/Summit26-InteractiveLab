-- =============================================================================
-- Summit 2026 Interactive Lab: Arcade Scores Streaming
-- Cleanup / Teardown Script
--
-- WARNING: Irreversible – all data will be dropped.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Streamlit dashboard
DROP STREAMLIT IF EXISTS ARCADE_DB.PUBLIC.ARCADE_SCORES_DASHBOARD;

-- Compute pool
DROP COMPUTE POOL IF EXISTS ARCADE_REPORTING_POOL;

-- Drop the interactive warehouse first (removes its ARCADE_SCORES association)
ALTER WAREHOUSE IF EXISTS SUMMIT_INT_WH SUSPEND;
DROP WAREHOUSE   IF EXISTS SUMMIT_INT_WH;

-- Standard setup warehouse
DROP WAREHOUSE IF EXISTS SUMMIT_TRAD_WH;

-- User
DROP USER IF EXISTS ARCADE_STREAMING_USER;

-- Database (cascades to schema, interactive table, and pipes)
DROP DATABASE IF EXISTS ARCADE_DB;

-- Roles
DROP ROLE IF EXISTS ARCADE_STREAMING_ROLE;
DROP ROLE IF EXISTS ARCADE_LAB_READER;

SELECT 'Cleanup complete.' AS STATUS;

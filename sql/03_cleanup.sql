-- =============================================================================
-- Summit 2026 Interactive Lab: Arcade Scores Streaming
-- Cleanup / Teardown Script
--
-- WARNING: Irreversible – all data will be dropped.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Drop the interactive warehouse first (removes its ARCADE_SCORES association)
ALTER WAREHOUSE IF EXISTS SUMMIT_LAB_WH SUSPEND;
DROP WAREHOUSE   IF EXISTS SUMMIT_LAB_WH;

-- Standard setup warehouse
DROP WAREHOUSE IF EXISTS SUMMIT_SETUP_WH;

-- Database (cascades to schema, interactive table, and pipe)
DROP DATABASE IF EXISTS ARCADE_DB;

-- Authentication policy
ALTER USER ARCADE_STREAMING_USER UNSET AUTHENTICATION POLICY;
DROP AUTHENTICATION POLICY IF EXISTS ARCADE_KEYPAIR_POLICY;

-- Users and roles
DROP USER IF EXISTS ARCADE_STREAMING_USER;
DROP ROLE IF EXISTS ARCADE_STREAMING_ROLE;
DROP ROLE IF EXISTS ARCADE_LAB_READER;

SELECT 'Cleanup complete.' AS STATUS;

#!/usr/bin/env bash
# Generates an RSA key pair (if not already present) and prints a Snowflake
# script that registers the public key for ARCADE_STREAMING_USER and emits
# profile JSON with account and URL filled from the session.
#
# Usage (from project root):
#   bash sql/02_service_auth.sh
#
# Paste the printed SQL into Snowsight and run it as ACCOUNTADMIN.
# After it runs, copy the profile_json cell into profile.json in the project root.

set -euo pipefail

PRIVATE_KEY="rsa_key.p8"
PUBLIC_KEY="rsa_key.pub"

if [[ ! -f "$PRIVATE_KEY" ]]; then
  echo "Generating RSA key pair..." >&2
  openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out "$PRIVATE_KEY" -nocrypt
  openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" 2>/dev/null
  echo "Created $PRIVATE_KEY and $PUBLIC_KEY." >&2
fi

PUBK=$(grep -v 'KEY-' "$PUBLIC_KEY" | tr -d '\n')
PRIVATE_KEY_FULL=$(cd "$(dirname "$PRIVATE_KEY")" && pwd)/$(basename "$PRIVATE_KEY")
# Escape single quotes for embedding in a SQL string literal
PRIVATE_KEY_SQL_ESC="${PRIVATE_KEY_FULL//\'/\'\'}"

IP=$(curl -s ifconfig.me)

echo -e "\n"
echo "************************************************************"
echo "Start generated SQL.   Please run in Snowsight to complete the setup process:"
echo "************************************************************"
echo -e "\n"

cat <<SQL
-- Run as ACCOUNTADMIN in Snowsight
USE ROLE ACCOUNTADMIN;
USE DATABASE ARCADE_DB;
USE SCHEMA PUBLIC;

--Create Network Policy
ALTER USER ARCADE_STREAMING_USER UNSET NETWORK_POLICY;
DROP NETWORK POLICY IF EXISTS GH_WORKSPACE_POLICY;
CREATE OR REPLACE NETWORK RULE GH_WORKSPACE_RULE TYPE = IPV4 MODE = INGRESS VALUE_LIST = ('${IP}/24');
CREATE NETWORK POLICY GH_WORKSPACE_POLICY ALLOWED_NETWORK_RULE_LIST = ('GH_WORKSPACE_RULE');
ALTER USER ARCADE_STREAMING_USER SET NETWORK_POLICY = GH_WORKSPACE_POLICY;

-- Run as ACCOUNTADMIN in Snowsight
ALTER USER ARCADE_STREAMING_USER SET RSA_PUBLIC_KEY='${PUBK}';

-- Copy the profile_json value into profile.json (project root).
-- Replace PASTE_ACCOUNT_URL_FROM_SNOWSIGHT with the Account URL from Snowsight
-- (account selector -> View account details). Do not build a hostname from a locator.
-- https://docs.snowflake.com/en/user-guide/ui-snowsight-gs#locate-your-snowflake-account-information-in-snowsight
SELECT TO_JSON(
  OBJECT_CONSTRUCT(
    'user',             'ARCADE_STREAMING_USER',
    'url',              'PASTE_ACCOUNT_URL_FROM_SNOWSIGHT',
    'private_key_file', '${PRIVATE_KEY_SQL_ESC}',
    'role',             'ARCADE_STREAMING_ROLE'
  )
) AS profile_json;
SQL

echo -e "\n"
echo "************************************************************"
echo "End generated SQL.  Please scroll up to capture all commands."
echo "************************************************************"

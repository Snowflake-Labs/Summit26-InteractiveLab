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

cat <<SQL
-- Run as ACCOUNTADMIN in Snowsight
USE ROLE ACCOUNTADMIN;
ALTER USER ARCADE_STREAMING_USER SET RSA_PUBLIC_KEY='${PUBK}';

-- Copy the profile_json value into profile.json (project root).
WITH account_ctx AS (
  SELECT IFF(
    CURRENT_ORGANIZATION_NAME() IS NOT NULL
    AND TRIM(CURRENT_ORGANIZATION_NAME()) <> '',
    CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT(),
    CURRENT_ACCOUNT()
  ) AS account_identifier
)
SELECT TO_JSON(
  OBJECT_CONSTRUCT(
    'user',             'ARCADE_STREAMING_USER',
    'account',          a.account_identifier,
    'url',              'https://' || a.account_identifier || '.snowflakecomputing.com:443',
    'private_key_file', '${PRIVATE_KEY_SQL_ESC}',
    'role',             'ARCADE_STREAMING_ROLE'
  )
) AS profile_json
FROM account_ctx a;
SQL

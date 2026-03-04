#!/usr/bin/env bash
# Generates an RSA key pair (if not already present) and outputs the
# ALTER USER statement needed to register the public key for
# ARCADE_STREAMING_USER.
#
# Usage (from project root):
#   bash sql/02_service_auth.sh
#
# Then paste the printed SQL into Snowsight and run it as ACCOUNTADMIN.

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

cat <<SQL
-- Run as ACCOUNTADMIN in Snowsight
ALTER USER ARCADE_STREAMING_USER SET RSA_PUBLIC_KEY='${PUBK}';
SQL

echo ""
echo "-- Save this as profile.json in the project root:"
cat <<JSON
{
    "user":             "ARCADE_STREAMING_USER",
    "account":          "YOUR_ACCOUNT_IDENTIFIER",
    "url":              "https://YOUR_ACCOUNT_IDENTIFIER.snowflakecomputing.com:443",
    "private_key_file": "${PRIVATE_KEY_FULL}",
    "role":             "ARCADE_STREAMING_ROLE"
}
JSON

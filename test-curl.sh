#!/bin/bash

set -euo pipefail

STAMP=$(date +%s)
TITLE="CLI smoke $STAMP"
BODY="This came from test-curl at $STAMP"

printf 'Creating note via API...\n'
RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"$TITLE\", \"content\": \"$BODY\", \"color\": \"sky\"}" \
  http://localhost:5000/api/notes)

echo "$RESPONSE"
NOTE_ID=$(echo "$RESPONSE" | python -c "import sys,json;print(json.load(sys.stdin).get('id', ''))")

printf '\nListing notes...\n'
curl -s http://localhost:5000/api/notes | python -m json.tool

if [ -n "$NOTE_ID" ]; then
  printf '\nFetching the new note (%s)...\n' "$NOTE_ID"
  curl -s http://localhost:5000/api/notes/$NOTE_ID | python -m json.tool
fi

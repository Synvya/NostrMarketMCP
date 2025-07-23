  
#!/bin/bash
# Minimal test script: health, chat (non-stream), chat (stream), debug trace
set -euo pipefail

API_URL=${API_URL:-"https://api.synvya.com"}
API_KEY=${API_KEY:-""}

if [ -z "$API_KEY" ]; then
  echo "ERROR: Set API_KEY env var first" >&2
  exit 1
fi

jq >/dev/null 2>&1 || { echo "jq not found. brew install jq" >&2; exit 1; }

printf "\n1) Health check\n";
curl -s -f "$API_URL/health" | jq .

printf "\n2) Chat non-stream\n";
curl -s -X POST "$API_URL/api/chat" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"find coffee in snoqualmie, wa"}],"stream":false}' | jq .

printf "\n3) Chat stream (SSE)\n";
curl -N -X POST "$API_URL/api/chat" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"find coffee in snoqualmie, wa"}],"stream":true}' \
  --max-time 30 || echo "(stream ended)"

printf "\n4) Debug last tool loop\n";
curl -s -H "X-API-Key: $API_KEY" "$API_URL/api/debug/last_tool_loop" | jq .

echo "\nDone."
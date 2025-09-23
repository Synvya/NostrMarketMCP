# NostrMarketMCP – HTTP API Testing Guide

> • **Scope** – tests & manual checks for the FastAPI server in `src/api/server.py`
> • **Audience** – contributors, CI pipelines, power-users
> • **Security** – placeholders only (`YOUR_API_KEY`, `YOUR_BEARER_TOKEN`)

---

## 1 · Quick-start (local)
# ❶ Create virtual-env & install deps
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

# ❷ Start the API locally
```bash
python scripts/run_api_service.py   # http://127.0.0.1:8080
```

# ❸ Run the API service tests (spawns services)
```bash
bash tests/run_api_local_tests.sh
```

All tests should pass ✔️

---

## 2 · Manual smoke-test (curl)

Environment helpers:
```bash
export HOST=http://127.0.0.1:8080        # or your load-balancer URL
export API_KEY=YOUR_API_KEY              # set one auth method only
# export BEARER_TOKEN=YOUR_BEARER_TOKEN

AUTH=()
[[ -n $API_KEY ]] && AUTH=(-H "X-API-Key: $API_KEY")
# [[ -n $BEARER_TOKEN ]] && AUTH=(-H "Authorization: Bearer $BEARER_TOKEN")
```

```bash
# Health check
curl -s $HOST/health | jq .

# Profile search (JSON body)
curl_args=(
  -s "$HOST/api/search"
  -H "Content-Type: application/json"
  --data '{"query":"test"}'
)

[[ -n $API_KEY ]] && curl_args+=(-H "X-API-Key: $API_KEY")

curl "${curl_args[@]}" | jq .

# Stats overview
curl_args=(
  -s "$HOST/api/stats"
  "${AUTH[@]}"
)

curl "${curl_args[@]}" | jq .
```
Expected: HTTP 200 and JSON keys `success | stats`.

---

## 3 · Automated test suite

| File | What it covers |
|------|----------------|
| `tests/test_api_service_local.py` | Core & security endpoints (against local server) |
| `tests/run_api_local_tests.sh` | Spawns DB+API locally and runs tests |
| `tests/mocks/` | Mock SDK objects (no external network) |

Run everything:
```bash
pytest tests/ -v   # or  python tests/run_tests.py
```

### Coverage highlights
- Core endpoints (`/health`, `/api/search`, `/api/search_by_business_type`, …)
- Auth checks (API Key **or** Bearer token)
- Input validation / SQL-injection guard
- Rate limiting path (HTTP 429 scenarios)
- Integration flow: refresh → search → stats

---

## 4 · Deployed / CI environments

1. **Set `HOST`** to your public URL.
2. Provide **one** authentication method via environment variables or secret store.
3. Ensure outbound network access to any configured Nostr relays if `refresh` is enabled.

CI snippet (GitHub Actions):
```yaml
- name: Run API local tests
  run: bash tests/run_api_local_tests.sh
```

---

## 5 · Common pitfalls & fixes
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Connection refused` | Server not running / wrong port | `python scripts/run_api_service.py` |
| `401 Unauthorized`   | Missing/incorrect auth header  | Check `API_KEY` or `BEARER_TOKEN` |
| `429 Too Many Requests` | Hit rate-limit | Increase `RATE_LIMIT_*` env vars or slow down |
| `500 Internal` | DB missing / corrupted | Delete DB & restart (`DATABASE_PATH`) |

---

## 6 · Load / performance (optional)
Small baseline with `wrk`:
```bash
wrk -t4 -c32 -d30s --header "X-API-Key: $API_KEY" $HOST/health
```
Record `Requests/sec` & latency percentiles in CI to catch regressions.

---

## 7 · File map after consolidation
```
docs/
└── testing/
    ├── api.md          ← you are here ✅
    ├── mcp.md          ← MCP testing 
    └── cheat-sheet.md  ← quick bash helper
```

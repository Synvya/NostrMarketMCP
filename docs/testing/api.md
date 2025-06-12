# NostrMarketMCP – HTTP API Testing Guide

> One file to rule them all. This replaces the old `API_TESTING_GUIDE.md` **and** `TESTING_GUIDE.md`.
>
> • **Scope** – tests & manual checks for the FastAPI server in `src/api/simple_secure_server.py`
> • **Audience** – contributors, CI pipelines, power-users
> • **Security** – placeholders only (`YOUR_API_KEY`, `YOUR_BEARER_TOKEN`)

---

## 1 · Quick-start (local)
# ❶ Create virtual-env & install deps
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

# ❷ Start the API in dev mode (auto-reload)
```bash
cd scripts && python run_api_server.py   # listens on http://127.0.0.1:8080
```

# ❸ Run the full pytest suite
```bash
pytest tests/test_api_endpoints.py -v
```

All tests should pass ✔️

---

## 2 · Manual smoke-test (curl)

Environment helpers:
```bash
export HOST=http://127.0.0.1:8080        # or your load-balancer URL
export API_KEY=YOUR_API_KEY              # set one auth method only
# export BEARER_TOKEN=YOUR_BEARER_TOKEN

AUTH=${API_KEY:+-H "X-API-Key: $API_KEY"}${BEARER_TOKEN:+-H "Authorization: Bearer $BEARER_TOKEN"}
```

```bash
# Health check
curl -s $HOST/health $AUTH | jq .

# Profile search
curl -s $HOST/api/search_profiles \
     -H "Content-Type: application/json" $AUTH \
     -d '{"query":"test"}' | jq .

# Stats overview
curl -s $HOST/api/stats $AUTH | jq .
```
Expected: HTTP 200 and JSON keys `status | profiles | stats`.

---

## 3 · Automated test suite

| File | What it covers |
|------|----------------|
| `tests/test_api_endpoints.py` | Core & security endpoints |
| `tests/run_tests.py` | Convenience wrapper for CI / local runs |
| `tests/mocks/` | Mock SDK objects (no external network) |

Run everything:
```bash
pytest tests/ -v   # or  python tests/run_tests.py
```

### Coverage highlights
- Core endpoints (`/health`, `/api/search_profiles`, …)
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
- name: Run API tests
  run: |
    export HOST="https://api.example.com"
    export API_KEY="${{ secrets.API_KEY }}"
    pytest tests/test_api_endpoints.py -q
```

---

## 5 · Common pitfalls & fixes
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Connection refused` | Server not running / wrong port | `python run_api_server.py` |
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
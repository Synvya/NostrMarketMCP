
# NostrMarketMCP – Testing Cheat‑Sheet
When you’re wondering **“is the server up and doing what it should?”** run the commands below—nothing more, nothing less.

---

## 1 · Pre‑flight

| Item                     | Default                    | How to change                     |
| ------------------------ | -------------------------- | --------------------------------- |
| Host / Load‑Balancer URL | `http://127.0.0.1:8080`    | `$ export HOST=http://your.host`  |
| API Key header           | `X-API-Key: local_test_api_key` | `$ export API_KEY=…`             |
| Bearer token header      | `Authorization: Bearer …`  | `$ export BEARER=…`               |

Set either `API_KEY` **or** `BEARER`—not both.

```bash
# one‑liner for local Docker compose
docker compose up -d nostr_api && sleep 3
```

---

## 2 · Smoke test (should finish in < 10 s)

```bash
#!/usr/bin/env bash
HOST=${HOST:-http://127.0.0.1:8080}
AUTH_HEADER=${API_KEY:+-H "X-API-Key: $API_KEY"}${BEARER:+-H "Authorization: Bearer $BEARER"}

curl -sS $HOST/health                                 $AUTH_HEADER | jq .
curl -sS $HOST/api/search_profiles     -d '{"query":"test"}' -H "Content-Type: application/json" $AUTH_HEADER | jq .
curl -sS $HOST/api/stats                                 $AUTH_HEADER | jq .
```

Expected: HTTP 200 three times and JSON keys `status`, `profiles`, `total_profiles`.

---

## 3 · Functional endpoints

```bash
# Search business profiles
curl -sS $HOST/api/search_business_profiles      -H "Content-Type: application/json" $AUTH_HEADER      -d '{"query":"coffee","business_type":"retail","limit":5}' | jq .

# Lookup by pubkey
curl -sS $HOST/api/profile/57d0…991  $AUTH_HEADER | jq .
```

If any call returns **401** you mis‑configured auth; **500** means the server choked—check container logs.

---

## 4 · Load & rate‑limit sanity

*10 parallel profile searches, repeated 100 × (≈ 1 k req):*

```bash
seq 1 1000 | xargs -n1 -P10 -I%   curl -sS $HOST/api/search_profiles        -H "Content-Type: application/json" $AUTH_HEADER        -d '{"query":"load"}' > /dev/null
```

**429 Too Many Requests** before ~100 req/min → rate‑limit working.

---

## 5 · Performance baseline (optional)

```bash
# <30 s micro‑benchmark
wrk -t8 -c32 -d30s --header "X-API-Key: $API_KEY" $HOST/health
```

Track `Requests/sec` and 95‑percentile latency; keep a log so you notice regressions.

---

## 6 · Troubleshooting crib‑sheet

| Symptom | Likely cause | Quick fix |
| --- | --- | --- |
| `curl: (7) Failed to connect` | Container not running / wrong port | `docker ps`, confirm `8080->8080` mapping |
| 401 Unauthorized | Header name or value wrong | Print headers with `--verbose` |
| 429 Too Many Requests | Exceeded `RATE_LIMIT_REQUESTS` | Back off or raise the env var |
| 500 Internal | DB locked / bad payload | `docker logs <container>` |

Environment variables you’ll touch most:

* `API_KEY` – string sent as `X-API-Key`
* `BEARER_TOKEN` – bearer auth alternative
* `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`
* `DATABASE_PATH` – path inside the container

---

## 7 · Cloud watchpoints (AWS ECS/Fargate)

1. **Container logs** → `/ecs/<task-def>`  
   ```bash
   aws logs tail /ecs/nostr_api --follow
   ```
2. **Metrics** to alarm on:
   * `5xx` count > 0
   * P95 latency > 2 s
   * CPU > 80 % for 5 min

---

## 8 · Next‑step hardening

* Add the smoke‑test script to CI/CD post‑deploy.  
* Wire CloudWatch alarms to Slack.  
* Run a nightly `wrk` job and chart latencies.

---

**That’s it.** No scrolling through pages of duplicate curl examples—just the commands you actually need.

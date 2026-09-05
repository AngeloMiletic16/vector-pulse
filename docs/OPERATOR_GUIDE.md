# VectorPulse Operator Guide

This guide covers the containerized demo and the `vectorpulse` CLI.

## Start

```bash
git clone https://github.com/AngeloMiletic16/vector-pulse.git
cd vector-pulse
docker compose --profile demo up --build -d
```

Check:

```bash
docker compose --profile demo ps
curl http://127.0.0.1:8000/health
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## CLI

With the development environment:

```bash
uv sync --locked --dev
uv run vectorpulse health
```

Or inside the backend container:

```bash
docker compose exec backend vectorpulse health
```

## Assets

```bash
uv run vectorpulse assets list
uv run vectorpulse assets show tag-001
uv run vectorpulse assets telemetry tag-001 --limit 10
uv run vectorpulse assets alerts tag-001
```

## Monitoring

```bash
uv run vectorpulse zones
uv run vectorpulse rules
uv run vectorpulse alerts
uv run vectorpulse alerts --json
```

Alert types include:

```text
dwell_time_exceeded
excessive_speed
impossible_movement
low_battery
anomaly_detected
```

## Live Events

```bash
uv run vectorpulse events watch
uv run vectorpulse events watch --alerts-only
uv run vectorpulse events watch --event-type low_battery
uv run vectorpulse events watch --event-type anomaly_detected
```

Stop with `Ctrl+C`.

## ML Operations

```bash
uv run vectorpulse ml status
uv run vectorpulse ml status --json
uv run vectorpulse ml train --limit 500 --nu 0.03
```

Training requires at least 100 persisted telemetry samples.

`anomaly_detected` means behavior is outside the learned normal operating region after confirmation logic. It is not a probability of failure.

## REST Endpoints

```text
GET  /health
GET  /assets
GET  /assets/{tag_id}
GET  /assets/{tag_id}/telemetry
GET  /assets/{tag_id}/zone-transitions
GET  /alerts
GET  /assets/{tag_id}/alerts
GET  /zones
GET  /monitoring-rules
GET  /ml/anomaly/status
POST /ml/anomaly/train
WS   /ws/assets
```

## Persistence

Docker stores persistent data under the backend's `/app/data` named volume.

Restart without deleting data:

```bash
docker compose restart backend
```

Persisted assets restart offline and return online after fresh telemetry. The trained ML model is also reloaded.

Stop while keeping data:

```bash
docker compose --profile demo down
```

Reset all Docker demo data:

```bash
docker compose --profile demo down -v
```

**Warning:** `-v` deletes the persisted SQLite database and trained ML model.

## Troubleshooting

Backend/broker logs:

```bash
docker compose logs backend
docker compose logs mosquitto
docker compose ps
```

Ensure simulator is running:

```bash
docker compose --profile demo up -d simulator
```

Override backend URL:

```bash
uv run vectorpulse --base-url http://HOST:PORT health
```

or:

```bash
export VECTORPULSE_URL=http://HOST:PORT
uv run vectorpulse health
```

If ML is not ready, collect normal telemetry and train after at least 100 samples.

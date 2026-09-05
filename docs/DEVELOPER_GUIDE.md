# VectorPulse Developer Guide

This guide covers local development, project navigation, configuration, and quality checks.

## Prerequisites

- Git
- Docker + Docker Compose
- `uv`
- Linux-like development environment

VectorPulse requires Python `3.13+`.

## Setup

```bash
git clone https://github.com/AngeloMiletic16/vector-pulse.git
cd vector-pulse
uv sync --locked --dev
```

Verify:

```bash
uv run python --version
uv run vectorpulse --help
```

## Local Runtime

Terminal 1:

```bash
docker compose up -d mosquitto
```

Terminal 2:

```bash
uv run python -m vector_pulse.gateway
```

Terminal 3:

```bash
uv run python -m vector_pulse.simulator.publisher
```

API:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

## Configuration

| Variable | Default |
| --- | --- |
| `VECTORPULSE_MQTT_HOST` | `localhost` |
| `VECTORPULSE_MQTT_PORT` | `1883` |
| `VECTORPULSE_DATABASE_PATH` | `data/vectorpulse.db` |
| `VECTORPULSE_API_HOST` | `127.0.0.1` |
| `VECTORPULSE_API_PORT` | `8000` |
| `VECTORPULSE_TELEMETRY_QUEUE_MAX_SIZE` | `1000` |

## Source Layout

```text
src/vector_pulse/
├── api/            # FastAPI REST + WebSocket
├── application/    # State, geofencing, rules, monitors, events
├── cli/            # Typer/Rich CLI
├── ingestion/      # MQTT consumer + schemas
├── ml/             # Features, model, anomaly service
├── persistence/    # SQLite + training repository
├── sdk/            # Async client
├── simulator/      # Simulated MQTT tags
├── gateway.py      # Runtime composition
└── settings.py     # Environment configuration
```

## Processing Rule

Do not add side effects before telemetry acceptance:

```text
schema validation
→ sequence validation
→ accepted state
→ geofencing / rules / persistence / ML / events
```

Duplicates and out-of-order messages must not alter monitoring state.

## Development Workflow

```text
requirement
→ design
→ implementation
→ focused tests
→ full tests
→ runtime verification
→ commit
```

For new alert types, keep structured details, persist through the shared alert path, broadcast through the event path, and update public SDK enums/models.

## Quality Checks

```bash
uv run ruff check .
uv run pytest -q
```

Before a substantial commit:

```bash
uv run ruff check .
uv run pytest -q
uv build
```

Docker-sensitive work:

```bash
docker compose config -q
docker compose --profile demo config -q
bash scripts/ci/docker_smoke_test.sh
```

## Generated Artifacts

Do not commit runtime/build artifacts such as:

```text
data/*.db
data/*.db-wal
data/*.db-shm
data/*.joblib
dist/
```

`joblib` model files are trusted local artifacts; do not load arbitrary external model files.

## SDK and CLI

SDK:

```python
from vector_pulse.sdk import VectorPulseClient
```

CLI:

```bash
uv run vectorpulse --help
```

Main commands:

```text
health
zones
rules
alerts
assets
events
ml
```

The SDK should use HTTP/WebSocket rather than application/persistence internals. The CLI should remain built on the SDK.

## ML Development

Current features:

```text
temperature_c
vibration_rms
speed_mps
battery_percent
position_quality
```

Train on accepted normal telemetry. Do not describe `anomaly_score` as a probability.

## Packaging and Release

```bash
uv build
```

Version tags matching:

```text
vMAJOR.MINOR.PATCH
```

trigger the release workflow.

Create `v1.0.0` only after the final procedure in `docs/TESTING.md` passes.

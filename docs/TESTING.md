# VectorPulse Testing Strategy and Procedures

VectorPulse uses layered automated testing to validate components, cross-component behavior, and the complete containerized runtime.

Current baseline before the final `v1.0.0` release:

```text
113 tests passing
Ruff clean
Docker smoke test passing
```

## Test Layers

### Unit Tests
Unit tests cover telemetry schemas, simulator logic, sequence integrity, geofencing, event broadcasting, offline/dwell monitoring, movement and battery rules, ML features/model behavior, persistence helpers, SDK URL logic, and settings.

```text
tests/unit/
```

### Integration Tests
Integration tests cover FastAPI endpoints, WebSockets, SQLite persistence, geofencing/rules APIs, low-battery processor integration, ML repository/service/API flows, and SDK behavior.

```text
tests/integration/
```

### End-to-End Docker Smoke Test

Run:

```bash
bash scripts/ci/docker_smoke_test.sh
```

The smoke scenario:

1. starts Mosquitto and the production backend
2. waits for container health
3. verifies host REST `/health`
4. verifies the CLI inside the production container
5. publishes real MQTT telemetry
6. waits for the asset to become online at sequence `1`
7. restarts the backend
8. verifies persisted state is restored as offline
9. publishes fresh sequence `2`
10. verifies the asset returns online
11. starts the containerized simulator profile
12. verifies a simulated tag appears
13. cleans up the isolated CI stack

## Standard Local Quality Gate

```bash
uv run ruff check .
uv run pytest -q
```

For packaging/release changes:

```bash
uv build
docker compose config -q
docker compose --profile demo config -q
```

For full runtime confidence:

```bash
docker compose down
bash scripts/ci/docker_smoke_test.sh
```

## Manual Acceptance Scenarios

### Live WebSocket events

```bash
uv run vectorpulse events watch
```

Publish/simulate telemetry and verify live events.

### Low-battery anti-spam

Expected:

```text
21% → no alert
20% → low_battery alert
15% → no additional alert
```

After recovery above threshold, a later crossing may alert again.

### ML model lifecycle

1. collect at least 100 normal accepted samples
2. train the anomaly detector
3. confirm model status is ready
4. send consecutive extreme but valid telemetry
5. confirm `anomaly_detected`
6. restart backend
7. confirm the same model reloads
8. confirm inference still works after restart

```bash
uv run vectorpulse ml status
uv run vectorpulse ml train --limit 500 --nu 0.03
uv run vectorpulse events watch --event-type anomaly_detected
uv run vectorpulse alerts --json
```

## CI Validation

GitHub Actions runs on pushes to `main`, pull requests, and manual dispatch.

Python quality:

```text
locked dependency install
Ruff
pytest
CLI entry-point check
SDK import check
uv build
```

Docker integration:

```text
Compose validation
Docker build
Docker smoke test
```

## Known Dependency Warning

ML serialization tests may emit a `DeprecationWarning` from `joblib`/NumPy. It originates in the dependency stack and currently does not fail the suite. Re-evaluate it when dependencies are upgraded rather than hiding it globally.

## Final v1.0.0 Procedure

From a clean working tree:

```bash
uv sync --locked --dev

uv run ruff check .
uv run pytest -q

uv build

docker compose config -q
docker compose --profile demo config -q

docker compose down
bash scripts/ci/docker_smoke_test.sh
```

Then test the documented quick start:

```bash
docker compose --profile demo up --build -d
curl -fsS http://127.0.0.1:8000/health
docker compose exec backend vectorpulse assets list
docker compose --profile demo down
```

Release only if all checks pass, README commands work, generated DB/model/build/helper files are not staged, and GitHub Actions is green.

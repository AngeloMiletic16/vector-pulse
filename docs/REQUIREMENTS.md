# VectorPulse Requirements and Design Specification

This document defines the functional and non-functional requirements implemented by VectorPulse and records the main design decisions used to satisfy them.

## Scope

VectorPulse shall simulate an industrial asset-tracking environment and provide a reliable Python edge gateway that receives device telemetry over MQTT, maintains asset state, detects operational problems, persists history, and exposes the system through developer and operator interfaces.

The project is intentionally scoped as a single-node industrial edge platform rather than a distributed cloud system.

## Functional Requirements

| ID | Requirement | Implementation / Acceptance Evidence |
| --- | --- | --- |
| FR-01 | Simulate multiple independent asset tags concurrently. | `simulator/` publishes telemetry for multiple tags asynchronously. |
| FR-02 | Tags communicate with the gateway through MQTT. | Eclipse Mosquitto + `aiomqtt`. |
| FR-03 | Validate incoming telemetry before application processing. | Pydantic telemetry schemas. |
| FR-04 | Track per-tag message sequence integrity. | Duplicate/out-of-order rejection and gap detection. |
| FR-05 | Maintain current asset state. | Asset registry stores telemetry, status, last-seen time, and zone state. |
| FR-06 | Track online/offline state. | Fresh telemetry restores online state; background monitor marks stale assets offline. |
| FR-07 | Map positions to logical industrial zones. | Geofencing for receiving, storage, assembly, and shipping. |
| FR-08 | Detect deterministic operational problems. | Dwell, speed, impossible movement, and low-battery alerts. |
| FR-09 | Persist accepted telemetry and derived state across restart. | SQLite state/history and startup restore. |
| FR-10 | Expose current and historical information over HTTP. | FastAPI REST endpoints. |
| FR-11 | Stream live asset and alert updates. | WebSocket `/ws/assets`. |
| FR-12 | Provide a Python client interface. | Async `VectorPulseClient` SDK. |
| FR-13 | Provide an operator command-line interface. | `vectorpulse` Typer/Rich CLI. |
| FR-14 | Support ML-based novelty detection. | RobustScaler + One-Class SVM. |
| FR-15 | Train ML from persisted accepted telemetry. | ML repository + API/SDK/CLI training flow. |
| FR-16 | Persist and reload the trained ML model. | Trusted local `joblib` artifact. |
| FR-17 | Reproduce the runtime with containers. | Dockerfile + Docker Compose demo profile. |
| FR-18 | Automatically validate release candidates. | GitHub Actions CI + release workflow. |

## Telemetry Contract

Each accepted message contains:

```text
tag_id
sequence_number
timestamp
position:
  x
  y
  quality
motion:
  speed_mps
condition:
  temperature_c
  vibration_rms
  battery_percent
```

## Event and Alert Requirements

VectorPulse supports state and monitoring events including:

```text
telemetry_updated
asset_online
asset_offline
zone_entered
zone_exited
dwell_time_exceeded
excessive_speed
impossible_movement
low_battery
anomaly_detected
```

## Non-Functional Requirements

| ID | Requirement | Design Response |
| --- | --- | --- |
| NFR-01 | Keep the gateway responsive while background responsibilities run. | Async I/O + `asyncio.TaskGroup`. |
| NFR-02 | Prevent unbounded memory growth during telemetry bursts. | Bounded queue, default `1000`. |
| NFR-03 | Prevent invalid/stale telemetry from creating monitoring side effects. | Validation + sequence acceptance before rules/ML. |
| NFR-04 | Make restart behavior deterministic. | SQLite restore; persisted devices restart offline until fresh telemetry. |
| NFR-05 | Configure runtime without editing source. | Environment-based MQTT, database, API, and queue settings. |
| NFR-06 | Test behavior without physical hardware. | Simulator, unit/integration tests, Docker E2E smoke test. |
| NFR-07 | Be installable as a Python package. | `pyproject.toml`, `uv`, SDK, console entry points. |
| NFR-08 | Avoid root execution in the production container. | Backend runs as user `10001`. |
| NFR-09 | Repeat quality checks locally and in CI. | Ruff, pytest, build, Compose checks. |
| NFR-10 | Reproduce delivery artifacts from version tags. | Tag-based release workflow. |

## Design Decisions

### DD-01 — MQTT as the device boundary
Simulated tags act as external devices. MQTT decouples the producer from the Python gateway.

### DD-02 — Bounded producer/consumer pipeline
MQTT ingestion and processing are separated by a bounded queue to create explicit backpressure.

### DD-03 — Sequence integrity before business logic
Duplicate and out-of-order messages are rejected before persistence, rules, or ML. Gaps are accepted but reported.

### DD-04 — SQLite for edge-local persistence
SQLite keeps a single-node edge deployment small while still demonstrating durable history and restart recovery.

### DD-05 — Explicit deterministic rules
Known limits stay explainable: dwell thresholds, speed limits, impossible movement, and low-battery threshold crossing.

### DD-06 — One-Class SVM for novelty detection
The ML task learns normal behavior rather than classifying labeled failures. Features are scaled with `RobustScaler`.

### DD-07 — REST for queries, WebSocket for live updates
REST handles current/historical access; WebSocket handles push events.

### DD-08 — SDK and CLI use external interfaces
The SDK talks through HTTP/WebSocket and the CLI uses the SDK, keeping public interfaces realistic.

### DD-09 — Integrated backend over microservices
One process is appropriate for project scale and avoids distributed complexity without a requirement.

## Out of Scope for Version 1.0

Version 1.0 does not claim:

- deployment to a real microcontroller or physical industrial tag
- high-availability multi-node processing
- user authentication/authorization
- MQTT TLS/device certificates
- cloud-scale persistence
- supervised failure prediction or remaining-useful-life estimation
- browser dashboard

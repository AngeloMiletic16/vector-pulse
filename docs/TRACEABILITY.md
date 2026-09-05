# Target Role Requirements Traceability

VectorPulse was deliberately designed to demonstrate the engineering areas targeted by the Python Developer student/intern role.

| Targeted requirement | VectorPulse implementation | Repository evidence |
| --- | --- | --- |
| **Python development** | Backend, simulator, SDK, CLI, tests, ML | `src/vector_pulse/`, `tests/` |
| **Edge / embedded-oriented Python features** | MQTT gateway, external device simulation, state, offline detection, local monitoring | `gateway.py`, `ingestion/`, `application/`, `simulator/` |
| **Python packages for application developers** | Installable package, async SDK, console entry points | `pyproject.toml`, `sdk/`, `cli/` |
| **Asyncio** | Concurrent consumer/processor/monitors and bounded queue | `gateway.py`, ingestion, processor |
| **MQTT** | Primary device telemetry protocol | Mosquitto, MQTT consumer, simulator |
| **HTTP** | FastAPI REST + HTTPX SDK | `api/`, `sdk/` |
| **WebSocket** | Live asset/alert stream | `/ws/assets`, broadcaster, SDK event watch |
| **Linux** | Debian-based production container | `Dockerfile` |
| **Technical / design requirements** | Functional, non-functional, and design decisions | `docs/REQUIREMENTS.md` |
| **Conceptual solution / specification** | Architecture and data-flow documentation | `docs/ARCHITECTURE.md` |
| **Test procedures** | Unit, integration, manual, CI, Docker E2E | `docs/TESTING.md`, `tests/`, smoke script |
| **Implementation / continuous upgrades** | Incremental Git history, CI, dependency automation | Git history, CI, Dependabot |
| **CI/CD** | Automated CI and tag-based release delivery | `.github/workflows/` |
| **Developer documentation** | Setup, architecture, testing | `README.md`, `docs/DEVELOPER_GUIDE.md` |
| **User/operator documentation** | Runtime and CLI operations | `docs/OPERATOR_GUIDE.md` |
| **Reliable telemetry handling** | Validation, duplicate/out-of-order rejection, gaps, bounded queue | ingestion + registry + processor |
| **Industrial monitoring** | Geofencing, dwell, speed, impossible movement, battery, offline | `application/` |
| **Applied ML** | Robust-scaled One-Class SVM and persisted model lifecycle | `ml/`, ML API/SDK/CLI |
| **Containerized delivery** | Broker/backend/simulator stack, non-root backend, persistent volume | Dockerfile + Compose |

## Reliability Evidence

VectorPulse demonstrates:

- malformed message validation
- duplicate rejection
- out-of-order rejection
- sequence-gap detection
- MQTT reconnect handling
- online/offline transitions
- persisted restart recovery
- bounded queue backpressure
- low-quality position handling
- low-battery anti-spam behavior
- ML model persistence across restart

## Scope Honesty

VectorPulse is an edge/IoT simulation and software-engineering project. It does **not** claim that Python runs on a physical microcontroller or that it has been deployed to real industrial hardware.

The simulator provides an external device boundary, while the gateway demonstrates the Python-side responsibilities around real devices: communication, state, persistence, monitoring, APIs, SDKs, testing, documentation, and delivery.

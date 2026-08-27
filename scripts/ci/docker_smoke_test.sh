#!/usr/bin/env bash

set -Eeuo pipefail


PROJECT_NAME="vectorpulse-ci-${GITHUB_RUN_ID:-local}"
API_URL="http://127.0.0.1:8000"
TEST_TAG_ID="ci-tag"

COMPOSE=(
    docker compose
    -p "${PROJECT_NAME}"
)


log() {
    printf '\n[VectorPulse CI] %s\n' "$1"
}


dump_diagnostics() {
    log "Docker diagnostics"

    "${COMPOSE[@]}" ps || true

    printf '\n--- Mosquitto logs ---\n'
    "${COMPOSE[@]}" logs mosquitto || true

    printf '\n--- Backend logs ---\n'
    "${COMPOSE[@]}" logs backend || true

    printf '\n--- Simulator logs ---\n'
    "${COMPOSE[@]}" logs simulator || true
}


cleanup() {
    log "Cleaning up CI stack"

    "${COMPOSE[@]}" \
        --profile demo \
        down \
        -v \
        --remove-orphans \
        >/dev/null 2>&1 || true
}


finish() {
    local status=$?

    trap - EXIT

    if [[ "${status}" -ne 0 ]]; then
        dump_diagnostics
    fi

    cleanup

    exit "${status}"
}


trap finish EXIT


wait_for_health() {
    local service="$1"
    local timeout_seconds="$2"

    local deadline
    local container_id
    local health_status

    deadline=$((SECONDS + timeout_seconds))

    while ((SECONDS < deadline)); do
        container_id=$(
            "${COMPOSE[@]}" \
                ps \
                -q \
                "${service}"
        )

        if [[ -n "${container_id}" ]]; then
            health_status=$(
                docker inspect \
                    --format \
                    '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
                    "${container_id}" \
                    2>/dev/null || true
            )

            case "${health_status}" in
                healthy)
                    log "${service} is healthy"
                    return 0
                    ;;

                unhealthy|exited|dead)
                    echo \
                        "${service} entered invalid state: ${health_status}" \
                        >&2

                    return 1
                    ;;
            esac
        fi

        sleep 2
    done

    echo \
        "Timed out waiting for ${service} health" \
        >&2

    return 1
}


asset_payload_matches() {
    local payload="$1"
    local expected_tag_id="$2"
    local expected_sequence="$3"
    local expected_status="$4"

    python3 \
        -c '
import json
import sys

expected_tag_id = sys.argv[1]
expected_sequence = int(sys.argv[2])
expected_status = sys.argv[3]

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, TypeError):
    raise SystemExit(1)

telemetry = payload.get("telemetry")

if not isinstance(telemetry, dict):
    raise SystemExit(1)

matches = (
    telemetry.get("tag_id") == expected_tag_id
    and telemetry.get("sequence_number") == expected_sequence
    and payload.get("status") == expected_status
)

raise SystemExit(0 if matches else 1)
' \
        "${expected_tag_id}" \
        "${expected_sequence}" \
        "${expected_status}" \
        <<< "${payload}"
}


wait_for_asset() {
    local tag_id="$1"
    local expected_sequence="$2"
    local expected_status="$3"

    local attempts=30
    local attempt
    local payload=""

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        payload=$(
            curl \
                --fail \
                --silent \
                "${API_URL}/assets/${tag_id}" \
                2>/dev/null || true
        )

        if [[ -n "${payload}" ]]; then
            if asset_payload_matches \
                "${payload}" \
                "${tag_id}" \
                "${expected_sequence}" \
                "${expected_status}"
            then
                log \
                    "Asset ${tag_id} reached sequence=${expected_sequence} status=${expected_status}"

                return 0
            fi
        fi

        sleep 1
    done

    echo \
        "Asset ${tag_id} did not reach expected state" \
        >&2

    echo \
        "Last payload: ${payload:-<empty>}" \
        >&2

    return 1
}


wait_for_asset_exists() {
    local tag_id="$1"

    local attempts=30
    local attempt

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if curl \
            --fail \
            --silent \
            "${API_URL}/assets/${tag_id}" \
            > /dev/null 2>&1
        then
            log "Asset ${tag_id} exists"
            return 0
        fi

        sleep 1
    done

    echo \
        "Timed out waiting for asset ${tag_id}" \
        >&2

    return 1
}


log "Starting core Docker stack"

"${COMPOSE[@]}" up \
    -d \
    mosquitto \
    backend


wait_for_health \
    "mosquitto" \
    30

wait_for_health \
    "backend" \
    60


log "Checking host-exposed REST health endpoint"

health_payload=$(
    curl \
        --fail \
        --silent \
        --show-error \
        "${API_URL}/health"
)

python3 \
    -c '
import json
import sys

payload = json.load(sys.stdin)

if payload.get("status") != "ok":
    raise SystemExit(
        f"Unexpected health response: {payload}"
    )
' \
    <<< "${health_payload}"


log "Checking CLI inside production container"

"${COMPOSE[@]}" exec \
    -T \
    backend \
    vectorpulse health


log "Publishing MQTT telemetry through Mosquitto container"

"${COMPOSE[@]}" exec \
    -T \
    mosquitto \
    mosquitto_pub \
    -h localhost \
    -p 1883 \
    -t "vectorpulse/assets/${TEST_TAG_ID}/telemetry" \
    -m '{
        "tag_id": "ci-tag",
        "sequence_number": 1,
        "timestamp": "2026-08-27T12:00:00Z",
        "position": {
            "x": 5.0,
            "y": 5.0,
            "quality": 0.95
        },
        "motion": {
            "speed_mps": 1.0
        },
        "condition": {
            "temperature_c": 25.0,
            "vibration_rms": 0.1,
            "battery_percent": 90.0
        }
    }'


wait_for_asset \
    "${TEST_TAG_ID}" \
    1 \
    "online"


log "Restarting backend to test SQLite volume persistence"

"${COMPOSE[@]}" restart \
    backend


wait_for_health \
    "backend" \
    60


wait_for_asset \
    "${TEST_TAG_ID}" \
    1 \
    "offline"


log "Publishing fresh telemetry after backend restart"

"${COMPOSE[@]}" exec \
    -T \
    mosquitto \
    mosquitto_pub \
    -h localhost \
    -p 1883 \
    -t "vectorpulse/assets/${TEST_TAG_ID}/telemetry" \
    -m '{
        "tag_id": "ci-tag",
        "sequence_number": 2,
        "timestamp": "2026-08-27T12:00:01Z",
        "position": {
            "x": 6.0,
            "y": 5.0,
            "quality": 0.95
        },
        "motion": {
            "speed_mps": 1.0
        },
        "condition": {
            "temperature_c": 25.0,
            "vibration_rms": 0.1,
            "battery_percent": 89.9
        }
    }'


wait_for_asset \
    "${TEST_TAG_ID}" \
    2 \
    "online"


log "Starting containerized simulator profile"

"${COMPOSE[@]}" \
    --profile demo \
    up \
    -d \
    simulator


wait_for_asset_exists \
    "tag-001"


log "Docker smoke test passed"
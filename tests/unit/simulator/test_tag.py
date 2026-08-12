from vector_pulse.simulator.tag import SimulatedTag


def test_tag_increments_sequence_number() -> None:
    tag = SimulatedTag(tag_id="tag-001")

    first = tag.next_telemetry()
    second = tag.next_telemetry()

    assert first.sequence_number == 1
    assert second.sequence_number == 2


def test_tag_generates_correct_tag_id() -> None:
    tag = SimulatedTag(tag_id="tag-017")

    message = tag.next_telemetry()

    assert message.tag_id == "tag-017"


def test_generated_values_respect_schema_ranges() -> None:
    tag = SimulatedTag(tag_id="tag-001")

    message = tag.next_telemetry()

    assert 0.0 <= message.position.quality <= 1.0
    assert message.motion.speed_mps >= 0.0
    assert 0.0 <= message.condition.battery_percent <= 100.0
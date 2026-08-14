import pytest

from vector_pulse.simulator.publisher import create_tags


def test_create_tags_returns_requested_count() -> None:
    tags = create_tags(5)

    assert len(tags) == 5


def test_create_tags_generates_unique_ids() -> None:
    tags = create_tags(3)

    tag_ids = [tag.tag_id for tag in tags]

    assert tag_ids == [
        "tag-001",
        "tag-002",
        "tag-003",
    ]


def test_create_tags_rejects_invalid_count() -> None:
    with pytest.raises(ValueError):
        create_tags(0)
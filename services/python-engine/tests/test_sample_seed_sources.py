from pathlib import Path

import pytest

from app.sample_seed_sources import (
    SampleSeedSource,
    validate_sample_seed_source,
    assert_sample_seed_can_ship,
)


def test_seed_source_requires_profile_and_license_note(tmp_path):
    seed = SampleSeedSource(
        seed_id="wos-rare-earth",
        source_profile="wos",
        path=tmp_path / "wos.xlsx",
        redistribution="restricted",
        redistribution_note="",
    )

    with pytest.raises(ValueError, match="redistribution_note"):
        validate_sample_seed_source(seed)


def test_restricted_seed_cannot_ship_without_override(tmp_path, monkeypatch):
    seed = SampleSeedSource(
        seed_id="wos-rare-earth",
        source_profile="wos",
        path=tmp_path / "wos.xlsx",
        redistribution="restricted",
        redistribution_note="Local development export only.",
    )

    with pytest.raises(ValueError, match="not approved for release packaging"):
        assert_sample_seed_can_ship(seed)

    monkeypatch.setenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA", "1")
    assert_sample_seed_can_ship(seed)

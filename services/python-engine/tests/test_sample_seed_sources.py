from pathlib import Path

import pytest

from app.samples.seed_sources import (
    SampleSeedSource,
    default_sample_seed_sources,
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
    monkeypatch.delenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA", raising=False)
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


def test_default_seed_sources_discover_direct_seed_folder_files(tmp_path, monkeypatch):
    seed_root = tmp_path / "sample_seed_sources"
    seed_root.mkdir()
    wos_seed = seed_root / "稀土wos.xls"
    incopat_seed = seed_root / "稀缺稀土元素.xlsx"
    wos_seed.write_text("wos", encoding="utf-8")
    incopat_seed.write_text("incopat", encoding="utf-8")

    monkeypatch.setattr("app.samples.seed_sources.sample_seed_root", lambda: seed_root)
    monkeypatch.delenv("TEXTFLOW_SAMPLE_WOS_SOURCE", raising=False)
    monkeypatch.delenv("TEXTFLOW_SAMPLE_INCOPAT_SOURCE", raising=False)
    monkeypatch.delenv("TEXTFLOW_SAMPLE_SCOPUS_SOURCE", raising=False)

    sources = default_sample_seed_sources()
    by_id = {source.seed_id: source for source in sources}

    assert by_id["wos-rare-earth"].path == wos_seed.resolve()
    assert by_id["incopat-rare-earth"].path == incopat_seed.resolve()

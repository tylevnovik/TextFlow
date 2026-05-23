from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class SampleSeedSource:
    seed_id: str
    source_profile: str
    path: Path
    redistribution: Literal["approved", "restricted", "unknown"]
    redistribution_note: str


def validate_sample_seed_source(seed: SampleSeedSource) -> None:
    if not seed.seed_id or not seed.source_profile:
        raise ValueError("seed_id and source_profile are required")
    if not seed.redistribution_note.strip():
        raise ValueError("redistribution_note is required")


def assert_sample_seed_can_ship(seed: SampleSeedSource) -> None:
    validate_sample_seed_source(seed)
    if seed.redistribution in ("restricted", "unknown"):
        if os.getenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA") != "1":
            raise ValueError(
                f"Seed {seed.seed_id} from {seed.source_profile} is {seed.redistribution} "
                "and not approved for release packaging. "
                "Set TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA=1 for local/private builds."
            )


def sample_seed_root() -> Path:
    return Path(__file__).resolve().parents[4] / "sample_seed_sources"


def default_sample_seed_sources() -> list[SampleSeedSource]:
    root = sample_seed_root()
    private_dir = root / "private"
    sources: list[SampleSeedSource] = []

    wos_path = _resolve_seed_path(
        "TEXTFLOW_SAMPLE_WOS_SOURCE",
        private_dir / "wos-rare-earth.xls",
        _find_seed_file(root, extensions={".xls", ".xlsx"}, name_contains=("wos",)),
    )
    if wos_path.exists():
        sources.append(
            SampleSeedSource(
                seed_id="wos-rare-earth",
                source_profile="wos",
                path=wos_path,
                redistribution="restricted",
                redistribution_note="Local development WoS export only. Not cleared for redistribution.",
            )
        )

    incopat_path = _resolve_seed_path(
        "TEXTFLOW_SAMPLE_INCOPAT_SOURCE",
        private_dir / "incopat-rare-earth.xlsx",
        _find_seed_file(root, extensions={".xlsx"}, name_excludes=("wos", "scopus")),
    )
    if incopat_path.exists():
        sources.append(
            SampleSeedSource(
                seed_id="incopat-rare-earth",
                source_profile="incopat",
                path=incopat_path,
                redistribution="restricted",
                redistribution_note="Local development IncoPat export only. Not cleared for redistribution.",
            )
        )

    scopus_path = _resolve_seed_path(
        "TEXTFLOW_SAMPLE_SCOPUS_SOURCE",
        private_dir / "scopus-rare-earth.csv",
        _find_seed_file(root, extensions={".csv", ".tsv", ".xlsx"}, name_contains=("scopus",)),
    )
    if scopus_path.exists():
        sources.append(
            SampleSeedSource(
                seed_id="scopus-rare-earth",
                source_profile="scopus",
                path=scopus_path,
                redistribution="restricted",
                redistribution_note="Local development Scopus export only. Not cleared for redistribution.",
            )
        )

    return sources


def _resolve_seed_path(env_var: str, default: Path, discovered: Path | None = None) -> Path:
    override = os.getenv(env_var)
    if override:
        return Path(override).expanduser().resolve()
    if discovered is not None:
        return discovered.expanduser().resolve()
    return default


def _find_seed_file(
    root: Path,
    *,
    extensions: set[str],
    name_contains: tuple[str, ...] = (),
    name_excludes: tuple[str, ...] = (),
) -> Path | None:
    if not root.exists():
        return None
    candidates = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if path.suffix.lower() not in extensions:
            continue
        if name_contains and not all(token in lowered for token in name_contains):
            continue
        if any(token in lowered for token in name_excludes):
            continue
        candidates.append(path)
    return candidates[0] if candidates else None


def seed_source_by_id(seed_id: str, sources: list[SampleSeedSource] | None = None) -> SampleSeedSource | None:
    for source in sources or default_sample_seed_sources():
        if source.seed_id == seed_id:
            return source
    return None

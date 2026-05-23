from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path

from .registry import NodeRegistryBuilder


PLUGIN_ENV_VAR = "TEXTFLOW_NODE_PLUGIN_DIR"


def artifact_output_port(
    port_id: str,
    *,
    port_type: str = "AnyTable",
    label: str | None = None,
    artifact_kind: str = "table",
    **extra: object,
) -> dict[str, object]:
    if not port_id:
        raise ValueError("Artifact output port requires a port_id")
    if not artifact_kind:
        raise ValueError("Artifact output port requires an artifact_kind")
    return {
        "port_id": port_id,
        "port_type": port_type,
        "label": label or port_id,
        "artifact_kind": artifact_kind,
        **extra,
    }


def default_plugin_roots() -> list[Path]:
    roots: list[Path] = []
    configured = os.getenv(PLUGIN_ENV_VAR, "")
    if configured:
        roots.extend(Path(item).expanduser() for item in configured.split(os.pathsep) if item.strip())

    project_root = Path(__file__).resolve().parents[3]
    roots.append(project_root / "plugins" / "nodes")

    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent / "plugins" / "nodes")

    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)
    return deduped


def _plugin_entrypoint(module: object):
    for attr_name in ("register_nodes", "register"):
        candidate = getattr(module, attr_name, None)
        if callable(candidate):
            return candidate
    return None


def _invoke_entrypoint(entrypoint, builder: NodeRegistryBuilder) -> None:
    parameter_count = len(inspect.signature(entrypoint).parameters)
    if parameter_count >= 2:
        entrypoint(builder, builder.runtime_profile_definition)
    else:
        entrypoint(builder)


def load_node_plugins(builder: NodeRegistryBuilder) -> None:
    for root in default_plugin_roots():
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = f"textflow_node_plugin_{path.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    builder.add_plugin_error(f"{path.name}: 无法创建 importlib spec")
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                entrypoint = _plugin_entrypoint(module)
                if entrypoint is None:
                    builder.add_plugin_error(f"{path.name}: 未找到 register_nodes / register")
                    continue
                _invoke_entrypoint(entrypoint, builder)
            except Exception as exc:  # pragma: no cover - defensive plugin boundary
                builder.add_plugin_error(f"{path.name}: {exc}")

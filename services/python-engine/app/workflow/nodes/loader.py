from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Any, Iterable


class _DefinitionCollector:
    def __init__(self, runtime_profile: dict[str, Any] | None) -> None:
        self.runtime_profile_definition = runtime_profile
        self.definitions: list[dict[str, Any]] = []

    def register_definition(self, definition: dict[str, Any]) -> None:
        self.definitions.append(definition)

    def register_node(self, definition: dict[str, Any], **_hooks: Any) -> None:
        self.register_definition(definition)

    def register_compiler(self, _node_type: str, _compiler: Any) -> None:
        return None

    def register_executor(self, _executor_id: str, _executor: Any) -> None:
        return None


def iter_builtin_node_modules() -> Iterable[ModuleType]:
    import sys
    if getattr(sys, "frozen", False):
        try:
            from . import _builtin_list
            for name in _builtin_list.BUILTIN_NODE_MODULES:
                yield importlib.import_module(f"{__package__}.{name}")
            return
        except ImportError as exc:
            raise RuntimeError(
                "Frozen Python sidecar is missing the built-in workflow node list. "
                "Rebuild it with scripts/build-python-sidecar.ps1."
            ) from exc

    package = importlib.import_module(__package__ or "app.workflow.nodes")
    prefix = f"{package.__name__}."
    for module_info in sorted(pkgutil.iter_modules(package.__path__, prefix), key=lambda item: item.name):
        module_name = module_info.name.rsplit(".", 1)[-1]
        if module_name.startswith("_") or module_name == "loader":
            continue
        yield importlib.import_module(module_info.name)


def builtin_node_module_names() -> list[str]:
    return [module.__name__.rsplit(".", 1)[-1] for module in iter_builtin_node_modules()]


def _invoke_entrypoint(entrypoint: Any, builder: Any, runtime_profile: dict[str, Any] | None) -> None:
    parameter_count = len(inspect.signature(entrypoint).parameters)
    if parameter_count >= 2:
        entrypoint(builder, runtime_profile)
    else:
        entrypoint(builder)


def _module_definitions(module: ModuleType, runtime_profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    plural_factory = getattr(module, "node_definitions", None)
    if callable(plural_factory):
        definitions = plural_factory(runtime_profile)
        if isinstance(definitions, list):
            return [definition for definition in definitions if isinstance(definition, dict)]

    factory = getattr(module, "node_definition", None)
    if callable(factory):
        definition = factory(runtime_profile)
        return [definition] if isinstance(definition, dict) else []

    return []


def build_builtin_node_module_definitions(runtime_profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for module in iter_builtin_node_modules():
        entrypoint = getattr(module, "register_nodes", None) or getattr(module, "register", None)
        if callable(entrypoint):
            collector = _DefinitionCollector(runtime_profile)
            _invoke_entrypoint(entrypoint, collector, runtime_profile)
            definitions.extend(collector.definitions)
            continue
        definitions.extend(_module_definitions(module, runtime_profile))
    return definitions


def register_builtin_node_modules(builder: Any) -> None:
    for module in iter_builtin_node_modules():
        entrypoint = getattr(module, "register_nodes", None) or getattr(module, "register", None)
        if callable(entrypoint):
            _invoke_entrypoint(entrypoint, builder, builder.runtime_profile_definition)
            continue
        for definition in _module_definitions(module, builder.runtime_profile_definition):
            builder.register_definition(definition)

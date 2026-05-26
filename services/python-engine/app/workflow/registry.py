from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable

from .schema import port_compatibility_from_definitions, validate_node_definition

NodeCompilerHook = Callable[["NodeCompileContext", dict[str, Any]], None]
NodeExecutorHook = Callable[..., Any]


@dataclass
class NodeCompileContext:
    compiled: dict[str, Any]
    enabled_steps: set[str]
    export_config: dict[str, Any]
    active_node_ids: set[str]
    active_node_types: set[str]
    execution_order: list[str]
    workflow_definition: dict[str, Any] | None = None

    def enable_step(self, step_id: str) -> None:
        if step_id:
            self.enabled_steps.add(step_id)

    def merge_section(self, section_id: str, patch: dict[str, Any] | None) -> None:
        if not section_id:
            return
        existing = self.compiled.get(section_id)
        if not isinstance(existing, dict):
            existing = {}
        self.compiled[section_id] = {
            **deepcopy(existing),
            **deepcopy(patch or {}),
        }

    def enable_export(self, **patch: Any) -> None:
        self.enable_step("export")
        self.export_config.update(patch)


@dataclass
class NodeRegistry:
    definitions: list[dict[str, Any]]
    compilers: dict[str, NodeCompilerHook]
    executors: dict[str, NodeExecutorHook]
    plugin_errors: list[str] = field(default_factory=list)

    @property
    def definitions_by_type(self) -> dict[str, dict[str, Any]]:
        return {
            str(definition.get("type") or ""): definition
            for definition in self.definitions
            if definition.get("type")
        }


class NodeRegistryBuilder:
    def __init__(self, runtime_profile_definition: dict[str, Any] | None = None) -> None:
        self.runtime_profile_definition = deepcopy(runtime_profile_definition) if isinstance(runtime_profile_definition, dict) else None
        self._definitions: list[dict[str, Any]] = []
        self._definitions_by_type: dict[str, dict[str, Any]] = {}
        self._compilers: dict[str, NodeCompilerHook] = {}
        self._executors: dict[str, NodeExecutorHook] = {}
        self._plugin_errors: list[str] = []
        self._active_plugin_name: str | None = None

    def register_definition(self, definition: dict[str, Any]) -> bool:
        node_type = str(definition.get("type") or "")
        if not node_type:
            message = "Node definition requires a non-empty type"
            if self._active_plugin_name:
                self.add_plugin_error(f"{self._active_plugin_name}: {message}")
                return False
            raise ValueError(message)
        payload = deepcopy(definition)
        errors = validate_node_definition(payload)
        if errors:
            message = "; ".join(errors)
            if self._active_plugin_name:
                self.add_plugin_error(f"{self._active_plugin_name}: {node_type}: {message}")
                return False
            raise ValueError(message)
        existing_index = next(
            (index for index, item in enumerate(self._definitions) if str(item.get("type") or "") == node_type),
            None,
        )
        if existing_index is None:
            self._definitions.append(payload)
        else:
            self._definitions[existing_index] = payload
        self._definitions_by_type[node_type] = payload
        return True

    def register_compiler(self, node_type: str, compiler: NodeCompilerHook) -> None:
        if not node_type:
            raise ValueError("Compiler registration requires a node type")
        self._compilers[str(node_type)] = compiler

    def register_executor(self, executor_id: str, executor: NodeExecutorHook) -> None:
        if not executor_id:
            raise ValueError("Executor registration requires an executor id")
        self._executors[str(executor_id)] = executor

    def register_node(
        self,
        definition: dict[str, Any],
        *,
        compiler: NodeCompilerHook | None = None,
        executor: NodeExecutorHook | None = None,
    ) -> None:
        if not self.register_definition(definition):
            return
        node_type = str(definition.get("type") or "")
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        if compiler is not None:
            self.register_compiler(node_type, compiler)
        if executor is not None and executor_id:
            self.register_executor(executor_id, executor)

    def add_plugin_error(self, message: str) -> None:
        if message:
            self._plugin_errors.append(message)

    def begin_plugin(self, plugin_name: str) -> None:
        self._active_plugin_name = plugin_name

    def end_plugin(self) -> None:
        self._active_plugin_name = None

    def build(self) -> NodeRegistry:
        definitions = [deepcopy(definition) for definition in self._definitions]
        return NodeRegistry(
            definitions=definitions,
            compilers=dict(self._compilers),
            executors=dict(self._executors),
            plugin_errors=list(self._plugin_errors),
        )


def build_node_registry(runtime_profile: dict[str, Any] | None = None) -> NodeRegistry:
    from .nodes.loader import register_builtin_node_modules
    from .plugins import load_node_plugins

    builder = NodeRegistryBuilder(runtime_profile)
    register_builtin_node_modules(builder)
    load_node_plugins(builder)
    return builder.build()


def node_catalog_response(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = build_node_registry(runtime_profile)
    return {
        "schema_version": "1.0",
        "node_definitions": registry.definitions,
        "plugin_errors": registry.plugin_errors,
        "port_compatibility": port_compatibility_from_definitions(registry.definitions),
    }


def builtin_node_definitions(runtime_profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return build_node_registry(runtime_profile).definitions


def builtin_node_definition_map(runtime_profile: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    return build_node_registry(runtime_profile).definitions_by_type

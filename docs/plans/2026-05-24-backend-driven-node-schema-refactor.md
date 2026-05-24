# 后端驱动节点 Schema 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行。每个任务完成后必须运行对应测试并更新复选框。

**Goal:** 将 TextFlow 的节点类型、端口、参数、默认配置、属性面板布局、画布尺寸、默认位置、工具箱元数据、节点模板图和插件节点元数据全部收敛到 Python 节点模块，前端只保留通用脚手架、画布交互、通用控件和安全 slot 宿主。

**Architecture:** Python 后端节点目录 `services/python-engine/app/workflow/nodes/*.py` 是唯一节点真相源；registry 负责扫描内置与插件节点、校验 catalog、序列化给桌面端。React 前端通过 `RegisteredWorkflowNodeDefinition.ui` 动态渲染节点卡片、属性面板和 toolbox，不再维护任何按节点类型硬编码的 schema、尺寸、默认配置或节点列表。复杂交互以通用 slot component 宿主存在，节点 py 只声明 `component_id`、绑定字段和能力需求。

**Tech Stack:** Python 3.11+, pytest, React, TypeScript, Fluent UI, Vite/Vitest, Tauri bridge.

---

## 当前事实

- 后端已经通过 `load_workspace_snapshot()` 返回 `node_definitions`，前端在 workbench toolbox 中已经优先使用 snapshot catalog。
- 前端仍然在 `apps/desktop/src/generatedBuiltinWorkflowNodeSchema.ts` 和 `apps/desktop/src/workflowNodeCatalog.ts` 维护节点标题、端口、尺寸、默认配置、默认位置、工具箱列表、sink 类型、端口类型集合和 starter workflow 辅助逻辑。
- Python 节点模块已经拥有执行相关 definition、compiler 和 executor，但缺少 UI schema、graph schema、slot schema 和统一校验。
- 插件节点现在可以被 registry 扫描并执行，但不能完整驱动前端节点卡片、属性面板、默认布局和工具箱。

## 最终验收标准

- 新增或修改一个节点只需要改对应 Python 节点模块；不需要改任何前端节点 schema 文件。
- 插件节点只要在 Python plugin 中注册完整 definition，就能出现在 toolbox、拖到画布、显示端口、创建默认 config、渲染属性面板并参与运行。
- 前端没有 `node_type === "save_xlsx"` 这类节点类型分支来决定节点 schema、尺寸、默认配置或属性编辑器。
- `generatedBuiltinWorkflowNodeSchema.ts` 被删除；`workflowNodeCatalog.ts` 如保留，只能是动态 catalog adapter，不能包含内置节点声明。
- Python 后端提供 catalog 契约测试，保证所有内置节点和插件节点的 UI schema 可序列化、可校验、可被前端安全渲染。
- 默认工作流、样例工作流和新 flow 模板使用后端 catalog 创建节点实例，不再复制端口、尺寸和默认 config。
- `npm run test:engine:fast`、`npm run test:engine:full`、前端相关 Vitest、一次本地浏览器 smoke test 通过。

## 全局设计规则

- **后端唯一真相：** 节点 py 定义 `type`、`title`、`category`、`description`、`inputs`、`outputs`、`params`、`runtime`、`ui`、`graph`。前端不得再定义这些内容。
- **项目文件兼容：** 已保存 `.tfproj` 中的 `node_type`、`inputs`、`outputs`、`config` 字段继续可读；迁移只改变 catalog 来源，不改已有 workflow 持久化语义。
- **前端脚手架边界：** 前端允许保留通用控件、布局解释器、slot 组件注册表、画布交互、拖拽、连线、缩放、选择态和运行态显示；不允许保留按节点类型硬编码的 UI schema。
- **slot 安全边界：** 后端只声明 `component_id` 和数据绑定，不下发 JSX/HTML/CSS/脚本；前端只渲染白名单 slot。
- **条件表达式安全：** 不使用字符串 eval。条件统一使用 JSON DSL，例如 `{ "field": "mode", "op": "eq", "value": "filtered_subset" }`。
- **彻底迁移但分批落地：** 每批迁移都能运行测试；最终删除静态前端节点 catalog。

---

## 后端 Catalog 契约

每个节点 definition 最终采用下面的稳定形状。已有字段保持兼容，新增 `ui` 和 `graph`。

```python
{
    "type": "save_xlsx",
    "title": "保存 XLSX",
    "category": "output",
    "description": "把上游表格结果整理成 Excel 文件。",
    "hidden_from_toolbox": False,
    "singleton": False,
    "inputs": [
        {"port_id": "table_in", "port_type": "AnyTable", "label": "表格输入", "allow_multiple": True}
    ],
    "outputs": [
        {"port_id": "artifact", "port_type": "ExportArtifact", "label": "导出产物", "artifact_kind": "export"}
    ],
    "params": [
        {"param_id": "file_prefix", "label": "文件名前缀", "kind": "string", "default_value": "tables"},
        {"param_id": "export_xlsx", "label": "启用 Excel 导出", "kind": "boolean", "default_value": True},
    ],
    "runtime": {
        "step_id": "export",
        "executor": "export.save_xlsx",
        "cacheable": False,
        "previewable": True,
        "output_node": True,
        "parallel_safe": True,
    },
    "graph": {
        "size": {"w": 280, "h": 210},
        "default_position": {"x": 5340, "y": 360},
        "toolbox_order": 420,
        "starter_roles": ["table_export_sink"],
    },
    "ui": {
        "schema_version": "1.0",
        "summary_template": "导出为 XLSX：{file_prefix}",
        "layout": [
            {"widget": "text", "config_key": "file_prefix", "label": "文件名前缀"},
            {"widget": "switch", "config_key": "export_xlsx", "label": "启用 Excel 导出"},
        ],
    },
}
```

### Layout Widget 白名单

- `text`：单行文本输入，绑定 string config。
- `textarea`：多行文本输入，绑定 string config。
- `number`：数字输入，支持 `min`、`max`、`step`。
- `switch`：布尔开关。
- `select`：枚举选择，使用 param `options` 或 widget 内 `options`。
- `multi_text`：逗号分隔字符串数组，负责 string[] 与文本互转。
- `condition_rows`：受控条件列表，结构为 `{ field, operator, values }[]`。
- `key_value_rows`：键值规则列表，结构为 `{ key, value, enabled }[]`。
- `group`：视觉分组，只组织 children。
- `row`：横向布局，只组织 children。
- `help`：说明文本，不绑定 config。
- `slot`：白名单复杂组件，必须包含 `component_id`。

### Slot Component 白名单

第一轮保留这些通用 slot。slot 名称不是节点类型名，而是通用交互能力名。

- `corpus_scope_selector`
- `dictionary_binding_selector`
- `dictionary_table_selector`
- `overlay_rule_grid`
- `metadata_condition_builder`
- `named_split_editor`
- `result_table_selector`
- `review_task_selector`
- `threshold_gate_editor`

---

## Task 1: 建立后端 Catalog Schema、Helper 与校验器

**Files:**
- Create: `services/python-engine/app/workflow/schema.py`
- Modify: `services/python-engine/app/workflow/nodes/_common.py`
- Modify: `services/python-engine/app/workflow/registry.py`
- Test: `services/python-engine/tests/test_node_catalog_contract.py`

- [ ] **Step 1: 新增 schema 常量和校验函数**

在 `services/python-engine/app/workflow/schema.py` 中定义：

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

NODE_CATEGORIES = {"input", "process", "analysis", "output", "utility", "legacy"}
PARAM_KINDS = {"boolean", "number", "string", "enum"}
WIDGET_KINDS = {
    "text",
    "textarea",
    "number",
    "switch",
    "select",
    "multi_text",
    "condition_rows",
    "key_value_rows",
    "group",
    "row",
    "help",
    "slot",
}
CONDITION_OPS = {"eq", "neq", "in", "not_in", "truthy", "falsy"}
SLOT_COMPONENTS = {
    "corpus_scope_selector",
    "dictionary_binding_selector",
    "dictionary_table_selector",
    "overlay_rule_grid",
    "metadata_condition_builder",
    "named_split_editor",
    "result_table_selector",
    "review_task_selector",
    "threshold_gate_editor",
}


def default_config_from_params(definition: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for param in definition.get("params") if isinstance(definition.get("params"), list) else []:
        if not isinstance(param, dict):
            continue
        param_id = str(param.get("param_id") or "").strip()
        if param_id and "default_value" in param:
            config[param_id] = deepcopy(param.get("default_value"))
    return config


def validate_node_definition(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    node_type = str(definition.get("type") or "").strip()
    if not node_type:
        errors.append("type is required")
    if str(definition.get("category") or "") not in NODE_CATEGORIES:
        errors.append(f"{node_type}: category is invalid")
    if not isinstance(definition.get("inputs"), list):
        errors.append(f"{node_type}: inputs must be a list")
    if not isinstance(definition.get("outputs"), list):
        errors.append(f"{node_type}: outputs must be a list")
    if not isinstance(definition.get("params"), list):
        errors.append(f"{node_type}: params must be a list")
    if not isinstance(definition.get("runtime"), dict):
        errors.append(f"{node_type}: runtime must be an object")
    graph = definition.get("graph")
    if not isinstance(graph, dict):
        errors.append(f"{node_type}: graph is required")
    else:
        size = graph.get("size")
        position = graph.get("default_position")
        if not isinstance(size, dict) or int(size.get("w", 0) or 0) <= 0 or int(size.get("h", 0) or 0) <= 0:
            errors.append(f"{node_type}: graph.size must contain positive w/h")
        if not isinstance(position, dict) or "x" not in position or "y" not in position:
            errors.append(f"{node_type}: graph.default_position must contain x/y")
    ui = definition.get("ui")
    if not isinstance(ui, dict):
        errors.append(f"{node_type}: ui is required")
    else:
        errors.extend(_validate_layout(node_type, ui.get("layout"), path="ui.layout"))
    return errors


def _validate_layout(node_type: str, layout: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(layout, list):
        return [f"{node_type}: {path} must be a list"]
    for index, item in enumerate(layout):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{node_type}: {item_path} must be an object")
            continue
        widget = str(item.get("widget") or "")
        if widget not in WIDGET_KINDS:
            errors.append(f"{node_type}: {item_path}.widget is invalid")
        if widget in {"group", "row"}:
            errors.extend(_validate_layout(node_type, item.get("children"), path=f"{item_path}.children"))
        if widget == "slot" and str(item.get("component_id") or "") not in SLOT_COMPONENTS:
            errors.append(f"{node_type}: {item_path}.component_id is not registered")
        condition = item.get("condition")
        if condition is not None:
            errors.extend(_validate_condition(node_type, condition, path=f"{item_path}.condition"))
    return errors


def _validate_condition(node_type: str, condition: Any, *, path: str) -> list[str]:
    if not isinstance(condition, dict):
        return [f"{node_type}: {path} must be an object"]
    if not str(condition.get("field") or "").strip():
        return [f"{node_type}: {path}.field is required"]
    if str(condition.get("op") or "eq") not in CONDITION_OPS:
        return [f"{node_type}: {path}.op is invalid"]
    return []
```

- [ ] **Step 2: 在 `_common.py` 增加 UI helper**

给节点 py 提供短 helper，避免每个节点手写重复结构：

```python
def graph(size: tuple[int, int], position: tuple[int, int], *, toolbox_order: int = 1000, starter_roles: list[str] | None = None) -> dict[str, Any]:
    return {
        "size": {"w": int(size[0]), "h": int(size[1])},
        "default_position": {"x": int(position[0]), "y": int(position[1])},
        "toolbox_order": int(toolbox_order),
        "starter_roles": list(starter_roles or []),
    }


def ui(layout: list[dict[str, Any]], *, summary_template: str = "") -> dict[str, Any]:
    payload = {"schema_version": "1.0", "layout": deepcopy(layout)}
    if summary_template:
        payload["summary_template"] = summary_template
    return payload


def field(widget: str, config_key: str, label: str, **extra: Any) -> dict[str, Any]:
    return {"widget": widget, "config_key": config_key, "label": label, **extra}


def slot(component_id: str, label: str = "", **extra: Any) -> dict[str, Any]:
    payload = {"widget": "slot", "component_id": component_id, **extra}
    if label:
        payload["label"] = label
    return payload
```

- [ ] **Step 3: registry 构建时校验节点**

在 `NodeRegistryBuilder.register_definition()` 中调用 `validate_node_definition()`。内置节点校验失败直接 `raise ValueError`；插件节点校验失败通过 `builder.add_plugin_error()` 记录并跳过该节点。为避免破坏当前中间态，这一步先允许 `graph` / `ui` 缺失，只对已经声明了 `ui` 的节点严格校验；Task 6 完成后改为所有节点强制必填。

- [ ] **Step 4: 添加契约测试**

在 `services/python-engine/tests/test_node_catalog_contract.py` 添加测试：

```python
from app.workflow.registry import builtin_node_definitions
from app.workflow.schema import default_config_from_params, validate_node_definition


def test_catalog_definitions_are_serializable_and_have_unique_types():
    definitions = builtin_node_definitions()
    node_types = [str(item["type"]) for item in definitions]
    assert len(node_types) == len(set(node_types))


def test_ui_enabled_definitions_pass_contract_validation():
    errors = []
    for definition in builtin_node_definitions():
        if "ui" in definition or "graph" in definition:
            errors.extend(validate_node_definition(definition))
    assert errors == []


def test_default_config_is_derived_from_param_defaults():
    definition = {
        "params": [
            {"param_id": "file_prefix", "default_value": "tables"},
            {"param_id": "export_xlsx", "default_value": True},
        ]
    }
    assert default_config_from_params(definition) == {"file_prefix": "tables", "export_xlsx": True}
```

- [ ] **Step 5: 验证**

Run:

```powershell
npm run test:engine:fast
```

Expected: PASS。

---

## Task 2: 统一 Catalog API 与 Workspace Snapshot 来源

**Files:**
- Modify: `services/python-engine/app/api/actions/workflows.py`
- Modify: `services/python-engine/app/api/actions/dispatcher.py`
- Modify: `services/python-engine/app/storage/projects.py`
- Modify: `apps/desktop/src-tauri/src/main.rs`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`
- Test: `services/python-engine/tests/test_workspace_cli.py`

- [ ] **Step 1: 后端新增 catalog serializer**

在 `workflows.py` 添加 `action_get_node_catalog()`，返回结构：

```python
{
    "schema_version": "1.0",
    "node_definitions": builtin_node_definitions(),
    "plugin_errors": build_node_registry().plugin_errors,
}
```

`load_workspace_snapshot()` 中的 `node_definitions` 使用同一个 serializer 的 `node_definitions`，不要各自构造。

- [ ] **Step 2: 注册 action**

在 `dispatcher.py` 注册：

```python
"get-node-catalog": action_get_node_catalog,
```

- [ ] **Step 3: Tauri bridge 增加直连命令**

在 `main.rs` 增加 `get_node_catalog` command，内部调用 `engine_request(&app, &state, "get-node-catalog", json!({}))`，并加入 `invoke_handler`。

- [ ] **Step 4: TypeScript bridge 增加接口**

在 `desktopBridge.ts`：

```ts
getNodeCatalog(): Promise<NodeCatalogResponse>;
```

dev engine command map 增加：

```ts
get_node_catalog: { action: "get-node-catalog", mapPayload: () => ({}) }
```

browser-only fallback 返回 `demoWorkspace.node_definitions ?? []`，只用于无引擎测试空态。

- [ ] **Step 5: 测试**

更新 `test_workspace_cli.py`，断言 `get-node-catalog` 和 `load-workspace` 返回的内置节点数量一致，且包含 `save_xlsx`。

Run:

```powershell
npm run test:engine:fast
```

Expected: PASS。

---

## Task 3: 扩展共享类型并建立前端动态 Catalog Adapter

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflow.ts`
- Modify: `apps/desktop/src/store/workspaceStore.tsx`
- Modify: `apps/desktop/src/app/workbenchNavigation.ts`
- Test: `apps/desktop/src/workflowNodeCatalog.test.ts`

- [ ] **Step 1: 添加 shared-types 契约**

在 `RegisteredWorkflowNodeDefinition` 中增加：

```ts
export type WorkflowLayoutConditionOp = "eq" | "neq" | "in" | "not_in" | "truthy" | "falsy";

export interface WorkflowLayoutCondition {
  field: string;
  op: WorkflowLayoutConditionOp;
  value?: unknown;
}

export interface WorkflowNodeLayoutWidget {
  widget:
    | "text"
    | "textarea"
    | "number"
    | "switch"
    | "select"
    | "multi_text"
    | "condition_rows"
    | "key_value_rows"
    | "group"
    | "row"
    | "help"
    | "slot";
  label?: string;
  config_key?: string;
  description?: string;
  options?: WorkflowNodeParamOption[];
  condition?: WorkflowLayoutCondition;
  component_id?: string;
  children?: WorkflowNodeLayoutWidget[];
  min?: number;
  max?: number;
  step?: number;
}

export interface WorkflowNodeGraphDefinition {
  size: { w: number; h: number };
  default_position: { x: number; y: number };
  toolbox_order?: number;
  starter_roles?: string[];
}

export interface WorkflowNodeUiDefinition {
  schema_version: "1.0";
  summary_template?: string;
  layout: WorkflowNodeLayoutWidget[];
}

export interface WorkflowPortCompatibilityCatalog {
  table_sources: WorkflowPortType[];
  renderable_sources: WorkflowPortType[];
  analysis_result_sources: WorkflowPortType[];
  corpus_order: WorkflowPortType[];
}

export interface NodeCatalogResponse {
  schema_version: "1.0";
  node_definitions: RegisteredWorkflowNodeDefinition[];
  plugin_errors: string[];
  port_compatibility?: WorkflowPortCompatibilityCatalog;
}
```

并让 `RegisteredWorkflowNodeDefinition` 包含：

```ts
graph?: WorkflowNodeGraphDefinition;
ui?: WorkflowNodeUiDefinition;
```

- [ ] **Step 2: `workflowNodeCatalog.ts` 改成动态 adapter**

保留文件名减少调用方 churn，但删除内置节点对象。该文件只导出基于后端 `RegisteredWorkflowNodeDefinition[]` 的纯函数：

- `configureWorkflowNodeCatalog(definitions: RegisteredWorkflowNodeDefinition[]): void`
- `workflowNodeDefinitions(): RegisteredWorkflowNodeDefinition[]`
- `workflowNodeDefinition(nodeType: WorkflowNodeType): RegisteredWorkflowNodeDefinition | null`
- `workflowNodeFrameForType(nodeType: WorkflowNodeType): { w: number; h: number }`
- `workflowNodeDefaultPosition(nodeType: WorkflowNodeType): { x: number; y: number }`
- `workflowNodeDefaultConfig(definition): Record<string, unknown>`
- `workflowToolboxDefinitions(): RegisteredWorkflowNodeDefinition[]`
- `sinkNodeTypes(): Set<WorkflowNodeType>`
- `portCompatibilityRules()` 从后端 catalog 派生，不再写死节点类型。

默认 catalog 为空；没有后端 catalog 时，workflow 页面显示“节点目录尚未加载”的空态，而不是回退静态内置 catalog。

- [ ] **Step 3: workspace 加载时配置 catalog**

在 `workspaceStore.tsx` load workspace 成功后调用 `configureWorkflowNodeCatalog(snapshot.node_definitions ?? [])`。保存、创建、打开项目后如果响应包含新 snapshot 或 catalog，也刷新 catalog。

- [ ] **Step 4: `workflow.ts` 改用动态 adapter**

移除对 `builtinWorkflowNodeDefinition`、`defaultNodePositions`、`builtinWorkflowOptionalToolboxNodes`、`sinkNodeTypes` 这些静态对象的依赖。创建节点时从后端 definition 读取：

- label: `definition.title`
- position: `definition.graph.default_position`
- size: `definition.graph.size`
- inputs / outputs: 后端 ports
- config: params default values
- runtime_meta.step_id: `definition.runtime.step_id`

- [ ] **Step 5: 更新 workbench toolbox**

`workbenchNavigation.ts` 只使用 `snapshot.node_definitions` 或动态 adapter 的当前 catalog。删除对静态 `builtinWorkflowToolboxDefinitions()` 的 fallback。

- [ ] **Step 6: 前端单元测试**

把 `workflowNodeCatalog.test.ts` 改为构造一个测试 catalog 并断言：

- adapter 按 `graph.size` 返回 frame。
- adapter 按 `graph.default_position` 返回默认位置。
- adapter 从 `params.default_value` 生成默认 config。
- hidden 节点不出现在 toolbox。

Run:

```powershell
npm run test --workspace apps/desktop -- workflowNodeCatalog.test.ts
```

Expected: PASS。

---

## Task 4: 实现通用动态属性面板与 Slot 宿主

**Files:**
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`
- Create: `apps/desktop/src/features/workflow/DynamicNodeEditor.tsx`
- Create: `apps/desktop/src/features/workflow/workflowSlots.tsx`
- Create: `apps/desktop/src/features/workflow/workflowLayoutConditions.ts`
- Test: `apps/desktop/src/features/workflow/DynamicNodeEditor.test.tsx`

- [ ] **Step 1: 条件解释器**

实现 `workflowLayoutConditions.ts`：

```ts
export function workflowConditionVisible(
  condition: WorkflowLayoutCondition | undefined,
  config: Record<string, unknown>
): boolean {
  if (!condition) return true;
  const value = config[condition.field];
  switch (condition.op) {
    case "eq": return value === condition.value;
    case "neq": return value !== condition.value;
    case "in": return Array.isArray(condition.value) && condition.value.includes(value);
    case "not_in": return Array.isArray(condition.value) && !condition.value.includes(value);
    case "truthy": return Boolean(value);
    case "falsy": return !value;
    default: return false;
  }
}
```

- [ ] **Step 2: 通用控件渲染器**

`DynamicNodeEditor.tsx` 根据 `definition.ui.layout` 递归渲染 widget。所有控件只通过 `context.updateNodeConfig(nodeId, patch)` 修改 config。没有 `ui.layout` 的节点显示只读提示：“该节点未声明属性面板”。

- [ ] **Step 3: Slot 宿主**

`workflowSlots.tsx` 建立白名单：

```ts
export const workflowSlotRenderers = {
  corpus_scope_selector: CorpusScopeSelectorSlot,
  dictionary_binding_selector: DictionaryBindingSelectorSlot,
  dictionary_table_selector: DictionaryTableSelectorSlot,
  overlay_rule_grid: OverlayRuleGridSlot,
  metadata_condition_builder: MetadataConditionBuilderSlot,
  named_split_editor: NamedSplitEditorSlot,
  result_table_selector: ResultTableSelectorSlot,
  review_task_selector: ReviewTaskSelectorSlot,
  threshold_gate_editor: ThresholdGateEditorSlot
} satisfies Record<string, WorkflowSlotRenderer>;
```

未知 `component_id` 渲染为禁用提示，不执行任何动态代码。

- [ ] **Step 4: 移除节点类型 renderer map**

`workflowNodeRegistry.tsx` 中删除 `workflowNodeInlineRenderers: Partial<Record<WorkflowNodeInstance["node_type"], WorkflowNodeInlineRenderer>>`。`renderWorkflowNodeInlineEditor()` 只查 `nodeDefinitionsByType.get(node.node_type)` 并调用 `DynamicNodeEditor`。

- [ ] **Step 5: 保留预览但改成后端可声明**

现有 `renderWorkflowNodePreview()` 中按节点类型显示结果摘要的逻辑先保留为非 schema 阻塞项；本轮新增 `ui.summary_template` 支持，优先用后端模板渲染。后续再把所有按节点类型 preview 分支迁走。最终验收前不得新增新的节点类型 preview 分支。

- [ ] **Step 6: 测试**

Vitest 覆盖：

- string/number/boolean/enum widget 双向绑定。
- condition 控制显示/隐藏。
- slot component_id 只渲染白名单。
- 未知 slot 不抛异常。

Run:

```powershell
npm run test --workspace apps/desktop -- DynamicNodeEditor.test.tsx
```

Expected: PASS。

---

## Task 5: 迁移输出节点与辅助节点作为第一批完整切换

**Files:**
- Modify: `services/python-engine/app/workflow/nodes/save_csv.py`
- Modify: `services/python-engine/app/workflow/nodes/save_xlsx.py`
- Modify: `services/python-engine/app/workflow/nodes/save_png.py`
- Modify: `services/python-engine/app/workflow/nodes/save_html_report.py`
- Modify: `services/python-engine/app/workflow/nodes/note.py`
- Modify: `services/python-engine/app/workflow/nodes/group.py`
- Test: `services/python-engine/tests/test_node_catalog_contract.py`
- Test: `apps/desktop/src/features/workflow/DynamicNodeEditor.test.tsx`

- [ ] **Step 1: 输出节点增加 graph/ui**

给四个输出节点加入 `graph()` 与 `ui()`。示例 `save_xlsx.py`：

```python
"params": [
    string_param("file_prefix", "文件名前缀", "tables"),
    bool_param("export_xlsx", "启用 Excel 导出", True),
],
"graph": graph((280, 210), (5340, 360), toolbox_order=420, starter_roles=["table_export_sink"]),
"ui": ui(
    [
        field("text", "file_prefix", "文件名前缀"),
        field("switch", "export_xlsx", "启用 Excel 导出"),
    ],
    summary_template="XLSX · {file_prefix}",
),
```

- [ ] **Step 2: 辅助节点增加 graph/ui**

`note.py` 使用 `textarea` 绑定 `text`；`group.py` 使用 `text` 绑定 `title`。

- [ ] **Step 3: 前端试运行**

创建测试 catalog，仅包含 `save_xlsx` definition，调用 `addWorkflowNodeByType()`，断言创建出的节点尺寸、位置、config 来自后端。

- [ ] **Step 4: 验证**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop -- workflowNodeCatalog.test.ts DynamicNodeEditor.test.tsx
```

Expected: PASS。

---

## Task 6: 全量迁移内置节点的 graph/ui/default config

**Files:**
- Modify: `services/python-engine/app/workflow/nodes/*.py`
- Modify: `services/python-engine/app/workflow/nodes/_common.py`
- Modify: `services/python-engine/tests/test_node_catalog_contract.py`
- Modify: `services/python-engine/tests/test_new_flow_workflow.py`

- [ ] **Step 1: 按批次迁移节点**

按下面顺序迁移，每批后运行 `npm run test:engine:fast`：

1. 纯参数处理节点：`clean_text.py`、`normalize_text.py`、`tokenize.py`、`filter_terms.py`、`focus_terms.py`
2. 纯参数分析节点：`frequency_statistics.py`、`term_document_analysis.py`、`term_year_analysis.py`、`cooccurrence_analysis.py`、`similarity_analysis.py`、`feature_term_selection.py`、`keyword_extraction.py`
3. 聚类/主题/图分析节点：`keyword_clustering.py`、`topic_modeling.py`、`document_clustering.py`、`build_network.py`、`graph_metrics.py`、`community_detection.py`、`main_path_analysis.py`、`link_prediction.py`
4. 机构和技术节点：`institution_keyword_analysis.py`、`institution_topic_analysis.py`、`technology_indicators.py`、`technology_classification.py`
5. 语料处理节点：`merge_corpora.py`、`filter_by_metadata.py`、`deduplicate_documents.py`、`sample_corpus.py`、`split_corpus.py`、`bucket_by_time.py`
6. 资源和控制节点：`corpus_input.py`、`dictionary_input.py`、`select_dictionary_tables.py`、`overlay_dictionary_rules.py`、`conditional_router.py`、`result_gate.py`、`manual_review_gate.py`
7. legacy 节点：`load_project_corpus.py`、`filter_corpus.py`、`project_dictionary_set.py`、`analyze_corpus.py`、`export_results.py`

- [ ] **Step 2: 资源和复杂节点使用 slot**

这些节点不得在前端通过 node type 分支实现属性面板：

- `corpus_input`: `slot("corpus_scope_selector")`
- `dictionary_input`: `slot("dictionary_binding_selector")`
- `select_dictionary_tables`: `slot("dictionary_table_selector")`
- `overlay_dictionary_rules`: `slot("overlay_rule_grid")`
- `filter_by_metadata`: `slot("metadata_condition_builder")`
- `split_corpus`: `slot("named_split_editor")`
- `join_results`: `slot("result_table_selector")`
- `manual_review_gate`: `slot("review_task_selector")`
- `result_gate`: `slot("threshold_gate_editor")`

- [ ] **Step 3: 强制所有节点拥有 ui/graph**

Task 1 中 registry 的宽松校验改为强制校验。`test_node_catalog_contract.py` 增加：

```python
def test_all_builtin_nodes_have_graph_and_ui_schema():
    errors = []
    for definition in builtin_node_definitions():
        errors.extend(validate_node_definition(definition))
    assert errors == []
```

- [ ] **Step 4: 更新布局不重叠测试**

`test_new_flow_workflow.py` 不再从 `workflowNodeCatalog.ts` 正则提取尺寸，改为从 `builtin_node_definitions()` 的 `graph.size` 读取尺寸。

- [ ] **Step 5: 验证**

Run:

```powershell
npm run test:engine:fast
```

Expected: PASS。

---

## Task 7: 后端接管默认工作流和模板图节点实例创建

**Files:**
- Create: `services/python-engine/app/workflow/catalog.py`
- Modify: `services/python-engine/app/domain/workflow.py`
- Modify: `services/python-engine/app/workflow/templates.py`
- Modify: `services/python-engine/tests/test_new_flow_workflow.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`

- [ ] **Step 1: 新增后端节点实例工厂**

`workflow/catalog.py` 提供：

- `definition_by_type(runtime_profile=None) -> dict[str, dict[str, Any]]`
- `default_node_config(definition) -> dict[str, Any]`
- `new_workflow_node(node_type, node_id, runtime_profile=None, config=None) -> dict[str, Any]`
- `catalog_position(node_type) -> dict[str, int]`
- `catalog_size(node_type) -> dict[str, int]`

`new_workflow_node()` 必须从 definition 复制 title、ports、params defaults、runtime step、graph size、graph default_position。

- [ ] **Step 2: 改写 `workflow/templates.py`**

`_new_node()` 删除本地 `size={"w": 230, "h": 190}` 和 `_default_node_config()` 实现，改为调用 `new_workflow_node()`。`NEW_FLOW_NODE_POSITIONS` 删除，位置来自节点 `graph.default_position`；只有同类型重复节点才按偏移规则处理。

- [ ] **Step 3: 改写 `domain/workflow.py` 默认工作流**

`default_workflow_definition()` 中删除内置 node port/config/size 复制，改为用 catalog factory 创建节点。保留 edge 拓扑构建，但所有端口名通过 definition 验证存在。

- [ ] **Step 4: 测试**

Run:

```powershell
npm run test:engine:full
```

Expected: PASS。这里触及默认项目、样例和模板 bootstrap，必须跑 full。

---

## Task 8: 前端删除静态节点 schema，改为纯脚手架

**Files:**
- Delete: `apps/desktop/src/generatedBuiltinWorkflowNodeSchema.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflow.ts`
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/app/workbenchNavigation.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.test.ts`
- Modify: `services/python-engine/tests/test_node_catalog_parity.py`（重写为后端 catalog 契约测试，不再读取 TS 文件）

- [ ] **Step 1: 删除生成静态 schema 文件**

删除 `generatedBuiltinWorkflowNodeSchema.ts`。任何 import 失败都必须改为动态 catalog adapter。

- [ ] **Step 2: 删除前端节点清单和位置清单**

`workflowNodeCatalog.ts` 中不得出现内置节点 key，例如 `save_xlsx:`、`corpus_input:`、`keyword_extraction:`。保留纯函数、类型转换、排序和兜底空态。

- [ ] **Step 3: 删除 parity 正则测试，替换为后端契约测试**

删除 `test_ts_generated_workflow_node_schema_matches_builtin_python_definitions()`。保留并强化这些 Python 测试：

- 内置节点模块扫描完整。
- 所有非 utility 节点 executor 可解析。
- 所有节点 ui/graph 契约有效。
- 插件节点 catalog 可序列化。

- [ ] **Step 4: 前端 lint 防回归测试**

新增或更新 Vitest，读取源文件文本并断言：

```ts
expect(source).not.toContain("save_xlsx:");
expect(source).not.toContain("corpus_input:");
expect(source).not.toContain("workflowNodeInlineRenderers");
```

这个测试只针对前端脚手架核心文件，防止静态 catalog 回流。

- [ ] **Step 5: 验证**

Run:

```powershell
npm run test --workspace apps/desktop
npm run test:engine:fast
```

Expected: PASS。

---

## Task 9: 插件节点完整支持

**Files:**
- Modify: `services/python-engine/app/workflow/plugins.py`
- Modify: `services/python-engine/app/workflow/registry.py`
- Create: `services/python-engine/tests/test_plugin_node_catalog.py`
- Create: `apps/desktop/src/features/workflow/pluginNodeCatalog.test.ts`

- [ ] **Step 1: 插件节点校验与错误隔离**

插件节点注册时使用同一 `validate_node_definition()`。校验失败的插件节点不进入 catalog，不影响内置节点和其他插件节点；错误写入 `plugin_errors` 并随 `get-node-catalog` 返回。

- [ ] **Step 2: 插件测试样例**

Python 测试中创建临时 plugin：

```python
def register_nodes(builder):
    builder.register_node(
        {
            "type": "demo_plugin_node",
            "title": "Demo Plugin Node",
            "category": "analysis",
            "description": "Plugin node with dynamic UI.",
            "inputs": [],
            "outputs": [{"port_id": "demo_table", "port_type": "AnyTable", "label": "Demo Table"}],
            "params": [
                {"param_id": "limit", "label": "Limit", "kind": "number", "default_value": 10}
            ],
            "runtime": {
                "step_id": "analysis",
                "executor": "plugin.demo",
                "cacheable": False,
                "previewable": True,
                "output_node": False,
            },
            "graph": {
                "size": {"w": 320, "h": 220},
                "default_position": {"x": 120, "y": 220},
                "toolbox_order": 900,
            },
            "ui": {
                "schema_version": "1.0",
                "layout": [{"widget": "number", "config_key": "limit", "label": "Limit"}],
            },
        },
        executor=lambda _context, _node, _inputs: {"demo_table": [{"term": "plugin"}]},
    )
```

断言：

- catalog 包含 plugin 节点。
- default config 为 `{"limit": 10}`。
- workflow runner 能执行 plugin 节点。
- workspace snapshot 能返回 plugin definition。

- [ ] **Step 3: 前端插件测试**

前端构造上述 plugin definition，验证：

- toolbox 出现 plugin。
- `addWorkflowNodeByType()` 创建节点。
- `DynamicNodeEditor` 渲染 number 控件并写回 config。

- [ ] **Step 4: 验证**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop -- pluginNodeCatalog.test.ts
```

Expected: PASS。

---

## Task 10: 后端下发端口兼容和 graph 运行辅助元数据

**Files:**
- Modify: `services/python-engine/app/workflow/schema.py`
- Modify: `services/python-engine/app/workflow/registry.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/workflow.ts`
- Test: `services/python-engine/tests/test_port_compatibility.py`
- Test: `apps/desktop/src/workflow.test.ts`

- [ ] **Step 1: 后端 catalog 增加 port families**

在 catalog response 增加：

```python
"port_compatibility": {
    "table_sources": ["FrequencyTable", "TermDocumentTable", "AnyTable"],
    "renderable_sources": ["FrequencyTable", "KeywordTable", "AnalysisBundle"],
    "analysis_result_sources": ["FrequencyTable", "KeywordTable", "AnalysisBundle"],
    "corpus_order": ["CorpusTable", "ProjectCorpus", "ScopedCorpus", "CleanCorpus", "NormalizedCorpus", "TokenCorpus", "FilteredTokenCorpus"],
}
```

这些集合由后端根据节点 outputs 的 `port_type`、`result_bundle_key`、`png_chart_ids` 派生。

- [ ] **Step 2: 前端连接校验使用后端规则**

`workflowPortCompatible()` 不再维护静态 port 类型集合，改用 catalog response。缺少 catalog 时只允许完全相同 port type，保证空态安全。

- [ ] **Step 3: sink 类型使用后端 runtime**

`isSinkNode()` 使用 `definition.runtime.output_node === true`，不再维护 `save_csv/save_xlsx/save_png/save_html_report/export_results` 集合。

- [ ] **Step 4: 验证**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop -- workflow.test.ts
```

Expected: PASS。

---

## Task 11: 文档与迁移说明

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/workflow-runtime.md`
- Modify: `docs/development.md`
- Create: `docs/node-catalog-schema.md`

- [ ] **Step 1: 写节点 catalog 文档**

`docs/node-catalog-schema.md` 说明：

- 节点 py 是唯一真相源。
- definition 字段说明。
- layout widget 白名单。
- slot 白名单。
- 插件节点最小示例。
- 禁止前端新增静态节点 schema。

- [ ] **Step 2: 更新 architecture**

`docs/architecture.md` 的 workflow 节点章节更新为：

- registry 扫描内置和插件节点。
- catalog 同时服务运行时、默认图、工具箱和属性面板。
- 前端只做动态脚手架。

- [ ] **Step 3: 更新 development**

加入新增节点流程：

1. 在 `services/python-engine/app/workflow/nodes/<node>.py` 定义 node。
2. 添加 compiler/executor。
3. 添加 params/graph/ui。
4. 运行 `npm run test:engine:fast`。
5. 如果改默认样例或模板图，运行 `npm run test:engine:full`。

- [ ] **Step 4: 验证 docs**

Run:

```powershell
rg -n "generatedBuiltinWorkflowNodeSchema|静态 TS|workflowNodeCatalog.ts.*节点声明" docs apps services
```

Expected: 不再出现把前端静态 schema 描述为真相源的文档。

---

## Task 12: 最终验证与浏览器 Smoke

**Files:**
- No source changes unless verification exposes defects.

- [ ] **Step 1: 全量测试**

Run:

```powershell
npm run test:engine:fast
npm run test:engine:full
npm run test --workspace apps/desktop
```

Expected: all PASS。

- [ ] **Step 2: 启动本地前端**

Run:

```powershell
npm run dev --workspace apps/desktop -- --host 127.0.0.1 --port 5174 --strictPort
```

如果 5174 被占用，选择下一个空闲端口并记录实际 URL。

- [ ] **Step 3: 使用 Codex Browser 冒烟**

打开 `http://127.0.0.1:5174/`，验证：

- app 正常加载。
- 节点工具箱来自后端 catalog。
- 新建/打开 workflow 后可拖入 `save_xlsx`。
- `save_xlsx` 属性面板由 `ui.layout` 渲染。
- 复杂 slot 节点如 `corpus_input`、`dictionary_input` 可打开并编辑。
- 插件测试节点在配置 plugin env 后可出现在 toolbox。
- 画布拖拽、连线、缩放不报错。
- 小窗口宽度下属性面板文字不重叠。

- [ ] **Step 4: 最终源码扫描**

Run:

```powershell
rg -n "generatedBuiltinWorkflowNodeSchema|workflowNodeInlineRenderers|defaultNodePositions|builtinWorkflowNodeSchema|save_xlsx:" apps packages services
```

Expected:

- `generatedBuiltinWorkflowNodeSchema` 无结果。
- `workflowNodeInlineRenderers` 无结果。
- `defaultNodePositions` 无结果。
- `builtinWorkflowNodeSchema` 无结果。
- `save_xlsx:` 不出现在前端 schema 或 catalog 文件中；Python 节点模块、测试 fixture 和文档示例中允许出现。

---

## 执行顺序建议

1. Task 1-2 建立后端契约和 API。
2. Task 3-4 建立前端动态脚手架。
3. Task 5 迁移一小批节点验证端到端。
4. Task 6-7 全量迁移内置节点和模板图。
5. Task 8 删除静态前端 schema。
6. Task 9 完整打通插件节点。
7. Task 10 把连接规则和 sink 元数据也改为后端 catalog 派生。
8. Task 11-12 完成文档和最终验证。

## 风险与应对

- **风险：默认 config 依赖 runtime_profile。** 处理方式：后端 `node_definition(runtime_profile)` 已支持传入 profile，catalog serializer 用当前默认 profile 生成 defaults；项目加载时仍以已保存 node config 为准。
- **风险：一次性删除静态 catalog 影响大量前端函数。** 处理方式：先把 `workflowNodeCatalog.ts` 改成同名动态 adapter，减少 import churn；等测试通过后删除静态数据。
- **风险：复杂节点属性面板行为回退。** 处理方式：先把复杂交互抽成通用 slot，并用 `component_id` 声明挂载；slot 内不得判断 node type。
- **风险：插件节点 schema 不可信。** 处理方式：后端校验、前端白名单 slot、无 eval 条件表达式、未知 widget/slot 安全降级。
- **风险：样例和默认图仍复制旧端口。** 处理方式：Task 7 强制默认 workflow 和 new flow template 使用后端 catalog 工厂创建节点。

## 自检清单

- [ ] 每个任务都有明确文件范围和测试命令。
- [ ] 最终状态删除静态 TS 节点 schema。
- [ ] 插件节点被作为一等目标测试。
- [ ] 默认工作流、模板图、端口兼容、sink 判断都从后端 catalog 派生。
- [ ] 前端只剩脚手架、通用控件、slot 宿主和画布交互。

# 节点 Catalog Schema

TextFlow 的 workflow 节点 catalog 由 Python 后端驱动。内置节点和插件节点都通过同一套 definition 进入 registry，再序列化给桌面端。

## 真相源

节点的唯一真相源是：

```text
services/python-engine/app/workflow/nodes/*.py
plugins/nodes/*.py
```

前端只保留通用画布、拖拽、连线、动态属性面板、slot 宿主和安全降级逻辑。不要在前端新增内置节点清单、节点尺寸、默认位置、默认配置或按节点类型分支的属性编辑器。

## Definition 字段

每个节点 definition 至少包含：

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
        {"param_id": "file_prefix", "label": "文件名前缀", "kind": "string", "default_value": "tables"}
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
        "summary_template": "XLSX · {file_prefix}",
        "layout": [
            {"widget": "text", "config_key": "file_prefix", "label": "文件名前缀"}
        ],
    },
}
```

`params[*].default_value` 会生成新节点的默认 `config`。`graph` 驱动画布尺寸、默认位置和工具箱排序。`runtime.output_node` 驱动前端和后端的 sink 判断。输出口上的 `result_bundle_key`、`png_chart_ids`、`artifact_kind` 会参与结果绑定、端口兼容和 artifact 写入。

## Layout Widgets

`ui.layout` 只允许下面这些 widget：

- `text`
- `textarea`
- `number`
- `switch`
- `select`
- `multi_text`
- `condition_rows`
- `key_value_rows`
- `group`
- `row`
- `help`
- `slot`

条件显示使用 JSON DSL，不允许字符串 eval：

```python
{"field": "mode", "op": "eq", "value": "filtered_subset"}
```

支持的 `op` 是 `eq`、`neq`、`in`、`not_in`、`truthy`、`falsy`。

## Slot 白名单

slot 只声明 `component_id`，不下发 JSX、HTML、CSS 或脚本。前端只渲染白名单组件，未知 slot 显示安全提示。

当前白名单：

- `corpus_scope_selector`
- `dictionary_binding_selector`
- `dictionary_table_selector`
- `overlay_rule_grid`
- `metadata_condition_builder`
- `named_split_editor`
- `result_table_selector`
- `review_task_selector`
- `threshold_gate_editor`

## 插件节点示例

插件文件放在 `plugins/nodes` 或 `TEXTFLOW_NODE_PLUGIN_DIR` 指向的目录：

```python
def _execute(_context, _node, _inputs):
    return {"demo_table": [{"term": "plugin"}]}


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
        executor=_execute,
    )
```

registry 会校验插件 definition。无效插件节点会被跳过，错误进入 `plugin_errors`，不会影响内置节点或其他插件节点。

## 验证

常用验证命令：

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop -- workflowNodeCatalog.test.ts DynamicNodeEditor.test.tsx pluginNodeCatalog.test.tsx workflow.test.ts
```

修改默认样例、模板图、导出或 bootstrap 相关路径时，再运行：

```powershell
npm run test:engine:full
```

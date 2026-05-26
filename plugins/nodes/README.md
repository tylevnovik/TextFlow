# TextFlow Python Node Plugins

`plugins/nodes` 用来放 TextFlow 运行时扫描的本地纯 Python 节点插件。

## 当前扫描路径

sidecar 启动时会按顺序尝试扫描：

- 环境变量 `TEXTFLOW_NODE_PLUGIN_DIR` 指向的目录
- 仓库根目录下的 `plugins/nodes`
- 打包后 sidecar 同级目录下的 `plugins/nodes`

## 插件文件入口

每个插件文件应导出以下任一函数：

- `register_nodes(builder)`
- `register(builder)`

如果入口函数接收两个参数，第二个参数会传入当前 runtime profile 基线配置。

## builder 可注册的内容

插件可以注册：

- `builder.register_definition(definition)`
- `builder.register_compiler(node_type, compiler_hook)`
- `builder.register_executor(executor_id, executor_hook)`
- `builder.register_node(definition, compiler=..., executor=...)`

如果插件节点会产生可浏览的中间表格、对象或导出摘要，输出口必须显式声明产物类型。推荐使用：

```python
from app.workflow.plugins import artifact_output_port

artifact_output_port("plugin_table", label="插件表格", artifact_kind="table")
```

`artifact_kind` 当前建议使用 `table`、`object`、`csv`、`xlsx`、`png`、`html` 或插件自定义的短字符串。executor 仍然只需要在该输出口返回普通 JSON 可序列化 payload；native DAG 会把 payload 写入 run artifact store，并在 `run_record.artifacts` 与 `manifest.artifact_records` 中登记可懒加载的 handle。

## 当前运行时行为

插件节点现在已经能参与三件事：

1. 返回给前端工具箱
   sidecar 会把插件 definition 一起放进 `node_definitions`，前端可直接显示。

2. 影响运行时基线
   如果插件提供 compiler hook，它可以把节点配置编译回当前 runtime profile。

3. 进入 native DAG
   如果插件同时提供 executor，且当前 workflow 满足 native DAG 条件，它也可以进入原生节点执行链。

当前 workflow 运行统一进入 native DAG。插件节点如果要被实际执行，必须注册 definition 中声明的 executor；只有 compiler、没有 executor 的插件节点可以影响运行时编译，但不能作为可执行节点进入工作流主链。

## 最小示例

```python
def _compile(context, node):
    context.merge_section("analysis", {"top_n": int(node.get("config", {}).get("top_n", 64))})
    context.enable_step("analysis")


from app.workflow.plugins import artifact_output_port


def register_nodes(builder):
    builder.register_node(
        {
            "type": "demo_plugin_node",
            "title": "Demo Plugin Node",
            "category": "analysis",
            "description": "Loaded from plugins/nodes.",
            "inputs": [],
            "outputs": [artifact_output_port("plugin_out", port_type="KeywordTable", label="插件输出", artifact_kind="table")],
            "params": [{"param_id": "top_n", "label": "Top N", "kind": "number", "default_value": 64}],
            "runtime": {
                "step_id": "analysis",
                "executor": "plugin.demo",
                "cacheable": False,
                "previewable": False,
                "output_node": False,
            },
        },
        compiler=_compile,
        executor=lambda *_args, **_kwargs: {"plugin_out": [{"term": "plugin", "score": 1.0}]},
    )
```

## 当前边界

- 仅支持本地纯 Python 插件。
- 当前没有签名校验、权限模型或隔离执行。
- 前端对内置节点有更丰富的专用体验，插件节点当前主要走 schema 驱动表单。
- 当前不提供面向终端用户的插件市场或局部重跑 UI。

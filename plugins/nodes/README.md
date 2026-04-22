# TextFlow Python Node Plugins

`plugins/nodes` 用来放 TextFlow 运行时扫描的本地纯 Python 节点插件。

## 当前扫描路径

sidecar 启动时会按顺序尝试扫描：

- 仓库根目录下的 `plugins/nodes`
- 打包后 sidecar 同级目录下的 `plugins/nodes`
- 环境变量 `TEXTFLOW_NODE_PLUGIN_DIR` 指向的目录

## 插件文件入口

每个插件文件应导出以下任一函数：

- `register_nodes(builder)`
- `register(builder)`

如果入口函数接收两个参数，第二个参数会传入当前 pipeline 基线配置。

## builder 可注册的内容

插件可以注册：

- `builder.register_definition(definition)`
- `builder.register_compiler(node_type, compiler_hook)`
- `builder.register_executor(executor_id, executor_hook)`
- `builder.register_node(definition, compiler=..., executor=...)`

## 当前运行时行为

插件节点现在已经能参与三件事：

1. 返回给前端工具箱  
   sidecar 会把插件 definition 一起放进 `node_definitions`，前端可直接显示。

2. 影响兼容 pipeline  
   如果插件提供 compiler hook，它可以把节点配置编译回兼容 pipeline。

3. 进入 native DAG  
   如果插件同时提供 executor，且当前 workflow 满足 native DAG 条件，它也可以进入原生节点执行链。

如果插件节点只有 compiler、没有 executor，或者图中混入 legacy 聚合节点，那么整个 workflow 仍可能回退到兼容 bridge 路径。

## 最小示例

```python
def _compile(context, node):
    context.merge_section("analysis", {"top_n": int(node.get("config", {}).get("top_n", 64))})
    context.enable_step("analysis")


def register_nodes(builder):
    builder.register_node(
        {
            "type": "demo_plugin_node",
            "title": "Demo Plugin Node",
            "category": "analysis",
            "description": "Loaded from plugins/nodes.",
            "inputs": [],
            "outputs": [{"port_id": "plugin_out", "port_type": "KeywordTable", "label": "插件输出"}],
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
        executor=lambda *_args, **_kwargs: {"status": "ok"},
    )
```

## 当前边界

- 仅支持本地纯 Python 插件。
- 当前没有签名校验、权限模型或隔离执行。
- 前端对内置节点有更丰富的专用体验，插件节点当前主要走 schema 驱动表单。
- 当前不提供面向终端用户的插件市场或局部重跑 UI。

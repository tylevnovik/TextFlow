# TextFlow Studio Workflow Schema（V2 迁移版）

## 1. 文档目标

本文档定义 V2 节点工作流的持久化结构，以及它与当前 `ProjectManifest.pipeline` 的兼容关系。

设计原则：

- 旧 `.tfproj` 项目可无损升级
- 当前执行器继续可用
- 新字段能为后续多 workflow 和节点运行时预留空间
- 不把当前尚未实现的 artifact registry、node cache 伪装成已落地能力

## 2. 当前项目结构事实

当前 `ProjectManifest` 的核心流程字段为：

- `pipeline`
- `run_history`
- `results`

当前模型特点：

- 单项目只保存一个 `pipeline`
- `results` 是项目级最新结果快照
- `run_history` 是 run 级记录
- 没有 `workflow_id`
- 没有节点定义主表
- 没有 artifact registry

因此 V2 需要采用“双轨结构”，而不是直接删掉 `pipeline`。

## 3. V2 Phase 1 持久化策略

V2 Phase 1 建议在 `ProjectManifest` 中新增：

- `workflow_definitions`
- `active_workflow_id`

同时保留：

- `pipeline`
- `run_history`
- `results`

其中：

- `workflow_definitions` 是新的编辑真相
- `pipeline` 是当前执行兼容层
- `run_history` 仍是运行记录真相
- `results` 仍是项目内最新结果快照

## 4. 建议的 ProjectManifest 结构

```json
{
  "id": "project-123",
  "schema_version": "2.0.0",
  "name": "示例项目",
  "description": "",
  "created_at": "",
  "updated_at": "",
  "version": "0.2.0",
  "source_files": [],
  "settings": {},
  "paths": {},
  "import_template": {},
  "dictionary_set": {},
  "pipeline": {},
  "workflow_definitions": [],
  "active_workflow_id": "wf-default",
  "run_history": [],
  "results": {}
}
```

### 4.1 为什么 `pipeline` 继续保留

因为当前后端、测试和运行记录体系都围绕它展开。V2 首版应采用：

- 编辑时写 `workflow_definitions`
- 运行时把 `active_workflow` 编译为 `pipeline`
- 存盘时同时保留两份结构

## 5. WorkflowDefinition

首版建议结构：

```json
{
  "workflow_id": "wf-default",
  "name": "默认工作流",
  "version": "1.0.0",
  "graph_mode": "single_chain_dag",
  "source": "migrated_from_pipeline",
  "meta": {
    "template_id": "standard_analysis",
    "output_bundle_id": "full_report"
  },
  "nodes": [],
  "edges": [],
  "groups": [],
  "viewport": {
    "x": 0,
    "y": 0,
    "zoom": 1
  },
  "created_at": "",
  "updated_at": ""
}
```

说明：

- `graph_mode` 首版不要写成泛化 `dag`，而应明确是 `single_chain_dag`
- `source` 用于标识是手工新建还是由旧 pipeline 自动迁移
- `meta.template_id` 对应现有 `recipe_id`

## 6. NodeInstance

首版节点实例建议结构：

```json
{
  "node_id": "node-clean-text",
  "node_type": "clean_text",
  "label": "基础清洗",
  "position": { "x": 820, "y": 220 },
  "inputs": [
    { "port_id": "corpus_in", "port_type": "ScopedCorpus" }
  ],
  "outputs": [
    { "port_id": "clean_corpus", "port_type": "CleanCorpus" }
  ],
  "config": {
    "strip_html": true,
    "strip_urls": true
  },
  "ui_state": {
    "collapsed": false,
    "bypassed": false
  },
  "runtime_meta": {
    "step_id": "cleaning",
    "node_impl_version": "1.0.0"
  }
}
```

### 6.1 首版支持的 `node_type`

- `load_project_corpus`
- `filter_corpus`
- `project_dictionary_set`
- `clean_text`
- `normalize_text`
- `tokenize`
- `apply_dictionary_rules`
- `filter_terms`
- `analyze_corpus`
- `export_results`
- `note`
- `group`

### 6.2 节点配置来源

- 文本处理节点的 `config` 直接映射到现有 `pipeline.cleaning / normalization / tokenization / dictionary / filtering / analysis / export`
- `filter_corpus` 的 `config` 映射到 `pipeline.run_scope`
- `project_dictionary_set` 默认只引用项目词表，不复制内容到 workflow 中

## 7. Edge

```json
{
  "edge_id": "edge-003",
  "from_node": "node-tokenize",
  "from_port": "token_corpus",
  "to_node": "node-apply-dictionary",
  "to_port": "token_corpus_in"
}
```

首版校验规则：

- 一个工作流只能有一条主执行链
- `analyze_corpus` 只能出现一次
- `export_results` 最多出现一次
- `note` 和 `group` 不参与可执行链校验

## 8. Port 类型

首版只定义必要类型：

```json
[
  "ProjectCorpus",
  "ScopedCorpus",
  "DictionarySet",
  "CleanCorpus",
  "NormalizedCorpus",
  "TokenCorpus",
  "FilteredTokenCorpus",
  "AnalysisBundle",
  "AuditTable",
  "ExportBundle"
]
```

## 9. RunRecord 扩展建议

当前 `RunRecord` 不区分工作流来源。V2 建议新增：

```json
{
  "workflow_id": "wf-default",
  "workflow_name": "默认工作流",
  "workflow_hash": "sha256:..."
}
```

说明：

- `workflow_id` 用于追踪 run 来自哪个 workflow
- `workflow_hash` 用于判断运行时图结构与参数快照对应的唯一性
- 这三个字段可以在 Phase 1 就加，不依赖节点级执行器

## 10. 线性 pipeline 到 workflow 的迁移规则

## 10.1 节点映射

| V1 字段 / 步骤 | V2 节点 |
| --- | --- |
| `run_scope` | `filter_corpus` |
| `cleaning` | `clean_text` |
| `normalization` | `normalize_text` |
| `tokenization` | `tokenize` |
| `dictionary` | `apply_dictionary_rules` |
| `filtering` | `filter_terms` |
| `analysis` | `analyze_corpus` |
| `export` | `export_results` |

`ingestion` 不再迁移为可执行导入节点，而是隐含在 `load_project_corpus` 中，因为当前运行时是读取项目已有语料，而不是在 run 内导入文件。

## 10.2 启用状态迁移

- `enabled_steps` 不包含的步骤，迁移后节点 `ui_state.bypassed = true`
- 必需步骤如果在旧项目中缺失，迁移时仍应补齐节点，但标记为系统固定节点

## 10.3 顺序迁移

- `execution_order` 决定默认 edge 顺序
- 如果旧项目顺序异常，迁移器要按当前运行器允许的顺序修正为合法链路

## 10.4 配方迁移

- `recipe_id` 迁移到 `workflow.meta.template_id`
- `output_bundle_id` 迁移到 `workflow.meta.output_bundle_id`

## 11. 首版不写入 schema 的内容

以下字段方向正确，但首版不建议正式落盘：

- `artifact_registry`
- `workflow_runs`
- `node_templates`
- `workflow_templates`
- `cache_entries`

原因：

- 当前后端还没有节点级 artifact 和 cache 的真实写入逻辑
- 现阶段写这些字段，只会引入“结构存在、能力不存在”的假一致性

## 12. Phase 1 结论

V2 Phase 1 的 schema 目标不是完全换骨，而是建立稳定的兼容层：

- `workflow_definitions` 负责新编辑形态
- `pipeline` 负责旧执行形态
- `run_history` 和 `results` 暂时继续沿用

这能保证：

- 旧项目可升级
- 当前测试仍有清晰基线
- 后续真正的节点执行器和 artifact registry 有明确插入点

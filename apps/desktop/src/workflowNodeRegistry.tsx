import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Button } from "@fluentui/react-components";
import type {
  CorpusItem,
  WorkflowRuntimeProfile,
  ProjectManifest,
  RegisteredWorkflowNodeDefinition,
  RunRecord,
  RunScopeDefinition,
  WorkflowNodeInstance
} from "@textflow/shared-types";

interface WorkflowNodeEditorContext {
  node: WorkflowNodeInstance;
  project: ProjectManifest;
  snapshot: { corpus: CorpusItem[] };
  latestRun?: RunRecord;
  draftRuntimeProfile: WorkflowRuntimeProfile;
  loading: boolean;
  nodeDefinitionsByType: Map<string, RegisteredWorkflowNodeDefinition>;
  availableSources: string[];
  availableInstitutions: string[];
  availableCategories: string[];
  documentPickerQuery: string;
  setDocumentPickerQuery: Dispatch<SetStateAction<string>>;
  setActivePage: (page: "dictionaries") => void;
  bindDictionaryTableToWorkflow: (tableId: string) => void;
  runScopeForNode: (node: WorkflowNodeInstance | null | undefined) => RunScopeDefinition;
  runScopeSummary: (scope: RunScopeDefinition, totalCount: number, matchedCount: number) => string;
  corpusMatchesRunScope: (item: CorpusItem, scope: RunScopeDefinition) => boolean;
  updateNodeConfig: (nodeId: string, patch: Record<string, unknown>) => void;
  updateRunScope: (nodeId: string, patch: Partial<RunScopeDefinition>) => void;
  toggleScopeArrayValue: (
    nodeId: string,
    field: "source_values" | "institution_values" | "category_values",
    value: string
  ) => void;
  toggleSelectedDocument: (nodeId: string, docId: string) => void;
  enabledDictionaryEntryCount: (dictionarySet: ProjectManifest["dictionary_set"]) => number;
}

const dictionaryBindingGroups = [
  {
    title: "切词词典",
    items: [
      { key: "use_custom_lexicon", label: "自定义词典", sheet: "custom_lexicon" },
      { key: "use_phrase_lexicon", label: "短语词典", sheet: "phrase_lexicon" }
    ]
  },
  {
    title: "标准化规则",
    items: [
      { key: "apply_regex_rules", label: "Regex 规则", sheet: "regex_rules" }
    ]
  },
  {
    title: "规则应用",
    items: [
      { key: "apply_standard_terms", label: "标准词", sheet: "standard_terms" },
      { key: "apply_synonym_map", label: "同义词", sheet: "synonym_map" },
      { key: "apply_near_synonym_map", label: "近义词", sheet: "near_synonym_map" },
      { key: "apply_stopwords", label: "停用词", sheet: "stopwords" },
      { key: "apply_exclusion_terms", label: "排除词", sheet: "exclusion_terms" }
    ]
  }
] as const;

interface OverlayRuleRow {
  kind: string;
  source: string;
  target: string;
  enabled: boolean;
}

const resultTableOptions = [
  { value: "frequency_table", label: "词频统计" },
  { value: "term_document_table", label: "词项文档分析" },
  { value: "term_year_table", label: "词项年份分析" },
  { value: "cooccurrence_table", label: "共现分析" },
  { value: "group_compare_table", label: "分组比较" },
  { value: "keyness_table", label: "关键性分析" },
  { value: "selected_feature_terms", label: "特征词筛选" },
  { value: "keyword_result", label: "关键词提取" },
  { value: "keyword_cluster_result", label: "关键词聚类" },
  { value: "institution_keyword_cooccurrence", label: "机构关键词分析" },
  { value: "institution_topic_cooccurrence", label: "机构主题分析" },
  { value: "clustering_result", label: "文档聚类" },
  { value: "topic_term_table", label: "主题词项表" },
  { value: "document_topic_table", label: "文档主题表" },
  { value: "topic_summary_table", label: "主题摘要表" },
  { value: "cluster_evaluation_table", label: "聚类评估表" },
  { value: "joined_table", label: "连接结果表" }
] as const;

const controlSourceKindOptions = [
  { value: "corpus_metadata", label: "语料元数据" },
  { value: "table_field", label: "表格字段" },
  { value: "comparison_result", label: "比较结果字段" }
] as const;

const controlOperatorOptions = [
  { value: "in", label: "属于" },
  { value: "not_in", label: "不属于" },
  { value: "contains", label: "包含文本" },
  { value: "eq", label: "等于" },
  { value: "neq", label: "不等于" },
  { value: "gt", label: "大于" },
  { value: "gte", label: "大于等于" },
  { value: "lt", label: "小于" },
  { value: "lte", label: "小于等于" }
] as const;

const metricNameOptions = [
  "silhouette_score",
  "davies_bouldin_score",
  "frequency",
  "doc_count",
  "score",
  "p_value",
  "log_likelihood"
] as const;

const metricNameFieldOptions = ["metric", "row_type", "name", "label", "term", "cluster_id"] as const;
const metricValueFieldOptions = ["value", "silhouette_score", "davies_bouldin_score", "frequency", "doc_count", "score", "p_value", "log_likelihood"] as const;

function numericValue(value: unknown): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "";
  }
  return String(value);
}

function renderGenericParamField(context: WorkflowNodeEditorContext, param: RegisteredWorkflowNodeDefinition["params"][number]) {
  const value = context.node.config[param.param_id] ?? param.default_value ?? null;

  if (param.kind === "boolean") {
    return (
      <label key={param.param_id} className="switch-row compact">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { [param.param_id]: event.target.checked })}
          disabled={context.loading}
        />
        <span>{param.label}</span>
      </label>
    );
  }

  if (param.kind === "enum") {
    return (
      <label key={param.param_id} className="field compact">
        <span>{param.label}</span>
        <select
          value={String(value ?? "")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { [param.param_id]: event.target.value })}
          disabled={context.loading}
        >
          {(param.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
    );
  }

  if (param.kind === "number") {
    return (
      <label key={param.param_id} className="field compact">
        <span>{param.label}</span>
        <input
          type="number"
          value={numericValue(value)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            [param.param_id]: event.target.value === "" ? null : Number(event.target.value)
          })}
          disabled={context.loading}
        />
      </label>
    );
  }

  return (
    <label key={param.param_id} className="field compact">
      <span>{param.label}</span>
      <input
        value={String(value ?? "")}
        onChange={(event) => context.updateNodeConfig(context.node.node_id, { [param.param_id]: event.target.value })}
        disabled={context.loading}
      />
    </label>
  );
}

function renderGenericNodeParams(context: WorkflowNodeEditorContext) {
  const definition = context.nodeDefinitionsByType.get(context.node.node_type);
  if (!definition?.params.length) {
    return null;
  }
  return (
    <div className="workflow-node-inline-editor-grid">
      {definition.params.map((param) => renderGenericParamField(context, param))}
    </div>
  );
}

function renderCorpusInputEditor(context: WorkflowNodeEditorContext) {
  const nodeScope = context.runScopeForNode(context.node);
  const nodeMatchedDocuments = context.snapshot.corpus.filter((item) => context.corpusMatchesRunScope(item, nodeScope));
  const nodeDocumentPickerRows = nodeScope.mode === "selected_documents"
    ? context.snapshot.corpus.filter((item) =>
      !context.documentPickerQuery.trim().toLowerCase()
      || [item.doc_id, item.title, item.source, item.institution]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(context.documentPickerQuery.trim().toLowerCase())
    )
    : [];

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>范围</span>
          <select
            value={String(nodeScope.mode ?? "all_documents")}
            onChange={(event) => context.updateRunScope(context.node.node_id, { mode: event.target.value as RunScopeDefinition["mode"] })}
            disabled={context.loading}
          >
            <option value="all_documents">全部</option>
            <option value="filtered_subset">筛选</option>
            <option value="selected_documents">点选</option>
          </select>
        </label>
      </div>

      <small>{context.runScopeSummary(nodeScope, context.snapshot.corpus.length, nodeMatchedDocuments.length)}</small>

      {nodeScope.mode === "filtered_subset" && (
        <>
          <div className="workflow-node-inline-editor-grid">
            <label className="field compact">
              <span>起始年</span>
              <input
                type="number"
                value={numericValue(nodeScope.year_from)}
                onChange={(event) => context.updateRunScope(context.node.node_id, {
                  year_from: event.target.value ? Number(event.target.value) : null
                })}
                disabled={context.loading}
              />
            </label>
            <label className="field compact">
              <span>结束年</span>
              <input
                type="number"
                value={numericValue(nodeScope.year_to)}
                onChange={(event) => context.updateRunScope(context.node.node_id, {
                  year_to: event.target.value ? Number(event.target.value) : null
                })}
                disabled={context.loading}
              />
            </label>
          </div>
          <div className="workflow-node-inline-pill-block">
            <strong>来源</strong>
            <div className="pill-cloud compact">
              {context.availableSources.slice(0, 12).map((source) => (
                <button key={source} type="button" className={`intent-pill ${nodeScope.source_values.includes(source) ? "is-active" : ""}`} onClick={() => context.toggleScopeArrayValue(context.node.node_id, "source_values", source)} disabled={context.loading}>{source}</button>
              ))}
            </div>
          </div>
          <div className="workflow-node-inline-pill-block">
            <strong>机构</strong>
            <div className="pill-cloud compact">
              {context.availableInstitutions.slice(0, 10).map((institution) => (
                <button key={institution} type="button" className={`intent-pill ${nodeScope.institution_values.includes(institution) ? "is-active" : ""}`} onClick={() => context.toggleScopeArrayValue(context.node.node_id, "institution_values", institution)} disabled={context.loading}>{institution}</button>
              ))}
            </div>
          </div>
          <div className="workflow-node-inline-pill-block">
            <strong>标签</strong>
            <div className="pill-cloud compact">
              {context.availableCategories.slice(0, 10).map((category) => (
                <button key={category} type="button" className={`intent-pill ${nodeScope.category_values.includes(category) ? "is-active" : ""}`} onClick={() => context.toggleScopeArrayValue(context.node.node_id, "category_values", category)} disabled={context.loading}>{category}</button>
              ))}
            </div>
          </div>
        </>
      )}

      {nodeScope.mode === "selected_documents" && (
        <>
          <label className="field compact">
            <span>搜索文档</span>
            <input
              value={context.documentPickerQuery}
              onChange={(event) => context.setDocumentPickerQuery(event.target.value)}
              placeholder="标题 / 来源 / 机构"
              disabled={context.loading}
            />
          </label>
          <div className="document-picker-list compact">
            {nodeDocumentPickerRows.slice(0, 10).map((item) => (
              <label key={item.doc_id} className="document-picker-row">
                <input type="checkbox" checked={nodeScope.selected_doc_ids.includes(item.doc_id)} onChange={() => context.toggleSelectedDocument(context.node.node_id, item.doc_id)} disabled={context.loading} />
                <div>
                  <strong>{item.title}</strong>
                  <p>{[item.source, item.institution, item.year].filter(Boolean).join(" · ")}</p>
                </div>
              </label>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function renderDictionaryInputEditor(context: WorkflowNodeEditorContext) {
  const sheetEnabledCount = (sheetKey: keyof ProjectManifest["dictionary_set"]["sheets"]) =>
    context.project.dictionary_set.sheets[sheetKey]?.entries.filter((entry) => entry.enabled).length ?? 0;

  return (
    <>
      <div className="workflow-node-inline-pill-block">
        <strong>当前资源</strong>
        <small>当前启用 {context.enabledDictionaryEntryCount(context.project.dictionary_set)} 条词表规则</small>
      </div>
      {dictionaryBindingGroups.map((group) => (
        <div key={group.title} className="workflow-node-inline-pill-block">
          <strong>{group.title}</strong>
          <div className="workflow-node-inline-editor-grid">
            {group.items.map((item) => (
              <label key={item.key} className="switch-row compact">
                <input
                  type="checkbox"
                  checked={Boolean(context.node.config[item.key] ?? true)}
                  onChange={(event) => context.updateNodeConfig(context.node.node_id, { [item.key]: event.target.checked })}
                  disabled={context.loading}
                />
                <span>{item.label} · {sheetEnabledCount(item.sheet)}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
      <Button size="small" appearance="subtle" onClick={() => context.setActivePage("dictionaries")} disabled={context.loading}>
        打开词表中心
      </Button>
    </>
  );
}

function csvList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).join(", ") : "";
}

function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function conditionText(value: unknown): string {
  if (!Array.isArray(value)) {
    return "";
  }
  return value
    .filter((item): item is { field?: unknown; operator?: unknown; values?: unknown } => typeof item === "object" && item !== null)
    .map((item) => `${String(item.field ?? "")}|${String(item.operator ?? "in")}|${Array.isArray(item.values) ? item.values.map((entry) => String(entry)).join(",") : ""}`)
    .join("\n");
}

function parseConditionText(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [field, operator = "in", valuesText = ""] = line.split("|");
      return {
        field: field?.trim() ?? "",
        operator: operator.trim() || "in",
        values: parseCsvList(valuesText)
      };
    })
    .filter((condition) => condition.field);
}

function splitText(value: unknown): string {
  if (!Array.isArray(value)) {
    return "";
  }
  return value
    .filter((item): item is { name?: unknown; ratio?: unknown } => typeof item === "object" && item !== null)
    .map((item) => `${String(item.name ?? "")}:${String(item.ratio ?? "")}`)
    .join("\n");
}

function parseSplitText(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, ratioText = "0"] = line.split(":");
      return {
        name: name?.trim() ?? "",
        ratio: Number(ratioText.trim() || "0")
      };
    })
    .filter((item) => item.name);
}

function normalizeOverlayRows(value: unknown): OverlayRuleRow[] {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is Partial<OverlayRuleRow> => typeof item === "object" && item !== null)
      .map((item) => ({
        kind: String(item.kind ?? "").trim(),
        source: String(item.source ?? "").trim(),
        target: String(item.target ?? "").trim(),
        enabled: item.enabled !== false
      }))
      .filter((item) => item.kind && item.source);
  }

  return String(value ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [kind = "", source = "", target = "", enabledText = "true"] = line.split("|");
      return {
        kind: kind.trim(),
        source: source.trim(),
        target: target.trim(),
        enabled: enabledText.trim().toLowerCase() !== "false"
      };
    })
    .filter((item) => item.kind && item.source);
}

function serializeOverlayRows(rows: OverlayRuleRow[]): string {
  return rows
    .map((row) => `${row.kind}|${row.source}|${row.target}|${row.enabled ? "true" : "false"}`)
    .join("\n");
}

function corpusFieldValue(item: CorpusItem, field: string): string {
  if (field === "institution") {
    return String(item.institution ?? "").trim();
  }
  if (field === "source") {
    return String(item.source ?? "").trim();
  }
  if (field === "year") {
    return item.year === null || item.year === undefined ? "" : String(item.year);
  }
  if (field === "category_or_tag") {
    return String(item.category_or_tag ?? "").trim();
  }
  const extraValue = item.extra_metadata?.[field];
  return extraValue === null || extraValue === undefined ? "" : String(extraValue).trim();
}

function availableGroupFields(corpus: CorpusItem[]): string[] {
  const fields = new Set<string>(["institution", "source", "year", "category_or_tag"]);
  for (const item of corpus) {
    for (const key of Object.keys(item.extra_metadata ?? {})) {
      if (key.trim()) {
        fields.add(key.trim());
      }
    }
  }
  return [...fields];
}

function availableGroupValues(corpus: CorpusItem[], field: string): string[] {
  const values = new Set<string>();
  for (const item of corpus) {
    const value = corpusFieldValue(item, field);
    if (value) {
      values.add(value);
    }
  }
  return [...values].sort((left, right) => left.localeCompare(right, "zh-CN"));
}

function withCurrentOption(options: string[], currentValue: string): string[] {
  return [currentValue, ...options]
    .map((item) => item.trim())
    .filter((item, index, values) => item && values.indexOf(item) === index);
}

function normalizeStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  return parseCsvList(String(value ?? ""));
}

function persistStringList(
  context: WorkflowNodeEditorContext,
  patchKey: string,
  textKey: string,
  values: string[]
) {
  context.updateNodeConfig(context.node.node_id, {
    [patchKey]: values,
    [textKey]: values.join(",")
  });
}

function renderFilterByMetadataEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>条件列表</span>
        <textarea
          value={conditionText(context.node.config.conditions)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { conditions: parseConditionText(event.target.value) })}
          placeholder="institution|in|OpenAI,Anthropic"
          disabled={context.loading}
          rows={4}
        />
      </label>
      <small>每行一个条件：`字段|运算符|值1,值2`</small>
    </div>
  );
}

function renderDeduplicateDocumentsEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>去重字段</span>
        <input
          value={csvList(context.node.config.dedupe_keys)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { dedupe_keys: parseCsvList(event.target.value) })}
          placeholder="title, year"
          disabled={context.loading}
        />
      </label>
      <label className="field compact">
        <span>保留策略</span>
        <select
          value={String(context.node.config.strategy ?? "keep_first")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { strategy: event.target.value })}
          disabled={context.loading}
        >
          <option value="keep_first">保留首条</option>
        </select>
      </label>
    </div>
  );
}

function renderSampleCorpusEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>抽样方式</span>
        <select
          value={String(context.node.config.sample_mode ?? "random")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { sample_mode: event.target.value })}
          disabled={context.loading}
        >
          <option value="random">随机抽样</option>
        </select>
      </label>
      <label className="field compact">
        <span>样本数量</span>
        <input
          type="number"
          value={numericValue(context.node.config.sample_size)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { sample_size: event.target.value ? Number(event.target.value) : null })}
          disabled={context.loading}
        />
      </label>
      <label className="field compact">
        <span>抽样比例</span>
        <input
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={numericValue(context.node.config.sample_ratio)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { sample_ratio: event.target.value ? Number(event.target.value) : null })}
          disabled={context.loading}
        />
      </label>
      <label className="field compact">
        <span>随机种子</span>
        <input
          type="number"
          value={numericValue(context.node.config.seed)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { seed: event.target.value ? Number(event.target.value) : 42 })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

function renderSplitCorpusEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>切分方式</span>
        <select
          value={String(context.node.config.split_strategy ?? "ratio")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { split_strategy: event.target.value })}
          disabled={context.loading}
        >
          <option value="ratio">按比例</option>
        </select>
      </label>
      <label className="field compact">
        <span>切分定义</span>
        <textarea
          value={splitText(context.node.config.splits)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { splits: parseSplitText(event.target.value) })}
          placeholder={"train:0.7\ntest:0.3"}
          disabled={context.loading}
          rows={4}
        />
      </label>
      <label className="field compact">
        <span>随机种子</span>
        <input
          type="number"
          value={numericValue(context.node.config.seed)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { seed: event.target.value ? Number(event.target.value) : 42 })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

function renderBucketByTimeEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>时间字段</span>
        <input
          value={String(context.node.config.field ?? "year")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { field: event.target.value })}
          disabled={context.loading}
        />
      </label>
      <label className="field compact">
        <span>分桶粒度</span>
        <select
          value={String(context.node.config.granularity ?? "year")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { granularity: event.target.value })}
          disabled={context.loading}
        >
          <option value="year">按年</option>
          <option value="5_year">五年</option>
          <option value="decade">十年</option>
        </select>
      </label>
    </div>
  );
}

function renderSelectDictionaryTablesEditor(context: WorkflowNodeEditorContext) {
  const collections = Object.values(context.project.dictionary_set.collections ?? {});
  const allTableIds = collections.flatMap((collection) =>
    (collection?.tables ?? [])
      .map((table) => String(table.id ?? "").trim())
      .filter(Boolean)
  );
  const explicitSelection = normalizeStringList(
    Array.isArray(context.node.config.selected_table_ids) ? context.node.config.selected_table_ids : context.node.config.selected_table_ids_text
  );
  const useAllTables = explicitSelection.length === 0;
  const selectedTableIds = new Set(useAllTables ? allTableIds : explicitSelection);

  const persistSelection = (values: string[]) => {
    persistStringList(context, "selected_table_ids", "selected_table_ids_text", values);
  };

  const toggleTable = (tableId: string) => {
    const next = new Set(useAllTables ? allTableIds : [...selectedTableIds]);
    if (next.has(tableId)) {
      next.delete(tableId);
    } else {
      next.add(tableId);
    }
    persistSelection(allTableIds.filter((item) => next.has(item)));
  };

  return (
    <>
      <div className="workflow-node-inline-pill-block">
        <strong>分表选择</strong>
        <small>{useAllTables ? `未指定时默认启用全部 ${allTableIds.length} 个分表` : `当前显式启用 ${selectedTableIds.size}/${allTableIds.length} 个分表`}</small>
      </div>
      {collections.map((collection) => (
        <div key={collection.kind} className="workflow-node-inline-pill-block">
          <strong>{collection.name}</strong>
          <div className="workflow-node-inline-editor-grid">
            {collection.tables.map((table) => (
              <div key={table.id} className="workflow-node-inline-table-row">
                <label className="switch-row compact">
                  <input
                    type="checkbox"
                    checked={selectedTableIds.has(table.id)}
                    onChange={() => toggleTable(table.id)}
                    disabled={context.loading}
                  />
                  <span>{table.name} · {table.entries.length}</span>
                </label>
                <Button
                  size="small"
                  appearance="subtle"
                  onClick={() => context.bindDictionaryTableToWorkflow(table.id)}
                  disabled={context.loading}
                >
                  绑定到节点
                </Button>
              </div>
            ))}
          </div>
        </div>
      ))}
      <Button
        size="small"
        appearance="subtle"
        onClick={() => context.updateNodeConfig(context.node.node_id, { selected_table_ids: [], selected_table_ids_text: "" })}
        disabled={context.loading}
      >
        恢复为全部分表
      </Button>
    </>
  );
}

function renderOverlayDictionaryRulesEditor(context: WorkflowNodeEditorContext) {
  const collections = Object.values(context.project.dictionary_set.collections ?? {});
  const kinds = collections.map((collection) => collection.kind);
  const overlayRows = normalizeOverlayRows(
    Array.isArray(context.node.config.overlay_rows) ? context.node.config.overlay_rows : context.node.config.overlay_rows_text
  );
  const rows = overlayRows.length
    ? overlayRows
    : [{ kind: kinds[0] ?? "standard_terms", source: "", target: "", enabled: true }];

  const persistRows = (nextRows: OverlayRuleRow[]) => {
    const cleanRows = nextRows.filter((row) => row.kind && row.source);
    context.updateNodeConfig(context.node.node_id, {
      overlay_rows: cleanRows,
      overlay_rows_text: serializeOverlayRows(cleanRows)
    });
  };

  return (
    <>
      <div className="workflow-node-inline-pill-block">
        <strong>运行时叠加规则</strong>
        <small>只对本次运行生效，不会写回项目词表。</small>
      </div>
      {rows.map((row, index) => (
        <div key={`${row.kind}-${index}`} className="workflow-node-inline-editor-grid">
          <label className="field compact">
            <span>规则类型</span>
            <select
              value={row.kind}
              onChange={(event) => {
                const nextRows = rows.map((item, itemIndex) => itemIndex === index ? { ...item, kind: event.target.value } : item);
                persistRows(nextRows);
              }}
              disabled={context.loading}
            >
              {kinds.map((kind) => (
                <option key={kind} value={kind}>{kind}</option>
              ))}
            </select>
          </label>
          <label className="field compact">
            <span>源词项</span>
            <input
              value={row.source}
              onChange={(event) => {
                const nextRows = rows.map((item, itemIndex) => itemIndex === index ? { ...item, source: event.target.value } : item);
                persistRows(nextRows);
              }}
              placeholder="llm"
              disabled={context.loading}
            />
          </label>
          <label className="field compact">
            <span>目标词项</span>
            <input
              value={row.target}
              onChange={(event) => {
                const nextRows = rows.map((item, itemIndex) => itemIndex === index ? { ...item, target: event.target.value } : item);
                persistRows(nextRows);
              }}
              placeholder="large language model"
              disabled={context.loading}
            />
          </label>
          <label className="switch-row compact">
            <input
              type="checkbox"
              checked={row.enabled}
              onChange={(event) => {
                const nextRows = rows.map((item, itemIndex) => itemIndex === index ? { ...item, enabled: event.target.checked } : item);
                persistRows(nextRows);
              }}
              disabled={context.loading}
            />
            <span>启用</span>
          </label>
          <Button
            size="small"
            appearance="subtle"
            onClick={() => persistRows(rows.filter((_, itemIndex) => itemIndex !== index))}
            disabled={context.loading || rows.length <= 1}
          >
            删除
          </Button>
        </div>
      ))}
      <Button
        size="small"
        appearance="subtle"
        onClick={() => persistRows([...rows, { kind: kinds[0] ?? "standard_terms", source: "", target: "", enabled: true }])}
        disabled={context.loading}
      >
        添加规则
      </Button>
    </>
  );
}

function renderGroupCompareEditor(context: WorkflowNodeEditorContext) {
  const fieldOptions = availableGroupFields(context.snapshot.corpus);
  const groupField = String(context.node.config.group_field ?? "institution");
  const availableValues = availableGroupValues(context.snapshot.corpus, groupField);
  const baselineGroup = String(context.node.config.baseline_group ?? availableValues[0] ?? "");
  const comparisonGroups = normalizeStringList(
    Array.isArray(context.node.config.comparison_groups) ? context.node.config.comparison_groups : context.node.config.comparison_groups_text
  );
  const selectedComparisonGroups = new Set(comparisonGroups);

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>分组字段</span>
          <select
            value={groupField}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { group_field: event.target.value })}
            disabled={context.loading}
          >
            {fieldOptions.map((field) => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>基准分组</span>
          <select
            value={baselineGroup}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { baseline_group: event.target.value })}
            disabled={context.loading}
          >
            {[baselineGroup, ...availableValues].filter((value, index, values) => value && values.indexOf(value) === index).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>最小词频</span>
          <input
            type="number"
            min="1"
            value={numericValue(context.node.config.min_frequency ?? 1)}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, {
              min_frequency: event.target.value ? Number(event.target.value) : 1
            })}
            disabled={context.loading}
          />
        </label>
      </div>
      <div className="workflow-node-inline-pill-block">
        <strong>对比分组</strong>
        <div className="pill-cloud compact">
          {availableValues.filter((value) => value !== baselineGroup).map((value) => (
            <button
              key={value}
              type="button"
              className={`intent-pill ${selectedComparisonGroups.has(value) ? "is-active" : ""}`}
              onClick={() => {
                const next = new Set(selectedComparisonGroups);
                if (next.has(value)) {
                  next.delete(value);
                } else {
                  next.add(value);
                }
                persistStringList(context, "comparison_groups", "comparison_groups_text", availableValues.filter((item) => next.has(item)));
              }}
              disabled={context.loading}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

function renderKeynessAnalysisEditor(context: WorkflowNodeEditorContext) {
  const fieldOptions = availableGroupFields(context.snapshot.corpus);
  const groupField = String(context.node.config.group_field ?? "institution");
  const availableValues = availableGroupValues(context.snapshot.corpus, groupField);
  const baselineGroup = String(context.node.config.baseline_group ?? availableValues[0] ?? "");
  const comparisonGroup = String(
    context.node.config.comparison_group
    ?? availableValues.find((value) => value !== baselineGroup)
    ?? ""
  );

  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>分组字段</span>
        <select
          value={groupField}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { group_field: event.target.value })}
          disabled={context.loading}
        >
          {fieldOptions.map((field) => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>
      </label>
      <label className="field compact">
        <span>基准分组</span>
        <select
          value={baselineGroup}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { baseline_group: event.target.value })}
          disabled={context.loading}
        >
          {[baselineGroup, ...availableValues].filter((value, index, values) => value && values.indexOf(value) === index).map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
      </label>
      <label className="field compact">
        <span>目标分组</span>
        <select
          value={comparisonGroup}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { comparison_group: event.target.value })}
          disabled={context.loading}
        >
          {[comparisonGroup, ...availableValues.filter((value) => value !== baselineGroup)]
            .filter((value, index, values) => value && values.indexOf(value) === index)
            .map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
        </select>
      </label>
      <label className="field compact">
        <span>最小词频</span>
        <input
          type="number"
          min="1"
          value={numericValue(context.node.config.min_frequency ?? 2)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            min_frequency: event.target.value ? Number(event.target.value) : 2
          })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

function renderTopicModelingEditor(context: WorkflowNodeEditorContext) {
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>主题数量</span>
        <input
          type="number"
          min="1"
          value={numericValue(context.node.config.topic_model_k)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            topic_model_k: event.target.value ? Number(event.target.value) : 2
          })}
          disabled={context.loading}
        />
      </label>
      <label className="field compact">
        <span>每主题词项数</span>
        <input
          type="number"
          min="1"
          value={numericValue(context.node.config.top_terms_per_topic)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            top_terms_per_topic: event.target.value ? Number(event.target.value) : 5
          })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

function renderClusterEvaluationEditor() {
  return (
    <div className="workflow-node-inline-pill-block">
      <strong>评估说明</strong>
      <small>连接文档聚类节点后，会自动计算轮廓系数、Davies-Bouldin 指标和簇规模分布。</small>
    </div>
  );
}

function renderJoinResultsEditor(context: WorkflowNodeEditorContext) {
  const joinKeys = normalizeStringList(
    Array.isArray(context.node.config.join_keys) ? context.node.config.join_keys : context.node.config.join_keys_text
  );

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>左侧结果</span>
          <select
            value={String(context.node.config.left_artifact ?? "frequency_table")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { left_artifact: event.target.value })}
            disabled={context.loading}
          >
            {resultTableOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>右侧结果</span>
          <select
            value={String(context.node.config.right_artifact ?? "keyness_table")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { right_artifact: event.target.value })}
            disabled={context.loading}
          >
            {resultTableOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>连接方式</span>
          <select
            value={String(context.node.config.join_type ?? "inner")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { join_type: event.target.value })}
            disabled={context.loading}
          >
            <option value="inner">内连接</option>
            <option value="left">左连接</option>
            <option value="right">右连接</option>
            <option value="outer">全连接</option>
          </select>
        </label>
        <label className="field compact">
          <span>连接键</span>
          <input
            value={joinKeys.join(", ")}
            onChange={(event) => persistStringList(context, "join_keys", "join_keys_text", parseCsvList(event.target.value))}
            placeholder="term"
            disabled={context.loading}
          />
        </label>
      </div>
      <small>也可以通过左右输入端显式连线；未连线时会回退到这里选中的结果表。</small>
    </>
  );
}

function renderConditionalRouterEditor(context: WorkflowNodeEditorContext) {
  const sourceKind = String(context.node.config.source_kind ?? "corpus_metadata");
  const field = String(context.node.config.field ?? "institution");
  const fieldOptions = sourceKind === "corpus_metadata"
    ? availableGroupFields(context.snapshot.corpus)
    : ["metric", "value", "row_type", "term", "frequency", "score", "p_value", "cluster_id", "silhouette_score"];
  const selectedValues = normalizeStringList(
    Array.isArray(context.node.config.values) ? context.node.config.values : context.node.config.values_text
  );
  const availableValues = sourceKind === "corpus_metadata" ? availableGroupValues(context.snapshot.corpus, field) : [];

  const persistValues = (values: string[]) => {
    persistStringList(context, "values", "values_text", values);
  };

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>条件来源</span>
          <select
            value={sourceKind}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { source_kind: event.target.value })}
            disabled={context.loading}
          >
            {controlSourceKindOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>字段</span>
          <select
            value={field}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { field: event.target.value })}
            disabled={context.loading}
          >
            {withCurrentOption(fieldOptions, field).map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>运算符</span>
          <select
            value={String(context.node.config.operator ?? "in")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { operator: event.target.value })}
            disabled={context.loading}
          >
            {controlOperatorOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>条件值</span>
          <input
            value={selectedValues.join(", ")}
            onChange={(event) => persistValues(parseCsvList(event.target.value))}
            placeholder="OpenAI, Anthropic"
            disabled={context.loading}
          />
        </label>
      </div>
      {availableValues.length > 0 && (
        <div className="workflow-node-inline-pill-block">
          <strong>可选值</strong>
          <div className="pill-cloud compact">
            {availableValues.slice(0, 16).map((value) => (
              <button
                key={value}
                type="button"
                className={`intent-pill ${selectedValues.includes(value) ? "is-active" : ""}`}
                onClick={() => {
                  const next = new Set(selectedValues);
                  if (next.has(value)) {
                    next.delete(value);
                  } else {
                    next.add(value);
                  }
                  persistValues(availableValues.filter((item) => next.has(item)));
                }}
                disabled={context.loading}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      )}
      <small>条件只由字段、运算符和值组成，不支持循环或脚本。</small>
    </>
  );
}

function renderResultGateEditor(context: WorkflowNodeEditorContext) {
  const metricArtifact = String(context.node.config.metric_artifact ?? "cluster_evaluation_table");
  const metricName = String(context.node.config.metric_name ?? "silhouette_score");
  const metricNameField = String(context.node.config.metric_name_field ?? "metric");
  const metricField = String(context.node.config.metric_field ?? "value");

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>指标产物</span>
          <select
            value={metricArtifact}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { metric_artifact: event.target.value })}
            disabled={context.loading}
          >
            {withCurrentOption(resultTableOptions.map((option) => option.value), metricArtifact).map((value) => (
              <option key={value} value={value}>{resultTableOptions.find((option) => option.value === value)?.label ?? value}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>指标名</span>
          <select
            value={metricName}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { metric_name: event.target.value })}
            disabled={context.loading}
          >
            {withCurrentOption([...metricNameOptions], metricName).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>指标名字段</span>
          <select
            value={metricNameField}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { metric_name_field: event.target.value })}
            disabled={context.loading}
          >
            {withCurrentOption([...metricNameFieldOptions], metricNameField).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>指标值字段</span>
          <select
            value={metricField}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { metric_field: event.target.value })}
            disabled={context.loading}
          >
            {withCurrentOption([...metricValueFieldOptions], metricField).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>判断条件</span>
          <select
            value={String(context.node.config.operator ?? "gte")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { operator: event.target.value })}
            disabled={context.loading}
          >
            {controlOperatorOptions.filter((option) => ["gt", "gte", "lt", "lte", "eq", "neq"].includes(option.value)).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>阈值</span>
          <input
            type="number"
            step="0.01"
            value={numericValue(context.node.config.threshold ?? 0.5)}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, {
              threshold: event.target.value ? Number(event.target.value) : null
            })}
            disabled={context.loading}
          />
        </label>
      </div>
      <small>可连接指标表；未连接时会按“指标产物”读取上一轮结果。</small>
    </>
  );
}

function renderManualReviewGateEditor(context: WorkflowNodeEditorContext) {
  const reviewTasks = context.project.review_tasks ?? [];
  const reviewId = String(context.node.config.review_id ?? "");
  const selectedTask = reviewTasks.find((task) => task.review_id === reviewId);
  const taskLabel = (task: (typeof reviewTasks)[number]) => {
    const title = String((task as { title?: unknown }).title ?? "").trim();
    return `${title || task.review_type || task.review_id} · ${task.status}`;
  };

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>复核任务</span>
          <select
            value={reviewId}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { review_id: event.target.value })}
            disabled={context.loading}
          >
            <option value="">选择复核任务</option>
            {reviewTasks.map((task) => (
              <option key={task.review_id} value={task.review_id}>{taskLabel(task)}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>放行状态</span>
          <select
            value={String(context.node.config.required_status ?? "resolved")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { required_status: event.target.value })}
            disabled={context.loading}
          >
            <option value="resolved">已解决</option>
            <option value="open">打开</option>
          </select>
        </label>
        <label className="field compact">
          <span>找不到任务时</span>
          <select
            value={String(context.node.config.on_missing ?? "block")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { on_missing: event.target.value })}
            disabled={context.loading}
          >
            <option value="block">拦截</option>
            <option value="pass">放行</option>
          </select>
        </label>
      </div>
      <small>{selectedTask ? `当前任务状态：${selectedTask.status}` : "请选择一个复核任务；默认找不到任务时拦截。"}</small>
    </>
  );
}

type WorkflowNodeInlineRenderer = (context: WorkflowNodeEditorContext) => ReactNode;

const workflowNodeInlineRenderers: Partial<Record<WorkflowNodeInstance["node_type"], WorkflowNodeInlineRenderer>> = {
  corpus_input: renderCorpusInputEditor,
  dictionary_input: renderDictionaryInputEditor,
  select_dictionary_tables: renderSelectDictionaryTablesEditor,
  overlay_dictionary_rules: renderOverlayDictionaryRulesEditor,
  filter_by_metadata: renderFilterByMetadataEditor,
  deduplicate_documents: renderDeduplicateDocumentsEditor,
  sample_corpus: renderSampleCorpusEditor,
  split_corpus: renderSplitCorpusEditor,
  bucket_by_time: renderBucketByTimeEditor,
  group_compare: renderGroupCompareEditor,
  keyness_analysis: renderKeynessAnalysisEditor,
  topic_modeling: renderTopicModelingEditor,
  cluster_evaluation: renderClusterEvaluationEditor,
  join_results: renderJoinResultsEditor,
  conditional_router: renderConditionalRouterEditor,
  result_gate: renderResultGateEditor,
  manual_review_gate: renderManualReviewGateEditor
};

export function renderWorkflowNodeInlineEditor(context: WorkflowNodeEditorContext) {
  const customRenderer = workflowNodeInlineRenderers[context.node.node_type];
  const customContent = customRenderer ? customRenderer(context) : null;
  const genericContent = customRenderer ? null : renderGenericNodeParams(context);

  if (!customContent && !genericContent) {
    return null;
  }

  return (
    <div
      className="workflow-node-inline-editor"
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      {customContent}
      {genericContent}
    </div>
  );
}

export function renderWorkflowNodePreview(context: WorkflowNodeEditorContext) {
  const latestRun = context.latestRun;
  const results = context.project.results;
  const dynamicResults = results as unknown as Record<string, Array<Record<string, unknown>>>;
  const matchedDocuments = context.snapshot.corpus.filter((item) => context.corpusMatchesRunScope(item, context.runScopeForNode(context.node)));

  if (context.node.node_type === "frequency_statistics") {
    return <small>Top: {results.frequency_table.slice(0, 3).map((row) => row.term).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "term_document_analysis") {
    return <small>词项-文档: {results.term_document_table.slice(0, 2).map((row) => `${row.term}@${row.doc_id}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "cooccurrence_analysis") {
    return <small>共现: {results.cooccurrence_table.slice(0, 3).map((row) => `${row.term_a}×${row.term_b}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "feature_term_selection") {
    return <small>特征词: {results.selected_feature_terms.slice(0, 3).map((row) => row.term).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "focus_terms") {
    const rows = Array.isArray(dynamicResults.focus_term_summary) ? dynamicResults.focus_term_summary : [];
    const summary = rows[0];
    return <small>聚焦: {summary ? `${String(summary.tokens_before ?? 0)} -> ${String(summary.tokens_after ?? 0)} 词项` : "暂无结果"}</small>;
  }

  if (context.node.node_type === "keyword_clustering") {
    return <small>聚类: {results.keyword_cluster_result.slice(0, 2).map((row) => row.topic_label ?? `簇${row.cluster_id}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "institution_keyword_analysis") {
    return <small>机构词: {results.institution_keyword_cooccurrence.slice(0, 2).map((row) => `${row.institution}:${row.keyword}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "document_clustering") {
    return <small>文档聚类: {results.clustering_result.slice(0, 2).map((row) => `${row.title}→簇${row.cluster_id}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "topic_modeling") {
    const rows = Array.isArray(dynamicResults.topic_summary_table) ? dynamicResults.topic_summary_table : [];
    return <small>主题: {rows.slice(0, 2).map((row) => String(row.topic_label ?? "")).filter(Boolean).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "cluster_evaluation") {
    const rows = Array.isArray(dynamicResults.cluster_evaluation_table) ? dynamicResults.cluster_evaluation_table : [];
    const overall = rows.find((row) => row.row_type === "overall");
    return <small>轮廓系数: {overall ? String(overall.silhouette_score ?? "0") : "暂无结果"}</small>;
  }

  if (context.node.node_type === "join_results") {
    const rows = Array.isArray(dynamicResults.joined_table) ? dynamicResults.joined_table : [];
    return <small>连接结果: {rows.length ? `${rows.length} 行` : "暂无结果"}</small>;
  }

  if (context.node.node_type === "conditional_router") {
    const rows = Array.isArray(dynamicResults.conditional_route_summary) ? dynamicResults.conditional_route_summary : [];
    const summary = rows[0];
    return <small>路由: {summary ? `${String(summary.matched_count ?? 0)} 匹配 / ${String(summary.unmatched_count ?? 0)} 未匹配` : "暂无结果"}</small>;
  }

  if (context.node.node_type === "result_gate") {
    const rows = Array.isArray(dynamicResults.result_gate_summary) ? dynamicResults.result_gate_summary : [];
    const summary = rows[0];
    return <small>门禁: {summary ? `${summary.passed ? "已放行" : "已拦截"} · ${String(summary.observed_value ?? "无值")}` : "暂无结果"}</small>;
  }

  if (context.node.node_type === "manual_review_gate") {
    const rows = Array.isArray(dynamicResults.review_gate_summary) ? dynamicResults.review_gate_summary : [];
    const summary = rows[0];
    return <small>复核: {summary ? `${summary.waiting ? "等待复核" : "已放行"} · ${String(summary.status ?? "unknown")}` : "暂无结果"}</small>;
  }

  if (context.node.node_type === "save_html_report" || context.node.node_type === "save_png" || context.node.node_type === "save_csv" || context.node.node_type === "save_xlsx") {
    return <small>导出: {context.project.results.report_files.length} 个文件{latestRun ? ` · ${latestRun.status}` : ""}</small>;
  }

  if (context.node.node_type === "corpus_input") {
    return <small>{context.runScopeSummary(context.runScopeForNode(context.node), context.snapshot.corpus.length, matchedDocuments.length)}</small>;
  }

  return null;
}

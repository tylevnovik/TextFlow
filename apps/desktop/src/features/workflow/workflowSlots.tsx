import type { ReactNode } from "react";
import type { WorkflowNodeLayoutWidget } from "@textflow/shared-types";
import type { WorkflowNodeEditorContext } from "../../workflowNodeRegistry";

export type WorkflowSlotRenderer = (
  context: WorkflowNodeEditorContext,
  widget: WorkflowNodeLayoutWidget
) => ReactNode;

function csvList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).join(", ") : String(value ?? "");
}

function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function numericValue(value: unknown): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "";
  }
  return String(value);
}

function jsonText(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function parseJsonText(value: string, fallback: unknown) {
  if (!value.trim()) {
    return Array.isArray(fallback) ? [] : {};
  }
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function corpusFieldValue(item: WorkflowNodeEditorContext["snapshot"]["corpus"][number], field: string): string {
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

function availableCorpusFields(context: WorkflowNodeEditorContext): string[] {
  const fields = new Set<string>(["institution", "source", "year", "category_or_tag"]);
  for (const item of context.snapshot.corpus) {
    for (const key of Object.keys(item.extra_metadata ?? {})) {
      if (key.trim()) {
        fields.add(key.trim());
      }
    }
  }
  return [...fields];
}

function availableCorpusValues(context: WorkflowNodeEditorContext, field: string): string[] {
  const values = new Set<string>();
  for (const item of context.snapshot.corpus) {
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
    [textKey]: values.join(", ")
  });
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

function CorpusScopeSelectorSlot(context: WorkflowNodeEditorContext) {
  const scope = context.runScopeForNode(context.node);
  const matchedCount = context.snapshot.corpus.filter((item) => context.corpusMatchesRunScope(item, scope)).length;
  const pickerQuery = context.documentPickerQuery.trim().toLowerCase();
  const documentPickerRows = scope.mode === "selected_documents"
    ? context.snapshot.corpus.filter((item) =>
      !pickerQuery
      || [item.doc_id, item.title, item.source, item.institution]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(pickerQuery)
    )
    : [];

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>资源来源</span>
          <select
            value={String(context.node.config.resource_mode ?? "project_corpus")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { resource_mode: event.target.value })}
            disabled={context.loading}
          >
            <option value="project_corpus">项目语料</option>
          </select>
        </label>
        <label className="field compact">
          <span>范围</span>
          <select
            value={String(scope.mode ?? "all_documents")}
            onChange={(event) => context.updateRunScope(context.node.node_id, { mode: event.target.value as typeof scope.mode })}
            disabled={context.loading}
          >
            <option value="all_documents">全部</option>
            <option value="filtered_subset">筛选</option>
            <option value="selected_documents">点选</option>
          </select>
        </label>
        <small>{context.runScopeSummary(scope, context.snapshot.corpus.length, matchedCount)}</small>
      </div>

      {scope.mode === "filtered_subset" && (
        <>
          <div className="workflow-node-inline-editor-grid">
            <label className="field compact">
              <span>起始年</span>
              <input
                type="number"
                value={numericValue(scope.year_from)}
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
                value={numericValue(scope.year_to)}
                onChange={(event) => context.updateRunScope(context.node.node_id, {
                  year_to: event.target.value ? Number(event.target.value) : null
                })}
                disabled={context.loading}
              />
            </label>
          </div>
          <ScopePillGroup
            title="来源"
            values={context.availableSources}
            selectedValues={scope.source_values}
            onToggle={(value) => context.toggleScopeArrayValue(context.node.node_id, "source_values", value)}
            loading={context.loading}
          />
          <ScopePillGroup
            title="机构"
            values={context.availableInstitutions}
            selectedValues={scope.institution_values}
            onToggle={(value) => context.toggleScopeArrayValue(context.node.node_id, "institution_values", value)}
            loading={context.loading}
          />
          <ScopePillGroup
            title="标签"
            values={context.availableCategories}
            selectedValues={scope.category_values}
            onToggle={(value) => context.toggleScopeArrayValue(context.node.node_id, "category_values", value)}
            loading={context.loading}
          />
        </>
      )}

      {scope.mode === "selected_documents" && (
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
            {documentPickerRows.slice(0, 10).map((item) => (
              <label key={item.doc_id} className="document-picker-row">
                <input
                  type="checkbox"
                  checked={scope.selected_doc_ids.includes(item.doc_id)}
                  onChange={() => context.toggleSelectedDocument(context.node.node_id, item.doc_id)}
                  disabled={context.loading}
                />
                <div>
                  <strong>{item.title}</strong>
                  <p>{[item.source, item.institution, item.year].filter(Boolean).join(" · ")}</p>
                </div>
              </label>
            ))}
            {!documentPickerRows.length && <small>没有匹配的文档。</small>}
          </div>
        </>
      )}
    </>
  );
}

function ScopePillGroup({
  title,
  values,
  selectedValues,
  onToggle,
  loading
}: {
  title: string;
  values: string[];
  selectedValues: string[];
  onToggle: (value: string) => void;
  loading: boolean;
}) {
  return (
    <div className="workflow-node-inline-pill-block">
      <strong>{title}</strong>
      <div className="pill-cloud compact">
        {values.slice(0, 16).map((value) => (
          <button
            key={value}
            type="button"
            className={`intent-pill ${selectedValues.includes(value) ? "is-active" : ""}`}
            onClick={() => onToggle(value)}
            disabled={loading}
          >
            {value}
          </button>
        ))}
        {!values.length && <small>当前语料还没有{title}字段。</small>}
      </div>
    </div>
  );
}

const dictionaryBindingGroups = [
  {
    title: "切词词典",
    items: [
      ["use_custom_lexicon", "自定义词典"],
      ["use_phrase_lexicon", "短语词典"]
    ]
  },
  {
    title: "标准化规则",
    items: [
      ["apply_regex_rules", "Regex 规则"]
    ]
  },
  {
    title: "规则应用",
    items: [
      ["apply_standard_terms", "标准词"],
      ["apply_synonym_map", "同义词"],
      ["apply_near_synonym_map", "近义词"],
      ["apply_stopwords", "停用词"],
      ["apply_exclusion_terms", "排除词"]
    ]
  }
] as const;

function DictionaryBindingSelectorSlot(context: WorkflowNodeEditorContext) {
  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>资源来源</span>
          <select
            value={String(context.node.config.resource_mode ?? "project_dictionary")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { resource_mode: event.target.value })}
            disabled={context.loading}
          >
            <option value="project_dictionary">项目词表</option>
          </select>
        </label>
        <label className="field compact">
          <span>资源 ID</span>
          <input
            value={String(context.node.config.resource_id ?? "project:dictionary_set")}
            onChange={(event) => context.updateNodeConfig(context.node.node_id, { resource_id: event.target.value })}
            disabled={context.loading}
          />
        </label>
      </div>
      <div className="workflow-node-inline-pill-block">
        <strong>当前资源</strong>
        <small>当前启用 {context.enabledDictionaryEntryCount(context.project.dictionary_set)} 条词表规则</small>
      </div>
      {dictionaryBindingGroups.map((group) => (
        <div key={group.title} className="workflow-node-inline-pill-block">
          <strong>{group.title}</strong>
          <div className="workflow-node-inline-editor-grid">
            {group.items.map(([key, label]) => (
              <label key={key} className="switch-row compact">
                <input
                  type="checkbox"
                  checked={Boolean(context.node.config[key] ?? true)}
                  onChange={(event) => context.updateNodeConfig(context.node.node_id, { [key]: event.target.checked })}
                  disabled={context.loading}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function DictionaryTableSelectorSlot(context: WorkflowNodeEditorContext) {
  const tableIds = Object.values(context.project.dictionary_set.collections ?? {})
    .flatMap((collection) => collection.tables.map((table) => table.id));
  const selected = new Set(parseCsvList(csvList(context.node.config.selected_table_ids)));
  return (
    <div className="workflow-node-inline-pill-block">
      <strong>资源表</strong>
      <div className="pill-cloud compact">
        {tableIds.slice(0, 16).map((tableId) => (
          <button
            key={tableId}
            type="button"
            className={`intent-pill ${selected.has(tableId) ? "is-active" : ""}`}
            onClick={() => context.bindDictionaryTableToWorkflow(tableId)}
            disabled={context.loading}
          >
            {tableId}
          </button>
        ))}
      </div>
    </div>
  );
}

function JsonTextareaSlot(
  context: WorkflowNodeEditorContext,
  configKey: string,
  label: string,
  fallback: unknown
) {
  return (
    <label className="field compact">
      <span>{label}</span>
      <textarea
        value={jsonText(context.node.config[configKey] ?? fallback)}
        onChange={(event) => context.updateNodeConfig(context.node.node_id, {
          [configKey]: parseJsonText(event.target.value, context.node.config[configKey] ?? fallback)
        })}
        disabled={context.loading}
        rows={5}
      />
    </label>
  );
}

function OverlayRuleGridSlot(context: WorkflowNodeEditorContext) {
  return JsonTextareaSlot(context, "overlay_rows", "叠加规则", []);
}

function MetadataConditionBuilderSlot(context: WorkflowNodeEditorContext) {
  const field = String(context.node.config.field ?? "institution");
  const operator = String(context.node.config.operator ?? "in");
  const values = normalizeStringList(
    Array.isArray(context.node.config.values) ? context.node.config.values : context.node.config.values_text
  );
  const availableValues = availableCorpusValues(context, field);
  const persistCondition = (patch: { field?: string; operator?: string; values?: string[] }) => {
    const nextField = patch.field ?? field;
    const nextOperator = patch.operator ?? operator;
    const nextValues = patch.values ?? values;
    context.updateNodeConfig(context.node.node_id, {
      field: nextField,
      operator: nextOperator,
      values: nextValues,
      values_text: nextValues.join(", "),
      conditions: nextField ? [{ field: nextField, operator: nextOperator, values: nextValues }] : []
    });
  };

  return (
    <>
      <div className="workflow-node-inline-editor-grid">
        <label className="field compact">
          <span>筛选字段</span>
          <select
            value={field}
            onChange={(event) => persistCondition({ field: event.target.value, values: [] })}
            disabled={context.loading}
          >
            {withCurrentOption(availableCorpusFields(context), field).map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>运算符</span>
          <select
            value={operator}
            onChange={(event) => persistCondition({ operator: event.target.value })}
            disabled={context.loading}
          >
            {controlOperatorOptions.filter((option) => ["in", "not_in", "contains", "eq"].includes(option.value)).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>筛选值</span>
          <input
            value={values.join(", ")}
            onChange={(event) => persistCondition({ values: parseCsvList(event.target.value) })}
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
                className={`intent-pill ${values.includes(value) ? "is-active" : ""}`}
                onClick={() => {
                  const next = new Set(values);
                  if (next.has(value)) {
                    next.delete(value);
                  } else {
                    next.add(value);
                  }
                  persistCondition({ values: availableValues.filter((item) => next.has(item)) });
                }}
                disabled={context.loading}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function NamedSplitEditorSlot(context: WorkflowNodeEditorContext) {
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
          value={String(context.node.config.splits_text ?? "train:0.7\ntest:0.3")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { splits_text: event.target.value })}
          disabled={context.loading}
          rows={4}
        />
      </label>
      <label className="field compact">
        <span>随机种子</span>
        <input
          type="number"
          value={numericValue(context.node.config.seed ?? 42)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { seed: event.target.value ? Number(event.target.value) : 42 })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

function ResultTableSelectorSlot(context: WorkflowNodeEditorContext) {
  const joinKeys = normalizeStringList(
    Array.isArray(context.node.config.join_keys) ? context.node.config.join_keys : context.node.config.join_keys_text
  );

  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>左侧结果</span>
        <select
          value={String(context.node.config.left_artifact ?? "")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { left_artifact: event.target.value })}
          disabled={context.loading}
        >
          {withCurrentOption(resultTableOptions.map((option) => option.value), String(context.node.config.left_artifact ?? "frequency_table")).map((value) => (
            <option key={value} value={value}>{resultTableOptions.find((option) => option.value === value)?.label ?? value}</option>
          ))}
        </select>
      </label>
      <label className="field compact">
        <span>右侧结果</span>
        <select
          value={String(context.node.config.right_artifact ?? "")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { right_artifact: event.target.value })}
          disabled={context.loading}
        >
          {withCurrentOption(resultTableOptions.map((option) => option.value), String(context.node.config.right_artifact ?? "keyness_table")).map((value) => (
            <option key={value} value={value}>{resultTableOptions.find((option) => option.value === value)?.label ?? value}</option>
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
  );
}

function ReviewTaskSelectorSlot(context: WorkflowNodeEditorContext) {
  const reviewTasks = context.project.review_tasks ?? [];
  return (
    <div className="workflow-node-inline-editor-grid">
      <label className="field compact">
        <span>复核任务</span>
        <select
          value={String(context.node.config.review_id ?? "")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, { review_id: event.target.value })}
          disabled={context.loading}
        >
          <option value="">选择复核任务</option>
          {reviewTasks.map((task) => (
            <option key={task.review_id} value={task.review_id}>{task.review_id} · {task.status}</option>
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
  );
}

function ThresholdGateEditorSlot(context: WorkflowNodeEditorContext) {
  const metricArtifact = String(context.node.config.metric_artifact ?? "cluster_evaluation_table");
  const metricName = String(context.node.config.metric_name ?? "silhouette_score");
  const metricNameField = String(context.node.config.metric_name_field ?? "metric");
  const metricField = String(context.node.config.metric_field ?? "value");

  return (
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
          value={String(context.node.config.threshold ?? "")}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            threshold: event.target.value === "" ? null : Number(event.target.value)
          })}
          disabled={context.loading}
        />
      </label>
    </div>
  );
}

export const workflowSlotHandledConfigKeys: Record<string, string[]> = {
  corpus_scope_selector: [
    "resource_mode",
    "mode",
    "year_from",
    "year_to",
    "source_values",
    "institution_values",
    "category_values",
    "selected_doc_ids"
  ],
  dictionary_binding_selector: [
    "resource_mode",
    "resource_id",
    "use_custom_lexicon",
    "use_phrase_lexicon",
    "apply_regex_rules",
    "apply_standard_terms",
    "apply_synonym_map",
    "apply_near_synonym_map",
    "apply_stopwords",
    "apply_exclusion_terms"
  ],
  dictionary_table_selector: ["selected_table_ids", "selected_table_ids_text"],
  overlay_rule_grid: ["overlay_rows", "overlay_rows_text"],
  metadata_condition_builder: ["conditions", "field", "operator", "values", "values_text"],
  named_split_editor: ["split_strategy", "splits", "splits_text", "seed"],
  result_table_selector: ["left_artifact", "right_artifact", "join_keys", "join_keys_text", "join_type"],
  review_task_selector: ["review_id", "required_status", "on_missing"],
  threshold_gate_editor: ["metric_artifact", "metric_name", "metric_name_field", "metric_field", "operator", "threshold"]
};

export const workflowSlotRenderers: Record<string, WorkflowSlotRenderer> = {
  corpus_scope_selector: CorpusScopeSelectorSlot,
  dictionary_binding_selector: DictionaryBindingSelectorSlot,
  dictionary_table_selector: DictionaryTableSelectorSlot,
  overlay_rule_grid: OverlayRuleGridSlot,
  metadata_condition_builder: MetadataConditionBuilderSlot,
  named_split_editor: NamedSplitEditorSlot,
  result_table_selector: ResultTableSelectorSlot,
  review_task_selector: ReviewTaskSelectorSlot,
  threshold_gate_editor: ThresholdGateEditorSlot
};

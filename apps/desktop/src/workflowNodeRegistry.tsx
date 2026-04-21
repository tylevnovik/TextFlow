import type { Dispatch, ReactNode, SetStateAction } from "react";
import type {
  CorpusItem,
  PipelineDefinition,
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
  draftPipeline: PipelineDefinition;
  loading: boolean;
  nodeDefinitionsByType: Map<string, RegisteredWorkflowNodeDefinition>;
  availableSources: string[];
  availableInstitutions: string[];
  availableCategories: string[];
  documentPickerQuery: string;
  setDocumentPickerQuery: Dispatch<SetStateAction<string>>;
  setActivePage: (page: "dictionaries") => void;
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
      <button type="button" className="toolbar-button ghost compact" onClick={() => context.setActivePage("dictionaries")} disabled={context.loading}>
        打开词表中心
      </button>
    </>
  );
}

type WorkflowNodeInlineRenderer = (context: WorkflowNodeEditorContext) => ReactNode;

const workflowNodeInlineRenderers: Partial<Record<WorkflowNodeInstance["node_type"], WorkflowNodeInlineRenderer>> = {
  corpus_input: renderCorpusInputEditor,
  dictionary_input: renderDictionaryInputEditor
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
  const matchedDocuments = context.snapshot.corpus.filter((item) => context.corpusMatchesRunScope(item, context.runScopeForNode(context.node)));

  if (context.node.node_type === "frequency_statistics") {
    return <small>Top: {results.frequency_table.slice(0, 3).map((row) => row.term).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "cooccurrence_analysis") {
    return <small>共现: {results.cooccurrence_table.slice(0, 3).map((row) => `${row.term_a}×${row.term_b}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "keyword_clustering") {
    return <small>聚类: {results.keyword_cluster_result.slice(0, 2).map((row) => row.topic_label ?? `簇${row.cluster_id}`).join(" / ") || "暂无结果"}</small>;
  }

  if (context.node.node_type === "save_html_report" || context.node.node_type === "save_png" || context.node.node_type === "save_csv" || context.node.node_type === "save_xlsx") {
    return <small>导出: {context.project.results.report_files.length} 个文件{latestRun ? ` · ${latestRun.status}` : ""}</small>;
  }

  if (context.node.node_type === "corpus_input") {
    return <small>{context.runScopeSummary(context.runScopeForNode(context.node), context.snapshot.corpus.length, matchedDocuments.length)}</small>;
  }

  return null;
}

import type {
  CorpusItem,
  DictionarySet,
  ProjectManifest,
  RegisteredWorkflowNodeDefinition,
  RunScopeDefinition,
  WorkflowNodeInstance,
  WorkflowRuntimeProfile
} from "@textflow/shared-types";

export interface WorkflowNodeConfigFact {
  label: string;
  value: string;
  tone?: "default" | "muted" | "warning" | "success";
}

interface WorkflowNodeConfigFactsInput {
  node: WorkflowNodeInstance;
  definition?: RegisteredWorkflowNodeDefinition;
  runtimeProfile: WorkflowRuntimeProfile;
  project?: ProjectManifest;
  corpus?: CorpusItem[];
  runScope?: RunScopeDefinition;
  corpusMatchesRunScope?: (item: CorpusItem, scope: RunScopeDefinition) => boolean;
}

const cleaningToggleItems = [
  ["strip_html", "HTML"],
  ["strip_urls", "URL"],
  ["strip_email", "邮箱"],
  ["strip_phone", "手机"],
  ["normalize_whitespace", "空白"],
  ["normalize_punctuation", "标点"],
  ["full_half_width_normalize", "全半角"],
  ["lowercase_english", "小写"],
  ["remove_emoji", "表情"],
  ["remove_special_chars", "特殊字符"]
] as const;

const normalizationToggleItems = [
  ["convert_traditional_to_simplified", "繁简"],
  ["normalize_numbers", "数字"],
  ["normalize_time_expr", "时间"],
  ["apply_regex_rules", "Regex"]
] as const;

const dictionaryToggleItems = [
  ["apply_standard_terms", "标准词"],
  ["apply_synonym_map", "同义词"],
  ["apply_near_synonym_map", "近义词"],
  ["apply_stopwords", "停用词"],
  ["apply_exclusion_terms", "排除词"]
] as const;

const dictionaryInputToggleItems = [
  ["use_custom_lexicon", "自定义词"],
  ["use_phrase_lexicon", "短语"],
  ["apply_regex_rules", "Regex"],
  ...dictionaryToggleItems
] as const;

function valueFor(
  node: WorkflowNodeInstance,
  definition: RegisteredWorkflowNodeDefinition | undefined,
  key: string,
  fallback?: unknown
): unknown {
  if (Object.prototype.hasOwnProperty.call(node.config ?? {}, key)) {
    return node.config[key];
  }
  const param = definition?.params.find((item) => item.param_id === key);
  if (param && Object.prototype.hasOwnProperty.call(param, "default_value")) {
    return param.default_value;
  }
  return fallback;
}

function optionLabel(definition: RegisteredWorkflowNodeDefinition | undefined, key: string, value: unknown): string {
  const textValue = String(value ?? "");
  const option = definition?.params
    .find((param) => param.param_id === key)
    ?.options
    ?.find((item) => item.value === textValue);
  return option?.label ?? textValue;
}

function enabledFlagLabels(
  node: WorkflowNodeInstance,
  definition: RegisteredWorkflowNodeDefinition | undefined,
  items: readonly (readonly [string, string])[]
): string[] {
  return items
    .filter(([key]) => Boolean(valueFor(node, definition, key, false)))
    .map(([, label]) => label);
}

function enabledDictionaryEntryCount(dictionarySet: DictionarySet | undefined): number {
  if (!dictionarySet) {
    return 0;
  }
  return Object.values(dictionarySet.sheets ?? {}).reduce(
    (count, sheet) => count + (sheet.entries ?? []).filter((entry) => entry.enabled).length,
    0
  );
}

function compactList(values: string[], emptyText: string): string {
  if (!values.length) {
    return emptyText;
  }
  const visible = values.slice(0, 3).join(" / ");
  return values.length > 3 ? `${visible} +${values.length - 3}` : visible;
}

function scopedCorpusCount(input: WorkflowNodeConfigFactsInput, scope: RunScopeDefinition | undefined): string | null {
  if (!scope || !input.corpus || !input.corpusMatchesRunScope) {
    return null;
  }
  const matchedCount = input.corpus.filter((item) => input.corpusMatchesRunScope?.(item, scope)).length;
  return `${matchedCount}/${input.corpus.length} 篇`;
}

function genericFacts(input: WorkflowNodeConfigFactsInput): WorkflowNodeConfigFact[] {
  const { node, definition } = input;
  if (!definition?.params.length) {
    return [{ label: "配置", value: "无需配置", tone: "muted" }];
  }

  return definition.params.slice(0, 3).map((param) => {
    const value = valueFor(node, definition, param.param_id, param.default_value);
    if (param.kind === "boolean") {
      return { label: param.label, value: value ? "开" : "关" };
    }
    if (param.kind === "enum") {
      return { label: param.label, value: optionLabel(definition, param.param_id, value) };
    }
    return { label: param.label, value: String(value ?? "默认") };
  });
}

export function workflowNodeConfigFacts(input: WorkflowNodeConfigFactsInput): WorkflowNodeConfigFact[] {
  const { node, definition, runtimeProfile, project } = input;
  const config = node.config ?? {};

  switch (node.node_type) {
    case "corpus_input": {
      const scope = input.runScope;
      const mode = String(scope?.mode ?? valueFor(node, definition, "mode", "all_documents"));
      const scopeCount = scopedCorpusCount(input, scope);
      const modeLabel = mode === "selected_documents" ? "点选文档" : mode === "filtered_subset" ? "条件筛选" : "全部资料";
      const facts: WorkflowNodeConfigFact[] = [{ label: "范围", value: modeLabel }];
      if (scopeCount) {
        facts.push({ label: "命中", value: scopeCount, tone: "success" });
      }
      if (scope?.mode === "filtered_subset") {
        const filters = [
          scope.source_values.length ? `${scope.source_values.length} 来源` : "",
          scope.institution_values.length ? `${scope.institution_values.length} 机构` : "",
          scope.category_values.length ? `${scope.category_values.length} 标签` : "",
          scope.year_from || scope.year_to ? `${scope.year_from ?? ""}-${scope.year_to ?? ""}` : ""
        ].filter(Boolean);
        facts.push({ label: "条件", value: compactList(filters, "待设置"), tone: filters.length ? "default" : "warning" });
      }
      if (scope?.mode === "selected_documents") {
        facts.push({ label: "已选", value: `${scope.selected_doc_ids.length} 篇` });
      }
      return facts;
    }

    case "dictionary_input": {
      const enabledRules = enabledFlagLabels(node, definition, dictionaryInputToggleItems);
      const selectedTables = Array.isArray(config.selected_table_ids) ? config.selected_table_ids.length : 0;
      return [
        { label: "词表", value: `${enabledDictionaryEntryCount(project?.dictionary_set)} 条启用`, tone: "success" },
        { label: "规则", value: `${enabledRules.length}/${dictionaryInputToggleItems.length} 类` },
        { label: "资源表", value: selectedTables ? `${selectedTables} 张` : "全部表" }
      ];
    }

    case "clean_text": {
      const enabled = enabledFlagLabels(node, definition, cleaningToggleItems);
      return [
        { label: "清洗", value: `${enabled.length}/${cleaningToggleItems.length} 项` },
        { label: "启用", value: compactList(enabled, "未启用"), tone: enabled.length ? "default" : "warning" }
      ];
    }

    case "normalize_text": {
      const enabled = enabledFlagLabels(node, definition, normalizationToggleItems);
      return [
        { label: "统一化", value: `${enabled.length}/${normalizationToggleItems.length} 项` },
        { label: "启用", value: compactList(enabled, "未启用"), tone: enabled.length ? "default" : "warning" }
      ];
    }

    case "tokenize":
      return [
        { label: "语言", value: optionLabel(definition, "language_mode", valueFor(node, definition, "language_mode", runtimeProfile.tokenization.language_mode)) },
        { label: "词典", value: [
          valueFor(node, definition, "use_custom_lexicon", runtimeProfile.tokenization.use_custom_lexicon) ? "自定义" : "",
          valueFor(node, definition, "use_phrase_lexicon", runtimeProfile.tokenization.use_phrase_lexicon) ? "短语" : ""
        ].filter(Boolean).join(" + ") || "未启用", tone: "default" },
        { label: "词长", value: `>= ${Number(valueFor(node, definition, "min_token_length_before_filter", runtimeProfile.tokenization.min_token_length_before_filter))}` },
        { label: "n-gram", value: valueFor(node, definition, "enable_ngrams", runtimeProfile.tokenization.enable_ngrams)
          ? `${Number(valueFor(node, definition, "ngram_min", runtimeProfile.tokenization.ngram_min))}-${Number(valueFor(node, definition, "ngram_max", runtimeProfile.tokenization.ngram_max))}`
          : "关", tone: "muted" }
      ];

    case "apply_dictionary_rules": {
      const enabled = enabledFlagLabels(node, definition, dictionaryToggleItems);
      return [
        { label: "规则", value: `${enabled.length}/${dictionaryToggleItems.length} 类` },
        { label: "启用", value: compactList(enabled, "未启用"), tone: enabled.length ? "default" : "warning" },
        { label: "冲突", value: optionLabel(definition, "conflict_resolution", valueFor(node, definition, "conflict_resolution", "priority")) }
      ];
    }

    case "filter_terms":
      return [
        { label: "词长", value: `>= ${Number(valueFor(node, definition, "min_token_length", runtimeProfile.filtering.min_token_length))}` },
        { label: "词频", value: `>= ${Number(valueFor(node, definition, "min_term_frequency", runtimeProfile.filtering.min_term_frequency))}` },
        { label: "数字词", value: valueFor(node, definition, "filter_numeric_tokens", runtimeProfile.filtering.filter_numeric_tokens) ? "过滤" : "保留" }
      ];

    case "frequency_statistics":
      return [{ label: "输出", value: `Top ${Number(valueFor(node, definition, "top_n", runtimeProfile.analysis.top_n))}` }];

    case "feature_term_selection":
      return [{ label: "规模", value: optionLabel(definition, "feature_term_count", valueFor(node, definition, "feature_term_count", runtimeProfile.analysis.feature_term_count)) }];

    case "cooccurrence_analysis":
      return [
        { label: "窗口", value: String(Number(valueFor(node, definition, "cooccurrence_window", runtimeProfile.analysis.cooccurrence_window))) },
        { label: "最小共现", value: String(Number(valueFor(node, definition, "min_cooccurrence", runtimeProfile.analysis.min_cooccurrence))) }
      ];

    case "keyword_extraction":
      return [
        { label: "文档", value: `Top ${Number(valueFor(node, definition, "top_k_per_doc", runtimeProfile.analysis.top_k_per_doc))}` },
        { label: "项目", value: `Top ${Number(valueFor(node, definition, "top_k_project", runtimeProfile.analysis.top_k_project))}` }
      ];

    case "keyword_clustering":
      return [
        { label: "聚类", value: String(Number(valueFor(node, definition, "keyword_cluster_k", runtimeProfile.analysis.keyword_cluster_k))) },
        { label: "主题", value: String(Number(valueFor(node, definition, "topic_model_k", runtimeProfile.analysis.topic_model_k))) }
      ];

    case "topic_modeling":
      return [
        { label: "算法", value: String(valueFor(node, definition, "topic_algorithm", runtimeProfile.analysis.topic_algorithm)).toUpperCase() },
        { label: "主题", value: String(Number(valueFor(node, definition, "topic_model_k", runtimeProfile.analysis.topic_model_k))) }
      ];

    case "similarity_analysis":
      return [
        { label: "算法", value: "Cosine" },
        { label: "阈值", value: `>= ${Number(valueFor(node, definition, "min_similarity", runtimeProfile.analysis.min_similarity))}` }
      ];

    case "save_csv":
    case "save_xlsx":
      return [
        { label: "表", value: optionLabel(definition, "table_key", valueFor(node, definition, "table_key", "frequency_table")) },
        { label: "前缀", value: String(valueFor(node, definition, "file_prefix", node.node_type === "save_csv" ? "tables" : "workbook")) }
      ];

    case "save_png":
      return [
        { label: "图表", value: optionLabel(definition, "chart_key", valueFor(node, definition, "chart_key", "frequency_top_terms")) },
        { label: "DPI", value: String(Number(valueFor(node, definition, "chart_dpi", runtimeProfile.export.chart_dpi))) }
      ];

    case "save_html_report":
      return [
        { label: "报告", value: String(valueFor(node, definition, "file_prefix", "report")) },
        { label: "审计", value: valueFor(node, definition, "include_audit", runtimeProfile.export.include_audit) ? "包含" : "不包含" }
      ];

    default:
      return genericFacts(input);
  }
}

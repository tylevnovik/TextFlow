import { memo, useDeferredValue, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";
import type { DragEvent as ReactDragEvent } from "react";
import {
  Button,
  Checkbox,
  DataGrid,
  DataGridBody,
  DataGridCell,
  DataGridHeader,
  DataGridHeaderCell,
  DataGridRow,
  Input,
  Select,
  Switch,
  Tab,
  TabList,
  Textarea,
  Toolbar,
  ToolbarButton,
  createTableColumn,
  type TableColumnDefinition
} from "@fluentui/react-components";
import {
  ChevronLeftRegular,
  ChevronRightRegular,
  SearchRegular
} from "@fluentui/react-icons";
import type {
  CorpusItem,
  DictionaryCollection,
  DictionaryEntry,
  DictionaryKind,
  DictionarySet,
  DictionaryTableResource,
  FieldMappingRule,
  ImportTemplate,
  NodeOutputPreview,
  NodeRunSummary,
  OutputBundleId,
  WorkflowRuntimeProfile,
  WorkflowRecipeId,
  WorkflowStepId,
  PageId,
  ProjectManifest,
  RegisteredWorkflowNodeDefinition,
  ResultBundle,
  RunScopeDefinition,
  WorkflowDefinition,
  WorkflowNodeInstance,
  WorkflowNodeRuntimeState,
  WorkflowRunProgressDetail,
  WorkflowPortType
} from "@textflow/shared-types";
import { sourceProfileImportTemplates, sourceProfiles } from "@textflow/shared-types";
import type { ImportProjectFilesResponse } from "./bridge/desktopBridge";
import { ArtifactBrowser } from "./features/artifacts/ArtifactBrowser";
import { CorpusWorkspace } from "./features/corpus/CorpusWorkspace";
import { LexiconWorkspace } from "./features/lexicon/LexiconWorkspace";
import { WorkflowWorkspace } from "./features/workflow/WorkflowWorkspace";
import {
  WORKFLOW_NODE_TYPE_MIME,
  WORKFLOW_WORKBENCH_ACTION_EVENT,
  type WorkflowWorkbenchAction
} from "./features/workflow/workflowWorkbenchActions";
import { ReportPreviewPage } from "./features/runs/ReportPreviewPage";
import { RunArtifactsPage } from "./features/runs/RunArtifactsPage";
import {
  parseWorkbenchSelectionPayload,
  WORKBENCH_SELECTION_MIME,
  type WorkbenchSelection
} from "./app/workbenchSelection";
import { runArtifactCompactSummary } from "./runArtifacts";
import { useTaskProgress, useWorkspace } from "./store/workspaceStore";
import {
  addWorkflowNodeByType,
  autoLayoutWorkflow,
  buildBlankWorkflowFromRuntimeProfile,
  compileRuntimeProfileFromWorkflow,
  createWorkflowEdge,
  normalizeWorkflowGraph,
  removeWorkflowEdge,
  removeWorkflowNodeById,
  resolveActiveWorkflow,
  resolveWorkflowRuntimeProfile,
  restoreWorkflowDefaultEdges,
  syncWorkflowFromRuntimeProfile,
  updateWorkflowMeta,
  updateWorkflowNode,
  updateWorkflowNodePosition,
  updateWorkflowViewport,
  validateWorkflowGraph,
  workflowConnectionTargets,
  workflowNodeCanRemove,
  workflowNodeDefinition,
  workflowNodeDescriptionForType,
  workflowNodeStepId
} from "./workflow";
import type { WorkflowValidation } from "./workflow";
import {
  AuditTable,
  DocumentPreview,
  EmptyState,
  Meta,
  Panel,
  StatCard,
  Table,
} from "./ui";
import type { DocumentPreviewMode } from "./ui";
import { renderWorkflowNodeInlineEditor, renderWorkflowNodePreview } from "./workflowNodeRegistry";
import { builtinWorkflowToolboxDefinitions } from "./workflowNodeCatalog";

const mappingTargetOptions: FieldMappingRule["target_field"][] = [
  "doc_id",
  "source_type",
  "title",
  "raw_text",
  "year",
  "source",
  "author",
  "institution",
  "country_or_region",
  "category_or_tag",
  "keyword_field",
  "extra_metadata"
];

const workflowStepMeta: Array<{ id: WorkflowStepId; title: string; description: string }> = [
  { id: "ingestion", title: "读取资料", description: "按导入模板识别字段，并拼出主文本。" },
  { id: "cleaning", title: "基础清洗", description: "去掉网页标签、网址、空白和杂乱标点。" },
  { id: "normalization", title: "统一写法", description: "把数字、时间和自定义规则统一成同一种写法。" },
  { id: "tokenization", title: "切词", description: "中英文混合切词，并尽量保留短语。" },
  { id: "dictionary_application", title: "套用词表", description: "处理停用词、同义词、标准词和排除词。" },
  { id: "filtering", title: "过滤噪声", description: "去掉太短、太少或无意义的词。" },
  { id: "analysis", title: "生成分析", description: "输出词频、共现、YAKE 关键词、NMF 主题和聚类。" },
  { id: "export", title: "保存结果", description: "写出表格、图表和 HTML 报告。" }
];

const mandatoryWorkflowSteps: WorkflowStepId[] = ["ingestion", "tokenization", "analysis", "export"];
const optionalWorkflowSteps: WorkflowStepId[] = ["cleaning", "normalization", "dictionary_application", "filtering"];
const fixedWorkflowOrder = workflowStepMeta.map((step) => step.id);
const cleaningToggleItems = [
  ["strip_html", "去 HTML"],
  ["strip_urls", "去 URL"],
  ["strip_email", "去邮箱"],
  ["strip_phone", "去手机号"],
  ["normalize_whitespace", "空白归一"],
  ["normalize_punctuation", "标点统一"],
  ["full_half_width_normalize", "全半角归一"],
  ["lowercase_english", "英文小写"],
  ["remove_emoji", "去表情"],
  ["remove_special_chars", "去特殊字符"]
] as const;
const normalizationToggleItems = [
  ["convert_traditional_to_simplified", "繁简转换"],
  ["normalize_numbers", "数字归一"],
  ["normalize_time_expr", "时间表达归一"],
  ["apply_regex_rules", "应用 Regex 规则"]
] as const;
const tokenizationToggleItems = [
  ["use_custom_lexicon", "使用自定义词典"],
  ["use_phrase_lexicon", "使用短语词典"],
  ["preserve_domain_phrases", "保留领域短语"],
  ["split_hyphenated_terms", "拆分连字符"],
  ["split_slash_terms", "拆分斜杠词"],
  ["normalize_camel_case", "拆分 camelCase"],
  ["keep_original_order", "保留原始顺序"],
  ["enable_ngrams", "生成 n-gram"]
] as const;
const dictionaryToggleItems = [
  ["apply_standard_terms", "应用标准词"],
  ["apply_synonym_map", "应用同义词"],
  ["apply_near_synonym_map", "应用近义词"],
  ["apply_stopwords", "应用停用词"],
  ["apply_exclusion_terms", "应用排除词"]
] as const;
const filteringToggleItems = [
  ["filter_numeric_tokens", "过滤纯数字词"],
  ["keep_single_char_important_terms", "保留重要单字词"],
  ["filter_by_pos", "尝试按词性过滤"]
] as const;
const exportToggleItems = [
  ["export_csv", "导出 CSV"],
  ["export_xlsx", "导出 XLSX"],
  ["export_png", "导出 PNG"],
  ["export_html_report", "导出 HTML 报告"],
  ["include_audit", "导出审计表"]
] as const;
const analysisMethodCards = [
  {
    title: "TF-IDF 特征词",
    output: "影响：特征词、关键词聚类、后续主题建模底稿",
    description: "先用 TF-IDF 找出更值得关注的词，避免常见虚词把后续结果冲淡。",
    params: ["特征词数量"]
  },
  {
    title: "YAKE 关键词",
    output: "影响：每篇文档关键词、项目级关键词",
    description: "再从每篇文档提炼更像“人会拿来做标签”的关键词，而不只是高频词。",
    params: ["每篇文档关键词数", "项目级关键词数"]
  },
  {
    title: "NMF / LDA 主题",
    output: "影响：机构 × 主题、主题标签摘要",
    description: "把一组经常共同出现的词归成主题，用来概括机构、年份或来源的关注方向。",
    params: ["主题算法", "主题数量"]
  },
  {
    title: "共现、相似度与聚类",
    output: "影响：共现表、相似度表、关键词聚类、文档聚类图",
    description: "用窗口共现、文档相似度和聚类把词与文档的关联结构展示出来，方便找热点和分组。",
    params: ["共现窗口", "最小共现次数", "最小相似度", "关键词聚类数", "文档聚类数"]
  }
] as const;
const runScopeModeOptions: Array<{ id: RunScopeDefinition["mode"]; title: string; description: string }> = [
  { id: "all_documents", title: "全部资料", description: "直接处理项目里的全部文档，适合第一次跑通全流程。" },
  { id: "filtered_subset", title: "按条件筛选", description: "只处理符合来源、年份、机构或标签条件的一部分资料。" },
  { id: "selected_documents", title: "手动点选文档", description: "从项目语料里勾选少量文档做试跑或抽样检查。" }
];
const recipeCards: Array<{
  id: WorkflowRecipeId;
  title: string;
  description: string;
  output: string;
}> = [
  {
    id: "standard_analysis",
    title: "标准分析",
    description: "保留清洗、统一写法、词表和过滤，适合大多数项目的第一次正式运行。",
    output: "词频、共现、关键词、主题、聚类"
  },
  {
    id: "keyword_topic",
    title: "关键词与主题",
    description: "更强调 YAKE 关键词和 NMF 主题，适合做机构主题、热点词和汇报摘要。",
    output: "关键词、主题、机构 × 主题、图表"
  },
  {
    id: "trend_scan",
    title: "趋势速览",
    description: "保留基础治理，但压缩聚类规模，更适合先看词频、年份和共现趋势。",
    output: "词频、年份、共现、轻量聚类"
  },
  {
    id: "custom",
    title: "自定义",
    description: "表示你已经手动改过详细设置，当前配方不再完全等同于内置预设。",
    output: "按当前高级设置执行"
  }
];
const outputBundleCards: Array<{
  id: OutputBundleId;
  title: string;
  description: string;
  output: string;
}> = [
  {
    id: "full_report",
    title: "完整汇报包",
    description: "适合正式留档和对外发包。",
    output: "CSV、XLSX、PNG、HTML、审计表"
  },
  {
    id: "tables_only",
    title: "表格包",
    description: "只导出可继续在 Excel 里处理的数据表。",
    output: "CSV、XLSX、审计表"
  },
  {
    id: "charts_and_report",
    title: "图表与报告包",
    description: "适合快速做展示或周报，不塞太多原始表格。",
    output: "PNG、HTML"
  },
  {
    id: "audit_archive",
    title: "审计留档包",
    description: "更强调过程留痕和规则审计。",
    output: "CSV、HTML、审计表"
  },
  {
    id: "custom",
    title: "自定义",
    description: "表示你已经手动改过导出设置。",
    output: "按当前导出开关执行"
  }
];
const sampleProjectName = "示例项目 - 学术摘要机构主题";
const CORPUS_BROWSER_PAGE_SIZE = 12;
const dictionaryGuideMap: Record<
  DictionaryKind,
  {
    stepLabel: string;
    purpose: string;
    sourceHint: string;
    targetHint: string;
    usesTarget: boolean;
    bulkExample: string;
  }
> = {
  custom_lexicon: {
    stepLabel: "切词",
    purpose: "把专业术语或产品名预先告诉切词器，避免被拆散。",
    sourceHint: "要保留的术语或专有名词",
    targetHint: "这张表不用填目标词",
    usesTarget: false,
    bulkExample: "生成式AI\n电池回收\n供应链金融"
  },
  phrase_lexicon: {
    stepLabel: "切词",
    purpose: "把多词短语固定成一个整体，适合英文词组或固定搭配。",
    sourceHint: "原始短语",
    targetHint: "统一后的短语，例如 supply_chain",
    usesTarget: true,
    bulkExample: "battery recycling => battery_recycling\nsupply chain => supply_chain"
  },
  regex_rules: {
    stepLabel: "统一写法",
    purpose: "用正则规则把时间、编号、网址等模式化内容统一替换。",
    sourceHint: "正则表达式",
    targetHint: "替换结果，例如 YEAR_TOKEN",
    usesTarget: true,
    bulkExample: "\\d{4}年 => YEAR_TOKEN\nhttps?://\\S+ => "
  },
  standard_terms: {
    stepLabel: "套用词表",
    purpose: "把不同写法统一到你规定的标准词上，方便做统计。",
    sourceHint: "原始词",
    targetHint: "标准词",
    usesTarget: true,
    bulkExample: "AIGC => 生成式AI\n供应链 => supply_chain"
  },
  synonym_map: {
    stepLabel: "套用词表",
    purpose: "把严格同义的叫法合并成一个词，减少重复统计。",
    sourceHint: "同义写法",
    targetHint: "合并后的统一词",
    usesTarget: true,
    bulkExample: "generative ai => 生成式AI\nbattery recycle => battery_recycling"
  },
  near_synonym_map: {
    stepLabel: "套用词表",
    purpose: "把意思相近但不完全相同的词归到同一主题，适合做粗粒度归类。",
    sourceHint: "近义词或相关概念",
    targetHint: "归并后的主题词",
    usesTarget: true,
    bulkExample: "文本挖掘 => 文本分析\n知识抽取 => 工艺知识"
  },
  stopwords: {
    stepLabel: "套用词表",
    purpose: "去掉没有分析意义的虚词、常用词或行业套话。",
    sourceHint: "要过滤掉的词",
    targetHint: "这张表不用填目标词",
    usesTarget: false,
    bulkExample: "的\n我们\n研究表明"
  },
  exclusion_terms: {
    stepLabel: "套用词表",
    purpose: "去掉虽然常出现，但与你当前课题无关的干扰词。",
    sourceHint: "要排除的词",
    targetHint: "这张表不用填目标词",
    usesTarget: false,
    bulkExample: "misc\netc\n附录"
  }
};

export type WorkbenchActivityId =
  | "home"
  | "project"
  | "corpus"
  | "lexicon"
  | "workflow_graph"
  | "run_artifacts"
  | "report"
  | "settings";

export type WorkbenchSurfaceRole = "core" | "support" | "system";

export interface PageActivityMeta {
  title: string;
  headline: string;
  tag: string;
  activity: WorkbenchActivityId;
  role: WorkbenchSurfaceRole;
  surfaceLabel: string;
}

export const workbenchPrimaryPages: PageId[] = ["home", "project", "data", "dictionaries", "workflow", "results", "settings"];

export const pageMeta: Record<PageId, PageActivityMeta> = {
  home: {
    title: "开始",
    headline: "管理本地项目仓库",
    tag: "开始",
    activity: "home",
    role: "system",
    surfaceLabel: "项目管理"
  },
  project: {
    title: "项目",
    headline: "查看三核心对象、来源文件和历史运行",
    tag: "项目",
    activity: "project",
    role: "core",
    surfaceLabel: "项目概览"
  },
  data: {
    title: "语料",
    headline: "管理导入批次、字段映射、主文本和文档视图",
    tag: "语料",
    activity: "corpus",
    role: "core",
    surfaceLabel: "语料工作面"
  },
  workflow: {
    title: "节点图",
    headline: "用节点引用语料和词库，并运行可复现流程",
    tag: "节点图",
    activity: "workflow_graph",
    role: "core",
    surfaceLabel: "节点图工作面"
  },
  dictionaries: {
    title: "词库",
    headline: "维护停用词、同义词、标准词和排除规则",
    tag: "词库",
    activity: "lexicon",
    role: "core",
    surfaceLabel: "词库工作面"
  },
  results: {
    title: "运行产物",
    headline: "查看运行历史、产物和导出动作",
    tag: "支撑",
    activity: "run_artifacts",
    role: "support",
    surfaceLabel: "运行支撑面"
  },
  report: {
    title: "报告预览",
    headline: "预览 HTML 报告结构和摘要",
    tag: "报告",
    activity: "report",
    role: "support",
    surfaceLabel: "产物预览"
  },
  settings: {
    title: "设置",
    headline: "查看默认偏好和本地配置",
    tag: "设置",
    activity: "settings",
    role: "system",
    surfaceLabel: "应用设置"
  }
};

function cloneTemplate(template: ImportTemplate): ImportTemplate {
  return {
    ...template,
    field_mappings: template.field_mappings.map((rule) => ({ ...rule, aliases: rule.aliases ? [...rule.aliases] : undefined })),
    text_build: {
      ...template.text_build,
      fields: [...template.text_build.fields]
    }
  };
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function projectRuntimeProfile(
  project: ProjectManifest | null | undefined,
  workflow?: WorkflowDefinition | null
): WorkflowRuntimeProfile {
  return normalizeRuntimeProfileDraft(resolveWorkflowRuntimeProfile(project, workflow));
}

const dictionaryKindOrder: DictionaryKind[] = [
  "stopwords",
  "custom_lexicon",
  "phrase_lexicon",
  "synonym_map",
  "near_synonym_map",
  "standard_terms",
  "exclusion_terms",
  "regex_rules"
];

const dictionaryCollectionMeta: Record<DictionaryKind, { name: string; description: string }> = {
  stopwords: { name: "停用词", description: "过滤虚词、套话和无分析意义的常用词。" },
  custom_lexicon: { name: "自定义词典", description: "告诉切词器哪些术语与专名要整体保留。" },
  phrase_lexicon: { name: "短语词典", description: "把固定搭配或多词短语作为一个整体处理。" },
  synonym_map: { name: "同义词表", description: "归并别名、替代表达和区域说法。" },
  near_synonym_map: { name: "近义词表", description: "保留更宽松的扩展归并规则，按需启用。" },
  standard_terms: { name: "标准词库", description: "把词形和写法统一成固定标准词。" },
  exclusion_terms: { name: "排除词表", description: "整批排除当前课题不想保留的人名、地名或噪声词。" },
  regex_rules: { name: "Regex 规则", description: "在清洗和标准化阶段使用的正则规则。" }
};

const DICTIONARY_ENTRY_PAGE_SIZE = 24;

function cloneDictionaryEntry(entry: DictionaryEntry, fallbackId: string): DictionaryEntry {
  return {
    ...entry,
    id: entry.id || fallbackId,
    source: entry.source ?? "",
    target: entry.target ?? "",
    enabled: Boolean(entry.enabled ?? true),
    hits: Number(entry.hits ?? 0),
    tags: [...(entry.tags ?? [])],
    notes: entry.notes ?? ""
  };
}

function cloneDictionaryCollectionsForDraft(dictionarySet: DictionarySet): Record<DictionaryKind, DictionaryCollection> {
  const collections = {} as Record<DictionaryKind, DictionaryCollection>;

  dictionaryKindOrder.forEach((kind) => {
    const existingCollection = dictionarySet.collections?.[kind];
    if (existingCollection && Array.isArray(existingCollection.tables)) {
      collections[kind] = {
        kind,
        name: existingCollection.name || dictionaryCollectionMeta[kind].name,
        description: existingCollection.description || dictionaryCollectionMeta[kind].description,
        tables: existingCollection.tables.map((table, tableIndex) => ({
          id: table.id || `${kind}-table-${tableIndex + 1}`,
          kind,
          name: table.name || `${dictionaryCollectionMeta[kind].name} ${tableIndex + 1}`,
          version: table.version || "2.0.0",
          description: table.description || "",
          source_url: table.source_url,
          built_in: Boolean(table.built_in),
          editable: Boolean(table.editable ?? !table.built_in),
          enabled: Boolean(table.enabled ?? true),
          tags: [...(table.tags ?? [])],
          entries: table.editable
            ? (table.entries ?? []).map((entry, entryIndex) =>
                cloneDictionaryEntry(entry, `${kind}-entry-${tableIndex}-${entryIndex}`)
              )
            : (table.entries ?? [])
        }))
      };
      return;
    }

    const legacySheet = dictionarySet.sheets?.[kind];
    collections[kind] = {
      kind,
      name: legacySheet?.name || dictionaryCollectionMeta[kind].name,
      description: dictionaryCollectionMeta[kind].description,
      tables: [
        {
          id: `${kind}-project-custom`,
          kind,
          name: "项目自定义",
          version: legacySheet?.version || "2.0.0",
          description: "从旧版单表结构自动迁移的项目内词表资源。",
          source_url: undefined,
          built_in: false,
          editable: true,
          enabled: true,
          tags: [],
          entries: (legacySheet?.entries ?? []).map((entry, entryIndex) =>
            cloneDictionaryEntry(entry, `${kind}-legacy-${entryIndex}`)
          )
        }
      ]
    };
  });

  return collections;
}

function normalizeDictionaryDraft(dictionarySet: DictionarySet): DictionarySet {
  return {
    ...dictionarySet,
    version: dictionarySet.version || "2.0.0",
    collections: cloneDictionaryCollectionsForDraft(dictionarySet)
  };
}

function createEmptyDictionaryTable(kind: DictionaryKind, tableName = "新建资源表"): DictionaryTableResource {
  return {
    id: `${kind}-table-${Date.now()}`,
    kind,
    name: tableName,
    version: "2.0.0",
    description: "",
    source_url: undefined,
    built_in: false,
    editable: true,
    enabled: true,
    tags: [],
    entries: []
  };
}

function emptyMappingRule(): FieldMappingRule {
  return {
    source_field: "",
    target_field: "title",
    aliases: []
  };
}

function buildTemplateFromProfile(template: ImportTemplate, sourceProfile: ImportTemplate["source_profile"]): ImportTemplate {
  const preset = sourceProfileImportTemplates[sourceProfile];
  return {
    ...template,
    id: `template-${sourceProfile}`,
    name: preset.name,
    description: preset.description,
    source_profile: sourceProfile,
    field_mappings: preset.field_mappings.map((rule) => ({
      ...rule,
      aliases: rule.aliases ? [...rule.aliases] : []
    })),
    text_build: {
      ...preset.text_build,
      fields: [...preset.text_build.fields]
    }
  };
}

function summarizeImportTemplate(template: ImportTemplate) {
  const requiredMappings = template.field_mappings.filter((rule) => rule.required);
  const issues: string[] = [];
  if (!template.name.trim()) {
    issues.push("模板名称不能为空。");
  }
  if (!template.text_build.fields.length) {
    issues.push("至少需要一个主文本字段。");
  }
  if (!template.field_mappings.length) {
    issues.push("至少需要一条字段映射。");
  }
  if (requiredMappings.some((rule) => !rule.source_field.trim())) {
    issues.push("必填映射的源字段名不能为空。");
  }
  return { requiredMappings, issues };
}

function cloneCorpusItem(doc: CorpusItem): CorpusItem {
  return {
    ...doc,
    tokens: [...doc.tokens],
    phrase_hits: [...doc.phrase_hits],
    filtered_tokens: [...doc.filtered_tokens],
    extra_metadata: { ...doc.extra_metadata }
  };
}

function previewSummary(doc: CorpusItem): string {
  return doc.raw_text.length > 72 ? `${doc.raw_text.slice(0, 72)}...` : doc.raw_text;
}

function normalizeRuntimeProfileDraft(runtimeProfile: WorkflowRuntimeProfile): WorkflowRuntimeProfile {
  const enabledOptionalSteps = optionalWorkflowSteps.filter((step) => runtimeProfile.enabled_steps.includes(step));
  return {
    ...runtimeProfile,
    tokenization: {
      ...runtimeProfile.tokenization,
      enable_ngrams: runtimeProfile.tokenization.enable_ngrams ?? false,
      ngram_min: runtimeProfile.tokenization.ngram_min ?? 2,
      ngram_max: runtimeProfile.tokenization.ngram_max ?? 2
    },
    analysis: {
      ...runtimeProfile.analysis,
      similarity_method: runtimeProfile.analysis.similarity_method ?? "cosine",
      min_similarity: runtimeProfile.analysis.min_similarity ?? 0.2,
      similarity_top_k: runtimeProfile.analysis.similarity_top_k ?? 200,
      topic_algorithm: runtimeProfile.analysis.topic_algorithm ?? "nmf",
      topic_model_k: runtimeProfile.analysis.topic_model_k ?? runtimeProfile.analysis.keyword_cluster_k ?? 4
    },
    export: {
      ...runtimeProfile.export,
      chart_dpi: runtimeProfile.export.chart_dpi ?? 320,
      watermark_enabled: runtimeProfile.export.watermark_enabled ?? false,
      watermark_text: runtimeProfile.export.watermark_text ?? "TextFlow Studio"
    },
    run_scope: {
      mode: runtimeProfile.run_scope?.mode ?? "all_documents",
      source_values: [...(runtimeProfile.run_scope?.source_values ?? [])],
      institution_values: [...(runtimeProfile.run_scope?.institution_values ?? [])],
      category_values: [...(runtimeProfile.run_scope?.category_values ?? [])],
      year_from: runtimeProfile.run_scope?.year_from ?? null,
      year_to: runtimeProfile.run_scope?.year_to ?? null,
      selected_doc_ids: [...(runtimeProfile.run_scope?.selected_doc_ids ?? [])]
    },
    recipe_id: runtimeProfile.recipe_id ?? "standard_analysis",
    output_bundle_id: runtimeProfile.output_bundle_id ?? "full_report",
    enabled_steps: [...mandatoryWorkflowSteps, ...enabledOptionalSteps],
    execution_order: [...fixedWorkflowOrder]
  };
}

function applyRecipePreset(runtimeProfile: WorkflowRuntimeProfile, recipeId: WorkflowRecipeId): WorkflowRuntimeProfile {
  const next = normalizeRuntimeProfileDraft(deepClone(runtimeProfile));
  next.recipe_id = recipeId;

  if (recipeId === "standard_analysis") {
    next.enabled_steps = [...mandatoryWorkflowSteps, ...optionalWorkflowSteps];
    next.normalization.convert_traditional_to_simplified = false;
    next.normalization.normalize_time_expr = false;
    next.filtering.min_term_frequency = 1;
    next.analysis.top_k_per_doc = 10;
    next.analysis.top_k_project = 100;
    next.analysis.topic_model_k = 4;
    next.analysis.keyword_cluster_k = 4;
    next.analysis.document_cluster_k = 4;
    return normalizeRuntimeProfileDraft(next);
  }

  if (recipeId === "keyword_topic") {
    next.enabled_steps = [...mandatoryWorkflowSteps, ...optionalWorkflowSteps];
    next.normalization.convert_traditional_to_simplified = true;
    next.normalization.normalize_time_expr = true;
    next.filtering.min_term_frequency = 1;
    next.analysis.top_k_per_doc = 12;
    next.analysis.top_k_project = 120;
    next.analysis.topic_model_k = 6;
    next.analysis.keyword_cluster_k = 5;
    next.analysis.document_cluster_k = 4;
    next.export.export_png = true;
    next.export.export_html_report = true;
    return normalizeRuntimeProfileDraft(next);
  }

  if (recipeId === "trend_scan") {
    next.enabled_steps = [...mandatoryWorkflowSteps, "cleaning", "dictionary_application", "filtering"];
    next.normalization.convert_traditional_to_simplified = false;
    next.normalization.normalize_time_expr = false;
    next.analysis.top_n = 120;
    next.analysis.cooccurrence_window = 4;
    next.analysis.min_cooccurrence = 2;
    next.analysis.top_k_per_doc = 6;
    next.analysis.top_k_project = 60;
    next.analysis.topic_model_k = 3;
    next.analysis.keyword_cluster_k = 3;
    next.analysis.document_cluster_k = 3;
    return normalizeRuntimeProfileDraft(next);
  }

  return normalizeRuntimeProfileDraft(next);
}

function applyOutputBundlePreset(runtimeProfile: WorkflowRuntimeProfile, bundleId: OutputBundleId): WorkflowRuntimeProfile {
  const next = normalizeRuntimeProfileDraft(deepClone(runtimeProfile));
  next.output_bundle_id = bundleId;

  if (bundleId === "full_report") {
    next.export = {
      ...next.export,
      export_csv: true,
      export_xlsx: true,
      export_png: true,
      export_html_report: true,
      include_audit: true
    };
  } else if (bundleId === "tables_only") {
    next.export = {
      ...next.export,
      export_csv: true,
      export_xlsx: true,
      export_png: false,
      export_html_report: false,
      include_audit: true
    };
  } else if (bundleId === "charts_and_report") {
    next.export = {
      ...next.export,
      export_csv: false,
      export_xlsx: false,
      export_png: true,
      export_html_report: true,
      include_audit: false
    };
  } else if (bundleId === "audit_archive") {
    next.export = {
      ...next.export,
      export_csv: true,
      export_xlsx: false,
      export_png: false,
      export_html_report: true,
      include_audit: true
    };
  }

  return normalizeRuntimeProfileDraft(next);
}

function outputBundleSummary(exportParams: WorkflowRuntimeProfile["export"]): string {
  const labels: string[] = [];
  if (exportParams.export_csv || exportParams.export_xlsx) {
    labels.push("表格包");
  }
  if (exportParams.export_png) {
    labels.push("图表包");
  }
  if (exportParams.export_html_report) {
    labels.push("HTML 报告");
  }
  if (exportParams.include_audit) {
    labels.push("审计表");
  }
  return labels.join("、") || "仅运行快照";
}

function workflowNodeDescription(node: WorkflowNodeInstance): string {
  return workflowNodeDescriptionForType(node.node_type);
}

function countEnabledFlags(values: Record<string, unknown>, keys: readonly (readonly [string, string])[]): number {
  return keys.reduce((count, [key]) => count + (values[key] ? 1 : 0), 0);
}

function workflowNodeSummary(node: WorkflowNodeInstance, runtimeProfile: WorkflowRuntimeProfile, runSummary: string): string {
  const config = node.config ?? {};
  switch (node.node_type) {
    case "corpus_input":
      if (config.mode === "selected_documents") {
        return `手动选择 ${((config.selected_doc_ids as string[] | undefined) ?? []).length} 篇文档`;
      }
      if (config.mode === "filtered_subset") {
        return "按来源/机构/年份等条件筛选";
      }
      return "项目全部文档";
    case "dictionary_input":
      return "引用项目词表资源";
    case "merge_corpora":
      return `合并策略：${String(config.strategy ?? "append") === "dedupe" ? "按 doc_id 去重" : "直接追加"}`;
    case "clean_text":
      return `${countEnabledFlags(config, cleaningToggleItems)} 个清洗开关`;
    case "normalize_text":
      return `${countEnabledFlags(config, normalizationToggleItems)} 个统一化开关`;
    case "tokenize":
      return `${String(config.language_mode ?? runtimeProfile.tokenization.language_mode)} · 最短长度 ${Number(config.min_token_length_before_filter ?? runtimeProfile.tokenization.min_token_length_before_filter)}`;
    case "apply_dictionary_rules":
      return `${countEnabledFlags(config, dictionaryToggleItems)} 类词表规则`;
    case "filter_terms":
      return `长度 >= ${Number(config.min_token_length ?? runtimeProfile.filtering.min_token_length)} · 词频 >= ${Number(config.min_term_frequency ?? runtimeProfile.filtering.min_term_frequency)}`;
    case "frequency_statistics":
      return `词频 Top ${Number(config.top_n ?? runtimeProfile.analysis.top_n)}`;
    case "term_year_analysis":
      return "输出词项年份变化";
    case "cooccurrence_analysis":
      return `窗口 ${Number(config.cooccurrence_window ?? runtimeProfile.analysis.cooccurrence_window)} · 最小共现 ${Number(config.min_cooccurrence ?? runtimeProfile.analysis.min_cooccurrence)}`;
    case "similarity_analysis":
      return `Cosine · >= ${Number(config.min_similarity ?? runtimeProfile.analysis.min_similarity)}`;
    case "keyword_extraction":
      return `文档 ${Number(config.top_k_per_doc ?? runtimeProfile.analysis.top_k_per_doc)} · 项目 ${Number(config.top_k_project ?? runtimeProfile.analysis.top_k_project)}`;
    case "keyword_clustering":
      return `聚类 ${Number(config.keyword_cluster_k ?? runtimeProfile.analysis.keyword_cluster_k)} · 主题 ${Number(config.topic_model_k ?? runtimeProfile.analysis.topic_model_k)}`;
    case "institution_topic_analysis":
      return `主题 ${Number(config.topic_model_k ?? runtimeProfile.analysis.topic_model_k)}`;
    case "topic_modeling":
      return `${String(config.topic_algorithm ?? runtimeProfile.analysis.topic_algorithm).toUpperCase()} · 主题 ${Number(config.topic_model_k ?? runtimeProfile.analysis.topic_model_k)}`;
    case "save_csv":
      return `CSV · ${String(config.file_prefix ?? "tables")}`;
    case "save_xlsx":
      return `XLSX · ${String(config.file_prefix ?? "tables")}`;
    case "save_png":
      return `PNG · ${Number(config.chart_dpi ?? runtimeProfile.export.chart_dpi)} DPI`;
    case "save_html_report":
      return `${Boolean(config.include_audit ?? runtimeProfile.export.include_audit) ? "含审计" : "不含审计"} · ${String(config.file_prefix ?? "report")}`;
    case "note":
      return String(config.text ?? "画布备注");
    case "group":
      return String(config.title ?? "分组容器");
    case "load_project_corpus":
      return "旧版项目语料入口";
    case "filter_corpus":
      return runSummary;
    case "project_dictionary_set":
      return "旧版项目词表入口";
    case "analyze_corpus":
      return `Top ${runtimeProfile.analysis.top_n} · 主题 ${runtimeProfile.analysis.topic_model_k} · 聚类 ${runtimeProfile.analysis.keyword_cluster_k}`;
    case "export_results":
      return outputBundleSummary(runtimeProfile.export);
    default:
      return "等待配置";
  }
}

function workflowNodeBadge(node: WorkflowNodeInstance, validation?: WorkflowValidation): string {
  if (validation?.missing_inputs_by_node_id[node.node_id]?.length) {
    return "缺线";
  }
  if (validation && !validation.reachable_node_ids.includes(node.node_id) && node.inputs.length) {
    return "未接入";
  }
  if (node.ui_state.bypassed) {
    return "已跳过";
  }
  if (node.node_type === "corpus_input" || node.node_type === "dictionary_input" || node.node_type === "load_project_corpus" || node.node_type === "project_dictionary_set") {
    return "输入";
  }
  if (node.node_type === "merge_corpora") {
    return "合并";
  }
  if (node.node_type === "save_csv" || node.node_type === "save_xlsx" || node.node_type === "save_png" || node.node_type === "save_html_report" || node.node_type === "export_results") {
    return "输出";
  }
  const stepId = workflowNodeStepId(node);
  if (!stepId) {
    return node.node_type === "filter_corpus" ? "范围" : "辅助";
  }
  return stepId === "analysis" ? "分析" : "处理";
}

const workflowCanvasNodeWidth = 220;
const workflowCanvasNodeHeight = 190;
const workflowCanvasPadding = 160;
const workflowCanvasMinWidth = 12000;
const workflowCanvasMinHeight = 7600;
const workflowCanvasBaseOriginX = 5200;
const workflowCanvasBaseOriginY = 3200;

function workflowDraftStorageKey(projectId: string, workflowId: string): string {
  return `textflow.workflow-draft.${projectId}.${workflowId}`;
}

function workflowEditorStateStorageKey(projectId: string, workflowId: string): string {
  return `textflow.workflow-ui.${projectId}.${workflowId}`;
}

function loadPersistedWorkflowDraft(projectId: string, workflowId: string): WorkflowDefinition | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(workflowDraftStorageKey(projectId, workflowId));
    return raw ? JSON.parse(raw) as WorkflowDefinition : null;
  } catch {
    return null;
  }
}

function loadPersistedWorkflowEditorState(
  projectId: string,
  workflowId: string
): {
  selectedNodeId?: string;
  selectedEdgeId?: string;
  documentPickerQuery?: string;
} | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(workflowEditorStateStorageKey(projectId, workflowId));
    return raw ? JSON.parse(raw) as {
      selectedNodeId?: string;
      selectedEdgeId?: string;
      documentPickerQuery?: string;
    } : null;
  } catch {
    return null;
  }
}

function clampWorkflowZoom(zoom: number): number {
  return Math.min(1.2, Math.max(0.5, Math.round(zoom * 100) / 100));
}

function workflowNodeCanvasFrame(nodeOrType: WorkflowNodeInstance | WorkflowNodeInstance["node_type"]) {
  const nodeType = typeof nodeOrType === "string" ? nodeOrType : nodeOrType.node_type;
  const declaredSize = workflowNodeDefinition(nodeType).size;
  if (declaredSize) {
    return declaredSize;
  }
  if (typeof nodeOrType !== "string" && nodeOrType.size) {
    return nodeOrType.size;
  }
  return { w: workflowCanvasNodeWidth, h: workflowCanvasNodeHeight };
}

function workflowCanvasMetrics(nodes: WorkflowNodeInstance[]) {
  const minX = Math.min(...nodes.map((node) => node.position.x), 0);
  const minY = Math.min(...nodes.map((node) => node.position.y), 0);
  const maxX = Math.max(...nodes.map((node) => node.position.x + workflowNodeCanvasFrame(node).w), workflowCanvasNodeWidth);
  const maxY = Math.max(...nodes.map((node) => node.position.y + workflowNodeCanvasFrame(node).h), workflowCanvasNodeHeight);
  return {
    minX,
    minY,
    maxX,
    maxY,
    width: Math.max(
      workflowCanvasMinWidth,
      workflowCanvasBaseOriginX + maxX + workflowCanvasPadding,
      workflowCanvasBaseOriginX - minX + workflowCanvasPadding
    ),
    height: Math.max(
      workflowCanvasMinHeight,
      workflowCanvasBaseOriginY + maxY + workflowCanvasPadding,
      workflowCanvasBaseOriginY - minY + workflowCanvasPadding
    )
  };
}

function workflowFitViewport(_nodes: WorkflowNodeInstance[]) {
  const minX = Math.min(..._nodes.map((node) => node.position.x), 0);
  const minY = Math.min(..._nodes.map((node) => node.position.y), 0);
  const zoom = 0.82;
  return {
    x: 96 - (workflowCanvasBaseOriginX + minX) * zoom,
    y: 132 - (workflowCanvasBaseOriginY + minY) * zoom,
    zoom
  };
}

function workflowViewportNeedsInitialFit(workflow: WorkflowDefinition, hasPersistedDraft: boolean): boolean {
  if (!workflow.nodes.length) {
    return false;
  }
  if (!hasPersistedDraft) {
    return true;
  }
  const viewport = workflow.viewport;
  return Math.abs(viewport.x ?? 0) < 1 && Math.abs(viewport.y ?? 0) < 1;
}

function workflowCanvasOrigin(_metrics: ReturnType<typeof workflowCanvasMetrics>) {
  return {
    x: workflowCanvasBaseOriginX,
    y: workflowCanvasBaseOriginY
  };
}

function workflowMiniMapMetrics(metrics: ReturnType<typeof workflowCanvasMetrics>) {
  const maxWidth = 220;
  const maxHeight = 150;
  const boundsPadding = 120;
  const originX = workflowCanvasBaseOriginX + metrics.minX - boundsPadding;
  const originY = workflowCanvasBaseOriginY + metrics.minY - boundsPadding;
  const worldWidth = Math.max(1, metrics.maxX - metrics.minX + boundsPadding * 2);
  const worldHeight = Math.max(1, metrics.maxY - metrics.minY + boundsPadding * 2);
  const scale = Math.min(maxWidth / worldWidth, maxHeight / worldHeight);
  return {
    originX,
    originY,
    scale,
    width: worldWidth * scale,
    height: worldHeight * scale
  };
}

function workflowMiniMapViewportRect(
  viewportWorldRect: { x: number; y: number; width: number; height: number },
  miniMap: ReturnType<typeof workflowMiniMapMetrics>
) {
  const rawLeft = (viewportWorldRect.x - miniMap.originX) * miniMap.scale;
  const rawTop = (viewportWorldRect.y - miniMap.originY) * miniMap.scale;
  const rawRight = (viewportWorldRect.x + viewportWorldRect.width - miniMap.originX) * miniMap.scale;
  const rawBottom = (viewportWorldRect.y + viewportWorldRect.height - miniMap.originY) * miniMap.scale;
  const clampedLeft = Math.max(0, Math.min(miniMap.width, Math.min(rawLeft, rawRight)));
  const clampedTop = Math.max(0, Math.min(miniMap.height, Math.min(rawTop, rawBottom)));
  const clampedRight = Math.max(0, Math.min(miniMap.width, Math.max(rawLeft, rawRight)));
  const clampedBottom = Math.max(0, Math.min(miniMap.height, Math.max(rawTop, rawBottom)));
  const width = Math.min(miniMap.width, Math.max(6, clampedRight - clampedLeft));
  const height = Math.min(miniMap.height, Math.max(6, clampedBottom - clampedTop));
  return {
    left: Math.max(0, Math.min(miniMap.width - width, clampedLeft)),
    top: Math.max(0, Math.min(miniMap.height - height, clampedTop)),
    width,
    height
  };
}

function workflowViewportWorldRect(
  viewport: { x: number; y: number; zoom: number },
  canvasViewportSize: { width: number; height: number }
) {
  return {
    x: -viewport.x / viewport.zoom,
    y: -viewport.y / viewport.zoom,
    width: Math.max(120, (canvasViewportSize.width || 920) / viewport.zoom),
    height: Math.max(80, (canvasViewportSize.height || 640) / viewport.zoom)
  };
}

const workflowPortRailInset = 20;

function workflowPortLocalCenter(
  node: WorkflowNodeInstance,
  portId: string,
  direction: "inputs" | "outputs"
) {
  const ports = node[direction];
  const portIndex = Math.max(0, ports.findIndex((port) => port.port_id === portId));
  const { h: nodeHeight } = workflowNodeCanvasFrame(node);
  const usableHeight = Math.max(60, nodeHeight - workflowPortRailInset * 2);
  const rowGap = usableHeight / (ports.length + 1);
  return workflowPortRailInset + rowGap * (portIndex + 1);
}

function workflowPortAnchor(
  node: WorkflowNodeInstance,
  portId: string,
  direction: "inputs" | "outputs",
  origin: { x: number; y: number }
) {
  return {
    x: (direction === "outputs" ? node.position.x + workflowNodeCanvasFrame(node).w : node.position.x) + origin.x,
    y: node.position.y + workflowPortLocalCenter(node, portId, direction) + origin.y
  };
}

function workflowEdgePath(
  fromNode: WorkflowNodeInstance,
  toNode: WorkflowNodeInstance,
  fromPortId: string,
  toPortId: string,
  origin: { x: number; y: number }
): string {
  const fromPoint = workflowPortAnchor(fromNode, fromPortId, "outputs", origin);
  const toPoint = workflowPortAnchor(toNode, toPortId, "inputs", origin);
  const deltaX = toPoint.x - fromPoint.x;
  const verticalLink = Math.abs(deltaX) < 140;

  if (verticalLink) {
    const midY = (fromPoint.y + toPoint.y) / 2;
    return `M ${fromPoint.x} ${fromPoint.y} C ${fromPoint.x} ${midY}, ${toPoint.x} ${midY}, ${toPoint.x} ${toPoint.y}`;
  }

  const controlX = fromPoint.x + Math.max(60, (toPoint.x - fromPoint.x) / 2);
  return `M ${fromPoint.x} ${fromPoint.y} C ${controlX} ${fromPoint.y}, ${controlX} ${toPoint.y}, ${toPoint.x} ${toPoint.y}`;
}

function workflowPortLabel(
  node: WorkflowNodeInstance | undefined,
  portId: string,
  direction: "inputs" | "outputs"
): string {
  const port = node?.[direction].find((item) => item.port_id === portId);
  return port?.label ?? port?.port_id ?? portId;
}

function workflowPortTitle(port: WorkflowNodeInstance["inputs"][number]): string {
  const label = port.label ?? port.port_id;
  return `${label} · ${port.port_type} · ${port.port_id}`;
}

function workflowPortType(
  node: WorkflowNodeInstance | undefined,
  portId: string,
  direction: "inputs" | "outputs"
): WorkflowPortType | "Unknown" {
  const port = node?.[direction].find((item) => item.port_id === portId);
  return port?.port_type ?? "Unknown";
}

function enabledDictionaryEntryCount(dictionarySet: DictionarySet): number {
  return Object.values(dictionarySet.sheets).reduce(
    (count, sheet) => count + sheet.entries.filter((entry) => entry.enabled).length,
    0
  );
}

function previewSampleTexts(documents: CorpusItem[], field: "raw_text" | "clean_text" | "normalized_text"): string[] {
  return documents
    .map((item) => item[field]?.trim())
    .filter(Boolean)
    .slice(0, 2) as string[];
}

function previewSampleTerms(documents: CorpusItem[], field: "tokens" | "phrase_hits" | "filtered_tokens"): string[] {
  return documents
    .flatMap((item) => item[field] ?? [])
    .filter(Boolean)
    .slice(0, 12);
}

function stringifyNodeOutputPreviewCell(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => stringifyNodeOutputPreviewCell(item)).filter(Boolean).slice(0, 12).join(" / ");
  }
  if (value && typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value ?? "—");
}

function renderPersistedNodeOutputPreview(nodeRuntime?: WorkflowNodeRuntimeState) {
  const previewEntries = Object.entries(nodeRuntime?.output_previews ?? {})
    .filter((entry): entry is [string, NodeOutputPreview] => Boolean(entry[1]) && entry[1].kind !== "empty");
  if (!previewEntries.length) {
    return null;
  }
  const [portId, preview] = previewEntries[0];
  const rowCount = Number(preview.row_count ?? 0);

  if (preview.kind === "table" && preview.rows?.length) {
    const rows = preview.rows.slice(0, 5).map((row) =>
      Object.fromEntries(
        Object.entries(row).map(([key, value]) => [key, stringifyNodeOutputPreviewCell(value)])
      )
    );
    const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 8);
    return (
      <Panel title="节点输出预览（最近一次运行）">
        <div className="status-panel"><strong>输出端口</strong><span>{portId} · {rowCount} 行</span></div>
        <Table columns={columns} rows={rows} />
      </Panel>
    );
  }

  if (preview.kind === "list" && preview.items?.length) {
    return (
      <Panel title="节点输出预览（最近一次运行）">
        <div className="status-panel"><strong>输出端口</strong><span>{portId} · {rowCount} 项</span></div>
        <ul className="micro-list">
          {preview.items.slice(0, 8).map((item, index) => <li key={`${portId}-${index}`}>{item}</li>)}
        </ul>
      </Panel>
    );
  }

  if (preview.kind === "text" && preview.text) {
    return (
      <Panel title="节点输出预览（最近一次运行）">
        <div className="status-panel"><strong>输出端口</strong><span>{portId}</span></div>
        <p className="body-copy preview-copy">{preview.text}</p>
      </Panel>
    );
  }

  if ((preview.kind === "object" || preview.kind === "scalar") && preview.value !== undefined) {
    return (
      <Panel title="节点输出预览（最近一次运行）">
        <div className="status-panel"><strong>输出端口</strong><span>{portId}</span></div>
        <pre className="code-box preview-code">{stringifyNodeOutputPreviewCell(preview.value)}</pre>
      </Panel>
    );
  }

  if (preview.kind === "object" && preview.keys?.length) {
    return (
      <Panel title="节点输出预览（最近一次运行）">
        <div className="status-panel"><strong>输出端口</strong><span>{portId}</span></div>
        <div className="status-panel"><strong>字段</strong><span>{preview.keys.join(" / ")}</span></div>
      </Panel>
    );
  }

  return null;
}

function edgeDataSummary(
  portType: WorkflowPortType | "Unknown",
  project: ProjectManifest,
  matchedDocuments: CorpusItem[],
  latestRun: ProjectManifest["run_history"][number] | undefined
): { summary: string; samples: string[] } {
  const results: ResultBundle = project.results;
  switch (portType) {
    case "CorpusTable":
    case "ProjectCorpus":
    case "ScopedCorpus":
      return {
        summary: `当前项目共有 ${project.source_files.length} 个导入源、${matchedDocuments.length} 篇当前可见文档。`,
        samples: matchedDocuments.slice(0, 3).map((item) => item.title)
      };
    case "CleanCorpus":
    case "NormalizedCorpus":
    case "TokenCorpus":
    case "FilteredTokenCorpus":
      return {
        summary: `当前范围内共有 ${matchedDocuments.length} 篇文档参与流转。`,
        samples: matchedDocuments.slice(0, 3).map((item) => item.title)
      };
    case "DictionarySet":
      return {
        summary: `当前项目词表集中启用了 ${enabledDictionaryEntryCount(project.dictionary_set)} 条规则/词项。`,
        samples: Object.values(project.dictionary_set.sheets)
          .flatMap((sheet) => sheet.entries.filter((entry) => entry.enabled).slice(0, 2).map((entry) => `${sheet.name}：${entry.source}`))
          .slice(0, 4)
      };
    case "FrequencyTable":
      return {
        summary: `当前结果快照包含 ${results.frequency_table.length} 条词频统计。`,
        samples: results.frequency_table.slice(0, 5).map((row) => `${row.term} · ${row.tf}`)
      };
    case "TermDocumentTable":
      return {
        summary: `当前结果快照包含 ${results.term_document_table.length} 条词项-文档关系。`,
        samples: results.term_document_table.slice(0, 5).map((row) => `${row.term} · ${row.doc_id}`)
      };
    case "TermYearTable":
      return {
        summary: `当前结果快照包含 ${results.term_year_table.length} 条词项年份记录。`,
        samples: results.term_year_table.slice(0, 5).map((row) => `${row.term} · ${row.year}`)
      };
    case "CooccurrenceTable":
      return {
        summary: `当前结果快照包含 ${results.cooccurrence_table.length} 条共现关系。`,
        samples: results.cooccurrence_table.slice(0, 5).map((row) => `${row.term_a} × ${row.term_b}`)
      };
    case "KeywordTable":
      return {
        summary: `当前结果快照包含 ${results.keyword_result.length} 条关键词。`,
        samples: results.keyword_result.slice(0, 5).map((row) => `${row.keyword} · ${row.scope}`)
      };
    case "KeywordClusterTable":
      return {
        summary: `当前结果快照包含 ${results.keyword_cluster_result.length} 条关键词聚类结果。`,
        samples: results.keyword_cluster_result.slice(0, 5).map((row) => `${row.topic_label ?? `簇 ${row.cluster_id}`} · ${row.term}`)
      };
    case "InstitutionTopicTable":
      return {
        summary: `当前结果快照包含 ${results.institution_topic_cooccurrence.length} 条机构主题关系。`,
        samples: results.institution_topic_cooccurrence.slice(0, 5).map((row) => `${row.institution} · ${row.topic_label}`)
      };
    case "AnalysisBundle":
    case "AnyAnalysisResult":
      return {
        summary: `当前结果快照包含 ${results.frequency_table.length} 条词频、${results.keyword_result.length} 条关键词、${results.institution_topic_cooccurrence.length} 条机构主题关系。`,
        samples: results.frequency_table.slice(0, 5).map((row) => `${row.term} · ${row.tf}`)
      };
    case "AnyTable":
      return {
        summary: `当前结果快照包含 ${results.frequency_table.length + results.term_year_table.length + results.cooccurrence_table.length + (results.topic_summary_table?.length ?? 0) + (results.graph_metric_table?.length ?? 0)} 条主要表格结果。`,
        samples: [
          ...results.frequency_table.slice(0, 2).map((row) => `词频：${row.term}`),
          ...results.term_year_table.slice(0, 2).map((row) => `年份：${row.term}`),
          ...results.cooccurrence_table.slice(0, 2).map((row) => `共现：${row.term_a}`),
          ...(results.topic_summary_table ?? []).slice(0, 1).map((row) => `主题：${String(row.topic_label ?? row.topic_id ?? "")}`),
          ...(results.graph_metric_table ?? []).slice(0, 1).map((row) => `网络：${String(row.term ?? row.node ?? "")}`)
        ].slice(0, 5)
      };
    case "AnyRenderable":
      return {
        summary: `当前可渲染的分析结果主要来自词频、年份、共现、聚类和机构主题输出。`,
        samples: [
          ...results.frequency_table.slice(0, 2).map((row) => `词频图：${row.term}`),
          ...results.keyword_cluster_result.slice(0, 2).map((row) => `聚类图：${row.topic_label ?? `簇 ${row.cluster_id}`}`),
          ...results.institution_topic_cooccurrence.slice(0, 2).map((row) => `机构主题：${row.institution}`)
        ].slice(0, 5)
      };
    case "AuditTable":
      return {
        summary: `最近一次结果中共有 ${results.audit_table.length} 条规则命中审计。`,
        samples: results.audit_table.slice(0, 5).map((row) => `${row.source_term} -> ${row.target_term ?? row.action}`)
      };
    case "ExportArtifact":
    case "ExportBundle":
      return {
        summary: `当前项目结果中可见 ${results.report_files.length} 个导出文件。${latestRun ? `最近一次运行状态：${latestRun.status}` : ""}`.trim(),
        samples: results.report_files.slice(0, 5)
      };
    default:
      return { summary: "当前端口类型的流转摘要还在补充。", samples: [] };
  }
}

function runtimeStatusLabel(status: WorkflowNodeRuntimeState["status"]): string {
  switch (status) {
    case "running":
      return "运行中";
    case "completed":
      return "已完成";
    case "cached":
      return "命中缓存";
    case "failed":
      return "失败";
    case "skipped":
      return "已跳过";
    default:
      return "等待中";
  }
}

function formatRuntimeDuration(durationMs?: number): string {
  if (!Number.isFinite(durationMs ?? NaN) || durationMs === undefined) {
    return "进行中";
  }
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  return `${(durationMs / 1000).toFixed(durationMs >= 10_000 ? 0 : 1)} s`;
}

function historicalRuntimeState(nodeRun: NodeRunSummary, index: number, totalNodes: number): WorkflowNodeRuntimeState {
  return {
    node_id: nodeRun.node_id,
    node_type: nodeRun.node_type,
    label: nodeRun.label,
    status: nodeRun.status,
    node_index: index,
    total_nodes: totalNodes,
    progress: 1,
    started_at: nodeRun.started_at,
    ended_at: nodeRun.ended_at,
    duration_ms: nodeRun.duration_ms,
    cache_hit: nodeRun.cache_hit,
    cache_key: nodeRun.cache_key,
    cache_path: nodeRun.cache_path,
    output_ports: nodeRun.output_ports,
    output_summary: nodeRun.output_summary,
    sample_outputs: nodeRun.sample_outputs,
    output_previews: nodeRun.output_previews,
    error: nodeRun.error,
  };
}

function workflowRuntimeProgress(detail: WorkflowRunProgressDetail): number {
  if (!detail.total_nodes) {
    return 0;
  }
  const currentNode = detail.current_node_id ? detail.node_states[detail.current_node_id] : undefined;
  const currentProgress = currentNode?.status === "running" ? (currentNode.progress ?? 0) : 0;
  return Math.max(0, Math.min(1, (detail.completed_nodes + currentProgress) / detail.total_nodes));
}

function runScopeSummary(scope: RunScopeDefinition, totalCount: number, matchedCount: number): string {
  if (scope.mode === "selected_documents") {
    return `已手动选择 ${scope.selected_doc_ids.length} 篇文档，当前能命中 ${matchedCount}/${totalCount} 篇。`;
  }
  if (scope.mode === "filtered_subset") {
    const parts: string[] = [];
    if (scope.source_values.length) {
      parts.push(`来源=${scope.source_values.join("、")}`);
    }
    if (scope.institution_values.length) {
      parts.push(`机构=${scope.institution_values.join("、")}`);
    }
    if (scope.category_values.length) {
      parts.push(`标签=${scope.category_values.join("、")}`);
    }
    if (scope.year_from || scope.year_to) {
      if (scope.year_from && scope.year_to) {
        parts.push(`年份=${scope.year_from}-${scope.year_to}`);
      } else if (scope.year_from) {
        parts.push(`年份>=${scope.year_from}`);
      } else if (scope.year_to) {
        parts.push(`年份<=${scope.year_to}`);
      }
    }
    return `按条件处理：${parts.join("；") || "尚未设置具体条件"}，当前能命中 ${matchedCount}/${totalCount} 篇。`;
  }
  return `处理项目里的全部资料，共 ${matchedCount}/${totalCount} 篇文档。`;
}

function corpusMatchesRunScope(item: CorpusItem, scope: RunScopeDefinition): boolean {
  if (scope.mode === "selected_documents") {
    return scope.selected_doc_ids.includes(item.doc_id);
  }
  if (scope.mode !== "filtered_subset") {
    return true;
  }
  if (scope.source_values.length && !scope.source_values.includes(item.source ?? "")) {
    return false;
  }
  if (scope.institution_values.length && !scope.institution_values.includes(item.institution ?? "")) {
    return false;
  }
  if (scope.category_values.length && !scope.category_values.includes(item.category_or_tag ?? "")) {
    return false;
  }
  if (scope.year_from && (!item.year || item.year < scope.year_from)) {
    return false;
  }
  if (scope.year_to && (!item.year || item.year > scope.year_to)) {
    return false;
  }
  return true;
}

interface PageViewProps {
  page: PageId;
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}

export const PageView = memo(function PageView({ page, workbenchSelection, onWorkbenchSelect }: PageViewProps) {
  switch (page) {
    case "home":
      return <HomePage />;
    case "project":
      return <ProjectPage />;
    case "data":
      return (
        <DataPage
          workbenchSelection={workbenchSelection}
          onWorkbenchSelect={onWorkbenchSelect}
        />
      );
    case "workflow":
      return (
        <WorkflowEditorPage
          workbenchSelection={workbenchSelection}
          onWorkbenchSelect={onWorkbenchSelect}
        />
      );
    case "dictionaries":
      return (
        <DictionariesPage
          workbenchSelection={workbenchSelection}
          onWorkbenchSelect={onWorkbenchSelect}
        />
      );
    case "results":
      return (
        <RunArtifactsPage
          workbenchSelection={workbenchSelection}
          onWorkbenchSelect={onWorkbenchSelect}
        />
      );
    case "report":
      return <ReportPreviewPage />;
    case "settings":
      return <SettingsPage />;
    default:
      return null;
  }
});

function HomePage() {
  const {
    state: { snapshot, loading },
    createProject,
    deleteProject,
    exportProjectBackup,
    importProjectPackage,
    openProject,
    pickProjectPackageFile,
    duplicateProject,
    saveProjectPackagePath,
    setActivePage
  } = useWorkspace();
  const [name, setName] = useState("我的 TextFlow 项目");
  const [description, setDescription] = useState("围绕语料导入、清洗、词表治理和关键词分析的新项目。");
  const [projectQuery, setProjectQuery] = useState("");
  const currentProject = snapshot.current_project;
  const deferredProjectQuery = useDeferredValue(projectQuery.trim().toLowerCase());
  const sampleProject = useMemo(
    () => snapshot.recent_projects.find((project) => project.name === sampleProjectName || project.name.includes("示例项目")),
    [snapshot.recent_projects]
  );
  const libraryProjects = useMemo(() => {
    if (!deferredProjectQuery) {
      return snapshot.recent_projects;
    }
    return snapshot.recent_projects.filter((project) =>
      [project.name, project.description, project.path].join(" ").toLowerCase().includes(deferredProjectQuery)
    );
  }, [deferredProjectQuery, snapshot.recent_projects]);

  const handleImportPackage = async () => {
    const path = await pickProjectPackageFile();
    if (!path) {
      return;
    }
    await importProjectPackage(path);
  };

  const handleExportPackage = async () => {
    if (!currentProject) {
      return;
    }
    const path = await saveProjectPackagePath(`${currentProject.name}.tfproj`);
    if (!path) {
      return;
    }
    await exportProjectBackup(path);
  };

  const handleDeleteProject = async (projectId: string, projectName: string) => {
    const confirmed = window.confirm(`删除项目“${projectName}”？\n\n这会把仓库里的 .tfproj 项目一并删除，无法恢复。`);
    if (!confirmed) {
      return;
    }
    await deleteProject(projectId);
  };

  const openProjectAndGo = async (projectId: string, page?: PageId) => {
    await openProject(projectId);
    if (page) {
      setActivePage(page);
    }
  };

  return (
    <>
      <Panel className="project-manager-panel">
        <div className="project-manager-head">
          <div>
            <p className="eyebrow">项目仓库</p>
            <h3>{currentProject ? currentProject.name : "本地 TextFlow 项目"}</h3>
            <p className="helper-note">
              {currentProject
                ? `${snapshot.corpus.length} 篇文档 · ${currentProject.run_history.length} 次运行 · ${currentProject.workflow_definitions.length} 张节点图`
                : "新建、导入或打开一个 .tfproj 项目。"}
            </p>
          </div>
          <div className="button-row project-manager-shortcuts">
            <Button
              appearance="primary"
              onClick={() => void createProject(name, description)}
              disabled={loading || !name.trim()}
            >
              新建空白项目
            </Button>
            <Button onClick={() => void handleImportPackage()} disabled={loading}>
              导入 .tfproj
            </Button>
            {sampleProject && (
              <Button appearance="subtle" onClick={() => void openProjectAndGo(sampleProject.id)} disabled={loading}>
                打开示例
              </Button>
            )}
            <Button
              appearance="subtle"
              onClick={() => void handleExportPackage()}
              disabled={loading || !currentProject}
            >
              导出项目包
            </Button>
          </div>
        </div>
        <div className="project-manager-form">
          <label className="field">
            <span>项目名称</span>
            <Input value={name} onChange={(_, data) => setName(data.value)} />
          </label>
          <label className="field">
            <span>项目描述</span>
            <Textarea value={description} rows={2} onChange={(_, data) => setDescription(data.value)} />
          </label>
        </div>
      </Panel>

      <div className="home-overview-grid">
        <Panel
          title="仓库内项目"
          className="project-library-panel"
          actions={<span className="pill">共 {snapshot.recent_projects.length} 个</span>}
        >
          <label className="search-box">
            <span>按项目名、说明或路径筛选</span>
            <Input
              contentBefore={<SearchRegular />}
              value={projectQuery}
              onChange={(_, data) => setProjectQuery(data.value)}
              placeholder="例如：示例项目 / battery / tfproj"
            />
          </label>
          <div className="project-library">
            {libraryProjects.length ? (
              libraryProjects.map((project) => (
                <article
                  key={project.id}
                  className={`project-card project-library-card ${currentProject?.id === project.id ? "is-active" : ""}`.trim()}
                >
                  <div className="project-library-head">
                    <div>
                      <div className="button-row project-library-flags">
                        {currentProject?.id === project.id && <span className="badge ready">当前项目</span>}
                        {(project.name === sampleProjectName || project.name.includes("示例项目")) && <span className="pill">示例项目</span>}
                      </div>
                      <h4>{project.name}</h4>
                      <p>{project.description}</p>
                    </div>
                    <span className="pill">{new Date(project.updated_at).toLocaleDateString()}</span>
                  </div>
                  <div className="project-library-stats">
                    <span>{project.document_count} 篇文档</span>
                    <span>{project.run_count} 次运行</span>
                    <span>{new Date(project.updated_at).toLocaleString()}</span>
                  </div>
                  <p className="project-path">{project.path}</p>
                  <div className="button-row">
                    <Button onClick={() => void openProject(project.id)} disabled={loading}>
                      打开
                    </Button>
                    <Button
                      appearance="subtle"
                      onClick={() => void duplicateProject(project.id, `${project.name} 副本`)}
                      disabled={loading}
                    >
                      复制
                    </Button>
                    <Button
                      appearance="subtle"
                      onClick={() => void handleDeleteProject(project.id, project.name)}
                      disabled={loading}
                    >
                      删除
                    </Button>
                  </div>
                </article>
              ))
            ) : (
              <div className="status-panel">
                <strong>没有匹配的项目</strong>
                <span className="muted">换个关键词试试，或者先新建一个空白项目。</span>
              </div>
            )}
          </div>
        </Panel>

      </div>
    </>
  );
}

function ProjectPage() {
  const {
    state: { snapshot },
    setActivePage
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="还没有项目" body="先在首页创建或打开一个 `.tfproj` 项目。" />;
  }

  const recentProjectRuns = project.run_history.slice(-3).reverse();

  return (
    <>
      <div className="stat-grid">
        <StatCard label="文档总量" value={String(snapshot.corpus.length)} tone="gold" />
        <StatCard label="源文件数" value={String(project.source_files.length)} tone="ink" />
        <StatCard label="最近运行" value={String(project.run_history.length)} tone="emerald" />
        <StatCard label="导出文件" value={String(project.results.report_files.length)} tone="rose" />
      </div>

      <div className="two-column">
        <Panel title="项目概览">
          <dl className="meta-grid">
            <Meta label="项目名" value={project.name} />
            <Meta label="Schema 版本" value={project.schema_version} />
            <Meta label="项目根目录" value={project.paths.root} />
            <Meta label="默认语言" value={project.settings.default_language} />
            <Meta label="导入模板" value={project.import_template.name} />
            <Meta label="词表版本" value={project.dictionary_set.version} />
          </dl>
          <p className="body-copy">{project.description}</p>
        </Panel>

        <Panel
          title="源文件与最近运行"
          actions={
            <Button appearance="subtle" onClick={() => setActivePage("results")}>
              查看历史记录
            </Button>
          }
        >
          <ul className="micro-list">
            {project.source_files.slice(0, 5).map((source) => (
              <li key={source.id}>
                {source.name} · {source.row_count} 行 · {source.relative_path}
              </li>
            ))}
          </ul>
          <div className="stack-list">
            {recentProjectRuns.map((run) => (
              <article className="run-card" key={run.run_id}>
                <div className="run-head">
                  <strong>{run.run_id}</strong>
                  <span className={`badge ${run.status}`}>{run.status}</span>
                </div>
                <p>
                  {run.started_at} → {run.ended_at ?? "处理"}
                </p>
                <p className="muted">{run.run_scope_summary ?? "处理对象：项目内全部资料"}</p>
                <div className="run-history-tags">
                  <span className="pill">{run.processed_document_count} docs</span>
                  <span className="pill">{run.artifacts.length} 份产物</span>
                  {run.warnings.length > 0 && <span className="pill">{run.warnings.length} 个警告</span>}
                  {run.errors.length > 0 && <span className="pill">{run.errors.length} 个错误</span>}
                </div>
              </article>
            ))}
            {!recentProjectRuns.length && (
              <div className="status-panel">
                <strong>还没有运行记录</strong>
                <span className="muted">完成一次处理后，这里只显示最近几次运行摘要。</span>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <Panel title="项目源文件清单">
        <Table
          columns={["name", "source_type", "row_count", "imported_at", "relative_path"]}
          rows={project.source_files.map((source) => ({
            name: source.name,
            source_type: source.source_type,
            row_count: source.row_count,
            imported_at: new Date(source.imported_at).toLocaleString(),
            relative_path: source.relative_path
          }))}
        />
      </Panel>
    </>
  );
}

function DataPage({
  workbenchSelection,
  onWorkbenchSelect
}: {
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}) {
  const {
    state: { snapshot, loading },
    createCorpusView,
    deleteCorpusDocument,
    pickImportFiles,
    importProjectFiles,
    saveProject,
    setActivePage,
    updateCorpusDocument
  } = useWorkspace();
  const project = snapshot.current_project;
  const [search, setSearch] = useState("");
  const [searchMode, setSearchMode] = useState<"metadata" | "fulltext">("metadata");
  const [documentPage, setDocumentPage] = useState(1);
  const [filePathsText, setFilePathsText] = useState("");
  const [draftTemplate, setDraftTemplate] = useState<ImportTemplate | null>(project ? cloneTemplate(project.import_template) : null);
  const [lastImportResult, setLastImportResult] = useState<ImportProjectFilesResponse | null>(null);
  const [showTemplateEditor, setShowTemplateEditor] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(snapshot.corpus[0]?.doc_id ?? null);
  const [draftDocument, setDraftDocument] = useState<CorpusItem | null>(snapshot.corpus[0] ? cloneCorpusItem(snapshot.corpus[0]) : null);
  const [previewMode, setPreviewMode] = useState<DocumentPreviewMode>("raw_text");
  const deferredSearch = useDeferredValue(search);
  const templateSummary = draftTemplate ? summarizeImportTemplate(draftTemplate) : { requiredMappings: [], issues: [] };

  useEffect(() => {
    setDraftTemplate(project ? cloneTemplate(project.import_template) : null);
    setLastImportResult(null);
    setShowTemplateEditor(false);
    setSelectedDocId(snapshot.corpus[0]?.doc_id ?? null);
    setDraftDocument(snapshot.corpus[0] ? cloneCorpusItem(snapshot.corpus[0]) : null);
    setPreviewMode("raw_text");
    setSearchMode("metadata");
    setDocumentPage(1);
  }, [project?.id, project?.updated_at]);

  const documents = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase();
    if (!q) {
      return snapshot.corpus;
    }
    return snapshot.corpus.filter((item) =>
      [
        item.title,
        item.institution,
        item.source,
        item.category_or_tag,
        ...(searchMode === "fulltext" ? [item.raw_text] : [])
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    );
  }, [deferredSearch, searchMode, snapshot.corpus]);

  useEffect(() => {
    setDocumentPage(1);
  }, [documents.length, searchMode]);

  useEffect(() => {
    if (workbenchSelection?.kind !== "corpus_document" || workbenchSelection.docId === selectedDocId) {
      return;
    }
    const selectedDocument = snapshot.corpus.find((item) => item.doc_id === workbenchSelection.docId);
    if (!selectedDocument) {
      return;
    }
    setSelectedDocId(selectedDocument.doc_id);
    setDraftDocument(cloneCorpusItem(selectedDocument));
    setPreviewMode("raw_text");
  }, [selectedDocId, snapshot.corpus, workbenchSelection]);

  const totalDocumentPages = Math.max(1, Math.ceil(documents.length / CORPUS_BROWSER_PAGE_SIZE));
  const safeDocumentPage = Math.min(documentPage, totalDocumentPages);
  const visibleDocuments = useMemo(
    () => documents.slice((safeDocumentPage - 1) * CORPUS_BROWSER_PAGE_SIZE, safeDocumentPage * CORPUS_BROWSER_PAGE_SIZE),
    [documents, safeDocumentPage]
  );
  const corpusColumns = useMemo<TableColumnDefinition<CorpusItem>[]>(
    () => [
      createTableColumn<CorpusItem>({
        columnId: "title",
        compare: (a, b) => (a.title || a.doc_id).localeCompare(b.title || b.doc_id),
        renderHeaderCell: () => "文档",
        renderCell: (item) => (
          <div className="corpus-grid-title-cell">
            <strong>{item.title || item.doc_id}</strong>
            <span>{previewSummary(item)}</span>
          </div>
        )
      }),
      createTableColumn<CorpusItem>({
        columnId: "year",
        compare: (a, b) => (a.year ?? 0) - (b.year ?? 0),
        renderHeaderCell: () => "年份",
        renderCell: (item) => item.year ?? "未标年"
      }),
      createTableColumn<CorpusItem>({
        columnId: "source",
        compare: (a, b) => (a.institution ?? a.source ?? "").localeCompare(b.institution ?? b.source ?? ""),
        renderHeaderCell: () => "机构 / 来源",
        renderCell: (item) => item.institution ?? item.source ?? "未填写"
      }),
      createTableColumn<CorpusItem>({
        columnId: "profile",
        compare: (a, b) => a.source_profile.localeCompare(b.source_profile),
        renderHeaderCell: () => "资料类型",
        renderCell: (item) => item.source_profile
      }),
      createTableColumn<CorpusItem>({
        columnId: "status",
        compare: (a, b) => a.status.localeCompare(b.status),
        renderHeaderCell: () => "状态",
        renderCell: (item) => <span className={`badge ${item.status}`}>{item.status}</span>
      })
    ],
    []
  );

  if (!project || !draftTemplate) {
    return <EmptyState title="暂无语料" body="请先创建项目，再导入文本或样例数据。" />;
  }

  const canSaveTemplate = !loading && !templateSummary.issues.length;
  const canImport = !loading && !templateSummary.issues.length && Boolean(filePathsText.trim());
  const selectedDoc = snapshot.corpus.find((item) => item.doc_id === selectedDocId) ?? null;
  const canSaveDocument = Boolean(draftDocument?.raw_text.trim()) && !loading;

  const updateMapping = (index: number, patch: Partial<FieldMappingRule>) => {
    setDraftTemplate((current) => {
      if (!current) {
        return current;
      }
      const nextMappings = current.field_mappings.map((rule, mappingIndex) =>
        mappingIndex === index ? { ...rule, ...patch } : rule
      );
      return { ...current, field_mappings: nextMappings };
    });
  };

  const removeMapping = (index: number) => {
    setDraftTemplate((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        field_mappings: current.field_mappings.filter((_, mappingIndex) => mappingIndex !== index)
      };
    });
  };

  const handleSaveTemplate = async () => {
    await saveProject({
      ...project,
      import_template: draftTemplate
    }, {
      refresh: false,
      actionLabel: "保存导入模板"
    });
  };

  const handleImport = async () => {
    const filePaths = filePathsText
      .split(/\r?\n/)
      .map((path) => path.trim())
      .filter(Boolean);

    if (!filePaths.length) {
      return;
    }

    const result = await importProjectFiles(filePaths, draftTemplate);
    if (result) {
      setLastImportResult(result);
      setFilePathsText("");
    }
  };

  const handlePickFiles = async () => {
    const filePaths = await pickImportFiles();
    if (!filePaths.length) {
      return;
    }
    setFilePathsText(filePaths.join("\n"));
  };

  const handleSelectDocument = (doc: CorpusItem) => {
    setSelectedDocId(doc.doc_id);
    setDraftDocument(cloneCorpusItem(doc));
    setPreviewMode("raw_text");
    onWorkbenchSelect?.({ kind: "corpus_document", projectId: project.id, docId: doc.doc_id });
  };

  const handleCreateCorpusView = async () => {
    await createCorpusView({
      name: search.trim() ? `语料视图：${search.trim()}` : "当前语料视图",
      resource_ids: (project.corpus_resources ?? []).map((resource) => resource.id),
      filter_spec: {
        search: search.trim(),
        search_mode: searchMode
      },
      doc_ids: documents.map((doc) => doc.doc_id)
    });
  };

  const handleSendToWorkflow = () => {
    onWorkbenchSelect?.({
      kind: "workflow",
      projectId: project.id,
      workflowId: project.active_workflow_id || project.workflow_definitions[0]?.workflow_id || "active-workflow"
    });
    setActivePage?.("workflow");
  };

  const handleSaveDocument = async () => {
    if (!draftDocument) {
      return;
    }
    await updateCorpusDocument(draftDocument);
  };

  const handleDeleteDocument = async () => {
    if (!draftDocument) {
      return;
    }
    if (!window.confirm(`确认删除“${draftDocument.title}”吗？`)) {
      return;
    }
    await deleteCorpusDocument(draftDocument.doc_id);
  };

  return (
    <CorpusWorkspace
      project={project}
      corpus={snapshot.corpus}
      loading={loading}
      canSaveImportSpec={canSaveTemplate}
      canCreateView={documents.length > 0}
      onImportFiles={handlePickFiles}
      onSaveImportSpec={handleSaveTemplate}
      onCreateCorpusView={handleCreateCorpusView}
      onSendToWorkflow={handleSendToWorkflow}
    >
      <Panel
        title="语料导入与审查"
        actions={
          <div className="button-row">
            <Button onClick={() => void handleSaveTemplate()} disabled={!canSaveTemplate}>
              保存模板
            </Button>
            <Button
              appearance="subtle"
              onClick={() => setDraftTemplate(buildTemplateFromProfile(draftTemplate, draftTemplate.source_profile))}
              disabled={loading}
            >
              套用预设
            </Button>
            <Button appearance="subtle" onClick={() => setShowTemplateEditor((current) => !current)}>
              {showTemplateEditor ? "收起高级字段设置" : "展开高级字段设置"}
            </Button>
          </div>
        }
      >
        <div className="import-summary-grid">
          <article className="status-panel">
            <strong>资料类型</strong>
            <p>{sourceProfiles[draftTemplate.source_profile]}</p>
          </article>
          <article className="status-panel">
            <strong>主文本拼接</strong>
            <p>{draftTemplate.text_build.fields.join(" + ") || "未设置"}</p>
          </article>
          <article className="status-panel">
            <strong>必填字段</strong>
            <p>{templateSummary.requiredMappings.map((rule) => rule.source_field).join("、") || "无"}</p>
          </article>
        </div>

        <div className="settings-grid compact-settings-grid">
          <label className="field">
            <span>模板名称</span>
            <Input
              value={draftTemplate.name}
              onChange={(_, data) => setDraftTemplate({ ...draftTemplate, name: data.value })}
            />
          </label>
          <label className="field">
            <span>资料类型预设</span>
            <Select
              value={draftTemplate.source_profile}
              onChange={(event) =>
                setDraftTemplate({
                  ...draftTemplate,
                  source_profile: event.target.value as ImportTemplate["source_profile"]
                })
              }
            >
              {Object.entries(sourceProfiles).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </label>
          <label className="field">
            <span>正文来源字段</span>
            <Input
              value={draftTemplate.text_build.fields.join(", ")}
              onChange={(_, data) =>
                setDraftTemplate({
                  ...draftTemplate,
                  text_build: {
                    ...draftTemplate.text_build,
                    fields: data.value.split(",").map((field) => field.trim()).filter(Boolean)
                  }
                })
              }
              placeholder="title, abstract"
            />
          </label>
          <label className="field">
            <span>说明</span>
            <Input
              value={draftTemplate.description ?? ""}
              onChange={(_, data) => setDraftTemplate({ ...draftTemplate, description: data.value })}
            />
          </label>
        </div>

        <label className="field">
          <span>待导入文件</span>
          <Textarea
            rows={4}
            value={filePathsText}
            onChange={(_, data) => setFilePathsText(data.value)}
            placeholder={"每行一个文件路径，例如：\nC:\\data\\articles.xlsx\nC:\\data\\notes.txt"}
          />
        </label>

        <div className="button-row">
          <Button appearance="subtle" onClick={() => void handlePickFiles()} disabled={loading}>
            选择文件
          </Button>
          <Button appearance="primary" onClick={() => void handleImport()} disabled={!canImport}>
            开始导入
          </Button>
        </div>

        {templateSummary.issues.length ? (
          <div className="status-panel warning-panel">
            <strong>导入前还需要确认这些项</strong>
            <ul className="feature-list">
              {templateSummary.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="body-copy">支持 txt / csv / xlsx / json。导入时会复制原始文件进项目目录，后续可以回溯来源。</p>
        )}

        {lastImportResult ? (
          <div className="status-panel">
            <strong>最近一次导入</strong>
            <p>
              导入 {lastImportResult.imported_documents} 篇文档，当前累计 {lastImportResult.document_count} 篇。
              {lastImportResult.skipped_rows ? ` 跳过 ${lastImportResult.skipped_rows} 行。` : ""}
            </p>
            {lastImportResult.validation_issues.length ? (
              <ul className="feature-list">
                {lastImportResult.validation_issues.map((issue) => (
                  <li key={`${issue.file}-${issue.row}`}>
                    {issue.file} 第 {issue.row} 行：{issue.reason}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {showTemplateEditor ? (
          <div className="advanced-editor">
            <div className="settings-grid compact-settings-grid">
              <label className="field">
                <span>连接符</span>
                <Input
                  value={draftTemplate.text_build.delimiter}
                  onChange={(_, data) =>
                    setDraftTemplate({
                      ...draftTemplate,
                      text_build: {
                        ...draftTemplate.text_build,
                        delimiter: data.value
                      }
                    })
                  }
                />
              </label>
            </div>
            <div className="mapping-editor">
              {draftTemplate.field_mappings.map((rule, index) => (
                <div className="mapping-editor-row" key={index}>
                  <Input
                    value={rule.source_field}
                    onChange={(_, data) => updateMapping(index, { source_field: data.value })}
                    placeholder="源字段名"
                  />
                  <Select
                    value={rule.target_field}
                    onChange={(event) => updateMapping(index, { target_field: event.target.value as FieldMappingRule["target_field"] })}
                  >
                    {mappingTargetOptions.map((target) => (
                      <option key={target} value={target}>
                        {target}
                      </option>
                    ))}
                  </Select>
                  <Input
                    value={rule.aliases?.join(", ") ?? ""}
                    onChange={(_, data) =>
                      updateMapping(index, {
                        aliases: data.value
                          .split(",")
                          .map((alias) => alias.trim())
                          .filter(Boolean)
                      })
                    }
                    placeholder="别名，逗号分隔"
                  />
                  <Checkbox
                    checked={rule.required ?? false}
                    onChange={(_, data) => updateMapping(index, { required: Boolean(data.checked) })}
                    label="必填"
                  />
                  <Button appearance="subtle" onClick={() => removeMapping(index)}>
                    删除
                  </Button>
                </div>
              ))}
            </div>
            <div className="button-row">
              <Button
                appearance="subtle"
                onClick={() => setDraftTemplate({ ...draftTemplate, field_mappings: [...draftTemplate.field_mappings, emptyMappingRule()] })}
                disabled={loading}
              >
                新增映射
              </Button>
            </div>
          </div>
        ) : null}
      </Panel>

        <div className="corpus-review-grid">
        <Panel
          title="已导入语料库"
          actions={
            <div className="corpus-grid-actions">
              <label className="search-box">
                <span>{searchMode === "fulltext" ? "检索标题 / 正文 / 元数据" : "检索标题 / 元数据"}</span>
                <Input
                  contentBefore={<SearchRegular />}
                  value={search}
                  onChange={(_, data) => setSearch(data.value)}
                  placeholder="例如：智能制造 / patent / 复旦大学"
                />
              </label>
              <Toolbar aria-label="语料检索模式">
                <ToolbarButton
                  appearance={searchMode === "metadata" ? "primary" : "subtle"}
                  onClick={() => setSearchMode("metadata")}
                >
                  元数据优先
                </ToolbarButton>
                <ToolbarButton
                  appearance={searchMode === "fulltext" ? "primary" : "subtle"}
                  onClick={() => setSearchMode("fulltext")}
                >
                  全文检索
                </ToolbarButton>
              </Toolbar>
            </div>
          }
        >
          {documents.length ? (
            <>
              <div className="corpus-grid-shell">
                <DataGrid
                  items={visibleDocuments}
                  columns={corpusColumns}
                  sortable
                  getRowId={(item) => item.doc_id}
                  selectionMode="single"
                  selectedItems={selectedDocId ? new Set([selectedDocId]) : new Set()}
                  onSelectionChange={(_, data) => {
                    const nextId = Array.from(data.selectedItems)[0];
                    const nextDocument = snapshot.corpus.find((item) => item.doc_id === nextId);
                    if (nextDocument) {
                      handleSelectDocument(nextDocument);
                    }
                  }}
                  aria-label="已导入语料库"
                >
                  <DataGridHeader>
                    <DataGridRow selectionCell={{ "aria-label": "选择全部文档" }}>
                      {({ renderHeaderCell }) => <DataGridHeaderCell>{renderHeaderCell()}</DataGridHeaderCell>}
                    </DataGridRow>
                  </DataGridHeader>
                  <DataGridBody<CorpusItem>>
                    {({ item, rowId }) => (
                      <DataGridRow<CorpusItem>
                        key={rowId}
                        className={selectedDocId === item.doc_id ? "is-active" : undefined}
                        selectionCell={{ "aria-label": `选择 ${item.title || item.doc_id}` }}
                        onClick={() => handleSelectDocument(item)}
                      >
                        {({ renderCell }) => <DataGridCell>{renderCell(item)}</DataGridCell>}
                      </DataGridRow>
                    )}
                  </DataGridBody>
                </DataGrid>
              </div>
              <div className="button-row dictionary-page-nav">
                <span className="helper-note">
                  当前显示第 {safeDocumentPage} / {totalDocumentPages} 页，
                  第 {documents.length ? (safeDocumentPage - 1) * CORPUS_BROWSER_PAGE_SIZE + 1 : 0} - {Math.min(safeDocumentPage * CORPUS_BROWSER_PAGE_SIZE, documents.length)} 条。
                </span>
                <Button
                  appearance="subtle"
                  icon={<ChevronLeftRegular />}
                  onClick={() => setDocumentPage((current) => Math.max(1, current - 1))}
                  disabled={safeDocumentPage <= 1}
                >
                  上一页
                </Button>
                <Button
                  appearance="subtle"
                  icon={<ChevronRightRegular />}
                  onClick={() => setDocumentPage((current) => Math.min(totalDocumentPages, current + 1))}
                  disabled={safeDocumentPage >= totalDocumentPages}
                >
                  下一页
                </Button>
              </div>
            </>
          ) : (
            <EmptyState title="没有匹配文档" body="换个关键词试试，或先导入文件。" />
          )}
        </Panel>

        <Panel
          title="文档审查与编辑"
          actions={
            <div className="button-row">
              <Button onClick={() => void handleSaveDocument()} disabled={!canSaveDocument}>
                保存文档
              </Button>
              <Button appearance="subtle" onClick={() => void handleDeleteDocument()} disabled={loading || !draftDocument}>
                删除文档
              </Button>
            </div>
          }
        >
          {selectedDoc && draftDocument ? (
            <div className="document-workbench">
              <DocumentPreview doc={draftDocument} mode={previewMode} onModeChange={setPreviewMode} />

              <div className="settings-grid document-form-grid">
                <label className="field">
                  <span>标题</span>
                  <Input
                    value={draftDocument.title}
                    onChange={(_, data) => setDraftDocument({ ...draftDocument, title: data.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>年份</span>
                  <Input
                    type="number"
                    value={String(draftDocument.year ?? "")}
                    onChange={(_, data) =>
                      setDraftDocument({
                        ...draftDocument,
                        year: data.value.trim() ? Number(data.value) : null
                      })
                    }
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>机构</span>
                  <Input
                    value={draftDocument.institution ?? ""}
                    onChange={(_, data) => setDraftDocument({ ...draftDocument, institution: data.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>来源</span>
                  <Input
                    value={draftDocument.source ?? ""}
                    onChange={(_, data) => setDraftDocument({ ...draftDocument, source: data.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>作者</span>
                  <Input
                    value={draftDocument.author ?? ""}
                    onChange={(_, data) => setDraftDocument({ ...draftDocument, author: data.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>分类 / 标签</span>
                  <Input
                    value={draftDocument.category_or_tag ?? ""}
                    onChange={(_, data) => setDraftDocument({ ...draftDocument, category_or_tag: data.value })}
                    disabled={loading}
                  />
                </label>
              </div>

              <label className="field">
                <span>正文</span>
                <Textarea
                  rows={10}
                  value={draftDocument.raw_text}
                  onChange={(_, data) => setDraftDocument({ ...draftDocument, raw_text: data.value })}
                  disabled={loading}
                />
              </label>

                <div className="status-panel">
                  <strong>来源追踪</strong>
                  <p>
                    文件：{String(draftDocument.extra_metadata["_source_file_name"] ?? "—")} · 行号：
                    {String(draftDocument.extra_metadata["_source_row_index"] ?? "—")}
                  </p>
                  <p>保存后，下一次运行当前 workflow 时会基于最新文档内容重新处理。</p>
                </div>
              </div>
            ) : (
            <EmptyState title="暂无文档" body="导入后就能在这里逐篇查看、修改和删除。" />
          )}
        </Panel>
      </div>
    </CorpusWorkspace>
  );
}

export function WorkflowEditorPage({
  workbenchSelection,
  onWorkbenchSelect
}: {
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}) {
  const workspace = useWorkspace();
  const taskProgress = useTaskProgress();
  const {
    state: { snapshot, loading }
  } = workspace;
  const project = snapshot.current_project;
  const activeWorkflow = project ? resolveActiveWorkflow(project) : null;

  if (!project || !activeWorkflow) {
    return (
      <EmptyState
        title="流程配置待初始化"
        body={loading ? "项目仍在加载中，稍等一下就能继续配置流程。" : "请先建立项目工作区。"}
      />
    );
  }

  return (
    <WorkflowEditorPageContent
      workspace={workspace}
      taskProgress={taskProgress}
      project={project}
      activeWorkflow={activeWorkflow}
      workbenchSelection={workbenchSelection}
      onWorkbenchSelect={onWorkbenchSelect}
    />
  );
}

function WorkflowEditorPageContent({
  workspace,
  taskProgress,
  project,
  activeWorkflow,
  workbenchSelection,
  onWorkbenchSelect
}: {
  workspace: ReturnType<typeof useWorkspace>;
  taskProgress: ReturnType<typeof useTaskProgress>;
  project: ProjectManifest;
  activeWorkflow: WorkflowDefinition;
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}) {
  const {
    state: { snapshot, loading },
    saveProject,
    runWorkflow,
    setActivePage,
    loadArtifactPreview
  } = workspace;
  const [draftWorkflow, setDraftWorkflow] = useState<WorkflowDefinition | null>(
    deepClone(activeWorkflow)
  );
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [pendingConnection, setPendingConnection] = useState<{ fromNodeId: string; fromPortId: string } | null>(null);
  const [documentPickerQuery, setDocumentPickerQuery] = useState("");
  const [isCanvasDropActive, setIsCanvasDropActive] = useState(false);
  const [previewNodeId, setPreviewNodeId] = useState<string | null>(null);
  const canvasScrollRef = useRef<HTMLDivElement | null>(null);
  const canvasTopbarRef = useRef<HTMLDivElement | null>(null);
  const canvasBannerRef = useRef<HTMLDivElement | null>(null);
  const miniMapRef = useRef<HTMLDivElement | null>(null);
  const miniMapSurfaceRef = useRef<HTMLDivElement | null>(null);
  const miniMapViewportRef = useRef<HTMLDivElement | null>(null);
  const canvasPanStateRef = useRef<{
    startClientX: number;
    startClientY: number;
    startViewportX: number;
    startViewportY: number;
  } | null>(null);
  const miniMapDragStateRef = useRef(false);
  const dragStateRef = useRef<{
    nodeId: string;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
  } | null>(null);
  const [canvasViewportSize, setCanvasViewportSize] = useState({ width: 0, height: 0 });
  const [canvasOverlayOffset, setCanvasOverlayOffset] = useState(120);
  const [draggingNodeId, setDraggingNodeId] = useState("");
  const [isCanvasPanning, setIsCanvasPanning] = useState(false);
  const canvasSurfaceRef = useRef<HTMLDivElement | null>(null);
  const workflowNodeElementRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const scheduledCanvasFrameRef = useRef<number | null>(null);
  const pendingCanvasDomWriteRef = useRef<(() => void) | null>(null);
  const latestNodeDragRef = useRef<{ nodeId: string; x: number; y: number } | null>(null);
  const latestViewportDragRef = useRef<{ x: number; y: number; zoom: number } | null>(null);
  const saveWorkflowRef = useRef<(() => Promise<boolean>) | null>(null);
  const runWorkflowRef = useRef<(() => Promise<void>) | null>(null);
  const draftPersistenceRef = useRef<{
    projectId: string;
    workflowId: string;
    workflow: WorkflowDefinition | null;
  }>({ projectId: "", workflowId: "", workflow: null });
  const draftWorkflowId = draftWorkflow?.workflow_id ?? "";

  draftPersistenceRef.current = {
    projectId: project?.id ?? "",
    workflowId: draftWorkflowId,
    workflow: draftWorkflow
  };

  const persistDraftWorkflow = () => {
    const { projectId, workflowId, workflow } = draftPersistenceRef.current;
    if (!projectId || !workflowId || !workflow) {
      return;
    }
    try {
      window.localStorage.setItem(
        workflowDraftStorageKey(projectId, workflowId),
        JSON.stringify(workflow)
      );
    } catch {
      // Ignore draft persistence failures and keep the in-memory editor usable.
    }
  };

  const scheduleCanvasDomWrite = (writer: () => void) => {
    pendingCanvasDomWriteRef.current = writer;
    if (scheduledCanvasFrameRef.current !== null) {
      return;
    }
    scheduledCanvasFrameRef.current = window.requestAnimationFrame(() => {
      scheduledCanvasFrameRef.current = null;
      const pendingWriter = pendingCanvasDomWriteRef.current;
      pendingCanvasDomWriteRef.current = null;
      if (!pendingWriter) {
        return;
      }
      pendingWriter();
    });
  };

  const flushCanvasDomWrite = () => {
    if (scheduledCanvasFrameRef.current !== null) {
      window.cancelAnimationFrame(scheduledCanvasFrameRef.current);
      scheduledCanvasFrameRef.current = null;
    }
    const pendingWriter = pendingCanvasDomWriteRef.current;
    pendingCanvasDomWriteRef.current = null;
    pendingWriter?.();
  };

  useEffect(() => () => {
    if (scheduledCanvasFrameRef.current !== null) {
      window.cancelAnimationFrame(scheduledCanvasFrameRef.current);
    }
    pendingCanvasDomWriteRef.current = null;
    persistDraftWorkflow();
  }, []);

  useEffect(() => {
    const handleExternalSave = () => {
      void saveWorkflowRef.current?.();
    };
    const handleExternalRun = () => {
      void runWorkflowRef.current?.();
    };
    window.addEventListener("textflow:workflow-save", handleExternalSave);
    window.addEventListener("textflow:workflow-run", handleExternalRun);
    return () => {
      window.removeEventListener("textflow:workflow-save", handleExternalSave);
      window.removeEventListener("textflow:workflow-run", handleExternalRun);
    };
  }, []);

  useEffect(() => {
    const nextWorkflow = resolveActiveWorkflow(project) ?? activeWorkflow;
    const persistedDraft = nextWorkflow
      ? loadPersistedWorkflowDraft(project.id, nextWorkflow.workflow_id)
      : null;
    const persistedEditorState = nextWorkflow
      ? loadPersistedWorkflowEditorState(project.id, nextWorkflow.workflow_id)
      : null;
    const normalizedWorkflow = nextWorkflow
      ? normalizeWorkflowGraph(
        deepClone(persistedDraft ?? nextWorkflow),
        projectRuntimeProfile(project, persistedDraft ?? nextWorkflow)
      )
      : null;
    const hydratedWorkflow = normalizedWorkflow && workflowViewportNeedsInitialFit(normalizedWorkflow, Boolean(persistedDraft))
      ? updateWorkflowViewport(normalizedWorkflow, workflowFitViewport(normalizedWorkflow.nodes))
      : normalizedWorkflow;
    const nextDraftWorkflow = hydratedWorkflow ?? deepClone(activeWorkflow);
    const sortedNodeIds = [...nextDraftWorkflow.nodes]
      .sort((left, right) => left.position.x - right.position.x || left.position.y - right.position.y)
      .map((node) => node.node_id);
    setDraftWorkflow(nextDraftWorkflow);
    setSelectedNodeId(
      persistedEditorState?.selectedNodeId && sortedNodeIds.includes(persistedEditorState.selectedNodeId)
        ? persistedEditorState.selectedNodeId
        : (sortedNodeIds[0] ?? "")
    );
    setSelectedEdgeId(persistedEditorState?.selectedEdgeId ?? "");
    setPendingConnection(null);
    setDocumentPickerQuery(persistedEditorState?.documentPickerQuery ?? "");
  }, [activeWorkflow, project]);

  useEffect(() => {
    if (!selectedNodeId || !draftWorkflow?.nodes.some((node) => node.node_id === selectedNodeId)) {
      return;
    }

    const nodeElement = workflowNodeElementRefs.current.get(selectedNodeId);
    if (!nodeElement) {
      return;
    }

    if (typeof nodeElement.scrollIntoView !== "function") {
      return;
    }

    nodeElement.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selectedNodeId, draftWorkflow?.workflow_id]);

  useEffect(() => {
    if (!project || !draftWorkflow) {
      return undefined;
    }
    const timeoutId = window.setTimeout(persistDraftWorkflow, 450);
    return () => window.clearTimeout(timeoutId);
  }, [draftWorkflow, project?.id]);

  useEffect(() => {
    if (!project || !draftWorkflowId) {
      return;
    }
    try {
      window.localStorage.setItem(
        workflowEditorStateStorageKey(project.id, draftWorkflowId),
        JSON.stringify({
          selectedNodeId,
          selectedEdgeId,
          documentPickerQuery
        })
      );
    } catch {
      // Ignore editor-state persistence failures and keep the in-memory editor usable.
    }
  }, [
    documentPickerQuery,
    draftWorkflowId,
    project?.id,
    selectedEdgeId,
    selectedNodeId
  ]);

  useEffect(() => {
    const canvasElement = canvasScrollRef.current;
    if (!canvasElement) {
      return undefined;
    }
    const updateViewportSize = () => {
      setCanvasViewportSize({
        width: canvasElement.clientWidth,
        height: canvasElement.clientHeight
      });
    };
    updateViewportSize();
    const observer = new ResizeObserver(updateViewportSize);
    observer.observe(canvasElement);
    return () => observer.disconnect();
  }, [draftWorkflow?.workflow_id]);

  const draftRuntimeProfile = useMemo(
    () => (project && draftWorkflow ? projectRuntimeProfile(project, draftWorkflow) : null),
    [draftWorkflow, project]
  );
  const workflowValidation = draftWorkflow ? validateWorkflowGraph(draftWorkflow) : null;

  useEffect(() => {
    const topbarElement = canvasTopbarRef.current;
    const bannerElement = canvasBannerRef.current;
    const updateOffset = () => {
      setCanvasOverlayOffset((topbarElement?.offsetHeight ?? 0) + (bannerElement?.offsetHeight ?? 0) + 28);
    };
    updateOffset();
    const observer = new ResizeObserver(updateOffset);
    if (topbarElement) {
      observer.observe(topbarElement);
    }
    if (bannerElement) {
      observer.observe(bannerElement);
    }
    return () => observer.disconnect();
  }, [pendingConnection, workflowValidation]);

  useEffect(() => {
    if (!workbenchSelection || !project || !draftWorkflow || !workflowValidation || workbenchSelection.projectId !== project.id) {
      return;
    }

    if (
      workbenchSelection.kind === "workflow_node"
      && workbenchSelection.workflowId === draftWorkflow.workflow_id
      && draftWorkflow.nodes.some((node) => node.node_id === workbenchSelection.nodeId)
      && selectedNodeId !== workbenchSelection.nodeId
    ) {
      setSelectedNodeId(workbenchSelection.nodeId);
      setSelectedEdgeId("");
      setPendingConnection(null);
    }

    if (
      workbenchSelection.kind === "workflow_edge"
      && workbenchSelection.workflowId === draftWorkflow.workflow_id
      && workflowValidation.normalized_edges.some((edge) => edge.edge_id === workbenchSelection.edgeId)
      && selectedEdgeId !== workbenchSelection.edgeId
    ) {
      setSelectedEdgeId(workbenchSelection.edgeId);
      setSelectedNodeId("");
      setPendingConnection(null);
    }

    if (
      workbenchSelection.kind === "workflow"
      && workbenchSelection.workflowId === draftWorkflow.workflow_id
      && (selectedNodeId || selectedEdgeId)
    ) {
      setSelectedNodeId("");
      setSelectedEdgeId("");
      setPendingConnection(null);
    }
  }, [
    workbenchSelection,
    project,
    draftWorkflow,
    workflowValidation,
    selectedNodeId,
    selectedEdgeId
  ]);

  if (!project || !draftWorkflow || !draftRuntimeProfile || !workflowValidation) {
    return <EmptyState title="流程配置待初始化" body="请先建立项目工作区。" />;
  }

  const sortedNodes = [...draftWorkflow.nodes].sort((left, right) => left.position.x - right.position.x || left.position.y - right.position.y);
  const nodeLookup = new Map(draftWorkflow.nodes.map((node) => [node.node_id, node]));
  const reachableNodeIds = new Set(workflowValidation.reachable_node_ids);
  const activeNodeIds = new Set(workflowValidation.active_node_ids);
  const connectionTargets = pendingConnection
    ? workflowConnectionTargets(draftWorkflow, pendingConnection.fromNodeId, pendingConnection.fromPortId)
    : [];
  const connectionTargetKeys = new Set(connectionTargets.map((target) => `${target.node_id}:${target.port_id}`));
  const canvasMetrics = workflowCanvasMetrics(draftWorkflow.nodes);
  const canvasOrigin = workflowCanvasOrigin(canvasMetrics);
  const viewport = {
    x: draftWorkflow.viewport.x ?? 0,
    y: draftWorkflow.viewport.y ?? 0,
    zoom: clampWorkflowZoom(draftWorkflow.viewport.zoom ?? 0.82)
  };
  const miniMap = workflowMiniMapMetrics(canvasMetrics);
  const viewportWorldRect = workflowViewportWorldRect(viewport, canvasViewportSize);
  const miniMapViewportRect = workflowMiniMapViewportRect(viewportWorldRect, miniMap);
  const writeMiniMapViewportDom = (nextViewport: { x: number; y: number; zoom: number }) => {
    const element = miniMapViewportRef.current;
    if (!element) {
      return;
    }
    const rect = workflowMiniMapViewportRect(
      workflowViewportWorldRect(nextViewport, canvasViewportSize),
      miniMap
    );
    element.style.left = `${rect.left}px`;
    element.style.top = `${rect.top}px`;
    element.style.width = `${rect.width}px`;
    element.style.height = `${rect.height}px`;
  };
  const writeWorkflowViewportDom = (nextViewport: { x: number; y: number; zoom: number }) => {
    if (canvasSurfaceRef.current) {
      canvasSurfaceRef.current.style.transform = `translate3d(${nextViewport.x}px, ${nextViewport.y}px, 0) scale(${nextViewport.zoom})`;
    }
    writeMiniMapViewportDom(nextViewport);
  };
  const viewportFromMiniMapPoint = (clientX: number, clientY: number, surfaceRect: DOMRect) => {
    const canvasElement = canvasScrollRef.current;
    if (!canvasElement) {
      return null;
    }
    const clampedX = Math.min(surfaceRect.right, Math.max(surfaceRect.left, clientX));
    const clampedY = Math.min(surfaceRect.bottom, Math.max(surfaceRect.top, clientY));
    const worldX = miniMap.originX + (clampedX - surfaceRect.left) / miniMap.scale;
    const worldY = miniMap.originY + (clampedY - surfaceRect.top) / miniMap.scale;
    return {
      x: canvasElement.clientWidth / 2 - worldX * viewport.zoom,
      y: canvasElement.clientHeight / 2 - worldY * viewport.zoom,
      zoom: viewport.zoom
    };
  };
  const selectedNode = sortedNodes.find((node) => node.node_id === selectedNodeId) ?? null;
  const displayEdges = workflowValidation.normalized_edges;
  const selectedEdge = displayEdges.find((edge) => edge.edge_id === selectedEdgeId) ?? null;
  const selectedEdgeSourceNode = selectedEdge ? nodeLookup.get(selectedEdge.from_node) : null;
  const selectedEdgeTargetNode = selectedEdge ? nodeLookup.get(selectedEdge.to_node) : null;
  const selectedEdgeLabel = selectedEdge
    ? `${selectedEdgeSourceNode?.label ?? selectedEdge.from_node} -> ${selectedEdgeTargetNode?.label ?? selectedEdge.to_node}`
    : "";
  const latestRun = project.run_history.at(-1);
  const liveWorkflowRun = taskProgress.status === "running"
    && taskProgress.action === "run-workflow"
    && taskProgress.detail?.kind === "workflow_run"
    && (!taskProgress.detail.workflow_id || taskProgress.detail.workflow_id === draftWorkflow.workflow_id)
    ? taskProgress.detail
    : null;
  const historicalRuntimeStates = useMemo<Record<string, WorkflowNodeRuntimeState>>(() => {
    const nodeRuns = latestRun?.node_runs ?? [];
    const totalNodes = Math.max(nodeRuns.length, 1);
    return nodeRuns.reduce<Record<string, WorkflowNodeRuntimeState>>((accumulator, nodeRun, index) => {
      accumulator[nodeRun.node_id] = historicalRuntimeState(nodeRun, index + 1, totalNodes);
      return accumulator;
    }, {});
  }, [latestRun?.run_id, latestRun?.node_runs]);
  const runtimeNodeStates = liveWorkflowRun?.node_states ?? historicalRuntimeStates;
  const runtimeStateForNode = (node: WorkflowNodeInstance | null | undefined): WorkflowNodeRuntimeState | undefined => {
    if (!node) {
      return undefined;
    }
    return runtimeNodeStates[node.node_id]
      ?? Object.values(runtimeNodeStates).find((nodeState) => nodeState.node_type === node.node_type);
  };
  const previewArtifacts = useMemo(() => {
    if (!previewNodeId || !project) return [];
    return project.artifact_records.filter((artifact) => artifact.node_id === previewNodeId);
  }, [previewNodeId, project]);
  const previewNode = previewNodeId ? nodeLookup.get(previewNodeId) ?? null : null;
  const handleLoadArtifactPreview = async (artifactId: string) => {
    const data = await loadArtifactPreview(artifactId);
    if (!data) {
      throw new Error("加载产物预览失败");
    }
    return data;
  };
  useEffect(() => {
    if (!previewNodeId) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPreviewNodeId(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [previewNodeId]);
  const liveRuntimeProgress = liveWorkflowRun ? workflowRuntimeProgress(liveWorkflowRun) : (latestRun?.node_runs?.length ? 1 : 0);
  const runtimeCompletedNodes = liveWorkflowRun?.completed_nodes
    ?? Object.values(runtimeNodeStates).filter((nodeRun) => nodeRun.status !== "pending" && nodeRun.status !== "running").length;
  const runtimeTotalNodes = liveWorkflowRun?.total_nodes
    ?? (latestRun?.node_runs?.length ?? workflowValidation.active_node_ids.length);
  const activeRuntimeNode = liveWorkflowRun?.current_node_id ? runtimeNodeStates[liveWorkflowRun.current_node_id] : undefined;
  const lastCompletedRuntimeNode = liveWorkflowRun?.last_completed_node_id
    ? runtimeNodeStates[liveWorkflowRun.last_completed_node_id]
    : undefined;
  const dictionaryInputNode = sortedNodes.find((node) => node.node_type === "dictionary_input")
    ?? sortedNodes.find((node) => node.node_type === "project_dictionary_set")
    ?? null;
  const corpusInputNode = sortedNodes.find((node) => node.node_type === "corpus_input")
    ?? sortedNodes.find((node) => node.node_type === "filter_corpus")
    ?? null;
  const dictionaryTableIds = project.dictionary_set.collections
    ? Object.values(project.dictionary_set.collections)
        .flatMap((collection) => collection.tables.map((table) => table.id))
    : [];
  const selectedDictionaryTableIds = new Set(
    Array.isArray(dictionaryInputNode?.config.selected_table_ids)
      ? dictionaryInputNode.config.selected_table_ids.map((item) => String(item))
      : []
  );
  const useAllDictionaryTables = selectedDictionaryTableIds.size === 0;
  const availableSources = Array.from(new Set(snapshot.corpus.map((item) => item.source).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const availableInstitutions = Array.from(new Set(snapshot.corpus.map((item) => item.institution).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const availableCategories = Array.from(new Set(snapshot.corpus.map((item) => item.category_or_tag).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const availableWorkflowNodeDefinitions = useMemo(
    () => snapshot.node_definitions?.length ? snapshot.node_definitions : builtinWorkflowToolboxDefinitions(),
    [snapshot.node_definitions]
  );
  const nodeDefinitionsByType = useMemo(
    () => new Map(availableWorkflowNodeDefinitions.map((definition) => [definition.type, definition])),
    [availableWorkflowNodeDefinitions]
  );
  const runScopeForNode = (node: WorkflowNodeInstance | null | undefined): RunScopeDefinition => {
    if (!node || (node.node_type !== "corpus_input" && node.node_type !== "filter_corpus")) {
      return draftRuntimeProfile.run_scope;
    }
    return {
      ...draftRuntimeProfile.run_scope,
      ...(node.config as Partial<RunScopeDefinition>),
      source_values: [...(((node.config.source_values as string[] | undefined) ?? draftRuntimeProfile.run_scope.source_values))],
      institution_values: [...(((node.config.institution_values as string[] | undefined) ?? draftRuntimeProfile.run_scope.institution_values))],
      category_values: [...(((node.config.category_values as string[] | undefined) ?? draftRuntimeProfile.run_scope.category_values))],
      selected_doc_ids: [...(((node.config.selected_doc_ids as string[] | undefined) ?? draftRuntimeProfile.run_scope.selected_doc_ids))]
    };
  };
  const workflowScopeNode = sortedNodes.find((node) => activeNodeIds.has(node.node_id) && node.node_type === "corpus_input")
    ?? sortedNodes.find((node) => node.node_type === "corpus_input")
    ?? sortedNodes.find((node) => node.node_type === "filter_corpus")
    ?? null;
  const workflowRunScope = runScopeForNode(workflowScopeNode);
  const matchedDocuments = snapshot.corpus.filter((item) => corpusMatchesRunScope(item, workflowRunScope));
  const pickerQuery = documentPickerQuery.trim().toLowerCase();
  const pickerScope = selectedNode?.node_type === "corpus_input" || selectedNode?.node_type === "filter_corpus"
    ? runScopeForNode(selectedNode)
    : workflowRunScope;
  const documentPickerRows = pickerScope.mode === "selected_documents"
    ? snapshot.corpus.filter((item) =>
      !pickerQuery || [item.doc_id, item.title, item.source, item.institution].filter(Boolean).join(" ").toLowerCase().includes(pickerQuery)
    )
    : [];
  const canRun = !loading && matchedDocuments.length > 0 && workflowValidation.valid;
  const runSummary = runScopeSummary(workflowRunScope, snapshot.corpus.length, matchedDocuments.length);
  const toolboxDefinitions = useMemo(
    () => [...availableWorkflowNodeDefinitions]
      .filter((definition) => !definition.hidden_from_toolbox)
      .sort((left, right) => left.category.localeCompare(right.category) || left.title.localeCompare(right.title, "zh-CN")),
    [availableWorkflowNodeDefinitions]
  );
  const toolNodeTypes = useMemo(
    () => new Set(toolboxDefinitions.map((definition) => definition.type)),
    [toolboxDefinitions]
  );
  const toolboxDefinitionByType = useMemo(
    () => new Map(toolboxDefinitions.map((definition) => [definition.type, definition])),
    [toolboxDefinitions]
  );

  const selectNode = (nodeId: string) => {
    const node = nodeLookup.get(nodeId);
    setSelectedNodeId(nodeId);
    setSelectedEdgeId("");
    setPendingConnection(null);
    onWorkbenchSelect?.({
      kind: "workflow_node",
      projectId: project.id,
      workflowId: draftWorkflow.workflow_id,
      nodeId,
      nodeType: node?.node_type,
      node
    });
  };

  const selectEdge = (edgeId: string) => {
    const edge = displayEdges.find((item) => item.edge_id === edgeId);
    setSelectedEdgeId(edgeId);
    setSelectedNodeId("");
    setPendingConnection(null);
    onWorkbenchSelect?.({
      kind: "workflow_edge",
      projectId: project.id,
      workflowId: draftWorkflow.workflow_id,
      edgeId,
      edge
    });
  };

  useEffect(() => {
    if (!draggingNodeId) {
      return undefined;
    }

    const handlePointerMove = (event: PointerEvent) => {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }
      const deltaX = (event.clientX - dragState.startClientX) / viewport.zoom;
      const deltaY = (event.clientY - dragState.startClientY) / viewport.zoom;
      const nextPosition = {
        x: dragState.startX + deltaX,
        y: dragState.startY + deltaY
      };
      latestNodeDragRef.current = { nodeId: dragState.nodeId, ...nextPosition };
      const dragOffset = {
        x: nextPosition.x - dragState.startX,
        y: nextPosition.y - dragState.startY
      };
      scheduleCanvasDomWrite(() => {
        const nodeElement = workflowNodeElementRefs.current.get(dragState.nodeId);
        if (!nodeElement) {
          return;
        }
        nodeElement.style.setProperty("--node-drag-x", `${dragOffset.x}px`);
        nodeElement.style.setProperty("--node-drag-y", `${dragOffset.y}px`);
      });
    };

    const handlePointerUp = () => {
      flushCanvasDomWrite();
      const latestPosition = latestNodeDragRef.current;
      if (latestPosition) {
        const nodeElement = workflowNodeElementRefs.current.get(latestPosition.nodeId);
        if (nodeElement) {
          nodeElement.style.left = `${canvasOrigin.x + latestPosition.x}px`;
          nodeElement.style.top = `${canvasOrigin.y + latestPosition.y}px`;
          nodeElement.style.removeProperty("--node-drag-x");
          nodeElement.style.removeProperty("--node-drag-y");
        }
        setDraftWorkflow((current) =>
          current
            ? updateWorkflowNodePosition(current, latestPosition.nodeId, {
              x: latestPosition.x,
              y: latestPosition.y
            })
            : current
        );
      }
      latestNodeDragRef.current = null;
      dragStateRef.current = null;
      setDraggingNodeId("");
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [canvasOrigin.x, canvasOrigin.y, draggingNodeId, viewport.zoom]);

  useEffect(() => {
    if (!isCanvasPanning) {
      return undefined;
    }

    const handlePointerMove = (event: PointerEvent) => {
      const panState = canvasPanStateRef.current;
      if (!panState) {
        return;
      }
      const deltaX = event.clientX - panState.startClientX;
      const deltaY = event.clientY - panState.startClientY;
      const nextViewport = {
        x: panState.startViewportX + deltaX,
        y: panState.startViewportY + deltaY,
        zoom: viewport.zoom
      };
      latestViewportDragRef.current = nextViewport;
      scheduleCanvasDomWrite(() => {
        writeWorkflowViewportDom(nextViewport);
      });
    };

    const handlePointerUp = () => {
      flushCanvasDomWrite();
      const latestViewport = latestViewportDragRef.current;
      if (latestViewport) {
        setDraftWorkflow((current) => current
          ? updateWorkflowViewport(current, {
            x: latestViewport.x,
            y: latestViewport.y
          })
          : current);
      }
      latestViewportDragRef.current = null;
      canvasPanStateRef.current = null;
      setIsCanvasPanning(false);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isCanvasPanning, viewport.zoom]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (!miniMapDragStateRef.current) {
        return;
      }
      const minimapElement = miniMapSurfaceRef.current;
      if (!minimapElement) {
        return;
      }
      const rect = minimapElement.getBoundingClientRect();
      const nextViewport = viewportFromMiniMapPoint(event.clientX, event.clientY, rect);
      if (!nextViewport) {
        return;
      }
      latestViewportDragRef.current = nextViewport;
      scheduleCanvasDomWrite(() => {
        writeWorkflowViewportDom(nextViewport);
      });
    };

    const handlePointerUp = () => {
      flushCanvasDomWrite();
      const latestViewport = latestViewportDragRef.current;
      if (latestViewport) {
        setDraftWorkflow((current) => current
          ? updateWorkflowViewport(current, {
            x: latestViewport.x,
            y: latestViewport.y
          })
          : current);
      }
      latestViewportDragRef.current = null;
      miniMapDragStateRef.current = false;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [miniMap.originX, miniMap.originY, miniMap.scale, viewport.zoom]);

  const updateWorkflow = (updater: (current: WorkflowDefinition) => WorkflowDefinition) => {
    setDraftWorkflow((current) => current ? updater(current) : current);
  };

  const corpusScopeFromSelection = (selection: WorkbenchSelection): Partial<RunScopeDefinition> | null => {
    if (selection.kind !== "corpus_collection") {
      return null;
    }
    if (selection.collectionId === "all-corpus") {
      return {
        mode: "all_documents",
        source_values: [],
        institution_values: [],
        category_values: [],
        year_from: null,
        year_to: null,
        selected_doc_ids: []
      };
    }
    if (selection.collectionId.startsWith("source:")) {
      const sourceFileId = selection.collectionId.slice("source:".length);
      const sourceFile = project.source_files.find((item) => item.id === sourceFileId);
      const matchingSourceValues = sourceFile
        ? Array.from(new Set(snapshot.corpus
            .filter((item) => item.source_profile === sourceFile.source_profile || item.source === sourceFile.name)
            .map((item) => item.source)
            .filter(Boolean) as string[]))
        : [];
      return {
        mode: "filtered_subset",
        source_values: matchingSourceValues,
        institution_values: [],
        category_values: [],
        selected_doc_ids: []
      };
    }

    const corpusView = project.corpus_views.find((view) => view.id === selection.collectionId);
    if (corpusView?.doc_ids?.length) {
      return {
        mode: "selected_documents",
        selected_doc_ids: corpusView.doc_ids,
        source_values: [],
        institution_values: [],
        category_values: []
      };
    }

    return {
      mode: "all_documents"
    };
  };

  const bindCorpusSelectionToWorkflow = (selection: WorkbenchSelection) => {
    const scopePatch = corpusScopeFromSelection(selection);
    if (!scopePatch) {
      return;
    }
    const targetNodeId = corpusInputNode?.node_id;
    if (!targetNodeId) {
      addWorkflowNode("corpus_input", toolboxDefinitionByType.get("corpus_input"));
      return;
    }
    updateWorkflow((current) => updateWorkflowNode(current, targetNodeId, (node) => ({
      ...node,
      config: {
        ...node.config,
        ...scopePatch
      }
    })));
    selectNode(targetNodeId);
  };

  const bindDictionaryTableToWorkflow = (tableId: string) => {
    if (!tableId) {
      return;
    }
    const targetNodeId = dictionaryInputNode?.node_id;
    if (!targetNodeId) {
      addWorkflowNode("dictionary_input", toolboxDefinitionByType.get("dictionary_input"));
      return;
    }
    const nextTableIds = useAllDictionaryTables
      ? [tableId]
      : dictionaryTableIds.filter((id) => selectedDictionaryTableIds.has(id) || id === tableId);
    updateWorkflow((current) => updateWorkflowNode(current, targetNodeId, (node) => ({
      ...node,
      config: {
        ...node.config,
        selected_table_ids: nextTableIds,
        selected_table_ids_text: nextTableIds.join(", ")
      }
    })));
    selectNode(targetNodeId);
  };

  const bindLexiconSelectionToWorkflow = (selection: WorkbenchSelection) => {
    if (selection.kind !== "lexicon_table") {
      return;
    }
    bindDictionaryTableToWorkflow(selection.tableId);
  };

  const bindWorkbenchResourceToWorkflow = (selection: WorkbenchSelection) => {
    if (selection.kind === "corpus_collection") {
      bindCorpusSelectionToWorkflow(selection);
      return;
    }
    if (selection.kind === "lexicon_table") {
      bindLexiconSelectionToWorkflow(selection);
    }
  };

  const addWorkflowNode = (
    nodeType: WorkflowNodeInstance["node_type"],
    registeredDefinition?: RegisteredWorkflowNodeDefinition,
    position?: { x: number; y: number }
  ) => {
    let nextSelectedNodeId = "";
    updateWorkflow((current) => {
      let next = addWorkflowNodeByType(current, nodeType, draftRuntimeProfile, registeredDefinition);
      const previousNodeIds = new Set(current.nodes.map((node) => node.node_id));
      nextSelectedNodeId = next.nodes.find((node) => !previousNodeIds.has(node.node_id))?.node_id ?? "";
      if (position && nextSelectedNodeId) {
        next = updateWorkflowNodePosition(next, nextSelectedNodeId, position);
      }
      return next;
    });
    setSelectedEdgeId("");
    setSelectedNodeId(nextSelectedNodeId);
    if (nextSelectedNodeId) {
      const nextSelectedNode = draftWorkflow.nodes.find((node) => node.node_id === nextSelectedNodeId);
      onWorkbenchSelect?.({
        kind: "workflow_node",
      projectId: project.id,
      workflowId: draftWorkflow.workflow_id,
      nodeId: nextSelectedNodeId,
      nodeType: nextSelectedNode?.node_type ?? nodeType,
      node: nextSelectedNode
      });
    }
    setPendingConnection(null);
  };

  const removeWorkflowNode = (nodeId: string) => {
    updateWorkflow((current) => removeWorkflowNodeById(current, nodeId));
    if (selectedNodeId === nodeId) {
      setSelectedNodeId("");
    }
    setSelectedEdgeId("");
    setPendingConnection(null);
  };

  const clearWorkflowCanvas = () => {
    const confirmed = window.confirm("清空当前画布上的所有节点和连线？\n\n这不会删除项目语料和词表资源，只会把当前 workflow 变成空白画布。");
    if (!confirmed) {
      return;
    }
    setDraftWorkflow(buildBlankWorkflowFromRuntimeProfile(draftWorkflow.workflow_id, draftWorkflow.name, draftRuntimeProfile));
    setSelectedNodeId("");
    setSelectedEdgeId("");
    setPendingConnection(null);
  };

  const insertRecommendedStarter = () => {
    const blankWorkflow = buildBlankWorkflowFromRuntimeProfile(draftWorkflow.workflow_id, draftWorkflow.name, draftRuntimeProfile);
    const nextWorkflow = syncWorkflowFromRuntimeProfile(blankWorkflow, draftRuntimeProfile, "manual");
    setDraftWorkflow(nextWorkflow);
    setSelectedNodeId(nextWorkflow.nodes[0]?.node_id ?? "");
    setSelectedEdgeId("");
    setPendingConnection(null);
  };

  const restoreRecommendedEdges = () => {
    updateWorkflow((current) => restoreWorkflowDefaultEdges(current, draftRuntimeProfile));
    setSelectedEdgeId("");
    setPendingConnection(null);
  };

  const focusWorkflowCanvas = () => {
    updateWorkflow((current) => updateWorkflowViewport(current, workflowFitViewport(current.nodes)));
  };

  const handleValidateGraph = () => {
    if (workflowValidation.issues.length) {
      focusWorkflowCanvas();
    }
  };

  const resetWorkflowLayout = () => {
    updateWorkflow((current) => autoLayoutWorkflow(current));
    requestAnimationFrame(() => {
      canvasScrollRef.current?.scrollTo({ left: 0, top: 0, behavior: "smooth" });
    });
  };

  useEffect(() => {
    const handleWorkbenchAction = (event: Event) => {
      const action = (event as CustomEvent<WorkflowWorkbenchAction>).detail;
      if (!action || loading) {
        return;
      }

      if (action.type === "add_node") {
        if (!toolNodeTypes.has(action.nodeType)) {
          return;
        }
        addWorkflowNode(action.nodeType, toolboxDefinitionByType.get(action.nodeType));
        return;
      }

      switch (action.action) {
        case "insert_recommended_starter":
          insertRecommendedStarter();
          break;
        case "restore_recommended_edges":
          restoreRecommendedEdges();
          break;
        case "auto_layout":
          resetWorkflowLayout();
          break;
        case "fit_view":
          focusWorkflowCanvas();
          break;
        case "validate_graph":
          handleValidateGraph();
          break;
        case "clear_canvas":
          clearWorkflowCanvas();
          break;
        default:
          break;
      }
    };

    window.addEventListener(WORKFLOW_WORKBENCH_ACTION_EVENT, handleWorkbenchAction);
    return () => window.removeEventListener(WORKFLOW_WORKBENCH_ACTION_EVENT, handleWorkbenchAction);
  });

  const updateWorkflowZoom = (zoom: number) => {
    updateWorkflow((current) => updateWorkflowViewport(current, { zoom: clampWorkflowZoom(zoom) }));
  };

  const handleCanvasWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (
      target.closest(".workflow-node-card")
      || target.closest(".workflow-minimap-shell")
      || target.closest("input")
      || target.closest("textarea")
      || target.closest("select")
      || target.closest("button")
    ) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const canvasElement = canvasScrollRef.current;
    if (!canvasElement) {
      return;
    }
    const rect = canvasElement.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const nextZoom = clampWorkflowZoom(viewport.zoom + (event.deltaY < 0 ? 0.08 : -0.08));
    if (nextZoom === viewport.zoom) {
      return;
    }
    const worldX = (pointerX - viewport.x) / viewport.zoom;
    const worldY = (pointerY - viewport.y) / viewport.zoom;
    updateWorkflow((current) => updateWorkflowViewport(current, {
      zoom: nextZoom,
      x: pointerX - worldX * nextZoom,
      y: pointerY - worldY * nextZoom
    }));
  };

  const handleCanvasDragOver = (event: ReactDragEvent<HTMLDivElement>) => {
    if (event.dataTransfer.types.includes(WORKBENCH_SELECTION_MIME) || event.dataTransfer.types.includes(WORKFLOW_NODE_TYPE_MIME)) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      setIsCanvasDropActive(true);
    }
  };

  const handleCanvasDragLeave = (event: ReactDragEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsCanvasDropActive(false);
    }
  };

  const handleCanvasDrop = (event: ReactDragEvent<HTMLDivElement>) => {
    const nodeType = event.dataTransfer.getData(WORKFLOW_NODE_TYPE_MIME) as WorkflowNodeInstance["node_type"] | "";
    if (nodeType) {
      if (!toolNodeTypes.has(nodeType)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const rect = event.currentTarget.getBoundingClientRect();
      const frame = workflowNodeCanvasFrame(nodeType);
      const x = (event.clientX - rect.left - viewport.x) / viewport.zoom - canvasOrigin.x - frame.w / 2;
      const y = (event.clientY - rect.top - viewport.y) / viewport.zoom - canvasOrigin.y - frame.h / 3;
      addWorkflowNode(nodeType, toolboxDefinitionByType.get(nodeType), { x, y });
      setIsCanvasDropActive(false);
      return;
    }

    const payload = event.dataTransfer.getData(WORKBENCH_SELECTION_MIME);
    const droppedSelection = payload ? parseWorkbenchSelectionPayload(payload) : null;
    if (!droppedSelection) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setIsCanvasDropActive(false);
    bindWorkbenchResourceToWorkflow(droppedSelection);
  };

  const handleCanvasPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return;
    }
    const target = event.target as HTMLElement;
    if (target.closest(".workflow-node-card") || target.closest(".workflow-port") || target.closest(".workflow-minimap-shell")) {
      return;
    }
    canvasPanStateRef.current = {
      startClientX: event.clientX,
      startClientY: event.clientY,
      startViewportX: viewport.x,
      startViewportY: viewport.y
    };
    setIsCanvasPanning(true);
    setSelectedNodeId("");
    setSelectedEdgeId("");
    setPendingConnection(null);
    onWorkbenchSelect?.({
      kind: "workflow",
      projectId: project.id,
      workflowId: draftWorkflow.workflow_id
    });
    event.preventDefault();
  };

  const handleMiniMapPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const surfaceElement = miniMapSurfaceRef.current;
    if (!surfaceElement) {
      return;
    }
    const rect = surfaceElement.getBoundingClientRect();
    const centerViewport = (clientX: number, clientY: number) => {
      const nextViewport = viewportFromMiniMapPoint(clientX, clientY, rect);
      if (!nextViewport) {
        return;
      }
      latestViewportDragRef.current = nextViewport;
      writeWorkflowViewportDom(nextViewport);
      updateWorkflow((current) => updateWorkflowViewport(current, {
        x: nextViewport.x,
        y: nextViewport.y
      }));
    };
    miniMapDragStateRef.current = true;
    centerViewport(event.clientX, event.clientY);
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // ignore browsers that deny capture on synthetic layers
    }
    event.preventDefault();
    event.stopPropagation();
  };

  const beginConnection = (fromNodeId: string, fromPortId: string) => {
    setPendingConnection((current) =>
      current?.fromNodeId === fromNodeId && current?.fromPortId === fromPortId
        ? null
        : { fromNodeId, fromPortId }
    );
    setSelectedEdgeId("");
  };

  const connectPendingPort = (toNodeId: string, toPortId: string) => {
    if (!pendingConnection) {
      return;
    }
    updateWorkflow((current) => createWorkflowEdge(current, pendingConnection.fromNodeId, pendingConnection.fromPortId, toNodeId, toPortId));
    setPendingConnection(null);
    selectNode(toNodeId);
    setSelectedEdgeId("");
  };

  const removeSelectedWorkflowEdge = () => {
    if (!selectedEdge) {
      return;
    }
    updateWorkflow((current) => removeWorkflowEdge(current, selectedEdge.edge_id));
    setSelectedEdgeId("");
    onWorkbenchSelect?.({
      kind: "workflow",
      projectId: project.id,
      workflowId: draftWorkflow.workflow_id
    });
  };

  const handleCanvasNodePointerDown = (event: ReactPointerEvent<HTMLElement>, node: WorkflowNodeInstance) => {
    if (event.button !== 0) {
      return;
    }
    if (loading) {
      selectNode(node.node_id);
      event.preventDefault();
      return;
    }
    dragStateRef.current = {
      nodeId: node.node_id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: node.position.x,
      startY: node.position.y
    };
    selectNode(node.node_id);
    setDraggingNodeId(node.node_id);
    event.preventDefault();
  };

  const updateNodeConfig = (nodeId: string, patch: Record<string, unknown>) => {
    updateWorkflow((current) => updateWorkflowNode(current, nodeId, (node) => ({
      ...node,
      config: {
        ...node.config,
        ...patch
      }
    })));
  };

  const updateRunScope = (nodeId: string, patch: Partial<RunScopeDefinition>) => {
    updateNodeConfig(nodeId, patch as Record<string, unknown>);
  };

  const toggleScopeArrayValue = (
    nodeId: string,
    field: "source_values" | "institution_values" | "category_values",
    value: string
  ) => {
    const currentScope = runScopeForNode(nodeLookup.get(nodeId));
    const values = currentScope[field];
    updateRunScope(nodeId, {
      [field]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
    } as Partial<RunScopeDefinition>);
  };

  const toggleSelectedDocument = (nodeId: string, docId: string) => {
    const currentScope = runScopeForNode(nodeLookup.get(nodeId));
    updateRunScope(nodeId, {
      selected_doc_ids: currentScope.selected_doc_ids.includes(docId)
        ? currentScope.selected_doc_ids.filter((item) => item !== docId)
        : [...currentScope.selected_doc_ids, docId]
    });
  };

  const setNodeBypassed = (nodeId: string, bypassed: boolean) => {
    updateWorkflow((current) => updateWorkflowNode(current, nodeId, (node) => ({
      ...node,
      ui_state: {
        ...node.ui_state,
        bypassed
      }
    })));
  };

  const renderBooleanToggles = (
    nodeId: string,
    values: Record<string, unknown>,
    items: readonly (readonly [string, string])[]
  ) => (
    <div className="toggle-grid">
      {items.map(([key, label]) => (
        <label key={key} className="switch-row">
          <input
            type="checkbox"
            checked={Boolean(values[key])}
            onChange={(event) => updateNodeConfig(nodeId, { [key]: event.target.checked })}
            disabled={loading}
          />
          <span>{label}</span>
        </label>
      ))}
    </div>
  );

  const saveWorkflow = async () => {
    const normalizedWorkflow = normalizeWorkflowGraph(draftWorkflow, projectRuntimeProfile(project, draftWorkflow));
    const nextWorkflowDefinitions = project.workflow_definitions.some(
      (workflow) => workflow.workflow_id === normalizedWorkflow.workflow_id
    )
      ? project.workflow_definitions.map((workflow) =>
        workflow.workflow_id === normalizedWorkflow.workflow_id ? normalizedWorkflow : workflow
      )
      : [...project.workflow_definitions, normalizedWorkflow];

    try {
      window.localStorage.setItem(
        workflowDraftStorageKey(project.id, normalizedWorkflow.workflow_id),
        JSON.stringify(normalizedWorkflow)
      );
    } catch {
      // Ignore local draft persistence failures during save.
    }

    return saveProject({
      ...project,
      workflow_definitions: nextWorkflowDefinitions,
      active_workflow_id: normalizedWorkflow.workflow_id
    }, {
      refresh: false,
      actionLabel: "保存工作流"
    });
  };
  saveWorkflowRef.current = saveWorkflow;

  const runCurrentWorkflow = async () => {
    if (!matchedDocuments.length) {
      return;
    }
    const saved = await saveWorkflow();
    if (saved) {
      await runWorkflow();
    }
  };
  runWorkflowRef.current = runCurrentWorkflow;

  const renderRunScopeEditor = (node: WorkflowNodeInstance) => {
    const nodeScope = runScopeForNode(node);
    const scopeMatchedDocuments = snapshot.corpus.filter((item) => corpusMatchesRunScope(item, nodeScope));
    return (
      <Panel title="语料输入">
        <div className="status-panel"><strong>当前范围</strong><span>{runScopeSummary(nodeScope, snapshot.corpus.length, scopeMatchedDocuments.length)}</span></div>
        <div className="intent-option-grid">
          {runScopeModeOptions.map((option) => (
            <button key={option.id} type="button" className={`intent-choice ${nodeScope.mode === option.id ? "is-active" : ""}`} onClick={() => updateRunScope(node.node_id, { mode: option.id })} disabled={loading}>
              <div>
                <strong>{option.title}</strong>
                <p>{option.description}</p>
              </div>
            </button>
          ))}
        </div>
        {nodeScope.mode === "filtered_subset" && (
          <div className="intent-filter-stack">
            <div className="intent-filter-group">
              <strong>来源</strong>
              <div className="pill-cloud">
                {availableSources.length ? availableSources.map((source) => (
                  <button key={source} type="button" className={`intent-pill ${nodeScope.source_values.includes(source) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue(node.node_id, "source_values", source)} disabled={loading}>{source}</button>
                )) : <span className="muted">当前语料还没有来源字段。</span>}
              </div>
            </div>
            <div className="intent-filter-group">
              <strong>机构</strong>
              <div className="pill-cloud">
                {availableInstitutions.length ? availableInstitutions.map((institution) => (
                  <button key={institution} type="button" className={`intent-pill ${nodeScope.institution_values.includes(institution) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue(node.node_id, "institution_values", institution)} disabled={loading}>{institution}</button>
                )) : <span className="muted">当前语料还没有机构字段。</span>}
              </div>
            </div>
            <div className="intent-filter-group">
              <strong>标签</strong>
              <div className="pill-cloud">
                {availableCategories.length ? availableCategories.map((category) => (
                  <button key={category} type="button" className={`intent-pill ${nodeScope.category_values.includes(category) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue(node.node_id, "category_values", category)} disabled={loading}>{category}</button>
                )) : <span className="muted">当前语料还没有标签字段。</span>}
              </div>
            </div>
            <div className="settings-grid">
              <label className="field"><span>起始年份</span><input type="number" value={nodeScope.year_from ?? ""} onChange={(event) => updateRunScope(node.node_id, { year_from: event.target.value ? Number(event.target.value) : null })} disabled={loading} placeholder="例如 2024" /></label>
              <label className="field"><span>结束年份</span><input type="number" value={nodeScope.year_to ?? ""} onChange={(event) => updateRunScope(node.node_id, { year_to: event.target.value ? Number(event.target.value) : null })} disabled={loading} placeholder="例如 2025" /></label>
            </div>
          </div>
        )}
        {nodeScope.mode === "selected_documents" && (
          <div className="intent-filter-stack">
            <label className="field">
              <span>搜索文档</span>
              <input value={documentPickerQuery} onChange={(event) => setDocumentPickerQuery(event.target.value)} placeholder="按标题、来源或机构筛选" disabled={loading} />
            </label>
            <div className="document-picker-list">
              {documentPickerRows.slice(0, 24).map((item) => (
                <label key={item.doc_id} className="document-picker-row">
                  <input type="checkbox" checked={nodeScope.selected_doc_ids.includes(item.doc_id)} onChange={() => toggleSelectedDocument(node.node_id, item.doc_id)} disabled={loading} />
                  <div>
                    <strong>{item.title}</strong>
                    <p>{[item.doc_id, item.source, item.institution, item.year].filter(Boolean).join(" · ")}</p>
                  </div>
                </label>
              ))}
              {!documentPickerRows.length && <span className="muted">没有匹配的文档，请换个关键词试试。</span>}
            </div>
          </div>
        )}
      </Panel>
    );
  };

  const renderSelectedNodePanel = () => {
    if (!selectedNode) {
      return <EmptyState title="选择一个节点" body="从左侧工具箱加入节点，或点击画布中的节点卡片后，在这里继续补完整参数。" />;
    }

    if (selectedNode.node_type === "corpus_input" || selectedNode.node_type === "filter_corpus") {
      return renderRunScopeEditor(selectedNode);
    }

    if (selectedNode.node_type === "dictionary_input" || selectedNode.node_type === "project_dictionary_set") {
      return (
        <Panel title="词表输入" actions={<Button appearance="subtle" onClick={() => setActivePage("dictionaries")} disabled={loading}>打开词库中心</Button>}>
          <p className="body-copy">这里引用的是项目当前词表资源。后续如果要支持多词表切换，会继续把资源选择器下沉到节点体内。</p>
          <div className="status-panel"><strong>当前词表版本</strong><span>{project.dictionary_set.version}</span></div>
          <div className="status-panel"><strong>启用条目</strong><span>{enabledDictionaryEntryCount(project.dictionary_set)} 条</span></div>
          <div className="status-panel">
            <strong>绑定资源</strong>
            <span>{useAllDictionaryTables ? "全部资源表" : `${selectedDictionaryTableIds.size} 张资源表`}</span>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "merge_corpora") {
      return (
        <Panel title="合并语料">
          <p className="body-copy">合并节点已经接入原生 DAG 执行。多条语料支路会先在这里汇总，再继续流向后续清洗、切词和分析节点。</p>
          <label className="field">
            <span>合并策略</span>
            <select value={String(selectedNode.config.strategy ?? "append")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { strategy: event.target.value })} disabled={loading}>
              <option value="append">直接追加</option>
              <option value="dedupe">按 doc_id 去重</option>
            </select>
          </label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "clean_text") {
      return <Panel title="基础清洗">{renderBooleanToggles(selectedNode.node_id, selectedNode.config as Record<string, unknown>, cleaningToggleItems)}</Panel>;
    }

    if (selectedNode.node_type === "normalize_text") {
      return (
        <Panel title="统一写法">
          {renderBooleanToggles(selectedNode.node_id, selectedNode.config as Record<string, unknown>, normalizationToggleItems)}
          <label className="field">
            <span>Regex 优先策略</span>
            <select value={String(selectedNode.config.regex_rule_priority ?? draftRuntimeProfile.normalization.regex_rule_priority)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { regex_rule_priority: event.target.value })} disabled={loading}>
              <option value="rule_order">按规则顺序</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "tokenize") {
      return (
        <Panel title="切词">
          <div className="settings-grid">
            <label className="field">
              <span>语言模式</span>
              <select value={String(selectedNode.config.language_mode ?? draftRuntimeProfile.tokenization.language_mode)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { language_mode: event.target.value })} disabled={loading}>
                <option value="auto">自动判断</option>
                <option value="zh">中文</option>
                <option value="en">英文</option>
                <option value="mixed">中英混合</option>
              </select>
            </label>
            <label className="field">
              <span>切词前最短长度</span>
              <input type="number" value={Number(selectedNode.config.min_token_length_before_filter ?? draftRuntimeProfile.tokenization.min_token_length_before_filter)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { min_token_length_before_filter: Number(event.target.value) })} disabled={loading} />
            </label>
            <label className="field">
              <span>最小 n-gram</span>
              <input type="number" value={Number(selectedNode.config.ngram_min ?? draftRuntimeProfile.tokenization.ngram_min)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { ngram_min: Number(event.target.value) })} disabled={loading} />
            </label>
            <label className="field">
              <span>最大 n-gram</span>
              <input type="number" value={Number(selectedNode.config.ngram_max ?? draftRuntimeProfile.tokenization.ngram_max)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { ngram_max: Number(event.target.value) })} disabled={loading} />
            </label>
          </div>
          {renderBooleanToggles(selectedNode.node_id, selectedNode.config as Record<string, unknown>, tokenizationToggleItems)}
        </Panel>
      );
    }

    if (selectedNode.node_type === "apply_dictionary_rules") {
      return (
        <Panel title="套用词表">
          {renderBooleanToggles(selectedNode.node_id, selectedNode.config as Record<string, unknown>, dictionaryToggleItems)}
          <label className="field">
            <span>冲突处理</span>
            <select value={String(selectedNode.config.conflict_resolution ?? draftRuntimeProfile.dictionary.conflict_resolution)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { conflict_resolution: event.target.value })} disabled={loading}>
              <option value="priority">按词表优先级</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "filter_terms") {
      return (
        <Panel title="过滤词项">
          {renderBooleanToggles(selectedNode.node_id, selectedNode.config as Record<string, unknown>, filteringToggleItems)}
          <div className="settings-grid">
            <label className="field"><span>最短 token 长度</span><input type="number" value={Number(selectedNode.config.min_token_length ?? draftRuntimeProfile.filtering.min_token_length)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { min_token_length: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>最小词频</span><input type="number" value={Number(selectedNode.config.min_term_frequency ?? draftRuntimeProfile.filtering.min_term_frequency)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { min_term_frequency: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "frequency_statistics") {
      return (
        <Panel title="词频统计">
          <label className="field">
            <span>高频词 Top N</span>
            <input type="number" value={Number(selectedNode.config.top_n ?? draftRuntimeProfile.analysis.top_n)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { top_n: Number(event.target.value) })} disabled={loading} />
          </label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "term_year_analysis") {
      return <Panel title="词项年份分析"><p className="body-copy">这个节点会输出词项在不同年份上的变化表，适合继续连到图表和报表输出节点。</p></Panel>;
    }

    if (selectedNode.node_type === "cooccurrence_analysis") {
      return (
        <Panel title="共现分析">
          <div className="settings-grid">
            <label className="field"><span>共现窗口</span><input type="number" value={Number(selectedNode.config.cooccurrence_window ?? draftRuntimeProfile.analysis.cooccurrence_window)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { cooccurrence_window: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>最小共现次数</span><input type="number" value={Number(selectedNode.config.min_cooccurrence ?? draftRuntimeProfile.analysis.min_cooccurrence)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { min_cooccurrence: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "similarity_analysis") {
      return (
        <Panel title="相似度计算">
          <div className="settings-grid">
            <label className="field"><span>最小相似度</span><input type="number" step="0.01" value={Number(selectedNode.config.min_similarity ?? draftRuntimeProfile.analysis.min_similarity)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { min_similarity: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>最多文档对</span><input type="number" value={Number(selectedNode.config.similarity_top_k ?? draftRuntimeProfile.analysis.similarity_top_k)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { similarity_top_k: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>特征词数量</span><input value={String(selectedNode.config.feature_term_count ?? draftRuntimeProfile.analysis.feature_term_count)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { feature_term_count: event.target.value })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "topic_modeling") {
      return (
        <Panel title="主题建模">
          <div className="settings-grid">
            <label className="field">
              <span>主题算法</span>
              <select value={String(selectedNode.config.topic_algorithm ?? draftRuntimeProfile.analysis.topic_algorithm)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { topic_algorithm: event.target.value })} disabled={loading}>
                <option value="nmf">NMF</option>
                <option value="lda">LDA</option>
              </select>
            </label>
            <label className="field"><span>主题数量</span><input type="number" value={Number(selectedNode.config.topic_model_k ?? draftRuntimeProfile.analysis.topic_model_k)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { topic_model_k: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>每主题词项数</span><input type="number" value={Number(selectedNode.config.top_terms_per_topic ?? 5)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { top_terms_per_topic: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "keyword_extraction") {
      return (
        <Panel title="关键词提取">
          <div className="settings-grid">
            <label className="field"><span>每篇文档关键词数</span><input type="number" value={Number(selectedNode.config.top_k_per_doc ?? draftRuntimeProfile.analysis.top_k_per_doc)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { top_k_per_doc: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>项目级关键词数</span><input type="number" value={Number(selectedNode.config.top_k_project ?? draftRuntimeProfile.analysis.top_k_project)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { top_k_project: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "keyword_clustering") {
      return (
        <Panel title="关键词聚类">
          <div className="settings-grid">
            <label className="field"><span>关键词聚类数</span><input type="number" value={Number(selectedNode.config.keyword_cluster_k ?? draftRuntimeProfile.analysis.keyword_cluster_k)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { keyword_cluster_k: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>主题数量</span><input type="number" value={Number(selectedNode.config.topic_model_k ?? draftRuntimeProfile.analysis.topic_model_k)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { topic_model_k: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "institution_topic_analysis") {
      return (
        <Panel title="机构主题分析">
          <label className="field"><span>主题数量</span><input type="number" value={Number(selectedNode.config.topic_model_k ?? draftRuntimeProfile.analysis.topic_model_k)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { topic_model_k: Number(event.target.value) })} disabled={loading} /></label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "save_csv" || selectedNode.node_type === "save_xlsx") {
      return (
        <Panel title={selectedNode.node_type === "save_csv" ? "保存 CSV" : "保存 XLSX"}>
          <label className="field"><span>文件名前缀</span><input value={String(selectedNode.config.file_prefix ?? "tables")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { file_prefix: event.target.value })} disabled={loading} /></label>
          <p className="body-copy">这个输出节点支持多输入，可以把多个表格节点一起连进来统一导出。</p>
        </Panel>
      );
    }

    if (selectedNode.node_type === "save_png") {
      return (
        <Panel title="保存 PNG">
          <div className="settings-grid">
            <label className="field"><span>文件名前缀</span><input value={String(selectedNode.config.file_prefix ?? "charts")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { file_prefix: event.target.value })} disabled={loading} /></label>
            <label className="field"><span>PNG 分辨率（DPI）</span><input type="number" value={Number(selectedNode.config.chart_dpi ?? draftRuntimeProfile.export.chart_dpi)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { chart_dpi: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }

    if (selectedNode.node_type === "save_html_report") {
      return (
        <Panel title="保存 HTML 报告">
          <label className="field"><span>文件名前缀</span><input value={String(selectedNode.config.file_prefix ?? "report")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { file_prefix: event.target.value })} disabled={loading} /></label>
          <label className="switch-row">
            <input type="checkbox" checked={Boolean(selectedNode.config.include_audit ?? draftRuntimeProfile.export.include_audit)} onChange={(event) => updateNodeConfig(selectedNode.node_id, { include_audit: event.target.checked })} disabled={loading} />
            <span>在报告中附带审计摘要</span>
          </label>
        </Panel>
      );
    }

    if (selectedNode.node_type === "note") {
      return <Panel title="注释"><label className="field"><span>注释文本</span><textarea value={String(selectedNode.config.text ?? "")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { text: event.target.value })} disabled={loading} rows={6} /></label></Panel>;
    }

    if (selectedNode.node_type === "group") {
      return <Panel title="分组"><label className="field"><span>分组标题</span><input value={String(selectedNode.config.title ?? "")} onChange={(event) => updateNodeConfig(selectedNode.node_id, { title: event.target.value })} disabled={loading} /></label></Panel>;
    }

    return <Panel title="节点参数"><p className="body-copy">这个节点类型的完整配置面板还在继续补充，当前已经可以在节点体内做快捷调整。</p></Panel>;
  };

  const renderNodeInlineEditor = (node: WorkflowNodeInstance) => renderWorkflowNodeInlineEditor({
    node,
    project,
    snapshot: { corpus: snapshot.corpus },
    latestRun,
    draftRuntimeProfile,
    loading,
    nodeDefinitionsByType,
    availableSources,
    availableInstitutions,
    availableCategories,
    documentPickerQuery,
    setDocumentPickerQuery,
    setActivePage,
    bindDictionaryTableToWorkflow,
    runScopeForNode,
    runScopeSummary,
    corpusMatchesRunScope,
    updateNodeConfig,
    updateRunScope,
    toggleScopeArrayValue,
    toggleSelectedDocument,
    enabledDictionaryEntryCount
  });

  const renderNodePreview = (node: WorkflowNodeInstance) => {
    const nodeScope = node.node_type === "corpus_input" || node.node_type === "filter_corpus"
      ? runScopeForNode(node)
      : workflowRunScope;
    const nodeMatchedDocuments = snapshot.corpus.filter((item) => corpusMatchesRunScope(item, nodeScope));
    const rawSamples = previewSampleTexts(nodeMatchedDocuments, "raw_text");
    const cleanSamples = previewSampleTexts(nodeMatchedDocuments, "clean_text");
    const normalizedSamples = previewSampleTexts(nodeMatchedDocuments, "normalized_text");
    const tokenSamples = previewSampleTerms(nodeMatchedDocuments, "tokens");
    const phraseSamples = previewSampleTerms(nodeMatchedDocuments, "phrase_hits");
    const filteredSamples = previewSampleTerms(nodeMatchedDocuments, "filtered_tokens");
    const latestArtifacts = latestRun?.artifacts ?? [];
    const nodeRuntime = runtimeStateForNode(node);
    const persistedOutputPreview = renderPersistedNodeOutputPreview(nodeRuntime);
    const resultBundle = project.results as unknown as Record<string, unknown>;
    const outputResultKeys = node.outputs
      .map((port) => (port as typeof port & { result_bundle_key?: string }).result_bundle_key)
      .filter((key): key is string => Boolean(key));
    const firstResultKey = outputResultKeys.find((key) => Array.isArray(resultBundle[key]));
    const firstResultRows = firstResultKey && Array.isArray(resultBundle[firstResultKey])
      ? resultBundle[firstResultKey] as Array<Record<string, unknown>>
      : [];
    const configKeys = Object.keys(node.config ?? {});

    if (node.node_type === "corpus_input" || node.node_type === "load_project_corpus" || node.node_type === "filter_corpus") {
      return (
        <Panel title="预览（基于当前项目快照）">
          <div className="status-panel"><strong>当前命中文档</strong><span>{nodeMatchedDocuments.length} 篇</span></div>
          <ul className="micro-list">
            {nodeMatchedDocuments.slice(0, 5).map((item) => <li key={item.doc_id}>{item.title}</li>)}
            {!nodeMatchedDocuments.length && <li>当前范围下还没有可见文档。</li>}
          </ul>
        </Panel>
      );
    }

    if (node.node_type === "dictionary_input" || node.node_type === "project_dictionary_set") {
      return (
        <Panel title="预览（基于当前项目词表）">
          <div className="status-panel"><strong>启用词条</strong><span>{enabledDictionaryEntryCount(project.dictionary_set)} 条</span></div>
          <ul className="micro-list">
            {Object.values(project.dictionary_set.sheets).flatMap((sheet) => sheet.entries.filter((entry) => entry.enabled).slice(0, 1).map((entry) => `${sheet.name}：${entry.source}`)).slice(0, 6).map((entry) => <li key={entry}>{entry}</li>)}
          </ul>
        </Panel>
      );
    }

    if (node.node_type === "clean_text") {
      return (
        <>
          <Panel title="预览（基于最近一次项目快照）">
            <div className="preview-compare-grid">
              <div className="preview-card"><strong>原文片段</strong><p>{rawSamples[0] ?? "暂无原文样本。"}</p></div>
              <div className="preview-card"><strong>清洗后片段</strong><p>{cleanSamples[0] ?? "暂无清洗后样本。"}</p></div>
            </div>
          </Panel>
          {!cleanSamples[0] ? persistedOutputPreview : null}
        </>
      );
    }

    if (node.node_type === "normalize_text") {
      return (
        <>
          <Panel title="预览（基于最近一次项目快照）">
            <div className="preview-compare-grid">
              <div className="preview-card"><strong>清洗后片段</strong><p>{cleanSamples[0] ?? "暂无清洗后样本。"}</p></div>
              <div className="preview-card"><strong>标准化片段</strong><p>{normalizedSamples[0] ?? "暂无标准化样本。"}</p></div>
            </div>
          </Panel>
          {!normalizedSamples[0] ? persistedOutputPreview : null}
        </>
      );
    }

    if (node.node_type === "tokenize") {
      return (
        <>
          <Panel title="预览（基于最近一次项目快照）">
            <div className="status-panel"><strong>Token 样本</strong><span>{tokenSamples.slice(0, 8).join(" / ") || "暂无 token 样本"}</span></div>
            <div className="status-panel"><strong>短语命中</strong><span>{phraseSamples.slice(0, 6).join(" / ") || "暂无短语命中"}</span></div>
          </Panel>
          {!tokenSamples.length ? persistedOutputPreview : null}
        </>
      );
    }

    if (node.node_type === "apply_dictionary_rules" || node.node_type === "filter_terms") {
      return (
        <>
          <Panel title="预览（基于最近一次项目快照）">
            <div className="status-panel"><strong>过滤后词项</strong><span>{filteredSamples.slice(0, 10).join(" / ") || "暂无过滤后词项"}</span></div>
            <div className="status-panel"><strong>审计命中</strong><span>{project.results.audit_table.length} 条</span></div>
          </Panel>
          {!filteredSamples.length ? persistedOutputPreview : null}
        </>
      );
    }

    if (node.node_type === "frequency_statistics" || node.node_type === "analyze_corpus") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>词频 Top 5</strong><span>{project.results.frequency_table.slice(0, 5).map((row) => `${row.term}(${row.tf})`).join(" / ") || "暂无词频结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "term_year_analysis") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>年份趋势样本</strong><span>{project.results.term_year_table.slice(0, 5).map((row) => `${row.term}(${row.year})`).join(" / ") || "暂无年份结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "cooccurrence_analysis") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>共现样本</strong><span>{project.results.cooccurrence_table.slice(0, 5).map((row) => `${row.term_a}×${row.term_b}`).join(" / ") || "暂无共现结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "similarity_analysis") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>相似文档对</strong><span>{(project.results.similarity_table ?? []).slice(0, 5).map((row) => `${String(row.doc_id_a)}~${String(row.doc_id_b)}`).join(" / ") || "暂无相似度结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "keyword_extraction") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>项目关键词</strong><span>{project.results.keyword_result.filter((row) => row.scope === "project").slice(0, 5).map((row) => row.keyword).join(" / ") || "暂无项目关键词"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "keyword_clustering") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>聚类样本</strong><span>{project.results.keyword_cluster_result.slice(0, 5).map((row) => `${row.topic_label ?? `簇 ${row.cluster_id}`}:${row.term}`).join(" / ") || "暂无聚类结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "institution_topic_analysis") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>机构主题样本</strong><span>{project.results.institution_topic_cooccurrence.slice(0, 5).map((row) => `${row.institution}:${row.topic_label}`).join(" / ") || "暂无机构主题结果"}</span></div>
        </Panel>
      );
    }

    if (node.node_type === "save_csv" || node.node_type === "save_xlsx" || node.node_type === "save_png" || node.node_type === "save_html_report" || node.node_type === "export_results") {
      return (
        <Panel title="预览（基于最近一次运行结果）">
          <div className="status-panel"><strong>导出文件</strong><span>{project.results.report_files.length} 个</span></div>
          <ul className="micro-list">
            {project.results.report_files.slice(0, 5).map((path) => <li key={path}>{path}</li>)}
            {!project.results.report_files.length && <li>最近一次运行还没有导出文件。</li>}
          </ul>
          <div className="status-panel"><strong>运行产物摘要</strong><span>{latestArtifacts.map((artifact) => runArtifactCompactSummary(artifact)).join(" / ") || "暂无运行产物摘要"}</span></div>
        </Panel>
      );
    }

    return (
      <>
        <Panel title="预览（节点概览）">
          <div className="status-panel"><strong>节点状态</strong><span>{nodeRuntime ? runtimeStatusLabel(nodeRuntime.status) : "尚未执行"}</span></div>
          <div className="status-panel"><strong>输出摘要</strong><span>{nodeRuntime?.output_summary ?? "当前还没有节点级结果摘要。"}</span></div>
          {nodeRuntime?.sample_outputs?.length ? (
            <div className="status-panel"><strong>样本输出</strong><span>{nodeRuntime.sample_outputs.slice(0, 5).join(" / ")}</span></div>
          ) : null}
          {firstResultKey ? (
            <div className="status-panel"><strong>结果表</strong><span>{firstResultKey} · {firstResultRows.length} 行</span></div>
          ) : null}
          <div className="status-panel"><strong>端口</strong><span>{node.inputs.length} 个输入 / {node.outputs.length} 个输出</span></div>
          <div className="status-panel"><strong>配置</strong><span>{configKeys.slice(0, 6).join(" / ") || "使用默认配置"}</span></div>
        </Panel>
        {persistedOutputPreview}
      </>
    );
  };

  return (
    <WorkflowWorkspace
      workflow={draftWorkflow}
      loading={loading}
      canRun={canRun}
      onSaveWorkflow={async () => { await saveWorkflow(); }}
      onRunWorkflow={runCurrentWorkflow}
      onAutoLayout={resetWorkflowLayout}
      onFitView={focusWorkflowCanvas}
      onValidateGraph={handleValidateGraph}
    >
      <div className="workflow-editor-page">
        <div className="workflow-editor-shell">
          <section
          className={`workflow-editor-canvas ${isCanvasPanning ? "is-panning" : ""} ${draggingNodeId ? "is-dragging-node" : ""} ${isCanvasDropActive ? "is-drop-active" : ""}`}
          style={{ ["--workflow-overlay-offset" as string]: `${canvasOverlayOffset}px` }}
          onDragOver={handleCanvasDragOver}
          onDragLeave={handleCanvasDragLeave}
          onDrop={handleCanvasDrop}
          >
            <div ref={canvasTopbarRef} className="workflow-floating-topbar">
            <div className="workflow-floating-topbar-group">
              <div className="workflow-title-stack">
                <p className="eyebrow">节点图</p>
                <h3>{draftWorkflow.name}</h3>
                <span>
                  {liveWorkflowRun
                    ? `${activeRuntimeNode?.label ?? "正在整理运行结果"} · ${liveWorkflowRun.detail ?? "运行中"}`
                    : (pendingConnection ? "点击高亮输入端完成连线" : `${sortedNodes.length} 个节点 · ${displayEdges.length} 条连线`)}
                </span>
              </div>
              <div className="workflow-floating-pills">
                <span className="pill">{workflowValidation.valid ? "图已连通" : "仍需补线"}</span>
                <span className="pill">{sortedNodes.length} 节点</span>
                {liveWorkflowRun && <span className="pill">{runtimeCompletedNodes}/{runtimeTotalNodes} 节点</span>}
                {liveWorkflowRun && <span className="pill">{Math.round(liveRuntimeProgress * 100)}%</span>}
                <span className="pill">{Math.round(viewport.zoom * 100)}%</span>
              </div>
            </div>
            {selectedEdge && (
              <div className="workflow-floating-topbar-group workflow-floating-topbar-actions">
                <span className="pill">{selectedEdgeLabel}</span>
                <Button appearance="subtle" onClick={removeSelectedWorkflowEdge} disabled={loading}>删除连线</Button>
              </div>
            )}
          </div>

          {(pendingConnection || workflowValidation.issues.length > 0) && (
            <div ref={canvasBannerRef} className={`workflow-floating-banner ${pendingConnection ? "is-warning" : ""}`}>
              {pendingConnection
                ? `正在从 ${nodeLookup.get(pendingConnection.fromNodeId)?.label ?? pendingConnection.fromNodeId} · ${workflowPortLabel(nodeLookup.get(pendingConnection.fromNodeId), pendingConnection.fromPortId, "outputs")} 连线，可连接 ${connectionTargets.length} 个输入端。`
                : workflowValidation.issues[0]}
            </div>
          )}

          <div
            ref={canvasScrollRef}
            className="workflow-canvas-scroll"
            onWheel={handleCanvasWheel}
            onPointerDown={handleCanvasPointerDown}
          >
            <div className="workflow-canvas-stage" onClick={() => setPendingConnection(null)}>
                <div
                  ref={canvasSurfaceRef}
                  className="workflow-canvas-surface"
                  style={{
                    width: canvasMetrics.width,
                    height: canvasMetrics.height,
                    transform: `translate3d(${viewport.x}px, ${viewport.y}px, 0) scale(${viewport.zoom})`
                  }}
                >
                  <svg className="workflow-edge-layer" width={canvasMetrics.width} height={canvasMetrics.height} viewBox={`0 0 ${canvasMetrics.width} ${canvasMetrics.height}`} aria-hidden="true">
                    <defs>
                      <marker id="workflow-arrow-head" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(138, 90, 15, 0.58)" />
                      </marker>
                    </defs>
                    {displayEdges.map((edge) => {
                      const fromNode = nodeLookup.get(edge.from_node);
                      const toNode = nodeLookup.get(edge.to_node);
                      if (!fromNode || !toNode) {
                        return null;
                      }
                      const edgePath = workflowEdgePath(fromNode, toNode, edge.from_port, edge.to_port, canvasOrigin);
                      const isSelected = selectedEdge?.edge_id === edge.edge_id;
                      return (
                        <g key={edge.edge_id}>
                          <path
                            d={edgePath}
                            className={`workflow-edge-path ${isSelected ? "is-selected" : ""}`}
                            markerEnd="url(#workflow-arrow-head)"
                          />
                          <path
                            d={edgePath}
                            className="workflow-edge-hit"
                            onClick={() => selectEdge(edge.edge_id)}
                          />
                        </g>
                      );
                    })}
                  </svg>
                {sortedNodes.map((node, index) => {
                  const nodeSelected = selectedNode?.node_id === node.node_id;
                  const nodeRuntime = runtimeStateForNode(node);
                  const nodeStepId = workflowNodeStepId(node);
                  const nodeCanBypass = Boolean(nodeStepId && optionalWorkflowSteps.includes(nodeStepId));
                  const nodeFrame = workflowNodeCanvasFrame(node);
                  const nodeInlinePreview = nodeSelected ? renderWorkflowNodePreview({
                    node,
                    project,
                    snapshot: { corpus: snapshot.corpus },
                    latestRun,
                    draftRuntimeProfile,
                    loading,
                    nodeDefinitionsByType,
                    availableSources,
                    availableInstitutions,
                    availableCategories,
                    documentPickerQuery,
                    setDocumentPickerQuery,
                    setActivePage,
                    bindDictionaryTableToWorkflow,
                    runScopeForNode,
                    runScopeSummary,
                    corpusMatchesRunScope,
                    updateNodeConfig,
                    updateRunScope,
                    toggleScopeArrayValue,
                    toggleSelectedDocument,
                    enabledDictionaryEntryCount
                  }) : null;
                  return (
                    <div
                      ref={(element) => {
                        if (element) {
                          workflowNodeElementRefs.current.set(node.node_id, element);
                        } else {
                          workflowNodeElementRefs.current.delete(node.node_id);
                        }
                      }}
                      key={node.node_id}
                      data-workflow-node-id={node.node_id}
                      className={`workflow-node-card workflow-node-card-canvas ${nodeSelected ? "is-selected" : ""} ${node.ui_state.bypassed ? "is-bypassed" : ""} ${draggingNodeId === node.node_id ? "is-dragging" : ""} ${nodeRuntime ? `is-runtime-${nodeRuntime.status}` : ""} ${activeRuntimeNode?.node_id === node.node_id ? "is-runtime-current" : ""}`.trim()}
                      style={{
                        left: canvasOrigin.x + node.position.x,
                        top: canvasOrigin.y + node.position.y,
                        width: nodeFrame.w,
                        minHeight: nodeFrame.h,
                        zIndex: draggingNodeId === node.node_id ? 40 : nodeSelected ? 30 : 10 + index
                      }}
                      onClick={(event) => {
                        event.stopPropagation();
                        selectNode(node.node_id);
                        setPendingConnection(null);
                      }}
                    >
                      {node.inputs.length > 0 && (
                        <div className="workflow-port-rail is-input">
                          {node.inputs.map((port) => {
                            const isCompatible = connectionTargetKeys.has(`${node.node_id}:${port.port_id}`);
                            const isPendingSource = pendingConnection?.fromNodeId === node.node_id && pendingConnection?.fromPortId === port.port_id;
                            return (
                              <button
                                key={`${node.node_id}-${port.port_id}`}
                                type="button"
                                className={`workflow-port is-input ${isCompatible ? "is-compatible" : ""} ${isPendingSource ? "is-pending" : ""}`}
                                style={{ top: workflowPortLocalCenter(node, port.port_id, "inputs") }}
                                aria-label={`输入端：${port.label ?? port.port_id}`}
                                title={workflowPortTitle(port)}
                                onPointerDown={(event) => event.stopPropagation()}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  if (pendingConnection && isCompatible) {
                                    connectPendingPort(node.node_id, port.port_id);
                                  }
                                }}
                                disabled={Boolean(pendingConnection) && !isCompatible}
                              >
                                <span>{port.label ?? "输入"}</span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                      <div className="workflow-node-card-body">
                        <div className="workflow-node-card-head">
                          <div
                            className="workflow-node-card-head-main"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              handleCanvasNodePointerDown(event, node);
                            }}
                          >
                            <button
                              type="button"
                              className="workflow-node-card-grab"
                              onClick={(event) => event.stopPropagation()}
                              aria-label={`拖动 ${node.label}`}
                              title="拖动节点"
                            >
                              ⋮⋮
                            </button>
                            <span className="pill">{workflowNodeBadge(node, workflowValidation)}</span>
                          </div>
                          {nodeSelected && (
                            <div className="workflow-node-card-actions" onPointerDown={(event) => event.stopPropagation()}>
                              {nodeCanBypass && (
                                <button type="button" className="workflow-node-card-action" onClick={(event) => {
                                  event.stopPropagation();
                                  setNodeBypassed(node.node_id, !node.ui_state.bypassed);
                                }}>
                                  {node.ui_state.bypassed ? "恢复" : "跳过"}
                                </button>
                              )}
                              {workflowNodeCanRemove() && (
                                <button type="button" className="workflow-node-card-action danger" onClick={(event) => {
                                  event.stopPropagation();
                                  removeWorkflowNode(node.node_id);
                                }}>
                                  删除
                                </button>
                              )}
                            </div>
                          )}
                          <button
                            type="button"
                            className="workflow-node-card-action"
                            title="预览节点"
                            onPointerDown={(event) => event.stopPropagation()}
                            onClick={(event) => {
                              event.stopPropagation();
                              selectNode(node.node_id);
                              setPreviewNodeId(node.node_id);
                            }}
                          >
                            预览
                          </button>
                        </div>
                        <strong>{node.label}</strong>
                        <small>{workflowNodeSummary(node, draftRuntimeProfile, runSummary)}</small>
                        {nodeRuntime && (
                          <div className={`workflow-node-runtime-card is-${nodeRuntime.status}`}>
                            <div className="workflow-node-runtime-head">
                              <span className={`pill runtime-${nodeRuntime.status}`}>{runtimeStatusLabel(nodeRuntime.status)}</span>
                              <span>{nodeRuntime.status === "running" ? `${Math.round((nodeRuntime.progress ?? 0) * 100)}%` : formatRuntimeDuration(nodeRuntime.duration_ms)}</span>
                            </div>
                            <small>{nodeRuntime.detail ?? nodeRuntime.output_summary ?? "正在等待节点结果摘要。"}</small>
                            {nodeRuntime.status === "running" && (
                              <div className="workflow-node-runtime-track" aria-hidden="true">
                                <div className="workflow-node-runtime-fill" style={{ width: `${Math.max(6, (nodeRuntime.progress ?? 0) * 100)}%` }} />
                              </div>
                            )}
                          </div>
                        )}
                        {nodeInlinePreview}
                        {!reachableNodeIds.has(node.node_id) && node.inputs.length > 0 && (
                          <span className="workflow-node-inline-warning">当前未接入有效链路</span>
                        )}
                        {nodeSelected && renderNodeInlineEditor(node)}
                      </div>
                      {node.outputs.length > 0 && (
                        <div className="workflow-port-rail is-output">
                          {node.outputs.map((port) => {
                            const isPending = pendingConnection?.fromNodeId === node.node_id && pendingConnection?.fromPortId === port.port_id;
                            return (
                              <button
                                key={`${node.node_id}-${port.port_id}`}
                                type="button"
                                className={`workflow-port is-output ${isPending ? "is-pending" : ""}`}
                                style={{ top: workflowPortLocalCenter(node, port.port_id, "outputs") }}
                                aria-label={`输出端：${port.label ?? port.port_id}`}
                                title={workflowPortTitle(port)}
                                onPointerDown={(event) => event.stopPropagation()}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  beginConnection(node.node_id, port.port_id);
                                }}
                              >
                                <span>{port.label ?? "输出"}</span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
                  {!sortedNodes.length && (
                    <div className="workflow-canvas-empty">
                      <strong>当前是空白画布</strong>
                      <p>从左侧工具箱拖入 `语料输入`、分析节点和输出节点，或者点击“生成推荐骨架”快速起步。</p>
                    </div>
                  )}
                </div>
            </div>
          </div>

          <div className="workflow-minimap-shell">
            <div className="workflow-minimap-head">
              <strong>Map</strong>
              <span>{Math.round(viewport.zoom * 100)}%</span>
            </div>
            <div ref={miniMapRef} className="workflow-minimap-canvas" onPointerDown={handleMiniMapPointerDown}>
              <div ref={miniMapSurfaceRef} className="workflow-minimap-surface" style={{ width: miniMap.width, height: miniMap.height }}>
                {sortedNodes.map((node) => (
                  <div
                    key={`mini-${node.node_id}`}
                    className={`workflow-minimap-node ${selectedNode?.node_id === node.node_id ? "is-active" : ""} ${runtimeStateForNode(node) ? `is-${runtimeStateForNode(node)?.status}` : ""} ${activeRuntimeNode?.node_id === node.node_id ? "is-current" : ""}`.trim()}
                    style={{
                      left: (canvasOrigin.x + node.position.x - miniMap.originX) * miniMap.scale,
                      top: (canvasOrigin.y + node.position.y - miniMap.originY) * miniMap.scale,
                      width: Math.max(12, workflowNodeCanvasFrame(node).w * miniMap.scale),
                      height: Math.max(10, workflowNodeCanvasFrame(node).h * miniMap.scale)
                    }}
                  />
                ))}
                <div
                  ref={miniMapViewportRef}
                  className="workflow-minimap-viewport"
                  style={{
                    left: miniMapViewportRect.left,
                    top: miniMapViewportRect.top,
                    width: miniMapViewportRect.width,
                    height: miniMapViewportRect.height
                  }}
                />
              </div>
            </div>
          </div>

          {previewNodeId && previewNode && (
            <div
              className="workflow-artifact-modal-backdrop"
              role="presentation"
              onMouseDown={() => setPreviewNodeId(null)}
            >
              <section
                className="workflow-artifact-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="workflow-artifact-modal-title"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <div className="workflow-artifact-modal-head">
                  <div>
                    <span className="eyebrow">节点预览</span>
                    <h3 id="workflow-artifact-modal-title">{previewNode.label}</h3>
                  </div>
                  <Button size="small" appearance="subtle" onClick={() => setPreviewNodeId(null)}>
                    关闭
                  </Button>
                </div>
                {renderNodePreview(previewNode)}
                <ArtifactBrowser
                  title="本节点产物"
                  artifacts={previewArtifacts}
                  loading={false}
                  onLoadPreview={handleLoadArtifactPreview}
                />
              </section>
            </div>
          )}
        </section>
      </div>
      </div>
    </WorkflowWorkspace>
  );
}

function DictionariesPage({
  workbenchSelection,
  onWorkbenchSelect
}: {
  workbenchSelection?: WorkbenchSelection;
  onWorkbenchSelect?: (selection: WorkbenchSelection) => void;
}) {
  const {
    state: { snapshot, loading },
    exportDictionaryTable,
    importDictionaryTable,
    pickJsonFile,
    saveJsonFilePath,
    saveProject,
    setActivePage
  } = useWorkspace();
  const project = snapshot.current_project;
  const [activeKind, setActiveKind] = useState<DictionaryKind>("stopwords");
  const [activeTableId, setActiveTableId] = useState("");
  const [draftSet, setDraftSet] = useState<DictionarySet | null>(project ? normalizeDictionaryDraft(project.dictionary_set) : null);
  const [bulkText, setBulkText] = useState("");
  const [entrySearch, setEntrySearch] = useState("");
  const [entryPage, setEntryPage] = useState(1);
  const deferredEntrySearch = useDeferredValue(entrySearch);

  useEffect(() => {
    const nextDraft = project ? normalizeDictionaryDraft(project.dictionary_set) : null;
    setDraftSet(nextDraft);
    setBulkText("");
    setEntrySearch("");
    setEntryPage(1);
    if (!nextDraft) {
      setActiveKind("stopwords");
      setActiveTableId("");
      return;
    }
    const preferredKind = nextDraft.collections[activeKind] ? activeKind : "stopwords";
    const preferredCollection = nextDraft.collections[preferredKind] ?? nextDraft.collections.stopwords;
    setActiveKind(preferredKind);
    setActiveTableId((current) => {
      if (preferredCollection.tables.some((table) => table.id === current)) {
        return current;
      }
      return preferredCollection.tables[0]?.id ?? "";
    });
  }, [project?.id, project?.updated_at]);

  const currentCollection = draftSet ? draftSet.collections[activeKind] ?? draftSet.collections.stopwords : null;
  const currentGuide = dictionaryGuideMap[activeKind];
  const currentTable = currentCollection?.tables.find((table) => table.id === activeTableId) ?? currentCollection?.tables[0] ?? null;
  const currentTableId = currentTable?.id ?? "";

  useEffect(() => {
    if (!currentCollection) {
      return;
    }
    if (!currentCollection.tables.some((table) => table.id === activeTableId)) {
      setActiveTableId(currentCollection.tables[0]?.id ?? "");
    }
  }, [activeKind, activeTableId, currentCollection]);

  if (!project || !draftSet || !currentCollection) {
    return <EmptyState title="词表中心为空" body="请先创建或加载项目。" />;
  }

  const visibleEntries = useMemo(() => {
    const q = deferredEntrySearch.trim().toLowerCase();
    const entries = currentTable?.entries ?? [];
    if (!q) {
      return entries;
    }
    return entries.filter((entry) => {
      const haystacks = [
        entry.source,
        entry.target,
        entry.notes,
        ...(entry.tags ?? [])
      ];
      return haystacks.some((value) => String(value ?? "").toLowerCase().includes(q));
    });
  }, [currentTable?.entries, deferredEntrySearch]);
  const totalEntryPages = Math.max(1, Math.ceil(visibleEntries.length / DICTIONARY_ENTRY_PAGE_SIZE));
  const safeEntryPage = Math.min(entryPage, totalEntryPages);
  const pageStartIndex = (safeEntryPage - 1) * DICTIONARY_ENTRY_PAGE_SIZE;
  const pagedEntries = useMemo(
    () => visibleEntries.slice(pageStartIndex, pageStartIndex + DICTIONARY_ENTRY_PAGE_SIZE),
    [pageStartIndex, visibleEntries]
  );

  useEffect(() => {
    setEntryPage(1);
  }, [activeKind, currentTableId, deferredEntrySearch]);

  useEffect(() => {
    if (
      workbenchSelection?.kind !== "lexicon_kind"
      && workbenchSelection?.kind !== "lexicon_table"
      && workbenchSelection?.kind !== "lexicon_entry"
    ) {
      return;
    }
    if (workbenchSelection.dictionaryKind !== activeKind) {
      setActiveKind(workbenchSelection.dictionaryKind);
    }
    if (
      (workbenchSelection.kind === "lexicon_table" || workbenchSelection.kind === "lexicon_entry")
      && workbenchSelection.tableId !== activeTableId
    ) {
      setActiveTableId(workbenchSelection.tableId);
    }
  }, [activeKind, activeTableId, workbenchSelection]);

  useEffect(() => {
    if (entryPage > totalEntryPages) {
      setEntryPage(totalEntryPages);
    }
  }, [entryPage, totalEntryPages]);

  const mutateDraftSet = (updater: (current: DictionarySet) => DictionarySet | void) => {
    setDraftSet((current) => {
      if (!current) {
        return current;
      }
      const updated = updater(current);
      return updated || current;
    });
  };

  const updateCurrentTable = (updater: (table: DictionaryTableResource) => void) => {
    mutateDraftSet((current) => {
      const collection = current.collections[activeKind];
      const tableIndex = collection.tables.findIndex((item) => item.id === currentTableId);
      if (tableIndex < 0) {
        return current;
      }
      const table = collection.tables[tableIndex];
      const nextTable: DictionaryTableResource = {
        ...table,
        tags: [...(table.tags ?? [])],
        entries: table.entries
      };
      updater(nextTable);
      const nextTables = collection.tables.slice();
      nextTables[tableIndex] = nextTable;
      return {
        ...current,
        collections: {
          ...current.collections,
          [activeKind]: {
            ...collection,
            tables: nextTables
          }
        }
      };
    });
  };

  const updateEntry = (entryId: string, patch: Partial<DictionaryEntry>) => {
    updateCurrentTable((table) => {
      table.entries = table.entries.map((entry) => (entry.id === entryId ? { ...entry, ...patch } : entry));
    });
  };

  const addTable = () => {
    const nextTable = createEmptyDictionaryTable(activeKind);
    mutateDraftSet((current) => {
      const collection = current.collections[activeKind];
      return {
        ...current,
        collections: {
          ...current.collections,
          [activeKind]: {
            ...collection,
            tables: [nextTable, ...collection.tables]
          }
        }
      };
    });
    setActiveTableId(nextTable.id);
    onWorkbenchSelect?.({
      kind: "lexicon_table",
      projectId: project.id,
      dictionaryKind: activeKind,
      tableId: nextTable.id
    });
  };

  const duplicateCurrentTable = () => {
    if (!currentTable) {
      return;
    }
    const nextTable = {
      ...deepClone(currentTable),
      id: `${activeKind}-table-${Date.now()}`,
      name: `${currentTable.name} 副本`,
      built_in: false,
      editable: true,
      tags: [...(currentTable.tags ?? [])]
    } satisfies DictionaryTableResource;
    mutateDraftSet((current) => {
      const collection = current.collections[activeKind];
      const tables = collection.tables.slice();
      const insertIndex = Math.max(0, tables.findIndex((item) => item.id === currentTable.id) + 1);
      tables.splice(insertIndex, 0, nextTable);
      return {
        ...current,
        collections: {
          ...current.collections,
          [activeKind]: {
            ...collection,
            tables
          }
        }
      };
    });
    setActiveTableId(nextTable.id);
    onWorkbenchSelect?.({
      kind: "lexicon_table",
      projectId: project.id,
      dictionaryKind: activeKind,
      tableId: nextTable.id
    });
  };

  const deleteCurrentTable = () => {
    if (!currentTable || currentTable.built_in) {
      return;
    }
    mutateDraftSet((current) => {
      const collection = current.collections[activeKind];
      return {
        ...current,
        collections: {
          ...current.collections,
          [activeKind]: {
            ...collection,
            tables: collection.tables.filter((table) => table.id !== currentTable.id)
          }
        }
      };
    });
  };

  const saveDictionarySet = async () => {
    await saveProject({
      ...project,
      dictionary_set: draftSet
        ? {
            ...draftSet,
            sheets: {} as DictionarySet["sheets"]
          }
        : project.dictionary_set
    }, {
      refresh: false,
      actionLabel: "保存词表"
    });
  };

  const addEntry = () => {
    if (!currentTable?.editable) {
      return;
    }
    const newEntry: DictionaryEntry = {
      id: `entry-${Date.now()}`,
      source: "",
      target: "",
      tags: [],
      enabled: true,
      hits: 0,
      notes: ""
    };
    updateCurrentTable((table) => {
      table.entries = [...table.entries, newEntry];
    });
  };

  const removeEntry = (entryId: string) => {
    if (!currentTable?.editable) {
      return;
    }
    updateCurrentTable((table) => {
      table.entries = table.entries.filter((entry) => entry.id !== entryId);
    });
  };

  const appendBulkEntries = () => {
    if (!currentTable?.editable) {
      return;
    }
    const nextEntries = bulkText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => {
        const [source, target = ""] = line.split(/\t|,|=>/).map((cell) => cell.trim());
        return {
          id: `bulk-${Date.now()}-${index}`,
          source,
          target,
          tags: [],
          enabled: true,
          hits: 0,
          notes: ""
        } as DictionaryEntry;
      })
      .filter((entry) => entry.source);

    if (!nextEntries.length) {
      return;
    }

    updateCurrentTable((table) => {
      table.entries = [...table.entries, ...nextEntries];
    });
    setBulkText("");
  };

  const handleImportTable = async () => {
    const path = await pickJsonFile();
    if (!path) {
      return;
    }
    const imported = await importDictionaryTable(activeKind, path);
    if (imported?.id) {
      setActiveTableId(imported.id);
    }
  };

  const handleExportTable = async () => {
    if (!currentTable) {
      return;
    }
    const path = await saveJsonFilePath(`${activeKind}-${currentTable.id}.json`);
    if (!path) {
      return;
    }
    await exportDictionaryTable(activeKind, currentTable.id, path);
  };

  const selectDictionaryKind = (kind: DictionaryKind) => {
    setActiveKind(kind);
    const nextCollection = draftSet.collections[kind];
    setActiveTableId((current) =>
      nextCollection.tables.some((table) => table.id === current)
        ? current
        : (nextCollection.tables[0]?.id ?? "")
    );
    onWorkbenchSelect?.({
      kind: "lexicon_kind",
      projectId: project.id,
      dictionaryKind: kind
    });
  };

  const selectDictionaryTable = (table: DictionaryTableResource) => {
    setActiveTableId(table.id);
    onWorkbenchSelect?.({
      kind: "lexicon_table",
      projectId: project.id,
      dictionaryKind: activeKind,
      tableId: table.id
    });
  };

  const selectDictionaryEntry = (entry: DictionaryEntry) => {
    if (!currentTable) {
      return;
    }
    onWorkbenchSelect?.({
      kind: "lexicon_entry",
      projectId: project.id,
      dictionaryKind: activeKind,
      tableId: currentTable.id,
      entryId: entry.id
    });
  };

  const handleBindToWorkflow = () => {
    onWorkbenchSelect?.({
      kind: "workflow",
      projectId: project.id,
      workflowId: project.active_workflow_id || project.workflow_definitions[0]?.workflow_id || "active-workflow"
    });
    setActivePage("workflow");
  };

  const enabledTableCount = currentCollection.tables.filter((table) => table.enabled).length;
  const activeCollectionEntryCount = currentCollection.tables.reduce((sum, table) => {
    if (!table.enabled) {
      return sum;
    }
    return sum + table.entries.filter((entry) => entry.enabled).length;
  }, 0);
  const currentTableHits = useMemo(
    () => currentTable?.entries.reduce((sum, entry) => sum + entry.hits, 0) ?? 0,
    [currentTable]
  );
  const currentTableEditable = Boolean(currentTable?.editable);

  return (
    <LexiconWorkspace
      dictionarySet={draftSet}
      activeKind={activeKind}
      currentTable={currentTable}
      loading={loading}
      onImportTable={handleImportTable}
      onExportTable={handleExportTable}
      onAddTable={addTable}
      onDuplicateTable={duplicateCurrentTable}
      onBindToWorkflow={handleBindToWorkflow}
    >
      <Panel
        title="词库中心"
        actions={
          <div className="button-row">
            <Button appearance="subtle" onClick={addTable} disabled={loading}>
              新增资源
            </Button>
            <Button onClick={() => void handleImportTable()} disabled={loading}>
              导入 JSON
            </Button>
            <Button appearance="subtle" onClick={duplicateCurrentTable} disabled={loading || !currentTable}>
              复制当前资源
            </Button>
            <Button appearance="subtle" onClick={deleteCurrentTable} disabled={loading || !currentTable || currentTable.built_in}>
              删除当前资源
            </Button>
            <Button appearance="primary" onClick={() => void saveDictionarySet()} disabled={loading}>
              保存词表
            </Button>
          </div>
        }
      >
        <div className="dictionary-overview-grid">
          <article className="project-card dictionary-guide-card">
            <div className="run-head">
              <div>
                <p className="eyebrow">当前分类</p>
                <h4>{currentCollection.name}</h4>
              </div>
              <span className="pill">处理流程 · {currentGuide.stepLabel}</span>
            </div>
            <p className="body-copy">{currentGuide.purpose}</p>
            <ul className="feature-list">
              <li>先选分类，再从资源列表中点开单张词表进行维护，不再把整类规则混成一张大表。</li>
              <li>每张资源都可以独立启用或停用；停用后会保留在项目里，但不会参与本次运行。</li>
              <li>项目自定义和导入资源可直接编辑；内置资源默认只读，建议复制为副本后再改。</li>
            </ul>
            {activeKind === "stopwords" && (
              <p className="helper-note">停用词已拆成独立资源表，默认只打开“项目自定义”，不再一股脑把所有内置停用词全部铺在页面上。</p>
            )}
            <div className="button-row">
              <Button appearance="subtle" onClick={() => setActivePage("workflow")} disabled={loading}>
                去看节点图里的这一步
              </Button>
            </div>
          </article>
          <div className="stat-grid dictionary-stat-grid">
            <StatCard label="当前分类" value={currentCollection.name} tone="ink" />
            <StatCard label="资源表数" value={String(currentCollection.tables.length)} tone="gold" />
            <StatCard label="已启用资源" value={String(enabledTableCount)} tone="emerald" />
            <StatCard label="生效步骤" value={currentGuide.stepLabel} tone="gold" />
            <StatCard label="当前分类启用条目" value={String(activeCollectionEntryCount)} tone="emerald" />
            <StatCard label="当前资源条目" value={String(currentTable?.entries.length ?? 0)} tone="gold" />
            <StatCard label="当前资源命中" value={String(currentTableHits)} tone="rose" />
          </div>
        </div>
      </Panel>

      <Panel
        title={`${currentCollection.name} 资源列表`}
        actions={
          <div className="button-row">
            <span className="helper-note">点开某张资源表后，右侧即可单独编辑、导出或复制。</span>
          </div>
        }
      >
        <div className="dictionary-library-layout">
          <div className="dictionary-resource-list">
            {currentCollection.tables.map((table) => (
              <Button
                key={table.id}
                appearance="subtle"
                className={`dictionary-resource-card ${currentTable?.id === table.id ? "is-active" : ""}`.trim()}
                onClick={() => selectDictionaryTable(table)}
                disabled={loading}
              >
                <div className="dictionary-resource-head">
                  <strong>{table.name}</strong>
                  <span className={`pill ${table.enabled ? "" : "muted"}`.trim()}>{table.enabled ? "已启用" : "已停用"}</span>
                </div>
                <div className="dictionary-resource-meta">
                  <small>{table.entries.length} 条</small>
                  <small>{table.built_in ? "内置" : "项目内"}</small>
                  <small>{table.editable ? "可编辑" : "只读"}</small>
                </div>
                <p>{table.description || "未填写说明。"}</p>
              </Button>
            ))}
          </div>
          <article className="project-card dictionary-resource-detail">
            <div className="run-head">
              <div>
                <p className="eyebrow">当前资源</p>
                <h4>{currentTable?.name || "未选择资源"}</h4>
              </div>
              <Switch
                checked={Boolean(currentTable?.enabled)}
                onChange={(_, data) => updateCurrentTable((table) => {
                  table.enabled = Boolean(data.checked);
                })}
                disabled={loading || !currentTable}
                label="启用资源"
              />
            </div>
            <div className="dictionary-resource-form">
              <label className="field">
                <span>资源名称</span>
                <Input
                  value={currentTable?.name ?? ""}
                  onChange={(_, data) => updateCurrentTable((table) => {
                    table.name = data.value;
                  })}
                  disabled={loading || !currentTableEditable}
                />
              </label>
              <label className="field">
                <span>资源说明</span>
                <Textarea
                  rows={3}
                  value={currentTable?.description ?? ""}
                  onChange={(_, data) => updateCurrentTable((table) => {
                    table.description = data.value;
                  })}
                  disabled={loading || !currentTableEditable}
                />
              </label>
            </div>
            <ul className="feature-list">
              <li>当前资源作用于：{currentGuide.stepLabel}。</li>
              <li>左侧填写：{currentGuide.sourceHint}。</li>
              <li>右侧填写：{currentGuide.targetHint}。</li>
            </ul>
            {currentTable?.source_url ? (
              <p className="helper-note">
                来源：
                {" "}
                <a href={currentTable.source_url} target="_blank" rel="noreferrer">
                  查看公开词表来源
                </a>
              </p>
            ) : null}
            {!currentTableEditable && (
              <p className="helper-note">这张内置资源默认只读。若要改动，先点“复制当前资源”，再编辑副本。</p>
            )}
          </article>
        </div>
      </Panel>

      <Panel
        title={`${currentTable?.name ?? "当前资源"} 条目`}
        actions={
          <div className="button-row">
            <label className="search-box">
              <span>筛选条目</span>
              <Input
                contentBefore={<SearchRegular />}
                value={entrySearch}
                onChange={(_, data) => setEntrySearch(data.value)}
                placeholder="按原词、目标词、备注或标签检索"
              />
            </label>
            <Button onClick={() => void handleExportTable()} disabled={loading || !currentTable}>
              导出当前 JSON
            </Button>
            <Button appearance="subtle" onClick={addEntry} disabled={loading || !currentTableEditable}>
              新增条目
            </Button>
          </div>
        }
      >
        <div className="dictionary-editor">
          {currentTableEditable ? (
            pagedEntries.map((entry) => (
              <div className="dictionary-editor-row" key={entry.id}>
                <Input
                  value={entry.source}
                  onFocus={() => selectDictionaryEntry(entry)}
                  onChange={(_, data) => updateEntry(entry.id, { source: data.value })}
                  placeholder={currentGuide.sourceHint}
                  disabled={loading || !currentTableEditable}
                />
                <Input
                  value={entry.target ?? ""}
                  onFocus={() => selectDictionaryEntry(entry)}
                  onChange={(_, data) => updateEntry(entry.id, { target: data.value })}
                  placeholder={currentGuide.targetHint}
                  disabled={loading || !currentGuide.usesTarget || !currentTableEditable}
                />
                <Switch
                  checked={entry.enabled}
                  onChange={(_, data) => updateEntry(entry.id, { enabled: Boolean(data.checked) })}
                  disabled={loading || !currentTableEditable}
                  label="启用"
                />
                <Button appearance="subtle" onClick={() => removeEntry(entry.id)} disabled={loading || !currentTableEditable}>
                  删除
                </Button>
              </div>
            ))
          ) : (
            <Table
              columns={["source", "target", "hits", "enabled"]}
              rows={pagedEntries.map((entry) => ({
                source: entry.source || "—",
                target: entry.target || "—",
                hits: entry.hits,
                enabled: entry.enabled ? "启用" : "停用"
              }))}
            />
          )}
        </div>
        <div className="button-row dictionary-page-nav">
          <span className="helper-note">
            当前显示第 {safeEntryPage} / {totalEntryPages} 页，
            第 {visibleEntries.length ? pageStartIndex + 1 : 0} - {Math.min(pageStartIndex + pagedEntries.length, visibleEntries.length)} 条，
            每页 {DICTIONARY_ENTRY_PAGE_SIZE} 条。
          </span>
          <Button appearance="subtle" icon={<ChevronLeftRegular />} onClick={() => setEntryPage((current) => Math.max(1, current - 1))} disabled={safeEntryPage <= 1}>
            上一页
          </Button>
          <Button appearance="subtle" icon={<ChevronRightRegular />} onClick={() => setEntryPage((current) => Math.min(totalEntryPages, current + 1))} disabled={safeEntryPage >= totalEntryPages}>
            下一页
          </Button>
        </div>
        {!!entrySearch.trim() && (
          <p className="helper-note">当前按 “{entrySearch.trim()}” 显示 {visibleEntries.length} / {currentTable?.entries.length ?? 0} 条。</p>
        )}
        <label className="field">
          <span>批量粘贴</span>
          <Textarea
            rows={5}
            value={bulkText}
            onChange={(_, data) => setBulkText(data.value)}
            placeholder={currentGuide.bulkExample}
            disabled={loading || !currentTableEditable}
          />
        </label>
        <p className="helper-note">
          支持逐行粘贴，格式可以用“source,target”、“source to target”或只写左侧词项。
        </p>
        <div className="button-row">
          <Button onClick={appendBulkEntries} disabled={loading || !currentTableEditable || !bulkText.trim()}>
            追加批量条目
          </Button>
        </div>
      </Panel>
    </LexiconWorkspace>
  );
}

function SettingsPage() {
  const {
    state: { snapshot, uiScale },
    setUiScale
  } = useWorkspace();
  const project = snapshot.current_project;
  const scalePresets = [0.8, 0.9, 1, 1.1, 1.2];
  const scalePercent = Math.round(uiScale * 100);
  const applyScaleStep = (delta: number) => {
    setUiScale(uiScale + delta);
  };

  return (
    <>
      <Panel
        title="界面缩放"
        actions={(
          <Button
            appearance="subtle"
            onClick={() => setUiScale(1)}
            disabled={Math.abs(uiScale - 1) < 0.001}
          >
            恢复 100%
          </Button>
        )}
      >
        <div className="settings-scale-grid">
          <div className="settings-scale-summary">
            <strong>{scalePercent}%</strong>
            <p className="body-copy">
              调整整个工作台的显示密度。这个比例会保存在当前设备上，重新打开应用后也会继续使用。
            </p>
          </div>
          <div className="settings-scale-actions">
            <div className="tab-row">
              <Button
                onClick={() => applyScaleStep(-0.05)}
                disabled={uiScale <= 0.8}
              >
                缩小 5%
              </Button>
              <Button
                onClick={() => applyScaleStep(0.05)}
                disabled={uiScale >= 1.2}
              >
                放大 5%
              </Button>
            </div>
            <TabList
              className="tab-row"
              selectedValue={String(uiScale)}
              onTabSelect={(_, data) => setUiScale(Number(data.value))}
            >
              {scalePresets.map((preset) => (
                <Tab
                  key={preset}
                  value={String(preset)}
                >
                  {Math.round(preset * 100)}%
                </Tab>
              ))}
            </TabList>
          </div>
        </div>
      </Panel>
      {!project ? (
        <EmptyState title="尚未初始化项目设置" body="创建项目后会自动加载默认语言、导出格式等项目级设置。" />
      ) : (
        <>
      <div className="stat-grid">
        <StatCard label="默认语言" value={project.settings.default_language} tone="ink" />
        <StatCard label="主题" value={project.settings.preferred_theme} tone="gold" />
        <StatCard label="自动保存" value={project.settings.enable_auto_save ? "已启用" : "关闭"} tone="emerald" />
        <StatCard label="更新检查" value={project.settings.enable_update_check ? "开启" : "关闭"} tone="rose" />
      </div>
      <Panel title="默认导出格式">
        <div className="tab-row">
          {project.settings.default_export_formats.map((format) => (
            <span className="pill" key={format}>
              {format.toUpperCase()}
            </span>
          ))}
        </div>
        <p className="body-copy">
          V1 采用本地优先策略，默认不上传文本。后续可在这里接入更新检查、路径偏好和性能策略。
        </p>
      </Panel>
        </>
      )}
    </>
  );
}

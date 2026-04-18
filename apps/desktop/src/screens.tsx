import { useDeferredValue, useEffect, useMemo, useState } from "react";
import type {
  CorpusItem,
  DictionaryEntry,
  DictionaryKind,
  DictionarySet,
  FieldMappingRule,
  ImportTemplate,
  OutputBundleId,
  PipelineDefinition,
  PipelineRecipeId,
  PipelineStepId,
  PageId,
  RunScopeDefinition
} from "@textflow/shared-types";
import { sourceProfileImportTemplates, sourceProfiles } from "@textflow/shared-types";
import type { ImportProjectFilesResponse } from "./bridge/desktopBridge";
import { useWorkspace } from "./store/workspaceStore";
import {
  AuditTable,
  DictionaryTable,
  DocumentPreview,
  EmptyState,
  FrequencyTable,
  KeywordPanel,
  LineChart,
  Meta,
  Panel,
  ScatterChart,
  StatCard,
  Table,
  TopicPanel
} from "./ui";
import type { DocumentPreviewMode } from "./ui";

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

const pipelineStepMeta: Array<{ id: PipelineStepId; title: string; description: string }> = [
  { id: "ingestion", title: "读取资料", description: "按导入模板识别字段，并拼出主文本。" },
  { id: "cleaning", title: "基础清洗", description: "去掉网页标签、网址、空白和杂乱标点。" },
  { id: "normalization", title: "统一写法", description: "把数字、时间和自定义规则统一成同一种写法。" },
  { id: "tokenization", title: "切词", description: "中英文混合切词，并尽量保留短语。" },
  { id: "dictionary_application", title: "套用词表", description: "处理停用词、同义词、标准词和排除词。" },
  { id: "filtering", title: "过滤噪声", description: "去掉太短、太少或无意义的词。" },
  { id: "analysis", title: "生成分析", description: "输出词频、共现、YAKE 关键词、NMF 主题和聚类。" },
  { id: "export", title: "保存结果", description: "写出表格、图表和 HTML 报告。" }
];

const mandatoryPipelineSteps: PipelineStepId[] = ["ingestion", "tokenization", "analysis", "export"];
const optionalPipelineSteps: PipelineStepId[] = ["cleaning", "normalization", "dictionary_application", "filtering"];
const fixedPipelineOrder = pipelineStepMeta.map((step) => step.id);
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
  ["keep_original_order", "保留原始顺序"]
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
    title: "NMF 主题",
    output: "影响：机构 × 主题、主题标签摘要",
    description: "把一组经常共同出现的词归成主题，用来概括机构、年份或来源的关注方向。",
    params: ["主题数量"]
  },
  {
    title: "共现与聚类",
    output: "影响：共现表、关键词聚类、文档聚类图",
    description: "用窗口共现和聚类把词与文档的关联结构展示出来，方便找热点和分组。",
    params: ["共现窗口", "最小共现次数", "关键词聚类数", "文档聚类数"]
  }
] as const;
const runScopeModeOptions: Array<{ id: RunScopeDefinition["mode"]; title: string; description: string }> = [
  { id: "all_documents", title: "全部资料", description: "直接处理项目里的全部文档，适合第一次跑通全流程。" },
  { id: "filtered_subset", title: "按条件筛选", description: "只处理符合来源、年份、机构或标签条件的一部分资料。" },
  { id: "selected_documents", title: "手动点选文档", description: "从项目语料里勾选少量文档做试跑或抽样检查。" }
];
const recipeCards: Array<{
  id: PipelineRecipeId;
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
const sampleProjectName = "新能源与生成式语料示例项目";
const sampleJourneySteps = [
  "先打开示例项目，在“导入资料”里抽查 3 个来源文件和导入后的文档。",
  "再到“词表规则”看 8 张词表分别在切词、统一写法和套用词表时怎么生效。",
  "然后到“处理与分析”直接运行默认流程，不需要自己拼步骤顺序。",
  "最后到“结果导出”查看词频、共现、聚类和 HTML 报告，再导出 `.tfproj` 项目包。"
] as const;
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

export const pageMeta: Record<PageId, { title: string; headline: string; tag: string }> = {
  home: { title: "开始", headline: "先选一个项目，或新建一个项目", tag: "开始" },
  project: { title: "项目概览", headline: "查看项目规模、来源文件和历史运行", tag: "概览" },
  data: { title: "导入资料", headline: "把文件导入进来，并确认字段对应关系", tag: "导入" },
  pipeline: { title: "处理与分析", headline: "确认处理步骤，然后开始运行", tag: "处理" },
  dictionaries: { title: "词表规则", headline: "维护停用词、同义词和标准词规则", tag: "词表" },
  analysis: { title: "分析详情", headline: "查看词频、共现、YAKE 关键词和 NMF 主题", tag: "分析" },
  results: { title: "结果导出", headline: "查看本次运行，并导出需要的结果", tag: "结果" },
  report: { title: "报告预览", headline: "预览 HTML 报告结构和摘要", tag: "报告" },
  settings: { title: "设置", headline: "查看默认偏好和本地配置", tag: "设置" }
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

function joinFsPath(basePath: string, relativePath: string): string {
  const normalizedBase = basePath.replace(/[\\/]+$/, "");
  const normalizedRelative = relativePath.replace(/^[\\/]+/, "").replace(/\//g, "\\");
  return `${normalizedBase}\\${normalizedRelative}`;
}

function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).at(-1) ?? path;
}

function normalizePipelineDraft(pipeline: PipelineDefinition): PipelineDefinition {
  const enabledOptionalSteps = optionalPipelineSteps.filter((step) => pipeline.enabled_steps.includes(step));
  return {
    ...pipeline,
    analysis: {
      ...pipeline.analysis,
      topic_model_k: pipeline.analysis.topic_model_k ?? pipeline.analysis.keyword_cluster_k ?? 4
    },
    export: {
      ...pipeline.export,
      chart_dpi: pipeline.export.chart_dpi ?? 320,
      watermark_enabled: pipeline.export.watermark_enabled ?? false,
      watermark_text: pipeline.export.watermark_text ?? "TextFlow Studio"
    },
    run_scope: {
      mode: pipeline.run_scope?.mode ?? "all_documents",
      source_values: [...(pipeline.run_scope?.source_values ?? [])],
      institution_values: [...(pipeline.run_scope?.institution_values ?? [])],
      category_values: [...(pipeline.run_scope?.category_values ?? [])],
      year_from: pipeline.run_scope?.year_from ?? null,
      year_to: pipeline.run_scope?.year_to ?? null,
      selected_doc_ids: [...(pipeline.run_scope?.selected_doc_ids ?? [])]
    },
    recipe_id: pipeline.recipe_id ?? "standard_analysis",
    output_bundle_id: pipeline.output_bundle_id ?? "full_report",
    enabled_steps: [...mandatoryPipelineSteps, ...enabledOptionalSteps],
    execution_order: [...fixedPipelineOrder]
  };
}

function applyRecipePreset(pipeline: PipelineDefinition, recipeId: PipelineRecipeId): PipelineDefinition {
  const next = normalizePipelineDraft(deepClone(pipeline));
  next.recipe_id = recipeId;

  if (recipeId === "standard_analysis") {
    next.enabled_steps = [...mandatoryPipelineSteps, ...optionalPipelineSteps];
    next.normalization.convert_traditional_to_simplified = false;
    next.normalization.normalize_time_expr = false;
    next.filtering.min_term_frequency = 1;
    next.analysis.top_k_per_doc = 10;
    next.analysis.top_k_project = 100;
    next.analysis.topic_model_k = 4;
    next.analysis.keyword_cluster_k = 4;
    next.analysis.document_cluster_k = 4;
    return normalizePipelineDraft(next);
  }

  if (recipeId === "keyword_topic") {
    next.enabled_steps = [...mandatoryPipelineSteps, ...optionalPipelineSteps];
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
    return normalizePipelineDraft(next);
  }

  if (recipeId === "trend_scan") {
    next.enabled_steps = [...mandatoryPipelineSteps, "cleaning", "dictionary_application", "filtering"];
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
    return normalizePipelineDraft(next);
  }

  return normalizePipelineDraft(next);
}

function applyOutputBundlePreset(pipeline: PipelineDefinition, bundleId: OutputBundleId): PipelineDefinition {
  const next = normalizePipelineDraft(deepClone(pipeline));
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

  return normalizePipelineDraft(next);
}

function outputBundleSummary(exportParams: PipelineDefinition["export"]): string {
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

export function PageView({ page }: { page: PageId }) {
  switch (page) {
    case "home":
      return <HomePage />;
    case "project":
      return <ProjectPage />;
    case "data":
      return <DataPage />;
    case "pipeline":
      return <PipelinePage />;
    case "dictionaries":
      return <DictionariesPage />;
    case "analysis":
      return <AnalysisPage />;
    case "results":
      return <ResultsPage />;
    case "report":
      return <ReportPage />;
    case "settings":
      return <SettingsPage />;
    default:
      return null;
  }
}

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
      <Panel className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">第 1 步</p>
          <h3>先新建一个项目，或打开仓库里的现有项目。</h3>
          <p>TextFlow 会把语料、词表、流程和结果都收进一个 `.tfproj` 项目包里，方便继续编辑、备份和交接。</p>
          <ul className="feature-list">
            <li>从零开始时，先新建空白项目，再去“导入资料”。</li>
            <li>接着别人做过的项目时，直接导入 `.tfproj` 项目包。</li>
            <li>第一次上手时，建议先打开示例项目，看完整流程怎么跑一遍。</li>
          </ul>
        </div>
        <div className="hero-actions">
          <label className="field">
            <span>项目名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="field">
            <span>项目描述</span>
            <textarea value={description} rows={4} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="button-row hero-action-grid">
            <button
              type="button"
              className="toolbar-button accent"
              onClick={() => void createProject(name, description)}
              disabled={loading || !name.trim()}
            >
              新建空白项目
            </button>
            <button type="button" className="toolbar-button" onClick={() => void handleImportPackage()} disabled={loading}>
              导入 .tfproj 项目包
            </button>
            <button
              type="button"
              className="toolbar-button"
              onClick={() => sampleProject ? void openProjectAndGo(sampleProject.id, "data") : undefined}
              disabled={loading || !sampleProject}
            >
              打开示例项目
            </button>
            <button
              type="button"
              className="toolbar-button ghost"
              onClick={() => void handleExportPackage()}
              disabled={loading || !currentProject}
            >
              导出当前项目包
            </button>
          </div>
          <p className="helper-note">
            {currentProject
              ? `当前正在处理：${currentProject.name}`
              : "还没有打开项目。新建或导入后，这里会自动接着往下走。"}
          </p>
        </div>
      </Panel>

      <div className="two-column home-overview-grid">
        <Panel title="仓库内项目" actions={<span className="pill">共 {snapshot.recent_projects.length} 个</span>}>
          <label className="search-box">
            <span>按项目名、说明或路径筛选</span>
            <input
              value={projectQuery}
              onChange={(event) => setProjectQuery(event.target.value)}
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
                    <button type="button" className="toolbar-button" onClick={() => void openProject(project.id)} disabled={loading}>
                      打开
                    </button>
                    <button
                      type="button"
                      className="toolbar-button ghost"
                      onClick={() => void duplicateProject(project.id, `${project.name} 副本`)}
                      disabled={loading}
                    >
                      复制
                    </button>
                    <button
                      type="button"
                      className="toolbar-button danger ghost"
                      onClick={() => void handleDeleteProject(project.id, project.name)}
                      disabled={loading}
                    >
                      删除
                    </button>
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

        <div className="stack-list">
          <Panel title="第一次使用可以这样走">
            <ul className="feature-list">
              {sampleJourneySteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
            {sampleProject && (
              <div className="button-row">
                <button type="button" className="toolbar-button" onClick={() => void openProjectAndGo(sampleProject.id, "data")} disabled={loading}>
                  打开示例并看资料
                </button>
                <button type="button" className="toolbar-button ghost" onClick={() => void openProjectAndGo(sampleProject.id, "dictionaries")} disabled={loading}>
                  打开示例并看词表
                </button>
                <button type="button" className="toolbar-button ghost" onClick={() => void openProjectAndGo(sampleProject.id, "pipeline")} disabled={loading}>
                  打开示例并看流程
                </button>
              </div>
            )}
          </Panel>

          <Panel title="项目包说明">
            <ul className="feature-list">
              <li>`.tfproj` 是单文件项目包，适合发同事、备份和归档。</li>
              <li>“仓库内项目”显示的是当前工作区里已经存在的项目，不只是最近打开过的项目。</li>
              <li>如果项目很多，先用上面的筛选框，再决定打开、复制或删除。</li>
            </ul>
          </Panel>
        </div>
      </div>
    </>
  );
}

function ProjectPage() {
  const {
    state: { snapshot }
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="还没有项目" body="先在首页创建或打开一个 `.tfproj` 项目。" />;
  }

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

        <Panel title="源文件与最近运行">
          <ul className="micro-list">
            {project.source_files.slice(0, 5).map((source) => (
              <li key={source.id}>
                {source.name} · {source.row_count} 行 · {source.relative_path}
              </li>
            ))}
          </ul>
          <div className="stack-list">
            {project.run_history.slice().reverse().map((run) => (
              <article className="run-card" key={run.run_id}>
                <div className="run-head">
                  <strong>{run.run_id}</strong>
                  <span className={`badge ${run.status}`}>{run.status}</span>
                </div>
                <p>
                  {run.started_at} → {run.ended_at ?? "处理中"}
                </p>
                <p className="muted">{run.run_scope_summary ?? "处理对象：项目内全部资料"}</p>
                <ul className="micro-list">
                  {run.logs.map((entry) => (
                    <li key={`${run.run_id}-${entry.step}-${entry.message}`}>{entry.step}: {entry.message}</li>
                  ))}
                </ul>
              </article>
            ))}
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

function DataPage() {
  const {
    state: { snapshot, loading },
    deleteCorpusDocument,
    pickImportFiles,
    importProjectFiles,
    saveProject,
    updateCorpusDocument
  } = useWorkspace();
  const project = snapshot.current_project;
  const [search, setSearch] = useState("");
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
  }, [project?.id, project?.updated_at]);

  const documents = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase();
    if (!q) {
      return snapshot.corpus;
    }
    return snapshot.corpus.filter((item) =>
      [item.title, item.raw_text, item.institution, item.source, item.category_or_tag]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q))
    );
  }, [deferredSearch, snapshot.corpus]);

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
    <>
      <Panel
        title="第 2 步：导入资料"
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button" onClick={() => void handleSaveTemplate()} disabled={!canSaveTemplate}>
              保存模板
            </button>
            <button
              type="button"
              className="toolbar-button ghost"
              onClick={() => setDraftTemplate(buildTemplateFromProfile(draftTemplate, draftTemplate.source_profile))}
              disabled={loading}
            >
              套用预设
            </button>
            <button type="button" className="toolbar-button ghost" onClick={() => setShowTemplateEditor((current) => !current)}>
              {showTemplateEditor ? "收起高级字段设置" : "展开高级字段设置"}
            </button>
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
            <input
              value={draftTemplate.name}
              onChange={(event) => setDraftTemplate({ ...draftTemplate, name: event.target.value })}
            />
          </label>
          <label className="field">
            <span>资料类型预设</span>
            <select
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
            </select>
          </label>
          <label className="field">
            <span>正文来源字段</span>
            <input
              value={draftTemplate.text_build.fields.join(", ")}
              onChange={(event) =>
                setDraftTemplate({
                  ...draftTemplate,
                  text_build: {
                    ...draftTemplate.text_build,
                    fields: event.target.value.split(",").map((field) => field.trim()).filter(Boolean)
                  }
                })
              }
              placeholder="title, abstract"
            />
          </label>
          <label className="field">
            <span>说明</span>
            <input
              value={draftTemplate.description ?? ""}
              onChange={(event) => setDraftTemplate({ ...draftTemplate, description: event.target.value })}
            />
          </label>
        </div>

        <label className="field">
          <span>待导入文件</span>
          <textarea
            rows={4}
            value={filePathsText}
            onChange={(event) => setFilePathsText(event.target.value)}
            placeholder={"每行一个文件路径，例如：\nC:\\data\\articles.xlsx\nC:\\data\\notes.txt"}
          />
        </label>

        <div className="button-row">
          <button type="button" className="toolbar-button ghost" onClick={() => void handlePickFiles()} disabled={loading}>
            选择文件
          </button>
          <button type="button" className="toolbar-button accent" onClick={() => void handleImport()} disabled={!canImport}>
            开始导入
          </button>
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
                <input
                  value={draftTemplate.text_build.delimiter}
                  onChange={(event) =>
                    setDraftTemplate({
                      ...draftTemplate,
                      text_build: {
                        ...draftTemplate.text_build,
                        delimiter: event.target.value
                      }
                    })
                  }
                />
              </label>
            </div>
            <div className="mapping-editor">
              {draftTemplate.field_mappings.map((rule, index) => (
                <div className="mapping-editor-row" key={`${index}-${rule.source_field}-${rule.target_field}`}>
                  <input
                    value={rule.source_field}
                    onChange={(event) => updateMapping(index, { source_field: event.target.value })}
                    placeholder="源字段名"
                  />
                  <select
                    value={rule.target_field}
                    onChange={(event) => updateMapping(index, { target_field: event.target.value as FieldMappingRule["target_field"] })}
                  >
                    {mappingTargetOptions.map((target) => (
                      <option key={target} value={target}>
                        {target}
                      </option>
                    ))}
                  </select>
                  <input
                    value={rule.aliases?.join(", ") ?? ""}
                    onChange={(event) =>
                      updateMapping(index, {
                        aliases: event.target.value
                          .split(",")
                          .map((alias) => alias.trim())
                          .filter(Boolean)
                      })
                    }
                    placeholder="别名，逗号分隔"
                  />
                  <label className="switch-row compact">
                    <input
                      type="checkbox"
                      checked={rule.required ?? false}
                      onChange={(event) => updateMapping(index, { required: event.target.checked })}
                    />
                    <span>必填</span>
                  </label>
                  <button type="button" className="toolbar-button ghost" onClick={() => removeMapping(index)}>
                    删除
                  </button>
                </div>
              ))}
            </div>
            <div className="button-row">
              <button
                type="button"
                className="toolbar-button ghost"
                onClick={() => setDraftTemplate({ ...draftTemplate, field_mappings: [...draftTemplate.field_mappings, emptyMappingRule()] })}
                disabled={loading}
              >
                新增映射
              </button>
            </div>
          </div>
        ) : null}
      </Panel>

      <div className="corpus-review-grid">
        <Panel
          title="已导入语料库"
          actions={
            <label className="search-box">
              <span>检索标题 / 文本 / 元数据</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="例如：智能制造 / patent / 复旦大学" />
            </label>
          }
        >
          {documents.length ? (
            <div className="corpus-browser">
              {documents.map((item) => (
                <button
                  key={item.doc_id}
                  type="button"
                  className={`corpus-row ${selectedDocId === item.doc_id ? "is-active" : ""}`}
                  onClick={() => handleSelectDocument(item)}
                >
                  <div className="run-head">
                    <strong>{item.title || item.doc_id}</strong>
                    <span className="pill">{item.year ?? "未标年"}</span>
                  </div>
                  <p className="muted">{item.institution ?? item.source ?? "未填写来源信息"}</p>
                  <p className="body-copy">{previewSummary(item)}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="没有匹配文档" body="换个关键词试试，或先导入文件。" />
          )}
        </Panel>

        <Panel
          title="文档审查与编辑"
          actions={
            <div className="button-row">
              <button type="button" className="toolbar-button" onClick={() => void handleSaveDocument()} disabled={!canSaveDocument}>
                保存文档
              </button>
              <button type="button" className="toolbar-button ghost" onClick={() => void handleDeleteDocument()} disabled={loading || !draftDocument}>
                删除文档
              </button>
            </div>
          }
        >
          {selectedDoc && draftDocument ? (
            <div className="document-workbench">
              <DocumentPreview doc={draftDocument} mode={previewMode} onModeChange={setPreviewMode} />

              <div className="settings-grid document-form-grid">
                <label className="field">
                  <span>标题</span>
                  <input
                    value={draftDocument.title}
                    onChange={(event) => setDraftDocument({ ...draftDocument, title: event.target.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>年份</span>
                  <input
                    value={draftDocument.year ?? ""}
                    onChange={(event) =>
                      setDraftDocument({
                        ...draftDocument,
                        year: event.target.value.trim() ? Number(event.target.value) : null
                      })
                    }
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>机构</span>
                  <input
                    value={draftDocument.institution ?? ""}
                    onChange={(event) => setDraftDocument({ ...draftDocument, institution: event.target.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>来源</span>
                  <input
                    value={draftDocument.source ?? ""}
                    onChange={(event) => setDraftDocument({ ...draftDocument, source: event.target.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>作者</span>
                  <input
                    value={draftDocument.author ?? ""}
                    onChange={(event) => setDraftDocument({ ...draftDocument, author: event.target.value })}
                    disabled={loading}
                  />
                </label>
                <label className="field">
                  <span>分类 / 标签</span>
                  <input
                    value={draftDocument.category_or_tag ?? ""}
                    onChange={(event) => setDraftDocument({ ...draftDocument, category_or_tag: event.target.value })}
                    disabled={loading}
                  />
                </label>
              </div>

              <label className="field">
                <span>正文</span>
                <textarea
                  rows={10}
                  value={draftDocument.raw_text}
                  onChange={(event) => setDraftDocument({ ...draftDocument, raw_text: event.target.value })}
                  disabled={loading}
                />
              </label>

              <div className="status-panel">
                <strong>来源追踪</strong>
                <p>
                  文件：{String(draftDocument.extra_metadata["_source_file_name"] ?? "—")} · 行号：
                  {String(draftDocument.extra_metadata["_source_row_index"] ?? "—")}
                </p>
                <p>保存后会清空旧的清洗/切词结果，等你重新运行处理流程。</p>
              </div>
            </div>
          ) : (
            <EmptyState title="暂无文档" body="导入后就能在这里逐篇查看、修改和删除。" />
          )}
        </Panel>
      </div>
    </>
  );
}

function PipelinePageLegacyOld() {
  const {
    state: { snapshot, loading },
    saveProject,
    runPipeline
  } = useWorkspace();
  const project = snapshot.current_project;
  const [draftPipeline, setDraftPipeline] = useState<PipelineDefinition | null>(
    project ? normalizePipelineDraft(deepClone(project.pipeline)) : null
  );

  useEffect(() => {
    setDraftPipeline(project ? normalizePipelineDraft(deepClone(project.pipeline)) : null);
  }, [project?.id, project?.updated_at]);

  if (!project || !draftPipeline) {
    return <EmptyState title="流程配置待初始化" body="请先建立项目工作区。" />;
  }

  const latestRun = project.run_history.at(-1);
  const visibleConfigSteps = fixedPipelineOrder.filter((step) =>
    mandatoryPipelineSteps.includes(step) || draftPipeline.enabled_steps.includes(step)
  );
  const stepIsEnabled = (step: PipelineStepId) => mandatoryPipelineSteps.includes(step) || draftPipeline.enabled_steps.includes(step);
  const updateSection = <K extends "cleaning" | "normalization" | "tokenization" | "dictionary" | "filtering" | "analysis" | "export">(
    section: K,
    patch: Partial<PipelineDefinition[K]>
  ) => {
    setDraftPipeline({
      ...draftPipeline,
      [section]: {
        ...draftPipeline[section],
        ...patch
      }
    });
  };
  const renderBooleanToggles = (
    section: "cleaning" | "normalization" | "tokenization" | "dictionary" | "filtering" | "export",
    items: readonly (readonly [string, string])[]
  ) => {
    const values = draftPipeline[section] as unknown as Record<string, unknown>;
    return (
      <div className="toggle-grid">
        {items.map(([key, label]) => (
          <label key={key} className="switch-row">
            <input
              type="checkbox"
              checked={Boolean(values[key])}
              onChange={(event) => updateSection(section, { [key]: event.target.checked } as Partial<PipelineDefinition[typeof section]>)}
              disabled={loading}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
    );
  };

  const toggleOptionalStep = (step: PipelineStepId) => {
    if (!optionalPipelineSteps.includes(step)) {
      return;
    }
    const nextEnabledSteps = draftPipeline.enabled_steps.includes(step)
      ? draftPipeline.enabled_steps.filter((item) => item !== step)
      : [...draftPipeline.enabled_steps, step];
    setDraftPipeline(normalizePipelineDraft({ ...draftPipeline, enabled_steps: nextEnabledSteps }));
  };

  const savePipeline = async () => saveProject({ ...project, pipeline: normalizePipelineDraft(draftPipeline) });
  const runCurrentPipeline = async () => {
    const saved = await savePipeline();
    if (saved) {
      await runPipeline();
    }
  };

  const renderStepPanel = (stepId: PipelineStepId) => {
    if (stepId === "ingestion") {
      return <Panel title="读取资料"><p className="body-copy">字段映射和主文本拼接在“导入资料”页设置。这一步固定执行，用来读取当前项目里的语料。</p></Panel>;
    }
    if (stepId === "cleaning") {
      return <Panel title="基础清洗">{renderBooleanToggles("cleaning", cleaningToggleItems)}</Panel>;
    }
    if (stepId === "normalization") {
      return (
        <Panel title="统一写法">
          {renderBooleanToggles("normalization", normalizationToggleItems)}
          <label className="field">
            <span>Regex 优先策略</span>
            <select
              value={draftPipeline.normalization.regex_rule_priority}
              onChange={(event) => updateSection("normalization", { regex_rule_priority: event.target.value as PipelineDefinition["normalization"]["regex_rule_priority"] })}
              disabled={loading}
            >
              <option value="rule_order">按规则顺序</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }
    if (stepId === "tokenization") {
      return (
        <Panel title="切词">
          <div className="settings-grid">
            <label className="field">
              <span>语言模式</span>
              <select
                value={draftPipeline.tokenization.language_mode}
                onChange={(event) => updateSection("tokenization", { language_mode: event.target.value as PipelineDefinition["tokenization"]["language_mode"] })}
                disabled={loading}
              >
                <option value="auto">自动判断</option>
                <option value="zh">中文</option>
                <option value="en">英文</option>
                <option value="mixed">中英混合</option>
              </select>
            </label>
            <label className="field">
              <span>切词前最短长度</span>
              <input type="number" value={draftPipeline.tokenization.min_token_length_before_filter} onChange={(event) => updateSection("tokenization", { min_token_length_before_filter: Number(event.target.value) })} disabled={loading} />
            </label>
          </div>
          {renderBooleanToggles("tokenization", tokenizationToggleItems)}
        </Panel>
      );
    }
    if (stepId === "dictionary_application") {
      return (
        <Panel title="套用词表">
          {renderBooleanToggles("dictionary", dictionaryToggleItems)}
          <label className="field">
            <span>冲突处理</span>
            <select
              value={draftPipeline.dictionary.conflict_resolution}
              onChange={(event) => updateSection("dictionary", { conflict_resolution: event.target.value as PipelineDefinition["dictionary"]["conflict_resolution"] })}
              disabled={loading}
            >
              <option value="priority">按词表优先级</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }
    if (stepId === "filtering") {
      return (
        <Panel title="过滤噪声">
          {renderBooleanToggles("filtering", filteringToggleItems)}
          <div className="settings-grid">
            <label className="field">
              <span>最短 token 长度</span>
              <input type="number" value={draftPipeline.filtering.min_token_length} onChange={(event) => updateSection("filtering", { min_token_length: Number(event.target.value) })} disabled={loading} />
            </label>
            <label className="field">
              <span>最小词频</span>
              <input type="number" value={draftPipeline.filtering.min_term_frequency} onChange={(event) => updateSection("filtering", { min_term_frequency: Number(event.target.value) })} disabled={loading} />
            </label>
          </div>
        </Panel>
      );
    }
    if (stepId === "analysis") {
      return (
        <Panel title="生成分析">
          <div className="analysis-method-grid">
            {analysisMethodCards.map((card) => (
              <article className="analysis-method-card" key={card.title}>
                <div className="run-head">
                  <strong>{card.title}</strong>
                  <span className="pill">{card.output}</span>
                </div>
                <p className="body-copy">{card.description}</p>
                <p className="muted">对应参数：{card.params.join("、")}</p>
              </article>
            ))}
          </div>

          <div className="analysis-config-list">
            <section className="analysis-config-group">
              <div className="analysis-config-head">
                <h4>词频与共现</h4>
                <p className="body-copy">这组参数控制高频词数量和词之间“算作一起出现”的窗口范围。</p>
              </div>
              <div className="settings-grid">
                <label className="field">
                  <span>高频词 Top N</span>
                  <input type="number" value={draftPipeline.analysis.top_n} onChange={(event) => updateSection("analysis", { top_n: Number(event.target.value) })} disabled={loading} />
                  <small>控制词频表和概览卡片里最多展示多少个高频词。</small>
                </label>
                <label className="field">
                  <span>共现窗口</span>
                  <input type="number" value={draftPipeline.analysis.cooccurrence_window} onChange={(event) => updateSection("analysis", { cooccurrence_window: Number(event.target.value) })} disabled={loading} />
                  <small>一个词周围向前向后看多少个词，决定“共现”判断范围。</small>
                </label>
                <label className="field">
                  <span>最小共现次数</span>
                  <input type="number" value={draftPipeline.analysis.min_cooccurrence} onChange={(event) => updateSection("analysis", { min_cooccurrence: Number(event.target.value) })} disabled={loading} />
                  <small>低于这个次数的词对会被视为太偶然，不进入结果表。</small>
                </label>
              </div>
            </section>

            <section className="analysis-config-group">
              <div className="analysis-config-head">
                <h4>TF-IDF 特征词</h4>
                <p className="body-copy">这是后续 YAKE 关键词、主题建模和关键词聚类的基础词项池。</p>
              </div>
              <div className="settings-grid">
                <label className="field">
                  <span>特征词数量</span>
                  <input
                    value={String(draftPipeline.analysis.feature_term_count)}
                    onChange={(event) =>
                      updateSection("analysis", {
                        feature_term_count: event.target.value.trim().toLowerCase() === "all" ? "all" : Number(event.target.value)
                      })
                    }
                    placeholder="all 或数字"
                    disabled={loading}
                  />
                  <small>数量越大，覆盖面更广；数量越小，聚类和主题会更集中。</small>
                </label>
              </div>
            </section>

            <section className="analysis-config-group">
              <div className="analysis-config-head">
                <h4>YAKE 关键词</h4>
                <p className="body-copy">YAKE 会按每篇文档抽取关键词，再汇总出项目级关键词榜。</p>
              </div>
              <div className="settings-grid">
                <label className="field">
                  <span>每篇文档关键词数</span>
                  <input type="number" value={draftPipeline.analysis.top_k_per_doc} onChange={(event) => updateSection("analysis", { top_k_per_doc: Number(event.target.value) })} disabled={loading} />
                  <small>每篇文档最多保留多少个关键词，影响文档详情和机构 × 关键词统计。</small>
                </label>
                <label className="field">
                  <span>项目级关键词数</span>
                  <input type="number" value={draftPipeline.analysis.top_k_project} onChange={(event) => updateSection("analysis", { top_k_project: Number(event.target.value) })} disabled={loading} />
                  <small>汇总全项目时最多保留多少个关键词，适合控制结果页长度。</small>
                </label>
              </div>
            </section>

            <section className="analysis-config-group">
              <div className="analysis-config-head">
                <h4>NMF 主题与聚类</h4>
                <p className="body-copy">NMF 用来生成“机构 × 主题”，关键词聚类和文档聚类则负责看词和文档的分组结构。</p>
              </div>
              <div className="settings-grid">
                <label className="field">
                  <span>主题数量</span>
                  <input type="number" value={draftPipeline.analysis.topic_model_k} onChange={(event) => updateSection("analysis", { topic_model_k: Number(event.target.value) })} disabled={loading} />
                  <small>NMF 最多分出多少个主题，建议从 4 到 8 开始尝试。</small>
                </label>
                <label className="field">
                  <span>关键词聚类数</span>
                  <input type="number" value={draftPipeline.analysis.keyword_cluster_k} onChange={(event) => updateSection("analysis", { keyword_cluster_k: Number(event.target.value) })} disabled={loading} />
                  <small>把特征词分成几组，适合观察相近关键词的主题簇。</small>
                </label>
                <label className="field">
                  <span>文档聚类数</span>
                  <input type="number" value={draftPipeline.analysis.document_cluster_k} onChange={(event) => updateSection("analysis", { document_cluster_k: Number(event.target.value) })} disabled={loading} />
                  <small>决定散点图里会把文档分成多少组，适合粗看语料分布。</small>
                </label>
              </div>
            </section>
          </div>
        </Panel>
      );
    }
    return (
      <Panel title="保存结果">
        {renderBooleanToggles("export", exportToggleItems)}
        <div className="settings-grid">
          <label className="field">
            <span>PNG 分辨率（DPI）</span>
            <input
              type="number"
              value={draftPipeline.export.chart_dpi}
              onChange={(event) => updateSection("export", { chart_dpi: Number(event.target.value) })}
              disabled={loading}
            />
            <small>建议 240 到 400。默认 320，会输出适合汇报和打印的高清 PNG。</small>
          </label>
          <label className="field">
            <span>水印文字</span>
            <input
              value={draftPipeline.export.watermark_text}
              onChange={(event) => updateSection("export", { watermark_text: event.target.value })}
              disabled={loading || !draftPipeline.export.watermark_enabled}
              placeholder="例如 TextFlow Studio"
            />
            <small>只有打开“导出水印”后才会写到图表右下角。</small>
          </label>
        </div>
        <label className="switch-row">
          <input
            type="checkbox"
            checked={draftPipeline.export.watermark_enabled}
            onChange={(event) => updateSection("export", { watermark_enabled: event.target.checked })}
            disabled={loading}
          />
          <span>导出水印</span>
        </label>
        <p className="body-copy">PNG 图表会同时生成高频词柱状图、项目关键词图、关键词词云、机构主题热力图和文档聚类图，并自动处理中文字体。</p>
      </Panel>
    );
  };

  return (
    <>
      <Panel
        title="第 4 步：确认处理流程"
        actions={<div className="button-row"><button type="button" className="toolbar-button" onClick={() => void savePipeline()} disabled={loading}>保存当前设置</button><button type="button" className="toolbar-button accent" onClick={() => void runCurrentPipeline()} disabled={loading}>保存并开始处理</button></div>}
      >
        <div className="pipeline-step-list">
          {pipelineStepMeta.map((step, index) => {
            const mandatory = mandatoryPipelineSteps.includes(step.id);
            const enabled = stepIsEnabled(step.id);
            return (
              <article className={`pipeline-step-card ${enabled ? "is-active" : "is-muted"}`} key={step.id}>
                <div className="pipeline-step-main">
                  <div className="step-index">0{index + 1}</div>
                  <div>
                    <div className="run-head"><h4>{step.title}</h4><span className="pill">{mandatory ? "固定执行" : enabled ? "已启用" : "已跳过"}</span></div>
                    <p>{step.description}</p>
                  </div>
                </div>
                {!mandatory ? <label className="switch-row compact"><input type="checkbox" checked={enabled} onChange={() => toggleOptionalStep(step.id)} disabled={loading} /><span>{enabled ? "保留这一步" : "跳过这一步"}</span></label> : <span className="muted">这一步固定执行，不再开放开关。</span>}
              </article>
            );
          })}
        </div>
      </Panel>

      <div className="two-column">
        <Panel title="本次会执行的步骤">
          <ul className="feature-list">
            {visibleConfigSteps.map((stepId, index) => {
              const step = pipelineStepMeta.find((item) => item.id === stepId);
              return step ? <li key={stepId}>第 {index + 1} 步：{step.title}</li> : null;
            })}
          </ul>
          <p className="body-copy">读取资料、切词、生成分析和保存结果是固定主流程，只开放真正需要控制的可选步骤。</p>
        </Panel>
        <Panel title="最近一次运行">
          <ul className="feature-list">
            {latestRun ? latestRun.artifacts.map((artifact) => <li key={artifact.step}>{artifact.step}: {artifact.output_files.join(", ")} ({artifact.record_count} 条)</li>) : <li>还没有运行记录，保存后点击“保存并开始处理”。</li>}
          </ul>
        </Panel>
      </div>

      <div className="pipeline-config-list">
        {visibleConfigSteps.map((stepId) => <div key={stepId}>{renderStepPanel(stepId)}</div>)}
      </div>
    </>
  );
}

function LegacyPipelinePageArchive() {
  const {
    state: { snapshot, loading },
    saveProject,
    runPipeline
  } = useWorkspace();
  const project = snapshot.current_project;
  const [draftPipeline, setDraftPipeline] = useState<PipelineDefinition | null>(project ? deepClone(project.pipeline) : null);

  useEffect(() => {
    setDraftPipeline(project ? deepClone(project.pipeline) : null);
  }, [project?.id, project?.updated_at]);

  if (!project || !draftPipeline) {
    return <EmptyState title="流程配置待初始化" body="请先建立项目工作区。" />;
  }
  const latestRun = project.run_history.at(-1);

  const savePipeline = async () => {
    return saveProject({
      ...project,
      pipeline: draftPipeline
    });
  };

  const toggleStep = (step: PipelineStepId) => {
    setDraftPipeline((current) => {
      if (!current) {
        return current;
      }
      const enabled = current.enabled_steps.includes(step);
      const nextEnabledSteps = enabled
        ? current.enabled_steps.filter((item) => item !== step)
        : [...current.enabled_steps, step];
      const nextExecutionOrder = current.execution_order.filter((item) => nextEnabledSteps.includes(item));
      for (const item of nextEnabledSteps) {
        if (!nextExecutionOrder.includes(item)) {
          nextExecutionOrder.push(item);
        }
      }
      return {
        ...current,
        enabled_steps: nextEnabledSteps,
        execution_order: nextExecutionOrder
      };
    });
  };

  const moveStep = (step: PipelineStepId, direction: "up" | "down") => {
    setDraftPipeline((current) => {
      if (!current) {
        return current;
      }
      const currentIndex = current.execution_order.indexOf(step);
      if (currentIndex < 0) {
        return current;
      }
      const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
      if (targetIndex < 0 || targetIndex >= current.execution_order.length) {
        return current;
      }
      const nextExecutionOrder = [...current.execution_order];
      [nextExecutionOrder[currentIndex], nextExecutionOrder[targetIndex]] = [
        nextExecutionOrder[targetIndex],
        nextExecutionOrder[currentIndex]
      ];
      return {
        ...current,
        execution_order: nextExecutionOrder
      };
    });
  };

  const runCurrentPipeline = async () => {
    const saved = await savePipeline();
    if (!saved) {
      return;
    }
    await runPipeline();
  };

  return (
    <>
      <Panel
        title="第 4 步：开始处理"
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button" onClick={() => void savePipeline()} disabled={loading}>
              保存当前设置
            </button>
            <button type="button" className="toolbar-button accent" onClick={() => void runCurrentPipeline()} disabled={loading}>
              保存并开始处理
            </button>
          </div>
        }
      >
        <div className="step-grid">
          {pipelineStepMeta.map((step, index) => (
            <article className="step-card" key={step.id}>
              <div className="step-index">0{index + 1}</div>
              <h4>{step.title}</h4>
              <p>{step.description}</p>
              <span className="pill">{draftPipeline.enabled_steps.includes(step.id) ? "已启用" : "已禁用"}</span>
            </article>
          ))}
        </div>
      </Panel>

      <div className="two-column">
        <Panel title="处理步骤">
          <div className="step-toggle-list">
            {pipelineStepMeta.map((step) => {
              const orderIndex = draftPipeline.execution_order.indexOf(step.id);
              const enabled = draftPipeline.enabled_steps.includes(step.id);
              return (
                <div className="step-toggle-row" key={step.id}>
                  <label className="switch-row">
                    <input type="checkbox" checked={enabled} onChange={() => toggleStep(step.id)} disabled={loading} />
                    <span>{step.title}</span>
                  </label>
                  <div className="button-row">
                    <span className="pill">{enabled ? `#${orderIndex + 1}` : "off"}</span>
                    <button
                      type="button"
                      className="toolbar-button ghost compact"
                      onClick={() => moveStep(step.id, "up")}
                      disabled={loading || !enabled || orderIndex <= 0}
                    >
                      上移
                    </button>
                    <button
                      type="button"
                      className="toolbar-button ghost compact"
                      onClick={() => moveStep(step.id, "down")}
                      disabled={loading || !enabled || orderIndex < 0 || orderIndex >= draftPipeline.execution_order.length - 1}
                    >
                      下移
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
        <Panel title="高级参数">
          <pre className="code-box">{JSON.stringify(draftPipeline, null, 2)}</pre>
        </Panel>
        <Panel title="最近一次运行">
          <ul className="feature-list">
            {latestRun ? (
              latestRun.artifacts.map((artifact) => (
                <li key={artifact.step}>
                  {artifact.step}: {artifact.output_files.join(", ")} ({artifact.record_count} 条)
                </li>
              ))
            ) : (
              <li>还没有运行记录，保存后点击“运行当前流程”。</li>
            )}
          </ul>
        </Panel>
      </div>

      <div className="two-column">
        <Panel title="清洗与标准化">
          <div className="toggle-grid">
            {[
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
            ].map(([key, label]) => (
              <label key={key} className="switch-row">
                <input
                  type="checkbox"
                  checked={draftPipeline.cleaning[key as keyof typeof draftPipeline.cleaning]}
                  onChange={(event) =>
                    setDraftPipeline({
                      ...draftPipeline,
                      cleaning: {
                        ...draftPipeline.cleaning,
                        [key]: event.target.checked
                      }
                    })
                  }
                  disabled={loading}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="toggle-grid">
            {[
              ["convert_traditional_to_simplified", "繁简转换"],
              ["normalize_numbers", "数字归一"],
              ["normalize_time_expr", "时间表达归一"],
              ["apply_regex_rules", "应用 Regex 规则"]
            ].map(([key, label]) => (
              <label key={key} className="switch-row">
                <input
                  type="checkbox"
                  checked={draftPipeline.normalization[key as keyof typeof draftPipeline.normalization] as boolean}
                  onChange={(event) =>
                    setDraftPipeline({
                      ...draftPipeline,
                      normalization: {
                        ...draftPipeline.normalization,
                        [key]: event.target.checked
                      }
                    })
                  }
                  disabled={loading}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <label className="field">
            <span>Regex 优先策略</span>
            <select
              value={draftPipeline.normalization.regex_rule_priority}
              onChange={(event) =>
                setDraftPipeline({
                  ...draftPipeline,
                  normalization: {
                    ...draftPipeline.normalization,
                    regex_rule_priority: event.target.value as PipelineDefinition["normalization"]["regex_rule_priority"]
                  }
                })
              }
              disabled={loading}
            >
              <option value="rule_order">按规则顺序</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>

        <Panel title="切词、过滤与分析">
          <div className="toggle-grid">
            {[
              ["use_custom_lexicon", "使用自定义词典"],
              ["use_phrase_lexicon", "使用短语词典"],
              ["preserve_domain_phrases", "保留领域短语"],
              ["split_hyphenated_terms", "拆分连字符"],
              ["split_slash_terms", "拆分斜杠词"],
              ["normalize_camel_case", "拆分 camelCase"],
              ["keep_original_order", "保留原始顺序"]
            ].map(([key, label]) => (
              <label key={key} className="switch-row">
                <input
                  type="checkbox"
                  checked={draftPipeline.tokenization[key as keyof typeof draftPipeline.tokenization] as boolean}
                  onChange={(event) =>
                    setDraftPipeline({
                      ...draftPipeline,
                      tokenization: {
                        ...draftPipeline.tokenization,
                        [key]: event.target.checked
                      }
                    })
                  }
                  disabled={loading}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="toggle-grid">
            {[
              ["apply_standard_terms", "应用标准词"],
              ["apply_synonym_map", "应用同义词"],
              ["apply_near_synonym_map", "应用近义词"],
              ["apply_stopwords", "应用停用词"],
              ["apply_exclusion_terms", "应用排除词"],
              ["filter_numeric_tokens", "过滤纯数字词"],
              ["keep_single_char_important_terms", "保留重要单字词"],
              ["filter_by_pos", "尝试按词性过滤"],
              ["export_csv", "导出 CSV"],
              ["export_xlsx", "导出 XLSX"],
              ["export_png", "导出 PNG"],
              ["export_html_report", "导出 HTML 报告"],
              ["include_audit", "导出审计表"]
            ].map(([key, label]) => {
              const collection =
                key in draftPipeline.dictionary
                  ? "dictionary"
                  : key in draftPipeline.filtering
                    ? "filtering"
                    : "export";
              const checked = draftPipeline[collection][key as keyof (typeof draftPipeline)[typeof collection]] as boolean;
              return (
                <label key={key} className="switch-row">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      setDraftPipeline({
                        ...draftPipeline,
                        [collection]: {
                          ...draftPipeline[collection],
                          [key]: event.target.checked
                        }
                      })
                    }
                    disabled={loading}
                  />
                  <span>{label}</span>
                </label>
              );
            })}
          </div>
          <div className="settings-grid">
            <label className="field">
              <span>切词前最短长度</span>
              <input
                type="number"
                value={draftPipeline.tokenization.min_token_length_before_filter}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    tokenization: {
                      ...draftPipeline.tokenization,
                      min_token_length_before_filter: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>最短 token 长度</span>
              <input
                type="number"
                value={draftPipeline.filtering.min_token_length}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    filtering: {
                      ...draftPipeline.filtering,
                      min_token_length: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>最小词频</span>
              <input
                type="number"
                value={draftPipeline.filtering.min_term_frequency}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    filtering: {
                      ...draftPipeline.filtering,
                      min_term_frequency: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>共现窗口</span>
              <input
                type="number"
                value={draftPipeline.analysis.cooccurrence_window}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      cooccurrence_window: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>最小共现次数</span>
              <input
                type="number"
                value={draftPipeline.analysis.min_cooccurrence}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      min_cooccurrence: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>高频词 Top N</span>
              <input
                type="number"
                value={draftPipeline.analysis.top_n}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      top_n: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>特征词数量</span>
              <input
                value={String(draftPipeline.analysis.feature_term_count)}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      feature_term_count: event.target.value.trim().toLowerCase() === "all"
                        ? "all"
                        : Number(event.target.value)
                    }
                  })
                }
                placeholder="all 或数字"
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>每篇文档关键词数</span>
              <input
                type="number"
                value={draftPipeline.analysis.top_k_per_doc}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      top_k_per_doc: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>项目级关键词数</span>
              <input
                type="number"
                value={draftPipeline.analysis.top_k_project}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      top_k_project: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>关键词聚类数</span>
              <input
                type="number"
                value={draftPipeline.analysis.keyword_cluster_k}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      keyword_cluster_k: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
            <label className="field">
              <span>文档聚类数</span>
              <input
                type="number"
                value={draftPipeline.analysis.document_cluster_k}
                onChange={(event) =>
                  setDraftPipeline({
                    ...draftPipeline,
                    analysis: {
                      ...draftPipeline.analysis,
                      document_cluster_k: Number(event.target.value)
                    }
                  })
                }
                disabled={loading}
              />
            </label>
          </div>
        </Panel>
      </div>
    </>
  );
}

function PipelinePage() {
  const {
    state: { snapshot, loading },
    saveProject,
    runPipeline
  } = useWorkspace();
  const project = snapshot.current_project;
  const [draftPipeline, setDraftPipeline] = useState<PipelineDefinition | null>(
    project ? normalizePipelineDraft(deepClone(project.pipeline)) : null
  );
  const [documentPickerQuery, setDocumentPickerQuery] = useState("");

  useEffect(() => {
    setDraftPipeline(project ? normalizePipelineDraft(deepClone(project.pipeline)) : null);
    setDocumentPickerQuery("");
  }, [project?.id, project?.updated_at]);

  if (!project || !draftPipeline) {
    return <EmptyState title="流程配置待初始化" body="请先建立项目工作区。" />;
  }

  const latestRun = project.run_history.at(-1);
  const visibleConfigSteps = fixedPipelineOrder.filter((step) =>
    mandatoryPipelineSteps.includes(step) || draftPipeline.enabled_steps.includes(step)
  );
  const availableSources = Array.from(new Set(snapshot.corpus.map((item) => item.source).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const availableInstitutions = Array.from(new Set(snapshot.corpus.map((item) => item.institution).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const availableCategories = Array.from(new Set(snapshot.corpus.map((item) => item.category_or_tag).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const matchedDocuments = snapshot.corpus.filter((item) => corpusMatchesRunScope(item, draftPipeline.run_scope));
  const pickerQuery = documentPickerQuery.trim().toLowerCase();
  const documentPickerRows = draftPipeline.run_scope.mode === "selected_documents"
    ? snapshot.corpus.filter((item) =>
      !pickerQuery || [item.doc_id, item.title, item.source, item.institution].filter(Boolean).join(" ").toLowerCase().includes(pickerQuery)
    )
    : [];
  const selectedRecipe = recipeCards.find((card) => card.id === draftPipeline.recipe_id) ?? recipeCards.at(-1)!;
  const selectedOutputBundle = outputBundleCards.find((card) => card.id === draftPipeline.output_bundle_id) ?? outputBundleCards.at(-1)!;
  const estimatedEffort = matchedDocuments.length <= 20 ? "短" : matchedDocuments.length <= 80 ? "中" : "长";
  const canRun = !loading && matchedDocuments.length > 0;
  const runSummary = runScopeSummary(draftPipeline.run_scope, snapshot.corpus.length, matchedDocuments.length);

  const updatePipeline = (updater: (current: PipelineDefinition) => PipelineDefinition) => {
    setDraftPipeline((current) => current ? normalizePipelineDraft(updater(current)) : current);
  };

  const updateSection = <K extends "cleaning" | "normalization" | "tokenization" | "dictionary" | "filtering" | "analysis" | "export">(
    section: K,
    patch: Partial<PipelineDefinition[K]>
  ) => {
    updatePipeline((current) => ({
      ...current,
      [section]: {
        ...current[section],
        ...patch
      },
      recipe_id: section === "export" ? current.recipe_id : "custom",
      output_bundle_id: section === "export" ? "custom" : current.output_bundle_id
    }));
  };

  const updateRunScope = (patch: Partial<RunScopeDefinition>) => {
    updatePipeline((current) => ({
      ...current,
      run_scope: {
        ...current.run_scope,
        ...patch
      }
    }));
  };

  const toggleScopeArrayValue = (
    field: "source_values" | "institution_values" | "category_values",
    value: string
  ) => {
    const values = draftPipeline.run_scope[field];
    updateRunScope({
      [field]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
    } as Partial<RunScopeDefinition>);
  };

  const toggleSelectedDocument = (docId: string) => {
    const selectedDocIds = draftPipeline.run_scope.selected_doc_ids;
    updateRunScope({
      selected_doc_ids: selectedDocIds.includes(docId)
        ? selectedDocIds.filter((item) => item !== docId)
        : [...selectedDocIds, docId]
    });
  };

  const toggleOptionalStep = (step: PipelineStepId) => {
    if (!optionalPipelineSteps.includes(step)) {
      return;
    }
    const nextEnabledSteps = draftPipeline.enabled_steps.includes(step)
      ? draftPipeline.enabled_steps.filter((item) => item !== step)
      : [...draftPipeline.enabled_steps, step];
    updatePipeline((current) => ({
      ...current,
      enabled_steps: nextEnabledSteps,
      recipe_id: "custom"
    }));
  };

  const renderBooleanToggles = (
    section: "cleaning" | "normalization" | "tokenization" | "dictionary" | "filtering" | "export",
    items: readonly (readonly [string, string])[]
  ) => {
    const values = draftPipeline[section] as unknown as Record<string, unknown>;
    return (
      <div className="toggle-grid">
        {items.map(([key, label]) => (
          <label key={key} className="switch-row">
            <input
              type="checkbox"
              checked={Boolean(values[key])}
              onChange={(event) => updateSection(section, { [key]: event.target.checked } as Partial<PipelineDefinition[typeof section]>)}
              disabled={loading}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
    );
  };

  const savePipeline = async () => saveProject({ ...project, pipeline: normalizePipelineDraft(draftPipeline) });
  const runCurrentPipeline = async () => {
    if (!matchedDocuments.length) {
      return;
    }
    const saved = await savePipeline();
    if (saved) {
      await runPipeline();
    }
  };

  const renderAdvancedPanel = (stepId: PipelineStepId) => {
    if (stepId === "ingestion") {
      return <Panel title="读取资料"><p className="body-copy">这一步固定执行，直接读取当前“处理对象”命中的项目语料。</p></Panel>;
    }
    if (stepId === "cleaning") {
      return <Panel title="基础清洗">{renderBooleanToggles("cleaning", cleaningToggleItems)}</Panel>;
    }
    if (stepId === "normalization") {
      return (
        <Panel title="统一写法">
          {renderBooleanToggles("normalization", normalizationToggleItems)}
          <label className="field">
            <span>Regex 优先策略</span>
            <select
              value={draftPipeline.normalization.regex_rule_priority}
              onChange={(event) => updateSection("normalization", { regex_rule_priority: event.target.value as PipelineDefinition["normalization"]["regex_rule_priority"] })}
              disabled={loading}
            >
              <option value="rule_order">按规则顺序</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }
    if (stepId === "tokenization") {
      return (
        <Panel title="切词">
          <div className="settings-grid">
            <label className="field">
              <span>语言模式</span>
              <select value={draftPipeline.tokenization.language_mode} onChange={(event) => updateSection("tokenization", { language_mode: event.target.value as PipelineDefinition["tokenization"]["language_mode"] })} disabled={loading}>
                <option value="auto">自动判断</option>
                <option value="zh">中文</option>
                <option value="en">英文</option>
                <option value="mixed">中英混合</option>
              </select>
            </label>
            <label className="field">
              <span>切词前最短长度</span>
              <input type="number" value={draftPipeline.tokenization.min_token_length_before_filter} onChange={(event) => updateSection("tokenization", { min_token_length_before_filter: Number(event.target.value) })} disabled={loading} />
            </label>
          </div>
          {renderBooleanToggles("tokenization", tokenizationToggleItems)}
        </Panel>
      );
    }
    if (stepId === "dictionary_application") {
      return (
        <Panel title="套用词表">
          {renderBooleanToggles("dictionary", dictionaryToggleItems)}
          <label className="field">
            <span>冲突处理</span>
            <select value={draftPipeline.dictionary.conflict_resolution} onChange={(event) => updateSection("dictionary", { conflict_resolution: event.target.value as PipelineDefinition["dictionary"]["conflict_resolution"] })} disabled={loading}>
              <option value="priority">按词表优先级</option>
              <option value="first_match">命中首条后停止</option>
            </select>
          </label>
        </Panel>
      );
    }
    if (stepId === "filtering") {
      return (
        <Panel title="过滤噪声">
          {renderBooleanToggles("filtering", filteringToggleItems)}
          <div className="settings-grid">
            <label className="field">
              <span>最短 token 长度</span>
              <input type="number" value={draftPipeline.filtering.min_token_length} onChange={(event) => updateSection("filtering", { min_token_length: Number(event.target.value) })} disabled={loading} />
            </label>
            <label className="field">
              <span>最小词频</span>
              <input type="number" value={draftPipeline.filtering.min_term_frequency} onChange={(event) => updateSection("filtering", { min_term_frequency: Number(event.target.value) })} disabled={loading} />
            </label>
          </div>
        </Panel>
      );
    }
    if (stepId === "analysis") {
      return (
        <Panel title="生成分析">
          <div className="analysis-method-grid">
            {analysisMethodCards.map((card) => (
              <article className="analysis-method-card" key={card.title}>
                <div className="run-head">
                  <strong>{card.title}</strong>
                  <span className="pill">{card.output}</span>
                </div>
                <p className="body-copy">{card.description}</p>
                <p className="muted">对应参数：{card.params.join("、")}</p>
              </article>
            ))}
          </div>
          <div className="settings-grid">
            <label className="field"><span>高频词 Top N</span><input type="number" value={draftPipeline.analysis.top_n} onChange={(event) => updateSection("analysis", { top_n: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>共现窗口</span><input type="number" value={draftPipeline.analysis.cooccurrence_window} onChange={(event) => updateSection("analysis", { cooccurrence_window: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>最小共现次数</span><input type="number" value={draftPipeline.analysis.min_cooccurrence} onChange={(event) => updateSection("analysis", { min_cooccurrence: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>特征词数量</span><input value={String(draftPipeline.analysis.feature_term_count)} onChange={(event) => updateSection("analysis", { feature_term_count: event.target.value.trim().toLowerCase() === "all" ? "all" : Number(event.target.value) })} placeholder="all 或数字" disabled={loading} /></label>
            <label className="field"><span>每篇文档关键词数</span><input type="number" value={draftPipeline.analysis.top_k_per_doc} onChange={(event) => updateSection("analysis", { top_k_per_doc: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>项目级关键词数</span><input type="number" value={draftPipeline.analysis.top_k_project} onChange={(event) => updateSection("analysis", { top_k_project: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>主题数量</span><input type="number" value={draftPipeline.analysis.topic_model_k} onChange={(event) => updateSection("analysis", { topic_model_k: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>关键词聚类数</span><input type="number" value={draftPipeline.analysis.keyword_cluster_k} onChange={(event) => updateSection("analysis", { keyword_cluster_k: Number(event.target.value) })} disabled={loading} /></label>
            <label className="field"><span>文档聚类数</span><input type="number" value={draftPipeline.analysis.document_cluster_k} onChange={(event) => updateSection("analysis", { document_cluster_k: Number(event.target.value) })} disabled={loading} /></label>
          </div>
        </Panel>
      );
    }
    return (
      <Panel title="保存结果">
        {renderBooleanToggles("export", exportToggleItems)}
        <div className="settings-grid">
          <label className="field">
            <span>PNG 分辨率（DPI）</span>
            <input type="number" value={draftPipeline.export.chart_dpi} onChange={(event) => updateSection("export", { chart_dpi: Number(event.target.value) })} disabled={loading} />
            <small>建议 240 到 400。默认 320，会输出适合汇报和打印的高清 PNG。</small>
          </label>
          <label className="field">
            <span>水印文字</span>
            <input value={draftPipeline.export.watermark_text} onChange={(event) => updateSection("export", { watermark_text: event.target.value })} disabled={loading || !draftPipeline.export.watermark_enabled} placeholder="例如 TextFlow Studio" />
            <small>只有打开“导出水印”后才会写到图表右下角。</small>
          </label>
        </div>
        <label className="switch-row">
          <input type="checkbox" checked={draftPipeline.export.watermark_enabled} onChange={(event) => updateSection("export", { watermark_enabled: event.target.checked })} disabled={loading} />
          <span>导出水印</span>
        </label>
      </Panel>
    );
  };

  return (
    <>
      <Panel
        title="第 4 步：确认本次运行"
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button" onClick={() => void savePipeline()} disabled={loading}>保存当前设置</button>
            <button type="button" className="toolbar-button accent" onClick={() => void runCurrentPipeline()} disabled={!canRun}>保存并开始处理</button>
          </div>
        }
      >
        <div className="run-intent-grid">
          <section className="intent-card">
            <div className="run-head">
              <div>
                <h4>1. 处理对象</h4>
                <p className="body-copy">先明确本次要处理哪批资料，再决定怎么处理。</p>
              </div>
              <span className="pill">{matchedDocuments.length} / {snapshot.corpus.length} 篇</span>
            </div>
            <div className="intent-option-grid">
              {runScopeModeOptions.map((option) => (
                <button key={option.id} type="button" className={`intent-choice ${draftPipeline.run_scope.mode === option.id ? "is-active" : ""}`} onClick={() => updateRunScope({ mode: option.id })} disabled={loading}>
                  <div>
                    <strong>{option.title}</strong>
                    <p>{option.description}</p>
                  </div>
                </button>
              ))}
            </div>
            {draftPipeline.run_scope.mode === "filtered_subset" && (
              <div className="intent-filter-stack">
                <div className="intent-filter-group">
                  <strong>来源</strong>
                  <div className="pill-cloud">
                    {availableSources.length ? availableSources.map((source) => (
                      <button key={source} type="button" className={`intent-pill ${draftPipeline.run_scope.source_values.includes(source) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue("source_values", source)} disabled={loading}>{source}</button>
                    )) : <span className="muted">当前语料还没有来源字段。</span>}
                  </div>
                </div>
                <div className="intent-filter-group">
                  <strong>机构</strong>
                  <div className="pill-cloud">
                    {availableInstitutions.length ? availableInstitutions.map((institution) => (
                      <button key={institution} type="button" className={`intent-pill ${draftPipeline.run_scope.institution_values.includes(institution) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue("institution_values", institution)} disabled={loading}>{institution}</button>
                    )) : <span className="muted">当前语料还没有机构字段。</span>}
                  </div>
                </div>
                <div className="intent-filter-group">
                  <strong>标签</strong>
                  <div className="pill-cloud">
                    {availableCategories.length ? availableCategories.map((category) => (
                      <button key={category} type="button" className={`intent-pill ${draftPipeline.run_scope.category_values.includes(category) ? "is-active" : ""}`} onClick={() => toggleScopeArrayValue("category_values", category)} disabled={loading}>{category}</button>
                    )) : <span className="muted">当前语料还没有标签字段。</span>}
                  </div>
                </div>
                <div className="settings-grid">
                  <label className="field"><span>起始年份</span><input type="number" value={draftPipeline.run_scope.year_from ?? ""} onChange={(event) => updateRunScope({ year_from: event.target.value ? Number(event.target.value) : null })} disabled={loading} placeholder="例如 2024" /></label>
                  <label className="field"><span>结束年份</span><input type="number" value={draftPipeline.run_scope.year_to ?? ""} onChange={(event) => updateRunScope({ year_to: event.target.value ? Number(event.target.value) : null })} disabled={loading} placeholder="例如 2025" /></label>
                </div>
              </div>
            )}
            {draftPipeline.run_scope.mode === "selected_documents" && (
              <div className="intent-filter-stack">
                <label className="field">
                  <span>搜索文档</span>
                  <input value={documentPickerQuery} onChange={(event) => setDocumentPickerQuery(event.target.value)} placeholder="按标题、来源或机构筛选" disabled={loading} />
                </label>
                <div className="document-picker-list">
                  {documentPickerRows.slice(0, 24).map((item) => (
                    <label key={item.doc_id} className="document-picker-row">
                      <input type="checkbox" checked={draftPipeline.run_scope.selected_doc_ids.includes(item.doc_id)} onChange={() => toggleSelectedDocument(item.doc_id)} disabled={loading} />
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
          </section>

          <section className="intent-card">
            <div className="run-head">
              <div>
                <h4>2. 处理配方</h4>
                <p className="body-copy">先选任务目的，再在高级设置里微调。</p>
              </div>
              <span className="pill">{selectedRecipe.title}</span>
            </div>
            <div className="intent-choice-stack">
              {recipeCards.map((recipe) => (
                <button key={recipe.id} type="button" className={`intent-choice ${draftPipeline.recipe_id === recipe.id ? "is-active" : ""}`} onClick={() => updatePipeline((current) => applyRecipePreset(current, recipe.id))} disabled={loading}>
                  <div>
                    <strong>{recipe.title}</strong>
                    <p>{recipe.description}</p>
                  </div>
                  <span className="pill">{recipe.output}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="intent-card">
            <div className="run-head">
              <div>
                <h4>3. 输出包</h4>
                <p className="body-copy">决定最后交付什么，再决定是否需要高清图和审计表。</p>
              </div>
              <span className="pill">{selectedOutputBundle.title}</span>
            </div>
            <div className="intent-choice-stack">
              {outputBundleCards.map((bundle) => (
                <button key={bundle.id} type="button" className={`intent-choice ${draftPipeline.output_bundle_id === bundle.id ? "is-active" : ""}`} onClick={() => updatePipeline((current) => applyOutputBundlePreset(current, bundle.id))} disabled={loading}>
                  <div>
                    <strong>{bundle.title}</strong>
                    <p>{bundle.description}</p>
                  </div>
                  <span className="pill">{bundle.output}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="intent-card intent-summary-card">
            <div className="run-head">
              <div>
                <h4>4. 本次运行摘要</h4>
                <p className="body-copy">点击开始前，先核对处理对象、处理方式和最终产物。</p>
              </div>
              <span className="pill">{estimatedEffort}耗时</span>
            </div>
            <div className="intent-summary-list">
              <div className="status-panel"><strong>处理对象</strong><span>{runSummary}</span></div>
              <div className="status-panel"><strong>处理配方</strong><span>{selectedRecipe.description}</span></div>
              <div className="status-panel"><strong>输出结果</strong><span>{outputBundleSummary(draftPipeline.export)}</span></div>
              <div className="status-panel">
                <strong>文档预览</strong>
                <ul className="micro-list">
                  {matchedDocuments.slice(0, 4).map((item) => <li key={item.doc_id}>{item.title}</li>)}
                  {!matchedDocuments.length && <li>当前范围下没有文档，请先调整处理对象。</li>}
                </ul>
              </div>
              {latestRun && <div className="status-panel"><strong>最近一次运行</strong><span>{latestRun.run_scope_summary ?? "处理对象：项目内全部资料"}</span></div>}
            </div>
          </section>
        </div>
      </Panel>

      <div className="two-column">
        <Panel title="本次会执行什么">
          <ul className="feature-list">
            {visibleConfigSteps.map((stepId, index) => {
              const step = pipelineStepMeta.find((item) => item.id === stepId);
              return step ? <li key={stepId}>第 {index + 1} 步：{step.title}</li> : null;
            })}
          </ul>
          <p className="body-copy">读取资料、切词、生成分析和保存结果是固定主流程。只有清洗、统一写法、词表和过滤这些可选阶段，才会在高级设置里开放开关。</p>
        </Panel>
        <Panel title="最近一次运行">
          <ul className="feature-list">
            {latestRun ? (
              <>
                <li>{latestRun.run_scope_summary ?? "处理对象：项目内全部资料"}</li>
                <li>实际处理文档数：{latestRun.processed_document_count ?? snapshot.corpus.length}</li>
                <li>输出包：{latestRun.output_summary ?? "按照当前导出设置生成结果文件"}</li>
              </>
            ) : <li>还没有运行记录，保存后点击“保存并开始处理”。</li>}
          </ul>
        </Panel>
      </div>

      <Panel title="高级设置（按步骤查看）">
        <p className="body-copy">只有需要细调参数时再展开这里。默认情况下，直接在上面的处理对象、处理配方和输出包里确认即可。</p>
        <div className="pipeline-config-list">
          {visibleConfigSteps.map((stepId, index) => {
            const step = pipelineStepMeta.find((item) => item.id === stepId);
            const mandatory = mandatoryPipelineSteps.includes(stepId);
            return (
              <section key={stepId} className="advanced-step-shell">
                <div className="run-head">
                  <div>
                    <h4>第 {index + 1} 步：{step?.title}</h4>
                    <p className="body-copy">{step?.description}</p>
                  </div>
                  {mandatory ? <span className="pill">固定执行</span> : (
                    <label className="switch-row compact">
                      <input type="checkbox" checked={draftPipeline.enabled_steps.includes(stepId)} onChange={() => toggleOptionalStep(stepId)} disabled={loading} />
                      <span>{draftPipeline.enabled_steps.includes(stepId) ? "启用" : "跳过"}</span>
                    </label>
                  )}
                </div>
                {mandatory || draftPipeline.enabled_steps.includes(stepId) ? renderAdvancedPanel(stepId) : (
                  <div className="status-panel"><span>这一步当前已跳过，不会进入本次运行。</span></div>
                )}
              </section>
            );
          })}
        </div>
      </Panel>
    </>
  );
}

function DictionariesPage() {
  const {
    state: { snapshot, loading },
    exportDictionarySheet,
    importDictionarySheet,
    pickJsonFile,
    saveJsonFilePath,
    saveProject,
    setActivePage
  } = useWorkspace();
  const project = snapshot.current_project;
  const [activeSheet, setActiveSheet] = useState<DictionaryKind>("stopwords");
  const [draftSet, setDraftSet] = useState<DictionarySet | null>(project ? deepClone(project.dictionary_set) : null);
  const [bulkText, setBulkText] = useState("");

  useEffect(() => {
    setDraftSet(project ? deepClone(project.dictionary_set) : null);
    setActiveSheet("stopwords");
    setBulkText("");
  }, [project?.id, project?.updated_at]);

  if (!project || !draftSet) {
    return <EmptyState title="词表中心为空" body="请先创建或加载项目。" />;
  }

  const currentSheet = draftSet.sheets[activeSheet] ?? draftSet.sheets.stopwords;
  const currentGuide = dictionaryGuideMap[activeSheet];

  const updateEntry = (entryId: string, patch: Partial<DictionaryEntry>) => {
    setDraftSet((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        sheets: {
          ...current.sheets,
          [activeSheet]: {
            ...current.sheets[activeSheet],
            entries: current.sheets[activeSheet].entries.map((entry) =>
              entry.id === entryId ? { ...entry, ...patch } : entry
            )
          }
        }
      };
    });
  };

  const addEntry = () => {
    const newEntry: DictionaryEntry = {
      id: `entry-${Date.now()}`,
      source: "",
      target: "",
      tags: [],
      enabled: true,
      hits: 0,
      notes: ""
    };
    setDraftSet((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        sheets: {
          ...current.sheets,
          [activeSheet]: {
            ...current.sheets[activeSheet],
            entries: [...current.sheets[activeSheet].entries, newEntry]
          }
        }
      };
    });
  };

  const removeEntry = (entryId: string) => {
    setDraftSet((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        sheets: {
          ...current.sheets,
          [activeSheet]: {
            ...current.sheets[activeSheet],
            entries: current.sheets[activeSheet].entries.filter((entry) => entry.id !== entryId)
          }
        }
      };
    });
  };

  const saveDictionarySet = async () => {
    await saveProject({
      ...project,
      dictionary_set: draftSet
    });
  };

  const appendBulkEntries = () => {
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

    setDraftSet((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        sheets: {
          ...current.sheets,
          [activeSheet]: {
            ...current.sheets[activeSheet],
            entries: [...current.sheets[activeSheet].entries, ...nextEntries]
          }
        }
      };
    });
    setBulkText("");
  };

  const handleImportSheet = async () => {
    const path = await pickJsonFile();
    if (!path) {
      return;
    }
    await importDictionarySheet(activeSheet as DictionaryKind, path);
  };

  const handleExportSheet = async () => {
    const path = await saveJsonFilePath(`${activeSheet}.json`);
    if (!path) {
      return;
    }
    await exportDictionarySheet(activeSheet as DictionaryKind, path);
  };

  return (
    <>
      <Panel
        title="词表规则"
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button" onClick={() => void handleImportSheet()} disabled={loading}>
              导入 JSON
            </button>
            <button type="button" className="toolbar-button" onClick={() => void handleExportSheet()} disabled={loading}>
              导出 JSON
            </button>
            <button type="button" className="toolbar-button accent" onClick={() => void saveDictionarySet()} disabled={loading}>
              保存词表
            </button>
          </div>
        }
      >
        <div className="dictionary-kind-tabs">
          {Object.entries(draftSet.sheets).map(([kind, sheet]) => (
            <button
              key={kind}
              type="button"
              className={`dictionary-kind-button ${activeSheet === kind ? "is-active" : ""}`.trim()}
              onClick={() => setActiveSheet(kind as DictionaryKind)}
              disabled={loading}
            >
              <strong>{sheet.name}</strong>
              <small>生效于：{dictionaryGuideMap[kind as DictionaryKind].stepLabel}</small>
            </button>
          ))}
        </div>
        <div className="dictionary-overview-grid">
          <article className="project-card dictionary-guide-card">
            <div className="run-head">
              <div>
                <p className="eyebrow">当前词表</p>
                <h4>{currentSheet.name}</h4>
              </div>
              <span className="pill">处理与分析 · {currentGuide.stepLabel}</span>
            </div>
            <p className="body-copy">{currentGuide.purpose}</p>
            <ul className="feature-list">
              <li>左侧填写：{currentGuide.sourceHint}。</li>
              <li>右侧填写：{currentGuide.targetHint}。</li>
              <li>关闭“启用”后，这条规则会保留在项目里，但本次运行不会生效。</li>
            </ul>
            <div className="button-row">
              <button type="button" className="toolbar-button ghost" onClick={() => setActivePage("pipeline")} disabled={loading}>
                去看流程里的这一步
              </button>
            </div>
          </article>
          <div className="stat-grid dictionary-stat-grid">
            <StatCard label="当前词表" value={currentSheet.name} tone="ink" />
            <StatCard label="生效步骤" value={currentGuide.stepLabel} tone="gold" />
            <StatCard label="条目数" value={String(currentSheet.entries.length)} tone="emerald" />
            <StatCard label="累计命中" value={String(currentSheet.entries.reduce((sum, entry) => sum + entry.hits, 0))} tone="rose" />
          </div>
        </div>
      </Panel>

      <Panel
        title={`${currentSheet.name} 条目`}
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button ghost" onClick={addEntry} disabled={loading}>
              新增条目
            </button>
          </div>
        }
      >
        <div className="dictionary-editor">
          {currentSheet.entries.map((entry) => (
            <div className="dictionary-editor-row" key={entry.id}>
              <input
                value={entry.source}
                onChange={(event) => updateEntry(entry.id, { source: event.target.value })}
                placeholder={currentGuide.sourceHint}
                disabled={loading}
              />
              <input
                value={entry.target ?? ""}
                onChange={(event) => updateEntry(entry.id, { target: event.target.value })}
                placeholder={currentGuide.targetHint}
                disabled={loading || !currentGuide.usesTarget}
              />
              <label className="switch-row compact">
                <input
                  type="checkbox"
                  checked={entry.enabled}
                  onChange={(event) => updateEntry(entry.id, { enabled: event.target.checked })}
                  disabled={loading}
                />
                <span>启用</span>
              </label>
              <button type="button" className="toolbar-button ghost" onClick={() => removeEntry(entry.id)} disabled={loading}>
                删除
              </button>
            </div>
          ))}
        </div>
        <label className="field">
          <span>批量粘贴</span>
          <textarea
            rows={5}
            value={bulkText}
            onChange={(event) => setBulkText(event.target.value)}
            placeholder={currentGuide.bulkExample}
            disabled={loading}
          />
        </label>
        <p className="helper-note">
          支持逐行粘贴，格式可以用“source,target”、“source to target”或只写左侧词项。
        </p>
        <div className="button-row">
          <button type="button" className="toolbar-button" onClick={appendBulkEntries} disabled={loading || !bulkText.trim()}>
            追加批量条目
          </button>
        </div>
        <DictionaryTable sheet={currentSheet} />
      </Panel>
    </>
  );
}

function AnalysisPage() {
  const {
    state: { snapshot }
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="分析结果待生成" body="先运行一次 pipeline，结果页会自动显示。" />;
  }

  const trendValues = project.results.term_year_table.map((item) => item.tf_in_year);

  return (
    <>
      <div className="analysis-grid">
        <Panel title="高频词">
          <FrequencyTable rows={project.results.frequency_table} />
        </Panel>

        <Panel title="按年词频趋势">
          <LineChart values={trendValues} labels={project.results.term_year_table.map((item) => String(item.year))} />
          <p className="chart-caption">示例词“分析”的逐年词频变化。</p>
        </Panel>
      </div>

      <div className="analysis-grid">
        <Panel title="共现热项">
          <Table columns={["term_a", "term_b", "cooccurrence_count", "score"]} rows={project.results.cooccurrence_table} />
        </Panel>
        <Panel title="文档聚类分布">
          <ScatterChart rows={project.results.clustering_result} />
        </Panel>
      </div>

      <div className="analysis-grid">
        <Panel title="特征词与关键词">
          <KeywordPanel featureTerms={project.results.selected_feature_terms} keywords={project.results.keyword_result} />
        </Panel>

        <Panel title="机构 × 主题">
          <TopicPanel rows={project.results.institution_topic_cooccurrence} />
        </Panel>
      </div>
    </>
  );
}

function ResultsPage() {
  const {
    state: { snapshot, loading, lastExport },
    exportProject,
    exportProjectBackup,
    openPath,
    revealPath,
    saveProjectPackagePath
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="还没有结果" body="先完成一次处理，这里就会出现表格、图表和报告。" />;
  }

  const currentProjectSummary = snapshot.recent_projects.find((item) => item.id === project.id);
  const projectRootPath = currentProjectSummary?.path;
  const fallbackExportDir = projectRootPath ? joinFsPath(projectRootPath, project.paths.exports_dir) : null;
  const visibleExport = lastExport?.project_id === project.id ? lastExport : null;
  const exportDirPath = visibleExport?.export_dir ?? fallbackExportDir;
  const exportDirLabel = visibleExport?.relative_export_dir ?? project.paths.exports_dir;
  const generatedFiles = projectRootPath
    ? project.results.report_files.map((relativePath) => ({
        path: joinFsPath(projectRootPath, relativePath),
        relative_path: relativePath
      }))
    : [];

  const handleExportProjectPackage = async () => {
    const path = await saveProjectPackagePath(`${project.name}.tfproj`);
    if (!path) {
      return;
    }
    await exportProjectBackup(path);
  };

  const handleExportResults = async (formats: ("csv" | "xlsx" | "html" | "png")[]) => {
    await exportProject(formats);
  };

  return (
    <>
      <Panel
        title="第 5 步：导出结果"
        actions={
          <div className="button-row">
            <button type="button" className="toolbar-button accent" onClick={() => void handleExportResults(["csv", "xlsx"])} disabled={loading}>
              导出表格
            </button>
            <button type="button" className="toolbar-button" onClick={() => void handleExportResults(["html", "png"])} disabled={loading}>
              导出报告与图表
            </button>
            <button type="button" className="toolbar-button ghost" onClick={() => void handleExportProjectPackage()} disabled={loading}>
              导出 .tfproj 项目包
            </button>
          </div>
        }
      >
        <ul className="feature-list">
          <li>表格导出适合继续在 Excel 里筛选和汇总。</li>
          <li>报告与图表导出会包含高频词图、项目关键词图、关键词词云、机构主题热力图和文档聚类图。</li>
          <li>`.tfproj` 项目包会把项目、语料、词表、运行记录和导出文件一起打成一个单文件。</li>
        </ul>
        <div className="status-panel export-location-panel">
          <strong>导出位置</strong>
          <p className="project-path">{exportDirPath ?? "还没有导出过结果。导出后会自动打开导出文件夹。"}</p>
          <div className="button-row">
            <button
              type="button"
              className="toolbar-button"
              onClick={() => exportDirPath ? void openPath(exportDirPath) : undefined}
              disabled={loading || !exportDirPath}
            >
              打开导出文件夹
            </button>
            <button
              type="button"
              className="toolbar-button ghost"
              onClick={() => visibleExport?.files[0] ? void revealPath(visibleExport.files[0].path) : undefined}
              disabled={loading || !visibleExport?.files.length}
            >
              定位最近导出的文件
            </button>
          </div>
          <span className="muted">
            {visibleExport
              ? `最近一次导出保存在 ${visibleExport.relative_export_dir}，导出完成后会自动打开该文件夹。`
              : `当前项目的导出目录固定在 ${exportDirLabel}。`}
          </span>
        </div>
      </Panel>

      <div className="two-column">
        <Panel title="历史运行记录">
          <div className="stack-list">
            {project.run_history.map((run) => (
              <article key={run.run_id} className="run-card">
                <div className="run-head">
                  <strong>{run.run_id}</strong>
                  <span className={`badge ${run.status}`}>{run.status}</span>
                </div>
                <p>{run.params_snapshot_path}</p>
                  <p className="muted">{run.run_scope_summary ?? "处理对象：项目内全部资料"}</p>
                <ul className="micro-list">
                  {run.artifacts.map((artifact) => (
                    <li key={`${run.run_id}-${artifact.step}`}>{artifact.step}: {artifact.output_files.length} 个文件</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </Panel>
        <Panel title={visibleExport ? "最近一次导出的文件" : "已生成文件"}>
          <div className="artifact-list">
            {(visibleExport?.files.length ? visibleExport.files : generatedFiles).map((file) => (
              <article key={file.path} className="project-card artifact-row">
                <div>
                  <h4>{fileNameFromPath(file.relative_path)}</h4>
                  <p className="project-path">{file.relative_path}</p>
                </div>
                <div className="button-row">
                  <button type="button" className="toolbar-button" onClick={() => void openPath(file.path)} disabled={loading}>
                    打开
                  </button>
                  <button type="button" className="toolbar-button ghost" onClick={() => void revealPath(file.path)} disabled={loading}>
                    定位
                  </button>
                </div>
              </article>
            ))}
            {!(visibleExport?.files.length || generatedFiles.length) && (
              <div className="status-panel">
                <strong>还没有可查看的导出文件</strong>
                <span className="muted">先运行一次导出，这里会显示文件列表，并支持打开或定位。</span>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}

function ReportPage() {
  const {
    state: { snapshot }
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="暂无报告" body="生成结果后即可预览 HTML 报告结构。" />;
  }

  return (
    <div className="report-layout">
      <Panel title="HTML 报告结构">
        <div className="report-block">
          <h4>1. 项目概览</h4>
          <p>{project.name}，共 {snapshot.corpus.length} 篇文档，最近更新时间 {project.updated_at}。</p>
        </div>
        <div className="report-block">
          <h4>2. 数据规模与流程参数</h4>
          <p>
            Source profile 为 <strong>{project.import_template.source_profile}</strong>，
            使用 {project.pipeline.analysis.feature_term_count} 规模的特征词集进行后续分析。
          </p>
        </div>
        <div className="report-block">
          <h4>3. 关键词聚类摘要</h4>
          <ul className="feature-list">
            {project.results.keyword_cluster_result
              .filter((row) => row.is_label_term)
              .map((row) => (
                <li key={`${row.cluster_id}-${row.term}`}>Cluster {row.cluster_id}: {row.topic_label}</li>
              ))}
          </ul>
        </div>
      </Panel>

      <Panel title="规则审计摘要">
        <AuditTable rows={project.results.audit_table} />
      </Panel>
    </div>
  );
}

function SettingsPage() {
  const {
    state: { snapshot }
  } = useWorkspace();
  const project = snapshot.current_project;

  if (!project) {
    return <EmptyState title="尚未初始化设置" body="创建项目后会自动加载默认设置。" />;
  }

  return (
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
  );
}

import type {
  ExportParameters,
  RegisteredWorkflowNodeDefinition,
  RunScopeDefinition,
  WorkflowPort,
  WorkflowPortCompatibilityCatalog,
  WorkflowPortType,
  WorkflowRuntimeProfile,
  WorkflowStepId,
  WorkflowNodeType
} from "@textflow/shared-types";

export type WorkflowStepRole = WorkflowStepId | "scope" | "resource" | "merge" | "sink" | "utility";

export interface WorkflowCatalogPort extends WorkflowPort {
  result_bundle_key?: string;
  png_chart_ids?: string[];
  include_in_html_audit?: boolean;
  artifact_kind?: string;
}

export interface WorkflowNodeDefinition {
  label: string;
  description: string;
  category: RegisteredWorkflowNodeDefinition["category"];
  singleton?: boolean;
  hidden_from_toolbox?: boolean;
  inputs: WorkflowCatalogPort[];
  outputs: WorkflowCatalogPort[];
  stepId: WorkflowStepRole;
  size?: { w: number; h: number };
  defaultPosition?: { x: number; y: number };
  defaultConfig: (runtimeProfile: WorkflowRuntimeProfile) => Record<string, unknown>;
  registeredDefinition?: RegisteredWorkflowNodeDefinition;
}

const fallbackFrame = { w: 280, h: 210 };
const fallbackPosition = { x: 120, y: 220 };

const defaultPortCompatibility: WorkflowPortCompatibilityCatalog = {
  table_sources: [],
  renderable_sources: [],
  analysis_result_sources: [],
  corpus_order: []
};

const derivedCorpusPortOrder: WorkflowPortType[] = [
  "CorpusTable",
  "ProjectCorpus",
  "ScopedCorpus",
  "CleanCorpus",
  "NormalizedCorpus",
  "TokenCorpus",
  "FilteredTokenCorpus"
];

const derivedPortCompatibilityFallback: WorkflowPortCompatibilityCatalog = {
  table_sources: [],
  renderable_sources: [],
  analysis_result_sources: [],
  corpus_order: [
    ...derivedCorpusPortOrder
  ]
};

let configuredDefinitions: RegisteredWorkflowNodeDefinition[] = [];
let configuredDefinitionsByType = new Map<WorkflowNodeType, RegisteredWorkflowNodeDefinition>();
let configuredPortCompatibility: WorkflowPortCompatibilityCatalog = { ...defaultPortCompatibility };

export const executionOrder: WorkflowStepId[] = [
  "ingestion",
  "cleaning",
  "normalization",
  "tokenization",
  "dictionary_application",
  "filtering",
  "analysis",
  "export"
];

export const defaultRunScope = (runtimeProfile: WorkflowRuntimeProfile): RunScopeDefinition => ({
  ...runtimeProfile.run_scope,
  mode: runtimeProfile.run_scope?.mode ?? "all_documents",
  source_values: [...(runtimeProfile.run_scope?.source_values ?? [])],
  institution_values: [...(runtimeProfile.run_scope?.institution_values ?? [])],
  category_values: [...(runtimeProfile.run_scope?.category_values ?? [])],
  year_from: runtimeProfile.run_scope?.year_from ?? null,
  year_to: runtimeProfile.run_scope?.year_to ?? null,
  selected_doc_ids: [...(runtimeProfile.run_scope?.selected_doc_ids ?? [])]
});

export const defaultExport = (runtimeProfile: WorkflowRuntimeProfile): ExportParameters => ({
  ...runtimeProfile.export,
  export_csv: runtimeProfile.export?.export_csv ?? true,
  export_xlsx: runtimeProfile.export?.export_xlsx ?? true,
  export_png: runtimeProfile.export?.export_png ?? true,
  export_html_report: runtimeProfile.export?.export_html_report ?? true,
  include_audit: runtimeProfile.export?.include_audit ?? true,
  chart_dpi: runtimeProfile.export?.chart_dpi ?? 320,
  watermark_enabled: runtimeProfile.export?.watermark_enabled ?? false,
  watermark_text: runtimeProfile.export?.watermark_text ?? "TextFlow Studio"
});

function cloneDefinitions(definitions: RegisteredWorkflowNodeDefinition[]): RegisteredWorkflowNodeDefinition[] {
  return definitions.map((definition) => ({
    ...definition,
    inputs: definition.inputs.map((port) => ({ ...port })),
    outputs: definition.outputs.map((port) => ({ ...port })),
    params: definition.params.map((param) => ({
      ...param,
      options: param.options?.map((option) => ({ ...option }))
    })),
    runtime: { ...definition.runtime },
    graph: definition.graph
      ? {
          size: { ...definition.graph.size },
          default_position: { ...definition.graph.default_position },
          toolbox_order: definition.graph.toolbox_order,
          starter_roles: definition.graph.starter_roles ? [...definition.graph.starter_roles] : undefined
        }
      : undefined,
    ui: definition.ui
      ? {
          ...definition.ui,
          layout: definition.ui.layout.map((widget) => ({ ...widget }))
        }
      : undefined
  }));
}

function derivePortCompatibility(definitions: RegisteredWorkflowNodeDefinition[]): WorkflowPortCompatibilityCatalog {
  const tableSources = new Set<WorkflowPortType>();
  const renderableSources = new Set<WorkflowPortType>();
  const outputTypes = new Set<WorkflowPortType>();

  for (const definition of definitions) {
    for (const port of definition.outputs as WorkflowCatalogPort[]) {
      outputTypes.add(port.port_type);
      if (port.result_bundle_key || port.port_type === "AnyTable") {
        tableSources.add(port.port_type);
      }
      if (port.png_chart_ids?.length || port.port_type === "AnyRenderable") {
        renderableSources.add(port.port_type);
      }
    }
  }

  if (outputTypes.has("AnalysisBundle")) {
    renderableSources.add("AnalysisBundle");
  }

  const analysisResultSources = new Set<WorkflowPortType>(tableSources);
  if (outputTypes.has("AnalysisBundle")) {
    analysisResultSources.add("AnalysisBundle");
  }

  return {
    table_sources: [...tableSources],
    renderable_sources: [...renderableSources],
    analysis_result_sources: [...analysisResultSources],
    corpus_order: [...derivedPortCompatibilityFallback.corpus_order]
  };
}

export function configureWorkflowNodeCatalog(
  definitions: RegisteredWorkflowNodeDefinition[],
  portCompatibility?: WorkflowPortCompatibilityCatalog
): void {
  configuredDefinitions = cloneDefinitions(definitions);
  configuredDefinitionsByType = new Map(configuredDefinitions.map((definition) => [definition.type, definition]));
  configuredPortCompatibility = portCompatibility
    ? {
        table_sources: [...portCompatibility.table_sources],
        renderable_sources: [...portCompatibility.renderable_sources],
        analysis_result_sources: [...portCompatibility.analysis_result_sources],
        corpus_order: [...portCompatibility.corpus_order]
      }
    : derivePortCompatibility(configuredDefinitions);
}

export function workflowNodeDefinitions(): RegisteredWorkflowNodeDefinition[] {
  return cloneDefinitions(configuredDefinitions);
}

export function workflowNodeDefinition(nodeType: WorkflowNodeType): RegisteredWorkflowNodeDefinition | null {
  return configuredDefinitionsByType.get(nodeType) ?? null;
}

export function workflowNodeFrameForType(nodeType: WorkflowNodeType): { w: number; h: number } {
  const size = workflowNodeDefinition(nodeType)?.graph?.size;
  return size ? { ...size } : { ...fallbackFrame };
}

export function workflowNodeDefaultPosition(nodeType: WorkflowNodeType): { x: number; y: number } {
  const position = workflowNodeDefinition(nodeType)?.graph?.default_position;
  return position ? { ...position } : { ...fallbackPosition };
}

export function workflowNodeDefaultConfig(
  definition: RegisteredWorkflowNodeDefinition | null | undefined
): Record<string, unknown> {
  return (definition?.params ?? []).reduce<Record<string, unknown>>((config, param) => {
    if (param.default_value !== undefined) {
      config[param.param_id] = structuredClone(param.default_value);
    }
    return config;
  }, {});
}

export function workflowToolboxDefinitions(): RegisteredWorkflowNodeDefinition[] {
  return workflowNodeDefinitions()
    .filter((definition) => !definition.hidden_from_toolbox)
    .sort((left, right) =>
      (left.graph?.toolbox_order ?? 1000) - (right.graph?.toolbox_order ?? 1000)
      || left.category.localeCompare(right.category)
      || left.title.localeCompare(right.title, "zh-CN")
    );
}

export function workflowNodeDefinitionForRuntime(nodeType: WorkflowNodeType): WorkflowNodeDefinition | null {
  const definition = workflowNodeDefinition(nodeType);
  if (!definition) {
    return null;
  }
  return {
    label: definition.title,
    description: definition.description ?? "",
    category: definition.category,
    hidden_from_toolbox: definition.hidden_from_toolbox,
    singleton: definition.singleton,
    inputs: definition.inputs.map((port) => ({ ...port })),
    outputs: definition.outputs.map((port) => ({ ...port })),
    stepId: definition.runtime.step_id,
    size: definition.graph?.size ? { ...definition.graph.size } : { ...fallbackFrame },
    defaultPosition: definition.graph?.default_position ? { ...definition.graph.default_position } : { ...fallbackPosition },
    defaultConfig: () => workflowNodeDefaultConfig(definition),
    registeredDefinition: definition
  };
}

export function sinkNodeTypes(): Set<WorkflowNodeType> {
  return new Set(
    configuredDefinitions
      .filter((definition) => definition.runtime.output_node)
      .map((definition) => definition.type)
  );
}

export function portCompatibilityRules(): WorkflowPortCompatibilityCatalog {
  return {
    table_sources: [...configuredPortCompatibility.table_sources],
    renderable_sources: [...configuredPortCompatibility.renderable_sources],
    analysis_result_sources: [...configuredPortCompatibility.analysis_result_sources],
    corpus_order: [...configuredPortCompatibility.corpus_order]
  };
}

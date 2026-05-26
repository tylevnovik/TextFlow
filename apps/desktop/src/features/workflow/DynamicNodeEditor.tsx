import type { ReactNode } from "react";
import type { RegisteredWorkflowNodeDefinition, WorkflowNodeLayoutWidget } from "@textflow/shared-types";
import type { WorkflowNodeEditorContext } from "../../workflowNodeRegistry";
import { workflowConditionVisible } from "./workflowLayoutConditions";
import { workflowSlotHandledConfigKeys, workflowSlotRenderers } from "./workflowSlots";

interface DynamicNodeEditorProps {
  context: WorkflowNodeEditorContext;
  definition?: RegisteredWorkflowNodeDefinition;
}

function valueFor(context: WorkflowNodeEditorContext, widget: WorkflowNodeLayoutWidget): unknown {
  return widget.config_key ? context.node.config[widget.config_key] : undefined;
}

function updateConfig(context: WorkflowNodeEditorContext, widget: WorkflowNodeLayoutWidget, value: unknown) {
  if (!widget.config_key) {
    return;
  }
  context.updateNodeConfig(context.node.node_id, { [widget.config_key]: value });
}

function textFromList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).join(", ") : String(value ?? "");
}

function listFromText(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function handledConfigKeysFromLayout(widgets: WorkflowNodeLayoutWidget[] | undefined): Set<string> {
  const keys = new Set<string>();
  for (const widget of widgets ?? []) {
    if (widget.config_key) {
      keys.add(widget.config_key);
    }
    if (widget.widget === "slot" && widget.component_id) {
      for (const key of workflowSlotHandledConfigKeys[widget.component_id] ?? []) {
        keys.add(key);
      }
    }
    for (const key of handledConfigKeysFromLayout(widget.children)) {
      keys.add(key);
    }
  }
  return keys;
}

function renderFallbackParam(
  context: WorkflowNodeEditorContext,
  param: RegisteredWorkflowNodeDefinition["params"][number]
): ReactNode {
  const value = context.node.config[param.param_id] ?? param.default_value ?? null;

  if (param.kind === "boolean") {
    return (
      <label key={`param-${param.param_id}`} className="switch-row compact">
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
      <label key={`param-${param.param_id}`} className="field compact">
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
      <label key={`param-${param.param_id}`} className="field compact">
        <span>{param.label}</span>
        <input
          type="number"
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(event) => context.updateNodeConfig(context.node.node_id, {
            [param.param_id]: event.target.value === "" ? null : Number(event.target.value)
          })}
          disabled={context.loading}
        />
      </label>
    );
  }

  return (
    <label key={`param-${param.param_id}`} className="field compact">
      <span>{param.label}</span>
      <input
        value={String(value ?? "")}
        onChange={(event) => context.updateNodeConfig(context.node.node_id, { [param.param_id]: event.target.value })}
        disabled={context.loading}
      />
    </label>
  );
}

function renderWidget(
  context: WorkflowNodeEditorContext,
  definition: RegisteredWorkflowNodeDefinition,
  widget: WorkflowNodeLayoutWidget,
  index: number
): ReactNode {
  if (!workflowConditionVisible(widget.condition, context.node.config)) {
    return null;
  }

  const key = `${widget.widget}-${widget.config_key ?? widget.component_id ?? index}`;
  const label = widget.label ?? widget.config_key ?? widget.widget;
  const value = valueFor(context, widget);

  if (widget.widget === "group") {
    return (
      <div key={key} className="workflow-node-inline-pill-block">
        {widget.label && <strong>{widget.label}</strong>}
        {widget.description && <small>{widget.description}</small>}
        {widget.children?.map((child, childIndex) => renderWidget(context, definition, child, childIndex))}
      </div>
    );
  }

  if (widget.widget === "row") {
    return (
      <div key={key} className="workflow-node-inline-editor-grid">
        {widget.children?.map((child, childIndex) => renderWidget(context, definition, child, childIndex))}
      </div>
    );
  }

  if (widget.widget === "help") {
    return <small key={key}>{widget.description ?? widget.label ?? ""}</small>;
  }

  if (widget.widget === "slot") {
    const renderer = widget.component_id ? workflowSlotRenderers[widget.component_id] : undefined;
    return (
      <div key={key}>
        {renderer
          ? renderer(context, widget)
          : <small>未注册的属性组件：{widget.component_id ?? "unknown"}</small>}
      </div>
    );
  }

  if (widget.widget === "switch") {
    return (
      <label key={key} className="switch-row compact">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => updateConfig(context, widget, event.target.checked)}
          disabled={context.loading}
        />
        <span>{label}</span>
      </label>
    );
  }

  if (widget.widget === "select") {
    const paramOptions = definition.params.find((param) => param.param_id === widget.config_key)?.options ?? [];
    const options = widget.options ?? paramOptions;
    return (
      <label key={key} className="field compact">
        <span>{label}</span>
        <select
          value={String(value ?? "")}
          onChange={(event) => updateConfig(context, widget, event.target.value)}
          disabled={context.loading}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
    );
  }

  if (widget.widget === "number") {
    return (
      <label key={key} className="field compact">
        <span>{label}</span>
        <input
          type="number"
          min={widget.min}
          max={widget.max}
          step={widget.step}
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(event) => updateConfig(context, widget, event.target.value === "" ? null : Number(event.target.value))}
          disabled={context.loading}
        />
      </label>
    );
  }

  if (widget.widget === "textarea" || widget.widget === "condition_rows" || widget.widget === "key_value_rows") {
    return (
      <label key={key} className="field compact">
        <span>{label}</span>
        <textarea
          value={typeof value === "string" ? value : JSON.stringify(value ?? "", null, 2)}
          onChange={(event) => updateConfig(context, widget, event.target.value)}
          disabled={context.loading}
          rows={4}
        />
      </label>
    );
  }

  if (widget.widget === "multi_text") {
    return (
      <label key={key} className="field compact">
        <span>{label}</span>
        <input
          value={textFromList(value)}
          onChange={(event) => updateConfig(context, widget, listFromText(event.target.value))}
          disabled={context.loading}
        />
      </label>
    );
  }

  return (
    <label key={key} className="field compact">
      <span>{label}</span>
      <input
        value={String(value ?? "")}
        onChange={(event) => updateConfig(context, widget, event.target.value)}
        disabled={context.loading}
      />
    </label>
  );
}

export function DynamicNodeEditor({ context, definition }: DynamicNodeEditorProps) {
  if (!definition) {
    return <small>节点定义尚未加载</small>;
  }

  const handledConfigKeys = handledConfigKeysFromLayout(definition.ui?.layout);
  const fallbackParams = definition.params.filter((param) => !handledConfigKeys.has(param.param_id));
  if (!definition.ui?.layout?.length && !fallbackParams.length) {
    return <small>该节点没有可编辑参数</small>;
  }

  return (
    <div className="workflow-node-inline-editor-grid">
      {definition.ui?.layout?.map((widget, index) => renderWidget(context, definition, widget, index))}
      {fallbackParams.map((param) => renderFallbackParam(context, param))}
    </div>
  );
}

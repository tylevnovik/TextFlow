import type { WorkflowLayoutCondition } from "@textflow/shared-types";

export function workflowConditionVisible(
  condition: WorkflowLayoutCondition | undefined,
  config: Record<string, unknown>
): boolean {
  if (!condition) {
    return true;
  }
  const value = config[condition.field];
  switch (condition.op) {
    case "eq":
      return value === condition.value;
    case "neq":
      return value !== condition.value;
    case "in":
      return Array.isArray(condition.value) && condition.value.includes(value);
    case "not_in":
      return Array.isArray(condition.value) && !condition.value.includes(value);
    case "truthy":
      return Boolean(value);
    case "falsy":
      return !value;
    default:
      return false;
  }
}

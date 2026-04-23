import type { ProjectManifest, ReviewTask as SharedReviewTask } from "@textflow/shared-types";

export type ReviewTaskType =
  | "keyword_merge"
  | "institution_merge"
  | "cluster_rename"
  | "document_patch"
  | "dictionary_patch";

export type ReviewDecision = "resolve" | "reject";

export interface ReviewResolutionInput {
  decision: ReviewDecision;
  notes?: string;
  dictionary_kind?: string;
  source_term?: string;
  target_term?: string;
  doc_id?: string;
  doc_ids?: string[];
  canonical_institution?: string;
  source_values?: string[];
  cluster_id?: string;
  label?: string;
  new_label?: string;
  entries?: Array<Record<string, unknown>>;
  document_patch?: Record<string, unknown>;
}

export interface ReviewResolutionRecord extends ReviewResolutionInput {
  applied_changes?: string[];
  resolved_at?: string;
}

export interface ReviewTaskRecord extends Omit<SharedReviewTask, "review_type"> {
  review_type: ReviewTaskType | string;
  title?: string;
  description?: string;
  payload?: Record<string, unknown>;
  resolution?: ReviewResolutionRecord;
  created_at?: string;
  updated_at?: string;
  resolved_at?: string;
}

export function coerceReviewTasks(project?: ProjectManifest | null): ReviewTaskRecord[] {
  if (!project || !Array.isArray(project.review_tasks)) {
    return [];
  }
  return project.review_tasks as unknown as ReviewTaskRecord[];
}

export function reviewTaskStatusLabel(task: ReviewTaskRecord): string {
  if (task.status === "resolved" && task.resolution?.decision === "reject") {
    return "Rejected";
  }
  if (task.status === "resolved") {
    return "Resolved";
  }
  return "Open";
}

export function reviewTaskSummary(task: ReviewTaskRecord): string {
  if (task.description?.trim()) {
    return task.description.trim();
  }
  if (task.review_type === "keyword_merge") {
    return `${task.target_ref.source_term ?? "待合并项"} -> ${task.target_ref.target_term ?? "目标词"}`;
  }
  if (task.review_type === "document_patch") {
    return `文档 ${task.target_ref.doc_id ?? "未指定"} 等待写回修订。`;
  }
  if (task.review_type === "institution_merge") {
    return `机构字段将统一为 ${(task.payload?.canonical_institution as string | undefined) ?? "目标机构名"}`;
  }
  if (task.review_type === "cluster_rename") {
    return `聚类 ${(task.target_ref.cluster_id ?? "未指定")} 等待命名。`;
  }
  return "等待人工复核后决定是否写回项目。";
}

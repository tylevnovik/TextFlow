import type { ArtifactRecord, RunArtifactSummary } from "@textflow/shared-types";

export function isRunArtifactHandle(artifact: RunArtifactSummary): artifact is ArtifactRecord {
  return "artifact_id" in artifact || "node_id" in artifact || "path" in artifact || "kind" in artifact;
}

export function runArtifactKey(artifact: RunArtifactSummary, index: number): string {
  if (isRunArtifactHandle(artifact)) {
    return artifact.artifact_id || artifact.node_id || artifact.path || `artifact-${index}`;
  }
  return artifact.step || `step-${index}`;
}

export function runArtifactRowCount(artifact: RunArtifactSummary): number {
  return isRunArtifactHandle(artifact) ? artifact.row_count ?? 0 : artifact.record_count ?? 0;
}

export function runArtifactSummaryLabel(artifact: RunArtifactSummary): string {
  if (isRunArtifactHandle(artifact)) {
    return `${artifact.node_id || artifact.artifact_id || "artifact"} · ${artifact.kind || "artifact"}`;
  }
  return artifact.step;
}

export function runArtifactSummaryDetail(artifact: RunArtifactSummary): string {
  if (isRunArtifactHandle(artifact)) {
    const parts = [`${runArtifactRowCount(artifact)} 行`];
    if (artifact.path) {
      parts.push(artifact.path);
    }
    return parts.join(" · ");
  }
  return `${artifact.output_files.length} 个文件`;
}

export function runArtifactCompactSummary(artifact: RunArtifactSummary): string {
  if (isRunArtifactHandle(artifact)) {
    return `${artifact.node_id || artifact.kind || artifact.artifact_id}:${runArtifactRowCount(artifact)}`;
  }
  return `${artifact.step}:${artifact.record_count}`;
}

import { useEffect, useState } from "react";
import { Button, Textarea } from "@fluentui/react-components";
import { Panel } from "../../ui";
import {
  reviewTaskStatusLabel,
  reviewTaskSummary,
  type ReviewResolutionInput,
  type ReviewTaskRecord
} from "./reviewTypes";

export interface ReviewQueuePanelProps {
  tasks: ReviewTaskRecord[];
  loading?: boolean;
  onResolve: (reviewId: string, resolution: ReviewResolutionInput) => Promise<void> | void;
  onReject: (reviewId: string, resolution: ReviewResolutionInput) => Promise<void> | void;
}

function taskSortValue(task: ReviewTaskRecord): number {
  return task.status === "open" ? 0 : 1;
}

export function ReviewQueuePanel({ tasks, loading = false, onResolve, onReject }: ReviewQueuePanelProps) {
  const orderedTasks = [...tasks].sort((left, right) => {
    const statusDiff = taskSortValue(left) - taskSortValue(right);
    if (statusDiff !== 0) {
      return statusDiff;
    }
    return String(right.updated_at ?? "").localeCompare(String(left.updated_at ?? ""));
  });
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(orderedTasks[0]?.review_id ?? null);
  const [notes, setNotes] = useState("");
  const [pendingDecision, setPendingDecision] = useState<"resolve" | "reject" | null>(null);

  useEffect(() => {
    if (!orderedTasks.length) {
      setSelectedReviewId(null);
      return;
    }
    if (!selectedReviewId || !orderedTasks.some((task) => task.review_id === selectedReviewId)) {
      setSelectedReviewId(orderedTasks[0].review_id);
    }
  }, [orderedTasks, selectedReviewId]);

  const selectedTask = orderedTasks.find((task) => task.review_id === selectedReviewId) ?? null;
  const openCount = orderedTasks.filter((task) => task.status === "open").length;

  const handleDecision = async (decision: "resolve" | "reject") => {
    if (!selectedTask) {
      return;
    }
    setPendingDecision(decision);
    const payload: ReviewResolutionInput = {
      decision,
      notes: notes.trim() || undefined
    };
    try {
      if (decision === "resolve") {
        await onResolve(selectedTask.review_id, payload);
      } else {
        await onReject(selectedTask.review_id, payload);
      }
      setNotes("");
    } finally {
      setPendingDecision(null);
    }
  };

  return (
    <Panel
      title="Review Queue"
      actions={
        <span className="muted">
          {orderedTasks.length} 项任务，{openCount} 项待处理
        </span>
      }
    >
      {!orderedTasks.length ? (
        <div className="status-panel">
          <strong>当前没有待处理复核任务</strong>
          <span className="muted">后续从关键词、机构名或文档修订入口创建任务后，这里会显示队列与写回结果。</span>
        </div>
      ) : (
        <div className="two-column">
          <div className="stack-list">
            {orderedTasks.map((task) => (
              <Button
                appearance="subtle"
                key={task.review_id}
                className={`project-card ${task.review_id === selectedReviewId ? "is-selected" : ""}`}
                onClick={() => setSelectedReviewId(task.review_id)}
                disabled={loading || pendingDecision !== null}
              >
                <div className="run-head">
                  <strong>{task.title ?? task.review_id}</strong>
                  <span className={`badge ${task.status === "open" ? "running" : "completed"}`}>
                    {reviewTaskStatusLabel(task)}
                  </span>
                </div>
                <p className="muted">{task.review_type}</p>
                <p>{reviewTaskSummary(task)}</p>
              </Button>
            ))}
          </div>
          <div className="stack-list">
            {selectedTask ? (
              <>
                <div className="status-panel">
                  <strong>{selectedTask.title ?? selectedTask.review_id}</strong>
                  <span>{reviewTaskSummary(selectedTask)}</span>
                </div>
                <div className="status-panel">
                  <strong>Target</strong>
                  <ul className="micro-list">
                    {Object.entries(selectedTask.target_ref ?? {}).map(([key, value]) => (
                      <li key={`${selectedTask.review_id}-${key}`}>{key}: {value}</li>
                    ))}
                    {!Object.keys(selectedTask.target_ref ?? {}).length && <li>当前任务没有额外 target_ref。</li>}
                  </ul>
                </div>
                <div className="status-panel">
                  <strong>Payload</strong>
                  <pre>{JSON.stringify(selectedTask.payload ?? {}, null, 2)}</pre>
                </div>
                <label className="search-box">
                  <span>处理备注</span>
                  <Textarea
                    value={notes}
                    onChange={(_, data) => setNotes(data.value)}
                    rows={4}
                    placeholder="例如：确认写入项目自定义词表，不改内置词库。"
                    disabled={loading || pendingDecision !== null}
                  />
                </label>
                <div className="button-row">
                  <Button
                    appearance="primary"
                    onClick={() => void handleDecision("resolve")}
                    disabled={loading || pendingDecision !== null || selectedTask.status !== "open"}
                  >
                    Resolve
                  </Button>
                  <Button
                    appearance="subtle"
                    onClick={() => void handleDecision("reject")}
                    disabled={loading || pendingDecision !== null || selectedTask.status !== "open"}
                  >
                    Reject
                  </Button>
                </div>
                {selectedTask.resolution && (
                  <div className="status-panel">
                    <strong>最近一次处理结果</strong>
                    <span>
                      {selectedTask.resolution.decision === "reject" ? "已拒绝写回。" : "已写回项目。"}
                    </span>
                    {!!selectedTask.resolution.applied_changes?.length && (
                      <ul className="micro-list">
                        {selectedTask.resolution.applied_changes.map((item) => (
                          <li key={`${selectedTask.review_id}-${item}`}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="status-panel">
                <strong>请选择一个复核任务</strong>
                <span className="muted">队列详情会显示 target_ref、payload，以及写回或拒绝操作。</span>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

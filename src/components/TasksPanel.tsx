import { useEffect, useMemo, useState } from "react";

const BACKEND_URL = "http://localhost:8000";

type TaskSummary = {
  id: string;
  title: string;
  summary: string;
  prompt: string;
  task_class: string;
  execution_domain: string;
  reporting_target: string;
  approval_scope: string;
  assigned_executor: string;
  result_channel: string;
  risk_level: string;
  next_suggested_action: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type TaskStep = {
  id: string;
  title: string;
  description: string;
  tool_id: string | null;
  risk_level: string;
  approval_required: number;
  depends_on_step_id: string | null;
  status: string;
  payload_json: Record<string, unknown>;
  rollback_note: string | null;
};

type Approval = {
  id: string;
  step_id: string;
  label: string;
  target: string;
  tool_name: string;
  risk_level: string;
  approval_scope: string;
  reason: string;
  rollback_note: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type TimelineEvent = {
  kind: string;
  timestamp: string;
  title: string;
  detail: string;
};

type ToolDefinition = {
  name: string;
  description: string;
  risk_level: string;
  approval_required: boolean;
  executor_type: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  rollback_hint: string;
};

type ExecutorDefinition = {
  id: string;
  role: string;
  capabilities: string[];
  health: string;
  supported_task_types: string[];
  execution_mode: string;
};

type TaskDetail = {
  task: TaskSummary;
  steps: TaskStep[];
  approvals: Approval[];
  timeline: TimelineEvent[];
  next_suggested_action: string;
  agent_state?: {
    active_role: string;
    summary: string;
    agents: { role: string; state: string }[];
  };
};

interface TasksPanelProps {
  initialTaskId?: string | null;
}

export default function TasksPanel({ initialTaskId = null }: TasksPanelProps) {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(initialTaskId);
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [executors, setExecutors] = useState<ExecutorDefinition[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refreshTasks = async () => {
    const [taskRes, toolRes, executorRes] = await Promise.all([
      fetch(`${BACKEND_URL}/v1/tasks?task_kind=workflow_task`),
      fetch(`${BACKEND_URL}/v1/tools`),
      fetch(`${BACKEND_URL}/v1/executors`),
    ]);
    const taskData = await taskRes.json();
    const toolData = await toolRes.json();
    const executorData = await executorRes.json();
    const nextTasks = taskData.tasks ?? [];
    setTasks(nextTasks);
    setTools(toolData.tools ?? []);
    setExecutors(executorData.executors ?? []);
    if (!selectedTaskId && nextTasks.length > 0) {
      setSelectedTaskId(nextTasks[0].id);
    }
  };

  const refreshDetail = async (taskId: string) => {
    const res = await fetch(`${BACKEND_URL}/v1/tasks/${taskId}`);
    const data = await res.json();
    setTaskDetail(data);
  };

  useEffect(() => {
    refreshTasks().catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (initialTaskId) {
      setSelectedTaskId(initialTaskId);
    }
  }, [initialTaskId]);

  useEffect(() => {
    if (!selectedTaskId) {
      setTaskDetail(null);
      return;
    }
    refreshDetail(selectedTaskId).catch((e) => setError(String(e)));
  }, [selectedTaskId]);

  useEffect(() => {
    const interval = setInterval(() => {
      refreshTasks().catch(() => {});
      if (selectedTaskId) refreshDetail(selectedTaskId).catch(() => {});
    }, 4000);
    return () => clearInterval(interval);
  }, [selectedTaskId]);

  const activeTasks = useMemo(
    () => tasks.filter((task) => !["completed", "failed", "rejected"].includes(task.status)),
    [tasks]
  );
  const completedTasks = useMemo(
    () => tasks.filter((task) => ["completed", "failed", "rejected"].includes(task.status)),
    [tasks]
  );
  const pendingApprovals = useMemo(
    () => taskDetail?.approvals.filter((approval) => approval.status === "pending") ?? [],
    [taskDetail]
  );
  const resolvedApprovals = useMemo(
    () => taskDetail?.approvals.filter((approval) => approval.status !== "pending") ?? [],
    [taskDetail]
  );

  const createTask = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/v1/tasks/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Could not create task.");
      setPrompt("");
      await refreshTasks();
      setSelectedTaskId(data.task.id);
      setTaskDetail(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const resolveApproval = async (approvalId: string, approved: boolean) => {
    if (!taskDetail) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/v1/tasks/${taskDetail.task.id}/approvals/${approvalId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Could not resolve approval.");
      setTaskDetail(data);
      await refreshTasks();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const retryStep = async (stepId: string) => {
    if (!taskDetail) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/v1/tasks/${taskDetail.task.id}/steps/${stepId}/retry`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Could not retry step.");
      setTaskDetail(data);
      await refreshTasks();
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const renderTaskList = (items: TaskSummary[], emptyText: string) => (
    <div className="task-list-group">
      {items.length > 0 ? (
        items.map((task) => (
          <button
            key={task.id}
            className={`task-list-item${selectedTaskId === task.id ? " active" : ""}`}
            onClick={() => setSelectedTaskId(task.id)}
          >
            <div className="task-list-top">
              <div className="task-list-title">{task.title}</div>
              <span className={`task-risk risk-${task.risk_level}`}>{task.risk_level}</span>
            </div>
            <div className="task-list-meta">{task.status} / {task.assigned_executor}</div>
          </button>
        ))
      ) : (
        <div className="tasks-empty">{emptyText}</div>
      )}
    </div>
  );

  return (
    <div className="tasks-panel">
      <div className="tasks-header">
        <div>
          <h2>Workflows</h2>
          <div className="tasks-subtitle">Repo, executor, and delegated work outside the local support lane.</div>
        </div>
      </div>

      <div className="tasks-create">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe a workflow. Oxy will plan reads first and hold writes or boundaries for approval."
          rows={3}
        />
        <button onClick={createTask} disabled={loading || !prompt.trim()}>
          {loading ? "Working…" : "Create Workflow"}
        </button>
      </div>

      {error && <div className="tasks-error">{error}</div>}

      <div className="tasks-layout">
        <aside className="tasks-list">
          <div className="tasks-section-title">Active</div>
          {renderTaskList(activeTasks, "No active tasks.")}
          <div className="tasks-section-title tasks-section-gap">Completed</div>
          {renderTaskList(completedTasks, "No completed tasks.")}
        </aside>

        <section className="task-detail">
          {taskDetail ? (
            <>
              <div className="tasks-section-title">Workflow</div>
              <div className="task-card">
                <div className="task-status-row">
                  <span className="task-pill">{taskDetail.task.status}</span>
                  <span className={`task-risk risk-${taskDetail.task.risk_level}`}>{taskDetail.task.risk_level}</span>
                </div>
                <div className="task-prompt">{taskDetail.task.prompt}</div>
                <div className="task-summary">{taskDetail.task.summary}</div>
                <div className="task-next">
                  {taskDetail.task.task_class} / {taskDetail.task.execution_domain} / {taskDetail.task.assigned_executor}
                </div>
                <div className="task-next">
                  Reporting: {taskDetail.task.reporting_target} / Approval: {taskDetail.task.approval_scope}
                </div>
                {taskDetail.agent_state && (
                  <div className="task-next">
                    Agents: {taskDetail.agent_state.active_role} / {taskDetail.agent_state.summary}
                  </div>
                )}
                <div className="task-next">Next: {taskDetail.next_suggested_action}</div>
              </div>

              <div className="tasks-section-title">Steps</div>
              <div className="task-steps">
                {taskDetail.steps.map((step) => (
                  <div key={step.id} className="task-step">
                    <div className="task-step-top">
                      <strong>{step.title}</strong>
                      <span className={`task-step-status status-${step.status}`}>{step.status}</span>
                    </div>
                    <div className="task-step-desc">{step.description}</div>
                    <div className="task-step-meta">
                      Tool: {step.tool_id ?? "rust.delegate"} | Risk:{" "}
                      <span className={`task-risk risk-${step.risk_level}`}>{step.risk_level}</span>
                    </div>
                    {step.rollback_note && <div className="task-step-rollback">Rollback: {step.rollback_note}</div>}
                    {step.status === "failed" && step.risk_level === "read" && (
                      <button className="task-retry-button" onClick={() => retryStep(step.id)} disabled={loading}>
                        Retry Read Step
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="tasks-section-title">Pending Approvals</div>
              <div className="task-card">
                {pendingApprovals.length > 0 ? (
                  pendingApprovals.map((approval) => (
                    <div key={approval.id} className="approval-row">
                      <div>
                        <div className="approval-title">{approval.label}</div>
                        <div className="approval-meta">
                          {approval.tool_name} {"->"} {approval.target}
                        </div>
                        <div className="approval-meta">Scope: {approval.approval_scope}</div>
                        <div className="approval-meta">{approval.reason}</div>
                        {approval.rollback_note && <div className="approval-meta">Rollback: {approval.rollback_note}</div>}
                      </div>
                      <div className="approval-actions">
                        <button onClick={() => resolveApproval(approval.id, true)} disabled={loading}>Approve</button>
                        <button onClick={() => resolveApproval(approval.id, false)} disabled={loading}>Reject</button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="tasks-empty">No pending approvals.</div>
                )}
              </div>

              <div className="tasks-section-title">Resolved Approvals</div>
              <div className="task-card">
                {resolvedApprovals.length > 0 ? (
                  resolvedApprovals.map((approval) => (
                    <div key={approval.id} className="approval-row approval-row-resolved">
                      <div>
                        <div className="approval-title">{approval.label}</div>
                        <div className="approval-meta">{approval.status}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="tasks-empty">No resolved approvals yet.</div>
                )}
              </div>

              <div className="tasks-section-title">Timeline</div>
              <div className="task-card timeline-card">
                {taskDetail.timeline.length > 0 ? (
                  taskDetail.timeline.map((event, index) => (
                    <div key={`${event.kind}-${event.timestamp}-${index}`} className="timeline-event">
                      <div className={`timeline-dot timeline-${event.kind}`} />
                      <div>
                        <div className="timeline-title">
                          {event.title} <span className="timeline-kind">{event.kind}</span>
                        </div>
                        <div className="timeline-detail">{event.detail}</div>
                        <div className="timeline-time">{event.timestamp}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="tasks-empty">No timeline events yet.</div>
                )}
              </div>
            </>
          ) : (
            <div className="tasks-empty">Select a workflow to inspect steps, approvals, and timeline.</div>
          )}
        </section>

        <aside className="tasks-tools">
          <div className="tasks-section-title">Tool Registry</div>
          <div className="task-card">
            {tools.map((tool) => (
              <div key={tool.name} className="tool-row">
                <div className="tool-name">{tool.name}</div>
                <div className="tool-meta">{tool.description}</div>
                <div className="tool-meta">
                  Risk: {tool.risk_level} | Approval: {tool.approval_required ? "yes" : "no"} | Executor: {tool.executor_type}
                </div>
              </div>
            ))}
          </div>
          <div className="tasks-section-title tasks-section-gap">Executors</div>
          <div className="task-card">
            {executors.map((executor) => (
              <div key={executor.id} className="tool-row">
                <div className="tool-name">{executor.id}</div>
                <div className="tool-meta">{executor.role}</div>
                <div className="tool-meta">
                  Mode: {executor.execution_mode} | Health: {executor.health}
                </div>
                <div className="tool-meta">Tasks: {executor.supported_task_types.join(", ")}</div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

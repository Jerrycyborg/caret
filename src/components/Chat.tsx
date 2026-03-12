import { useState, useRef, useEffect } from "react";
import ModelSelector from "./ModelSelector";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatProps {
  conversationId: string | null;
  onConversationCreated: (id: string) => void;
  onConversationUpdated: () => void;
  onOpenTask: (id: string, taskKind?: string) => void;
}

interface TaskHandoff {
  task_id: string;
  title: string;
  summary: string;
  task_kind: string;
  task_class: string;
  execution_domain: string;
  assigned_executor: string;
  risk_level: string;
  status: string;
  next_suggested_action: string;
  result_summary?: string;
  agent_state?: {
    active_role: string;
    summary: string;
  };
  task_report?: {
    status: string;
    headline: string;
    details: string[];
  };
}

interface ConversationMeta {
  channel_type: string;
  session_status: string;
  last_executor?: string;
  last_agent_state?: string;
}

const BACKEND_URL = "http://localhost:8000";

export default function Chat({
  conversationId,
  onConversationCreated,
  onConversationUpdated,
  onOpenTask,
}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState("ollama/llama3.2");
  const [isStreaming, setIsStreaming] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [taskHandoff, setTaskHandoff] = useState<TaskHandoff | null>(null);
  const [conversationMeta, setConversationMeta] = useState<ConversationMeta | null>(null);
  const activeConvRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetch(`${BACKEND_URL}/health`)
      .then((r) => r.ok && setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  // Load history when conversation changes
  useEffect(() => {
    activeConvRef.current = conversationId;
    if (!conversationId) {
      setMessages([]);
      setTaskHandoff(null);
      setConversationMeta(null);
      return;
    }
    fetch(`${BACKEND_URL}/v1/conversations/${conversationId}`)
      .then((r) => r.json())
      .then((data) => {
        if (activeConvRef.current !== conversationId) return;
        if (data.model) setModel(data.model);
        setConversationMeta({
          channel_type: data.channel_type ?? "desktop",
          session_status: data.session_status ?? "active",
          last_executor: data.last_executor ?? "",
          last_agent_state: data.last_agent_state ?? "",
        });
        setMessages(
          (data.messages ?? []).map((m: { id: string; role: "user" | "assistant"; content: string }) => ({
            id: m.id,
            role: m.role,
            content: m.content,
          }))
        );
      })
      .catch(() => {});
  }, [conversationId]);

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return;
    const text = input.trim();
    let convId = conversationId;

    if (!convId) {
      try {
        const res = await fetch(`${BACKEND_URL}/v1/conversations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: text.slice(0, 48) + (text.length > 48 ? "\u2026" : ""),
            model,
          }),
        });
        const data = await res.json();
        convId = data.id;
        onConversationCreated(convId!);
        activeConvRef.current = convId;
      } catch {
        setBackendOnline(false);
        return;
      }
    }

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: text };
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }]);
    setInput("");
    setIsStreaming(true);
    setTaskHandoff(null);

    try {
      const response = await fetch(`${BACKEND_URL}/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: [...messages, userMsg].map((m) => ({ role: m.role, content: m.content })),
          stream: true,
          conversation_id: convId,
        }),
      });

      if (!response.ok) throw new Error(`Backend returned ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder
          .decode(value)
          .split("\n")
          .filter((l) => l.startsWith("data: "));
        for (const line of lines) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            onConversationUpdated();
            break;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + parsed.content } : m
                )
              );
            }
            if (parsed.task_handoff) {
              setTaskHandoff(parsed.task_handoff);
            }
          } catch {
            // skip malformed chunks
          }
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content:
                  "Could not reach the Caret backend. Make sure the local assistant service is running on port 8000.\n\nRun: `npm run backend`",
              }
            : m
        )
      );
      setBackendOnline(false);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-header">
        <ModelSelector value={model} onChange={setModel} />
        {conversationMeta && (
          <span className="session-chip">
            {conversationMeta.channel_type} / {conversationMeta.session_status}
            {conversationMeta.last_executor ? ` / ${conversationMeta.last_executor}` : ""}
          </span>
        )}
        {backendOnline !== null && (
          <span className={`backend-status ${backendOnline ? "online" : "offline"}`}>
            {backendOnline ? "● Backend online" : "● Backend offline"}
          </span>
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-logo">OXY</div>
            <p>Your AI-powered personal OS assistant.</p>
            <p className="chat-empty-hint">
              Ask anything, give me a task, or explore the panels on the left.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <div className="message-role">{msg.role === "user" ? "You" : "Caret"}</div>
            <div className="message-content">
              {msg.content || <span className="typing">▋</span>}
            </div>
          </div>
        ))}
        {taskHandoff && (
          <div className="chat-task-handoff">
            <div className="chat-task-top">
              <strong>{taskHandoff.title}</strong>
              <span className={`task-risk risk-${taskHandoff.risk_level}`}>{taskHandoff.risk_level}</span>
            </div>
            <div className="chat-task-body">
              {taskHandoff.task_class} / {taskHandoff.execution_domain}
            </div>
            <div className="chat-task-body">{taskHandoff.summary}</div>
            {taskHandoff.task_report?.headline && (
              <div className="chat-task-body"><strong>{taskHandoff.task_report.headline}</strong></div>
            )}
            {taskHandoff.task_report?.details?.map((detail) => (
              <div key={detail} className="chat-task-body">{detail}</div>
            ))}
            {taskHandoff.result_summary && (
              <div className="chat-task-body">{taskHandoff.result_summary}</div>
            )}
            {taskHandoff.agent_state && (
              <div className="chat-task-body">
                Agent: {taskHandoff.agent_state.active_role} / {taskHandoff.agent_state.summary}
              </div>
            )}
            <div className="chat-task-body">{taskHandoff.next_suggested_action}</div>
            <button className="chat-task-button" onClick={() => onOpenTask(taskHandoff.task_id, taskHandoff.task_kind)}>
              Open Support
            </button>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder="Ask Caret for help with your device\u2026 (Enter to send, Shift+Enter for newline)"
          rows={2}
          disabled={isStreaming}
        />
        <button
          className={`send-button${isStreaming ? " sending" : ""}`}
          onClick={sendMessage}
          disabled={isStreaming || !input.trim()}
        >
          {isStreaming ? "\u2026" : "Send"}
        </button>
      </div>
    </div>
  );
}

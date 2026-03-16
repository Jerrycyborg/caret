use serde::{Deserialize, Serialize};
use tauri::command;

#[derive(Clone, Serialize)]
pub struct ToolAdapterInfo {
    pub id: String,
    pub name: String,
    pub adapter_type: String,
    pub health: String,
    pub capabilities: Vec<String>,
    pub input_contract: String,
    pub output_contract: String,
    pub error_contract: String,
    pub orchestration_role: String,
}

#[derive(Clone, Serialize)]
pub struct ToolAdapterExecutionResult {
    pub status: String,
    pub adapter_id: String,
    pub output: Option<String>,
    pub error: Option<String>,
}

#[derive(Clone, Deserialize)]
pub struct ToolAdapterExecutionRequest {
    pub adapter_id: String,
    pub input: String,
}

trait ToolAdapter {
    fn info(&self) -> ToolAdapterInfo;
    fn execute(&self, input: &str) -> ToolAdapterExecutionResult;
}

struct BackendSidecarAdapter;
struct PluginRuntimeAdapter;

impl ToolAdapter for BackendSidecarAdapter {
    fn info(&self) -> ToolAdapterInfo {
        ToolAdapterInfo {
            id: "backend_sidecar".to_string(),
            name: "Backend Sidecar".to_string(),
            adapter_type: "service".to_string(),
            health: "unknown".to_string(),
            capabilities: vec![
                "chat_orchestration".to_string(),
                "model_selection".to_string(),
                "conversation_storage".to_string(),
                "settings_management".to_string(),
            ],
            input_contract: "structured request payloads over the local Caret backend API".to_string(),
            output_contract: "structured JSON responses and SSE streaming responses".to_string(),
            error_contract: "HTTP status plus structured backend error payloads".to_string(),
            orchestration_role: "Primary AI workflow backend".to_string(),
        }
    }

    fn execute(&self, _input: &str) -> ToolAdapterExecutionResult {
        ToolAdapterExecutionResult {
            status: "unsupported".to_string(),
            adapter_id: self.info().id,
            output: None,
            error: Some("Service-backed execution is not implemented through the local CLI adapter path.".to_string()),
        }
    }
}

impl ToolAdapter for PluginRuntimeAdapter {
    fn info(&self) -> ToolAdapterInfo {
        ToolAdapterInfo {
            id: "plugin_runtime".to_string(),
            name: "Plugin Runtime".to_string(),
            adapter_type: "in_process".to_string(),
            health: "healthy".to_string(),
            capabilities: vec![
                "plugin_discovery".to_string(),
                "plugin_install_state".to_string(),
                "plugin_execution".to_string(),
            ],
            input_contract: "typed Tauri command invocation with plugin name and structured parameters".to_string(),
            output_contract: "structured plugin metadata or plugin execution output".to_string(),
            error_contract: "typed invocation errors or validation failures".to_string(),
            orchestration_role: "Extensibility and local capability composition".to_string(),
        }
    }

    fn execute(&self, _input: &str) -> ToolAdapterExecutionResult {
        ToolAdapterExecutionResult {
            status: "unsupported".to_string(),
            adapter_id: self.info().id,
            output: None,
            error: Some("In-process plugin execution stays on the plugin runtime path.".to_string()),
        }
    }
}

fn adapter_registry() -> Vec<Box<dyn ToolAdapter>> {
    vec![
        Box::new(BackendSidecarAdapter),
        Box::new(PluginRuntimeAdapter),
    ]
}

#[command]
pub fn list_tool_adapters() -> Vec<ToolAdapterInfo> {
    adapter_registry().into_iter().map(|adapter| adapter.info()).collect()
}

#[command]
pub fn execute_tool_adapter(request: ToolAdapterExecutionRequest) -> ToolAdapterExecutionResult {
    for adapter in adapter_registry() {
        let info = adapter.info();
        if info.id == request.adapter_id {
            return adapter.execute(&request.input);
        }
    }

    ToolAdapterExecutionResult {
        status: "invalid_target".to_string(),
        adapter_id: request.adapter_id,
        output: None,
        error: Some("Unknown tool adapter id.".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::{list_tool_adapters, execute_tool_adapter, ToolAdapterExecutionRequest};

    #[test]
    fn registry_contains_backend_sidecar() {
        let adapters = list_tool_adapters();
        assert!(adapters.iter().any(|a| a.id == "backend_sidecar"));
    }

    #[test]
    fn unknown_adapter_returns_invalid_target() {
        let result = execute_tool_adapter(ToolAdapterExecutionRequest {
            adapter_id: "nonexistent".to_string(),
            input: "test".to_string(),
        });
        assert_eq!(result.status, "invalid_target");
    }
}

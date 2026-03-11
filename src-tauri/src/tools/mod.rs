use serde::{Deserialize, Serialize};
use std::path::Path;
use std::process::Command;
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
struct ReferenceCliAdapter;

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
            input_contract: "structured request payloads over the local Oxy backend API".to_string(),
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

impl ReferenceCliAdapter {
    fn binary_path() -> &'static str {
        "/usr/bin/printf"
    }

    fn is_available(&self) -> bool {
        Path::new(Self::binary_path()).exists()
    }
}

impl ToolAdapter for ReferenceCliAdapter {
    fn info(&self) -> ToolAdapterInfo {
        ToolAdapterInfo {
            id: "reference_cli".to_string(),
            name: "Reference CLI Adapter".to_string(),
            adapter_type: "local_cli".to_string(),
            health: if self.is_available() {
                "healthy".to_string()
            } else {
                "unavailable".to_string()
            },
            capabilities: vec![
                "availability_check".to_string(),
                "typed_input".to_string(),
                "structured_output".to_string(),
                "structured_failure".to_string(),
            ],
            input_contract: "single string payload passed to a local CLI adapter".to_string(),
            output_contract: "structured adapter execution result with output and adapter id".to_string(),
            error_contract: "structured execution failure with stable status codes".to_string(),
            orchestration_role: "Reference implementation for future local CLI tool adapters".to_string(),
        }
    }

    fn execute(&self, input: &str) -> ToolAdapterExecutionResult {
        if !self.is_available() {
            return ToolAdapterExecutionResult {
                status: "unavailable".to_string(),
                adapter_id: self.info().id,
                output: None,
                error: Some("Reference CLI binary is not available on this host.".to_string()),
            };
        }

        match Command::new(Self::binary_path()).args(["%s", input]).output() {
            Ok(output) if output.status.success() => ToolAdapterExecutionResult {
                status: "executed".to_string(),
                adapter_id: self.info().id,
                output: Some(String::from_utf8_lossy(&output.stdout).to_string()),
                error: None,
            },
            Ok(output) => ToolAdapterExecutionResult {
                status: "execution_failed".to_string(),
                adapter_id: self.info().id,
                output: None,
                error: Some(String::from_utf8_lossy(&output.stderr).trim().to_string()),
            },
            Err(error) => ToolAdapterExecutionResult {
                status: "execution_failed".to_string(),
                adapter_id: self.info().id,
                output: None,
                error: Some(error.to_string()),
            },
        }
    }
}

fn adapter_registry() -> Vec<Box<dyn ToolAdapter>> {
    vec![
        Box::new(BackendSidecarAdapter),
        Box::new(PluginRuntimeAdapter),
        Box::new(ReferenceCliAdapter),
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
    use super::{execute_tool_adapter, list_tool_adapters, ToolAdapterExecutionRequest};

    #[test]
    fn registry_contains_reference_cli() {
        let adapters = list_tool_adapters();
        assert!(adapters.iter().any(|adapter| adapter.id == "reference_cli"));
    }

    #[test]
    fn reference_adapter_executes_or_reports_unavailable() {
        let result = execute_tool_adapter(ToolAdapterExecutionRequest {
            adapter_id: "reference_cli".to_string(),
            input: "oxy".to_string(),
        });
        assert!(matches!(result.status.as_str(), "executed" | "unavailable"));
    }
}

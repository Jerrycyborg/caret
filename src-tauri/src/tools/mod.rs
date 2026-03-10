use tauri::command;
use serde::Serialize;

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

#[command]
pub fn list_tool_adapters() -> Vec<ToolAdapterInfo> {
    vec![
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
        },
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
        },
        ToolAdapterInfo {
            id: "local_shell".to_string(),
            name: "Local Shell".to_string(),
            adapter_type: "process".to_string(),
            health: "healthy".to_string(),
            capabilities: vec![
                "local_command_execution".to_string(),
                "working_directory_control".to_string(),
                "command_history".to_string(),
            ],
            input_contract: "validated command requests from the Tauri shell integration".to_string(),
            output_contract: "stdout, stderr, and command exit status".to_string(),
            error_contract: "process launch errors and non-zero exit results".to_string(),
            orchestration_role: "Local system automation surface".to_string(),
        },
    ]
}

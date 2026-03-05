use tauri::command;
use serde::Serialize;

pub trait OxyPlugin {
    fn name(&self) -> &'static str;
    fn description(&self) -> &'static str;
    fn run(&self, input: &str) -> String;
}

#[derive(Serialize)]
pub struct PluginInfo {
    pub name: String,
    pub description: String,
    pub enabled: bool,
}

pub struct PluginRegistry {
    plugins: Vec<Box<dyn OxyPlugin + Send + Sync>>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        Self { plugins: Vec::new() }
    }
    pub fn register(&mut self, plugin: Box<dyn OxyPlugin + Send + Sync>) {
        self.plugins.push(plugin);
    }
    pub fn list(&self) -> Vec<PluginInfo> {
        self.plugins.iter().map(|p| PluginInfo {
            name: p.name().to_string(),
            description: p.description().to_string(),
            enabled: true,
        }).collect()
    }
    pub fn run(&self, name: &str, input: &str) -> Option<String> {
        self.plugins.iter().find(|p| p.name() == name).map(|p| p.run(input))
    }
}

// Example plugin
pub struct EchoPlugin;
impl OxyPlugin for EchoPlugin {
    fn name(&self) -> &'static str { "Echo" }
    fn description(&self) -> &'static str { "Echoes input string." }
    fn run(&self, input: &str) -> String { input.to_string() }
}

#[command]
pub fn list_plugins() -> Vec<PluginInfo> {
    let mut registry = PluginRegistry::new();
    registry.register(Box::new(EchoPlugin));
    registry.list()
}

#[command]
pub fn run_plugin(name: String, input: String) -> Option<String> {
    let mut registry = PluginRegistry::new();
    registry.register(Box::new(EchoPlugin));
    registry.run(&name, &input)
}

#[command]
pub fn toggle_plugin_enabled(name: String, enabled: bool) -> Result<(), String> {
    // In-memory only for now; real implementation would persist state
    // This is a stub: always returns Ok
    Ok(())
}

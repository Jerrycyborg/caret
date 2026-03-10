use serde::Serialize;
use std::collections::HashSet;
use std::fs;
use std::path::Path;
use tauri::command;

const INSTALL_STATE_PATH: &str = "plugins/installed.txt";

pub trait OxyPlugin {
    fn name(&self) -> &'static str;
    fn description(&self) -> &'static str;
    fn author(&self) -> &'static str;
    fn version(&self) -> &'static str;
    fn category(&self) -> &'static str;
    fn run(&self, input: &str) -> String;
}

#[derive(Clone, Serialize)]
pub struct PluginInfo {
    pub name: String,
    pub description: String,
    pub enabled: bool,
    pub installed: bool,
    pub author: String,
    pub version: String,
    pub category: String,
}

struct PluginCatalogEntry {
    name: &'static str,
    description: &'static str,
    author: &'static str,
    version: &'static str,
    category: &'static str,
}

const PLUGIN_CATALOG: &[PluginCatalogEntry] = &[
    PluginCatalogEntry {
        name: "Echo",
        description: "Echoes your input back to you.",
        author: "Oxy Core",
        version: "1.0.0",
        category: "Utility",
    },
    PluginCatalogEntry {
        name: "Weather",
        description: "Shows current weather for your city.",
        author: "Oxy Core",
        version: "0.1.0",
        category: "Weather",
    },
];

pub struct PluginRegistry {
    plugins: Vec<Box<dyn OxyPlugin + Send + Sync>>,
    installed: HashSet<String>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        Self {
            plugins: Vec::new(),
            installed: load_installed_plugins(),
        }
    }

    pub fn register(&mut self, plugin: Box<dyn OxyPlugin + Send + Sync>) {
        self.plugins.push(plugin);
    }

    pub fn list(&self) -> Vec<PluginInfo> {
        self.plugins
            .iter()
            .map(|plugin| PluginInfo {
                name: plugin.name().to_string(),
                description: plugin.description().to_string(),
                enabled: self.installed.contains(plugin.name()),
                installed: self.installed.contains(plugin.name()),
                author: plugin.author().to_string(),
                version: plugin.version().to_string(),
                category: plugin.category().to_string(),
            })
            .collect()
    }

    pub fn run(&self, name: &str, input: &str) -> Option<String> {
        self.plugins
            .iter()
            .find(|plugin| plugin.name() == name)
            .map(|plugin| plugin.run(input))
    }

    pub fn install(&mut self, name: &str) -> Result<(), String> {
        ensure_known_plugin(name)?;
        if !self.installed.insert(name.to_string()) {
            return Err(format!("Plugin '{name}' is already installed."));
        }
        save_installed_plugins(&self.installed)
    }

    pub fn uninstall(&mut self, name: &str) -> Result<(), String> {
        ensure_known_plugin(name)?;
        if !self.installed.remove(name) {
            return Err(format!("Plugin '{name}' is not installed."));
        }
        save_installed_plugins(&self.installed)
    }
}

pub struct EchoPlugin;

impl OxyPlugin for EchoPlugin {
    fn name(&self) -> &'static str {
        "Echo"
    }

    fn description(&self) -> &'static str {
        "Echoes your input back to you."
    }

    fn author(&self) -> &'static str {
        "Oxy Core"
    }

    fn version(&self) -> &'static str {
        "1.0.0"
    }

    fn category(&self) -> &'static str {
        "Utility"
    }

    fn run(&self, input: &str) -> String {
        input.to_string()
    }
}

fn load_installed_plugins() -> HashSet<String> {
    let mut installed = HashSet::new();
    if let Ok(data) = fs::read_to_string(INSTALL_STATE_PATH) {
        for line in data.lines() {
            let name = line.trim();
            if !name.is_empty() {
                installed.insert(name.to_string());
            }
        }
    }
    installed
}

fn save_installed_plugins(installed: &HashSet<String>) -> Result<(), String> {
    let path = Path::new(INSTALL_STATE_PATH);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let mut names = installed.iter().cloned().collect::<Vec<_>>();
    names.sort();
    fs::write(path, names.join("\n")).map_err(|e| e.to_string())
}

fn ensure_known_plugin(name: &str) -> Result<(), String> {
    if PLUGIN_CATALOG.iter().any(|plugin| plugin.name == name) {
        Ok(())
    } else {
        Err(format!("Unknown plugin '{name}'."))
    }
}

fn discover(installed: &HashSet<String>) -> Vec<PluginInfo> {
    PLUGIN_CATALOG
        .iter()
        .map(|plugin| PluginInfo {
            name: plugin.name.to_string(),
            description: plugin.description.to_string(),
            enabled: installed.contains(plugin.name),
            installed: installed.contains(plugin.name),
            author: plugin.author.to_string(),
            version: plugin.version.to_string(),
            category: plugin.category.to_string(),
        })
        .collect()
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
    let mut registry = PluginRegistry::new();
    if enabled {
        registry.install(&name)
    } else {
        registry.uninstall(&name)
    }
}

#[command]
pub fn discover_plugins() -> Vec<PluginInfo> {
    discover(&load_installed_plugins())
}

#[command]
pub fn install_plugin(name: String) -> Result<(), String> {
    let mut registry = PluginRegistry::new();
    registry.install(&name)
}

#[command]
pub fn uninstall_plugin(name: String) -> Result<(), String> {
    let mut registry = PluginRegistry::new();
    registry.uninstall(&name)
}


<div align="center">
	<h1>Oxy — AI OS Integration Assistant</h1>
	<p>Cross-platform AI assistant with plugin architecture, hardware acceleration, and multi-agent orchestration.</p>
</div>

---

## Features

- Plugin marketplace for extensibility and custom skills
- Hardware acceleration (GPU, NPU, etc.) for high-performance AI workloads
- Multi-agent orchestration for parallel, collaborative, or specialized AI tasks
- Deep OS integration (Tauri 2, Rust, React 19/TS, FastAPI/Python)
- User-friendly UI with security and onboarding panels

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+ recommended)
- [Rust](https://www.rust-lang.org/tools/install)
- [Python 3.9+](https://www.python.org/downloads/) (for FastAPI backend)
- [VS Code](https://code.visualstudio.com/) (recommended)

## Installation

Clone the repository:

```sh
git clone https://github.com/Jerrycyborg/oxy.git
cd oxy
```

Install dependencies:

```sh
npm install
```

## Build & Run

### Development (hot reload)

```sh
npm run tauri dev
```

### Production build

```sh
npm run build
npx tauri build
```

## Usage

- Launch the app and use the sidebar to access Chat, Files, Terminal, Security, Settings, and the Plugin Marketplace.
- Install and manage plugins from the Marketplace panel.
- Security and onboarding panels are designed for non-technical users.

## Contributing

Pull requests and issues are welcome! Please follow conventional commit messages and ensure all code is linted and tested before submitting.

## License

MIT License

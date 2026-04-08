# Volatility3 MCP Server

A Model Context Protocol (MCP) server that integrates Volatility3 memory forensics framework with LLM-based tools.

# Demo:
https://github.com/user-attachments/assets/f320bfbc-6737-4ce1-aefa-0d82213dd4dd


# Tested On:

- Windows 11 24h2
- Python 3.12.0
- VS Code
- Windows mem profiles

## Features

- **Goal-Oriented**: First understands the goal and then proceeds
- **Multi-OS Support**: Automatically detects and adapts to Windows, Linux, and Mac memory images
- **Intelligent Plugin Discovery**: Dynamically discovers available plugins based on loaded image
- **Error Analysis**: Automatic error analysis with solutions and alternatives
- **Batch Processing**: Execute multiple plugins in sequence
- **Documentation Generation**: Generate comprehensive analysis reports

## Available Tools

| Tool | Description |
|------|-------------|
| `load_memory_image` | Load a memory image and auto-detect OS type (Always start here) |
| `get_image_info` | Get detailed information about the loaded memory image |
| `list_available_plugins` | List all available plugins for the current OS |
| `build_plugin_command` | Build and validate Volatility3 commands |
| `execute_plugin` | Execute a Volatility3 plugin with error handling |
| `analyze_error` | Analyze errors and provide solutions |
| `suggest_plugins` | Get plugin suggestions based on analysis goal |
| `batch_execute` | Execute multiple plugins in sequence |
| `generate_documentation` | Create a new documentation file that AI can populate with content |
| `create_documentation_content` | AI writes content to documentation file - full creative control |
| `get_analysis_context` | Get complete analysis context for AI documentation |

## Installation

### Windows

```bash
git clone https://github.com/0xOb5k-J/volatility3-mcp
```

```bash
cd volatility3-mcp
```

```bash
python3 setup_all.py
```

***Note: after executing `setup_all.py` download `mcp_server.py` from releases and place it in `%USERPROFILE%\volatility-mcp-server\src` folder (replace the original file with this)***

***Link to download***: https://github.com/0xOb5k-J/volatility3-mcp/releases/download/mcp_server/mcp_server.py
## Configuration

### MCP Configuration for github co-pilot VS-code extension:

```json
{
  "servers": {
    "volatility3-mcp": {
      "command": "python",
      "args": [
        "C:\\Users\\<USERNAME>\\volatility-mcp-server\\launcher.py"
      ],
      "type": "stdio",
      "env": {
        "PYTHONPATH": "C:\\Users\\<USERNAME>\\volatility-mcp-server\\volatility3"
      }
    }
  },
  "inputs": []
}
```

### MCP Configuration for Claude Desktop:

```json
{
  "mcpServers": {
    "volatility3-mcp": {
      "command": "python",
      "args": [
        "C:\\Users\\<USERNAME>\\volatility-mcp-server\\launcher.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\<USERNAME>\\volatility-mcp-server\\volatility3"
      }
    }
  }
}
```

## Testing

### Test the Server

**Windows:**
```powershell
cd %USERPROFILE%\volatility-mcp-server
python launcher.py
```

---
### Using with GitHub Copilot (VSCode) as MCP Client

1. Copy the config to your MCP client configuration
2. Start the mcp-server from the config file os VSCode itself
3. The Volatility3 tools will be available in GitHub Copilot

### Using with Claude desktop as MCP Client

1. Copy the config to your MCP client configuration
2. Restart claude desktop
3. The Volatility3 tools will be available in GitHub Copilot

## Directory Structure

```
volatility-mcp-server/
├── volatility3/          # Volatility3 framework
├── src/
│   └── mcp_server.py     # MCP server implementation
├── config/
│   ├── mcp_linux.json    # Linux configuration
│   └── mcp_windows.json  # Windows configuration
├── tests/
│   └── test_server.py    # Test suite
├── logs/                 # Server logs
├── memory_images/        # Memory dumps location
├── reports/              # Generated reports
├── .vscode/
│   └── settings.json     # VSCode configuration
├── venv/                 # Python virtual environment
├── launch_server.sh      # Linux launcher
└── launcher.py           # Cross-platform launcher
```

---
## Troubleshooting

### Server won't start
- Check Python version: `python3 --version` (needs 3.8+)
- Verify virtual environment exists
- Check logs in `logs/mcp_server.log`


### Plugin execution fails
- Use `analyze_error()` tool for automatic diagnosis
- Check `suggest_plugins()` for alternatives
- Verify OS compatibility

## License

[[MIT License]](https://github.com/0xOb5k-J/vol3-mcp-win/blob/main/LICENSE)

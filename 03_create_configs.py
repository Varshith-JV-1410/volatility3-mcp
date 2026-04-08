#!/usr/bin/env python3
"""
Volatility3 MCP Server - Configuration Files Creator (Cross-Platform)
"""

import json
import os
import platform
import sys
from pathlib import Path

def print_colored(text, color='white', style='normal'):
    """Print colored text for better readability"""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m'
    }
    
    styles = {
        'bold': '\033[1m',
        'underline': '\033[4m',
        'normal': ''
    }
    
    color_code = colors.get(color, colors['white'])
    style_code = styles.get(style, styles['normal'])
    reset_code = colors['reset']
    
    print(f"{style_code}{color_code}{text}{reset_code}")

def get_python_command():
    """Get the appropriate Python command for the current platform"""
    if platform.system() == 'Windows':
        return "python"
    else:
        # On Linux/Mac, prefer python3 if available, fall back to python
        if os.system("which python3 > /dev/null 2>&1") == 0:
            return "python3"
        else:
            return "python"

def create_configs():
    """Create configuration files for different platforms"""
    print_colored("=== Creating Volatility3 MCP Configuration Files ===", 'cyan', 'bold')
    print()
    
    # Determine the project directory
    PROJECT_DIR = Path.home() / "volatility-mcp-server"
    CONFIG_DIR = PROJECT_DIR / "config"
    
    # Create config directory
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get current system info
    current_system = platform.system()
    username = os.environ.get('USERNAME' if os.name == 'nt' else 'USER', 'user')
    python_cmd = get_python_command()
    
    print_colored(f"System: {current_system}", 'white')
    print_colored(f"Username: {username}", 'white')
    print_colored(f"Python command: {python_cmd}", 'white')
    print_colored(f"Project directory: {PROJECT_DIR}", 'white')
    print()
    
    # Windows MCP configuration
    windows_config = {
        "servers": {
            "volatility3-mcp": {
                "command": "python",
                "args": [
                    str(PROJECT_DIR / "launcher.py").replace('\\', '/')
                ],
                "type": "stdio",
                "env": {
                    "PYTHONPATH": str(PROJECT_DIR / "volatility3").replace('\\', '/')
                }
            }
        },
        "inputs": []
    }
    
    # Linux/Mac MCP configuration
    unix_config = {
        "servers": {
            "volatility3-mcp": {
                "command": python_cmd,
                "args": [
                    str(PROJECT_DIR / "launcher.py")
                ],
                "type": "stdio",
                "env": {
                    "PYTHONPATH": str(PROJECT_DIR / "volatility3")
                }
            }
        },
        "inputs": []
    }
    
    # Claude Desktop configuration (cross-platform)
    claude_config = {
        "mcpServers": {
            "volatility3-mcp": {
                "command": python_cmd,
                "args": [
                    str(PROJECT_DIR / "launcher.py")
                ],
                "env": {
                    "PYTHONPATH": str(PROJECT_DIR / "volatility3")
                }
            }
        }
    }
    
    # Save configurations
    configs = [
        ("mcp_windows.json", windows_config, "Windows VS Code MCP"),
        ("mcp_linux.json", unix_config, "Linux/Mac VS Code MCP"),
        ("mcp_claude.json", claude_config, "Claude Desktop MCP")
    ]
    
    for filename, config, description in configs:
        config_file = CONFIG_DIR / filename
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print_colored(f"Created {description} config: {config_file}", 'green')
    
    # Print configuration instructions
    print()
    print_colored("="*70, 'cyan')
    print_colored("CONFIGURATION INSTRUCTIONS", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    print()
    
    if current_system == 'Windows':
        print_colored("For VS Code on Windows:", 'yellow', 'bold')
        print(json.dumps(windows_config, indent=2))
    else:
        print_colored(f"For VS Code on {current_system}:", 'yellow', 'bold')
        print(json.dumps(unix_config, indent=2))
    
    print()
    print_colored("For Claude Desktop (any platform):", 'yellow', 'bold')
    print(json.dumps(claude_config, indent=2))
    
    print()
    print_colored("="*70, 'cyan')
    print_colored("SETUP INSTRUCTIONS", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    print()
    
    print_colored("1. VS Code with GitHub Copilot:", 'white', 'bold')
    print_colored("   - Copy the appropriate JSON above to your MCP configuration", 'white')
    print_colored("   - Restart VS Code", 'white')
    print()
    
    print_colored("2. Claude Desktop:", 'white', 'bold')
    print_colored("   - Copy the Claude Desktop JSON to your Claude config file", 'white')
    print_colored("   - Restart Claude Desktop", 'white')
    print()
    
    print_colored("Configuration files saved to:", 'green', 'bold')
    for filename, _, description in configs:
        print_colored(f"  - {filename}: {description}", 'green')

if __name__ == "__main__":
    create_configs()
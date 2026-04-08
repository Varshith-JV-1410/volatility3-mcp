#!/usr/bin/env python3
"""
Volatility3 MCP Server - Launcher Script Creator (Cross-Platform)
"""

import os
import stat
import platform
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

def create_launcher_scripts():
    """Create cross-platform launcher scripts"""
    print_colored("=== Creating Cross-Platform Launcher Scripts ===", 'cyan', 'bold')
    print()
    
    PROJECT_DIR = Path.home() / "volatility-mcp-server"
    
    # Create the main Python launcher (cross-platform)
    launcher_content = '''#!/usr/bin/env python3
"""
Cross-Platform Launcher for Volatility3 MCP Server
Compatible with Windows, Linux, and macOS
"""

import sys
import os
import platform
import subprocess
from pathlib import Path

def setup_environment():
    """Set up environment variables"""
    project_dir = Path(__file__).parent
    volatility_dir = project_dir / "volatility3"
    
    # Set PYTHONPATH to include Volatility3
    current_pythonpath = os.environ.get('PYTHONPATH', '')
    new_pythonpath = str(volatility_dir)
    
    if current_pythonpath:
        os.environ['PYTHONPATH'] = f"{new_pythonpath}{os.pathsep}{current_pythonpath}"
    else:
        os.environ['PYTHONPATH'] = new_pythonpath
    
    # Ensure unbuffered output
    os.environ['PYTHONUNBUFFERED'] = '1'

def find_python_executable():
    """Find the appropriate Python executable in the virtual environment"""
    project_dir = Path(__file__).parent
    venv_dir = project_dir / "venv"
    
    if platform.system() == 'Windows':
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        # Try python3 first, then python
        python_exe = venv_dir / "bin" / "python3"
        if not python_exe.exists():
            python_exe = venv_dir / "bin" / "python"
    
    return python_exe

def main():
    """Main launcher function - silent mode for MCP server"""
    # Get project directories
    project_dir = Path(__file__).parent
    src_dir = project_dir / "src"
    volatility_dir = project_dir / "volatility3"
    
    # Check if virtual environment exists
    python_exe = find_python_executable()
    if not python_exe.exists():
        # Write error to stderr (won't interfere with MCP protocol)
        print(f"ERROR: Virtual environment not found at {python_exe}", file=sys.stderr)
        print("Please run the setup script first", file=sys.stderr)
        return 1
    
    # Check if Volatility3 directory exists
    if not volatility_dir.exists():
        print(f"ERROR: Volatility3 directory not found at {volatility_dir}", file=sys.stderr)
        print("Please run the setup script first", file=sys.stderr)
        return 1
    
    # Check if MCP server script exists
    server_script = src_dir / "mcp_server.py"
    if not server_script.exists():
        print(f"ERROR: MCP server script not found at {server_script}", file=sys.stderr)
        print("Please ensure the MCP server implementation is in place", file=sys.stderr)
        return 1
    
    # Set up environment
    setup_environment()
    
    try:
        # Execute the server directly without any output
        result = subprocess.run([str(python_exe), str(server_script)], 
                              cwd=project_dir)
        return result.returncode
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    # Write the main launcher
    launcher_path = PROJECT_DIR / "launcher.py"
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    # Make executable on Unix systems
    if platform.system() != 'Windows':
        st = os.stat(launcher_path)
        os.chmod(launcher_path, st.st_mode | stat.S_IEXEC)
    
    print_colored(f"Created main launcher: {launcher_path}", 'green')
    
    # Create a diagnostic launcher for manual testing
    diagnostic_content = '''#!/usr/bin/env python3
"""
Diagnostic Launcher for Volatility3 MCP Server
Use this for manual testing with colored output and diagnostics
"""

import sys
import os
import platform
import subprocess
from pathlib import Path

def print_colored(text, color='white', style='normal'):
    """Print colored text for better readability"""
    colors = {
        'red': '\\033[91m',
        'green': '\\033[92m',
        'yellow': '\\033[93m',
        'blue': '\\033[94m',
        'magenta': '\\033[95m',
        'cyan': '\\033[96m',
        'white': '\\033[97m',
        'reset': '\\033[0m'
    }
    
    styles = {
        'bold': '\\033[1m',
        'underline': '\\033[4m',
        'normal': ''
    }
    
    color_code = colors.get(color, colors['white'])
    style_code = styles.get(style, styles['normal'])
    reset_code = colors['reset']
    
    print(f"{style_code}{color_code}{text}{reset_code}")

def get_system_info():
    """Get system information for debugging"""
    return {
        'system': platform.system(),
        'release': platform.release(),
        'machine': platform.machine(),
        'python': sys.version
    }

def find_python_executable():
    """Find the appropriate Python executable in the virtual environment"""
    project_dir = Path(__file__).parent
    venv_dir = project_dir / "venv"
    
    if platform.system() == 'Windows':
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        # Try python3 first, then python
        python_exe = venv_dir / "bin" / "python3"
        if not python_exe.exists():
            python_exe = venv_dir / "bin" / "python"
    
    return python_exe

def setup_environment():
    """Set up environment variables"""
    project_dir = Path(__file__).parent
    volatility_dir = project_dir / "volatility3"
    
    # Set PYTHONPATH to include Volatility3
    current_pythonpath = os.environ.get('PYTHONPATH', '')
    new_pythonpath = str(volatility_dir)
    
    if current_pythonpath:
        os.environ['PYTHONPATH'] = f"{new_pythonpath}{os.pathsep}{current_pythonpath}"
    else:
        os.environ['PYTHONPATH'] = new_pythonpath
    
    # Ensure unbuffered output
    os.environ['PYTHONUNBUFFERED'] = '1'

def main():
    """Main diagnostic launcher function with full output"""
    system_info = get_system_info()
    
    print_colored("="*60, 'cyan')
    print_colored("VOLATILITY3 MCP SERVER - DIAGNOSTIC MODE", 'cyan', 'bold')
    print_colored("="*60, 'cyan')
    print_colored(f"System: {system_info['system']} {system_info['release']}", 'white')
    print_colored(f"Architecture: {system_info['machine']}", 'white')
    print_colored("="*60, 'cyan')
    
    # Get project directories
    project_dir = Path(__file__).parent
    src_dir = project_dir / "src"
    volatility_dir = project_dir / "volatility3"
    
    print_colored(f"Project Directory: {project_dir}", 'white')
    print_colored(f"Source Directory: {src_dir}", 'white')
    print_colored(f"Volatility3 Directory: {volatility_dir}", 'white')
    print()
    
    # Check if virtual environment exists
    python_exe = find_python_executable()
    if not python_exe.exists():
        print_colored("ERROR: Virtual environment not found!", 'red', 'bold')
        print_colored(f"Expected Python executable: {python_exe}", 'red')
        print_colored("Please run the setup script first:", 'yellow')
        print_colored("  python 01_setup_volatility_mcp.py", 'yellow')
        return 1
    
    print_colored(f"Python Executable: {python_exe}", 'green')
    
    # Check if Volatility3 directory exists
    if not volatility_dir.exists():
        print_colored("ERROR: Volatility3 directory not found!", 'red', 'bold')
        print_colored(f"Expected directory: {volatility_dir}", 'red')
        print_colored("Please run the setup script first.", 'yellow')
        return 1
    
    print_colored("Volatility3 Directory: OK", 'green')
    
    # Check if MCP server script exists
    server_script = src_dir / "mcp_server.py"
    if not server_script.exists():
        print_colored("ERROR: MCP server script not found!", 'red', 'bold')
        print_colored(f"Expected file: {server_script}", 'red')
        print_colored("Please ensure the MCP server implementation is in place.", 'yellow')
        return 1
    
    print_colored("MCP Server Script: OK", 'green')
    print()
    
    # Set up environment
    print_colored("Setting up environment...", 'white')
    setup_environment()
    print_colored("Environment configured successfully", 'green')
    print()
    
    # Launch the server
    print_colored("Starting Volatility3 MCP Server...", 'green', 'bold')
    print_colored("-" * 40, 'green')
    
    try:
        # Execute the server
        result = subprocess.run([str(python_exe), str(server_script)], 
                              cwd=project_dir)
        return result.returncode
    except KeyboardInterrupt:
        print_colored("\\n\\nServer stopped by user.", 'yellow')
        return 0
    except Exception as e:
        print_colored(f"\\nERROR: Failed to start server: {e}", 'red', 'bold')
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    diagnostic_path = PROJECT_DIR / "diagnostic_launcher.py"
    with open(diagnostic_path, 'w', encoding='utf-8') as f:
        f.write(diagnostic_content)
    
    # Make executable on Unix systems
    if platform.system() != 'Windows':
        st = os.stat(diagnostic_path)
        os.chmod(diagnostic_path, st.st_mode | stat.S_IEXEC)
    
    print_colored(f"Created diagnostic launcher: {diagnostic_path}", 'green')
    
    # Create platform-specific convenience scripts
    current_system = platform.system()
    
    if current_system == 'Windows':
        # Create Windows batch file
        batch_content = f'''@echo off
title Volatility3 MCP Server
echo Starting Volatility3 MCP Server...
cd /d "{PROJECT_DIR}"
python launcher.py
pause
'''
        
        batch_path = PROJECT_DIR / "launch_server.bat"
        with open(batch_path, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        print_colored(f"Created Windows batch launcher: {batch_path}", 'green')
        
        # Create PowerShell script
        ps1_content = f'''# Volatility3 MCP Server PowerShell Launcher
Write-Host "Starting Volatility3 MCP Server..." -ForegroundColor Green
Set-Location "{PROJECT_DIR}"
& python launcher.py
'''
        
        ps1_path = PROJECT_DIR / "launch_server.ps1"
        with open(ps1_path, 'w', encoding='utf-8') as f:
            f.write(ps1_content)
        print_colored(f"Created PowerShell launcher: {ps1_path}", 'green')
    
    else:
        # Create shell script for Linux/Mac
        shell_content = f'''#!/bin/bash
# Volatility3 MCP Server Shell Launcher

echo "Starting Volatility3 MCP Server..."
cd "{PROJECT_DIR}"
python3 launcher.py
'''
        
        shell_path = PROJECT_DIR / "launch_server.sh"
        with open(shell_path, 'w', encoding='utf-8') as f:
            f.write(shell_content)
        
        # Make executable
        st = os.stat(shell_path)
        os.chmod(shell_path, st.st_mode | stat.S_IEXEC)
        
        print_colored(f"Created shell launcher: {shell_path}", 'green')
    
    print()
    print_colored("="*70, 'green')
    print_colored("LAUNCHER SCRIPTS CREATED SUCCESSFULLY", 'green', 'bold')
    print_colored("="*70, 'green')
    print()
    
    print_colored("Available launchers:", 'white', 'bold')
    print_colored(f"1. Cross-platform: python {launcher_path}", 'cyan')
    
    if current_system == 'Windows':
        print_colored(f"2. Windows batch: {PROJECT_DIR / 'launch_server.bat'}", 'cyan')
        print_colored(f"3. PowerShell: {PROJECT_DIR / 'launch_server.ps1'}", 'cyan')
    else:
        print_colored(f"2. Shell script: {PROJECT_DIR / 'launch_server.sh'}", 'cyan')
    
    print()
    print_colored("Usage:", 'yellow', 'bold')
    print_colored("• Make sure to complete all setup steps first", 'white')
    print_colored("• Copy the full MCP server implementation to src/mcp_server.py", 'white')
    print_colored("• Run the test script to verify installation", 'white')
    print_colored("• Use any of the launcher scripts above to start the server", 'white')

if __name__ == "__main__":
    create_launcher_scripts()
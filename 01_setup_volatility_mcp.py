#!/usr/bin/env python3
"""
Volatility3 MCP Server Setup (Cross-Platform)
"""

import sys
import subprocess
import shutil
import platform
from pathlib import Path
import os

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

def run_command(command, cwd=None, shell=True):
    """Run a command and return success status"""
    try:
        result = subprocess.run(
            command, 
            shell=shell, 
            cwd=cwd, 
            capture_output=True, 
            text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def get_python_executable():
    """Get the appropriate Python executable"""
    return sys.executable

def get_pip_executable(venv_dir):
    """Get the pip executable from virtual environment"""
    if platform.system() == 'Windows':
        return venv_dir / "Scripts" / "pip.exe"
    else:
        return venv_dir / "bin" / "pip"

def get_venv_python(venv_dir):
    """Get the Python executable from virtual environment"""
    if platform.system() == 'Windows':
        return venv_dir / "Scripts" / "python.exe"
    else:
        return venv_dir / "bin" / "python3"

def clone_or_update_volatility(volatility_dir):
    """Clone or update Volatility3 repository"""
    print_colored("Setting up Volatility3...", 'white')
    
    if volatility_dir.exists():
        print_colored("Volatility3 directory already exists, pulling latest changes...", 'yellow')
        os.chdir(volatility_dir)
        
        # Try main branch first, then master
        success, stdout, stderr = run_command('git pull origin main')
        if not success:
            success, stdout, stderr = run_command('git pull origin master')
        
        if success:
            print_colored("Successfully updated Volatility3", 'green')
        else:
            print_colored(f"Warning: Failed to update repository: {stderr}", 'yellow')
    else:
        print_colored("Cloning Volatility3 repository...", 'white')
        success, stdout, stderr = run_command(
            'git clone https://github.com/volatilityfoundation/volatility3.git',
            cwd=volatility_dir.parent
        )
        
        if success:
            print_colored("Successfully cloned Volatility3", 'green')
        else:
            print_colored(f"ERROR: Failed to clone repository: {stderr}", 'red')
            return False
    
    return True

def create_virtual_environment(venv_dir):
    """Create Python virtual environment"""
    print_colored("Creating Python virtual environment...", 'white')
    
    python_exe = get_python_executable()
    success, stdout, stderr = run_command(f'"{python_exe}" -m venv "{venv_dir}"')
    
    if success:
        print_colored("Virtual environment created successfully", 'green')
        return True
    else:
        print_colored(f"ERROR: Failed to create virtual environment: {stderr}", 'red')
        return False

def install_requirements(venv_dir, volatility_dir):
    """Install required packages"""
    venv_python = get_venv_python(venv_dir)
    venv_pip = get_pip_executable(venv_dir)
    
    # Upgrade pip first
    print_colored("Upgrading pip...", 'white')
    success, stdout, stderr = run_command(f'"{venv_python}" -m pip install --upgrade pip')
    if not success:
        print_colored(f"Warning: Failed to upgrade pip: {stderr}", 'yellow')
    
    # Install Volatility3 dependencies
    requirements_file = volatility_dir / "requirements.txt"
    if requirements_file.exists():
        print_colored("Installing Volatility3 dependencies...", 'white')
        success, stdout, stderr = run_command(
            f'"{venv_pip}" install -r "{requirements_file}"'
        )
        if not success:
            print_colored(f"Warning: Some Volatility3 dependencies failed to install: {stderr}", 'yellow')
        else:
            print_colored("Volatility3 dependencies installed", 'green')
    
    # Install MCP server dependencies
    print_colored("Installing MCP server dependencies...", 'white')
    mcp_packages = ['mcp', 'pydantic', 'typing-extensions', 'asyncio']
    
    for package in mcp_packages:
        success, stdout, stderr = run_command(f'"{venv_pip}" install {package}')
        if success:
            print_colored(f"Installed {package}", 'green')
        else:
            print_colored(f"Warning: Failed to install {package}: {stderr}", 'yellow')
    
    return True

def create_project_structure(project_dir):
    """Create project directory structure"""
    print_colored("Creating project structure...", 'white')
    
    directories = [
        "src",
        "config", 
        "logs",
        "memory_images",
        "reports",
        "tests",
        "scripts"
    ]
    
    for dir_name in directories:
        dir_path = project_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print_colored(f"Created directory: {dir_name}/", 'green')
    
    return True

def main():
    """Main setup function"""
    print_colored("=== Setting up Volatility3 MCP Server (Cross-Platform) ===", 'cyan', 'bold')
    print()
    
    # Configuration
    PROJECT_NAME = "volatility-mcp-server"
    PROJECT_DIR = Path.home() / PROJECT_NAME
    VENV_DIR = PROJECT_DIR / "venv"
    VOLATILITY_DIR = PROJECT_DIR / "volatility3"
    
    print_colored(f"Project directory: {PROJECT_DIR}", 'white')
    print_colored(f"System: {platform.system()} {platform.release()}", 'white')
    print()
    
    try:
        # Create project directory
        print_colored(f"Creating project directory at {PROJECT_DIR}...", 'white')
        PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        os.chdir(PROJECT_DIR)
        
        # Clone/update Volatility3
        if not clone_or_update_volatility(VOLATILITY_DIR):
            return 1
        
        # Create virtual environment
        if not create_virtual_environment(VENV_DIR):
            return 1
        
        # Install requirements
        if not install_requirements(VENV_DIR, VOLATILITY_DIR):
            return 1
        
        # Create project structure
        if not create_project_structure(PROJECT_DIR):
            return 1
        
        print()
        print_colored("=== Project Structure Created Successfully! ===", 'green', 'bold')
        print()
        print_colored(f"Project location: {PROJECT_DIR}", 'cyan')
        print_colored("Directory structure:", 'white')
        
        # Show directory tree
        for item in sorted(PROJECT_DIR.iterdir()):
            if item.is_dir():
                print_colored(f"  {item.name}/", 'blue')
        
        print()
        print_colored("Next steps:", 'yellow')
        print_colored("1. Run the next setup scripts in order", 'white')
        print_colored("2. Copy the full MCP server implementation to src/mcp_server.py", 'white')
        print_colored("3. Configure your MCP client", 'white')
        
        return 0
        
    except Exception as e:
        print_colored(f"ERROR: Setup failed: {e}", 'red')
        return 1

if __name__ == "__main__":
    sys.exit(main())
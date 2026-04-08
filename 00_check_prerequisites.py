#!/usr/bin/env python3
"""
Volatility3 MCP Server - Prerequisites Check (Cross-Platform)
"""

import sys
import subprocess
import platform
import shutil
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

def run_command(command):
    """Run a command and return its output"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_python():
    """Check Python version"""
    print("Checking Python...", end=" ")
    try:
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
        
        if version_info >= (3, 8):
            print_colored(f"OK - Python {version_str} installed", 'green')
            return True
        else:
            print_colored(f"ERROR - Python {version_str} is too old (need 3.8+)", 'red')
            print_colored("Please install Python 3.8+ from https://www.python.org/downloads/", 'yellow')
            return False
    except Exception as e:
        print_colored(f"ERROR - Python check failed: {e}", 'red')
        return False

def check_git():
    """Check Git installation"""
    print("Checking Git...", end=" ")
    
    # Check if git command is available
    if shutil.which('git') is None:
        print_colored("ERROR - Git not found", 'red')
        system = platform.system().lower()
        if system == 'windows':
            print_colored("Please install Git from https://git-scm.com/download/win", 'yellow')
        elif system == 'darwin':
            print_colored("Please install Git using: brew install git or from https://git-scm.com/download/mac", 'yellow')
        else:
            print_colored("Please install Git using your package manager (e.g., apt install git, yum install git)", 'yellow')
        return False
    
    success, stdout, stderr = run_command('git --version')
    if success and 'git version' in stdout:
        print_colored("OK - Git installed", 'green')
        return True
    else:
        print_colored(f"ERROR - Git version check failed: {stderr}", 'red')
        return False

def check_pip():
    """Check pip installation"""
    print("Checking pip...", end=" ")
    
    # Try different ways to check pip
    pip_commands = [
        f'{sys.executable} -m pip --version',
        'pip --version',
        'pip3 --version'
    ]
    
    for cmd in pip_commands:
        success, stdout, stderr = run_command(cmd)
        if success and 'pip' in stdout.lower():
            print_colored("OK - pip installed", 'green')
            return True
    
    print_colored("ERROR - pip not found", 'red')
    print_colored("Please install pip or repair your Python installation", 'yellow')
    return False

def check_venv():
    """Check virtual environment support"""
    print("Checking venv module...", end=" ")
    
    # Try to import venv module directly
    try:
        import venv
        print_colored("OK - venv module available", 'green')
        return True
    except ImportError:
        pass
    
    # Try command line venv
    success, stdout, stderr = run_command(f'{sys.executable} -m venv --help')
    if success:
        print_colored("OK - venv module available", 'green')
        return True
    
    print_colored("ERROR - venv module not found", 'red')
    system = platform.system().lower()
    if system == 'linux':
        print_colored("Try: sudo apt-get install python3-venv (Ubuntu/Debian)", 'yellow')
    else:
        print_colored("Please repair your Python installation", 'yellow')
    return False

def main():
    """Main function"""
    print_colored("=== Volatility3 MCP Server - Prerequisites Check (Cross-Platform) ===", 'cyan', 'bold')
    
    # System information
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    
    print_colored(f"System: {system} {release} ({machine})", 'white')
    print_colored(f"Python: {sys.executable}", 'white')
    print()
    
    errors = 0
    
    # Run checks
    checks = [
        check_python,
        check_git,
        check_pip,
        check_venv
    ]
    
    for check in checks:
        if not check():
            errors += 1
    
    print()
    
    if errors == 0:
        print_colored("Prerequisites check complete! All requirements met.", 'green', 'bold')
        print_colored("You can now proceed with the setup.", 'green')
        return 0
    else:
        print_colored(f"Prerequisites check failed with {errors} error(s).", 'red', 'bold')
        print_colored("Please install missing prerequisites before continuing.", 'yellow')
        return 1

if __name__ == "__main__":
    sys.exit(main())
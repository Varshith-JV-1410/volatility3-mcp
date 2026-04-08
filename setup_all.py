#!/usr/bin/env python3
"""
Master Cross-Platform Setup Script for Volatility3 MCP Server
Compatible with Windows, Linux, and macOS
"""

import sys
import subprocess
import platform
import time
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

def run_script(script_name, script_path):
    """Run a Python script and handle errors"""
    print_colored(f"Running {script_name}...", 'yellow', 'bold')
    print_colored("-" * 50, 'yellow')
    
    try:
        result = subprocess.run([sys.executable, str(script_path)], 
                              check=True, 
                              capture_output=False)
        print_colored(f"✓ {script_name} completed successfully", 'green', 'bold')
        return True
    except subprocess.CalledProcessError as e:
        print_colored(f"✗ {script_name} failed with exit code {e.returncode}", 'red', 'bold')
        return False
    except Exception as e:
        print_colored(f"✗ {script_name} failed with error: {e}", 'red', 'bold')
        return False

def display_header():
    """Display setup header with system information"""
    print_colored("="*80, 'cyan')
    print_colored("VOLATILITY3 MCP SERVER - COMPLETE CROSS-PLATFORM SETUP", 'cyan', 'bold')
    print_colored("="*80, 'cyan')
    
    # System information
    system_info = {
        'System': platform.system(),
        'Release': platform.release(),
        'Machine': platform.machine(),
        'Python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'Python Path': sys.executable
    }
    
    for key, value in system_info.items():
        print_colored(f"{key}: {value}", 'white')
    
    print_colored("="*80, 'cyan')
    print()

def display_setup_steps():
    """Display what the setup will do"""
    print_colored("This script will:", 'white', 'bold')
    steps = [
        "1. Check prerequisites (Python, Git, pip, venv)",
        "2. Set up project structure and dependencies",
        "3. Create MCP server placeholder",
        "4. Generate configuration files",
        "5. Create test scripts",
        "6. Create launcher scripts"
    ]
    
    for step in steps:
        print_colored(f"  {step}", 'blue')
    
    print()
    print_colored("The complete setup typically takes 2-5 minutes depending on your system.", 'yellow')
    print()

def confirm_setup():
    """Ask user to confirm setup"""
    print_colored("Do you want to proceed with the complete setup? [Y/n]: ", 'white', 'bold')
    try:
        response = input().strip().lower()
        return response in ['', 'y', 'yes']
    except KeyboardInterrupt:
        print()
        print_colored("Setup cancelled by user.", 'yellow')
        return False

def main():
    """Main setup function"""
    display_header()
    display_setup_steps()
    
    if not confirm_setup():
        print_colored("Setup cancelled.", 'yellow')
        return 0
    
    print()
    print_colored("Starting complete setup...", 'green', 'bold')
    print()
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Define setup scripts in order
    setup_scripts = [
        ("Prerequisites Check", "00_check_prerequisites.py"),
        ("Project Setup", "01_setup_volatility_mcp.py"),
        ("MCP Server Creation", "02_create_mcp_server.py"),
        ("Configuration Files", "03_create_configs.py"),
        ("Test Scripts", "04_create_test_script.py"),
        ("Launcher Scripts", "05_create_launch_script.py")
    ]
    
    # Track progress
    total_steps = len(setup_scripts)
    completed_steps = 0
    failed_steps = []
    start_time = time.time()
    
    # Run each setup script
    for i, (step_name, script_file) in enumerate(setup_scripts, 1):
        script_path = script_dir / script_file
        
        if not script_path.exists():
            print_colored(f"✗ Script not found: {script_file}", 'red', 'bold')
            failed_steps.append(step_name)
            continue
        
        print_colored(f"[{i}/{total_steps}] {step_name}", 'cyan', 'bold')
        
        # Special handling for prerequisites check
        if script_file == "00_check_prerequisites.py":
            try:
                result = subprocess.run([sys.executable, str(script_path)], 
                                      check=True, capture_output=False)
                if result.returncode != 0:
                    print_colored("Prerequisites check failed. Please install missing components.", 'red', 'bold')
                    failed_steps.append(step_name)
                    continue
            except subprocess.CalledProcessError:
                print_colored("Prerequisites check failed. Please install missing components.", 'red', 'bold')
                failed_steps.append(step_name)
                continue
        
        if run_script(step_name, script_path):
            completed_steps += 1
        else:
            failed_steps.append(step_name)
            
            # For critical failures, ask if user wants to continue
            if script_file in ["00_check_prerequisites.py", "01_setup_volatility_mcp.py"]:
                print_colored(f"Critical step '{step_name}' failed.", 'red', 'bold')
                print_colored("Do you want to continue anyway? [y/N]: ", 'yellow')
                try:
                    response = input().strip().lower()
                    if response not in ['y', 'yes']:
                        print_colored("Setup aborted.", 'red')
                        return 1
                except KeyboardInterrupt:
                    print()
                    print_colored("Setup aborted by user.", 'yellow')
                    return 1
        
        print()
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Display final results
    print_colored("="*80, 'cyan')
    print_colored("SETUP COMPLETE", 'cyan', 'bold')
    print_colored("="*80, 'cyan')
    
    print_colored(f"Completed: {completed_steps}/{total_steps} steps", 'white')
    print_colored(f"Time taken: {elapsed_time:.1f} seconds", 'white')
    
    if failed_steps:
        print_colored(f"Failed steps: {', '.join(failed_steps)}", 'red')
    
    print()
    
    # Project information
    project_dir = Path.home() / "volatility-mcp-server"
    
    if completed_steps == total_steps:
        print_colored("🎉 Setup completed successfully!", 'green', 'bold')
        print()
        print_colored("Project Structure:", 'white', 'bold')
        structure = [
            f"📁 {project_dir}/",
            "  📁 volatility3/          # Volatility3 framework",
            "  📁 src/",
            "    📄 mcp_server.py       # MCP server (placeholder - replace with full version)",
            "  📁 config/",
            "    📄 mcp_windows.json    # Windows VS Code configuration",
            "    📄 mcp_linux.json      # Linux/Mac VS Code configuration", 
            "    📄 mcp_claude.json     # Claude Desktop configuration",
            "  📁 tests/",
            "    📄 test_server.py      # Comprehensive test suite",
            "  📁 logs/                 # Server logs",
            "  📁 memory_images/        # Memory dumps storage",
            "  📁 reports/              # Generated reports",
            "  📁 venv/                 # Python virtual environment",
            "  📄 launcher.py           # Cross-platform launcher"
        ]
        
        for line in structure:
            if line.startswith("📁"):
                print_colored(line, 'blue')
            elif line.startswith("    📄"):
                print_colored(line, 'green')
            else:
                print_colored(line, 'white')
        
        print()
        print_colored("Next Steps:", 'yellow', 'bold')
        steps = [
            "1. Download the full MCP server implementation from releases",
            "2. Replace src/mcp_server.py with the downloaded version",
            "3. Run the test script: python tests/test_server.py", 
            "4. Configure your MCP client using the config files",
            "5. Launch the server using launcher.py"
        ]
        
        for step in steps:
            print_colored(f"  {step}", 'white')
        
        print()
        print_colored("Quick Start:", 'cyan', 'bold')
        print_colored(f"  cd {project_dir}", 'cyan')
        print_colored("  python launcher.py", 'cyan')
        
    else:
        print_colored("⚠️  Setup completed with errors.", 'yellow', 'bold')
        print_colored("Please review the failed steps above and fix any issues.", 'yellow')
    
    print_colored("="*80, 'cyan')
    
    return 0 if completed_steps == total_steps else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_colored("Setup interrupted by user.", 'yellow')
        sys.exit(1)
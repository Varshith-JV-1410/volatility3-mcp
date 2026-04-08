#!/usr/bin/env python3
"""
Volatility3 MCP Server - Test Script Creator (Cross-Platform)
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

def create_test_script():
    """Create comprehensive test script"""
    PROJECT_DIR = Path.home() / "volatility-mcp-server"
    TESTS_DIR = PROJECT_DIR / "tests"
    
    test_content = '''#!/usr/bin/env python3
"""
Cross-Platform Test Script for Volatility3 MCP Server
"""

import json
import asyncio
import sys
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

def test_python_environment():
    """Test Python environment and dependencies"""
    print_colored("Testing Python Environment...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    
    # Python version
    version = sys.version_info
    print_colored(f"Python Version: {version.major}.{version.minor}.{version.micro}", 'white')
    
    if version >= (3, 8):
        print_colored("✓ Python version OK", 'green')
    else:
        print_colored("✗ Python version too old (need 3.8+)", 'red')
        return False
    
    # Test virtual environment
    project_dir = Path(__file__).parent.parent
    if platform.system() == 'Windows':
        venv_python = project_dir / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_dir / "venv" / "bin" / "python3"
    
    if venv_python.exists():
        print_colored("✓ Virtual environment found", 'green')
    else:
        print_colored("✗ Virtual environment not found", 'red')
        return False
    
    return True

def test_volatility_installation():
    """Test Volatility3 installation"""
    print_colored("\\nTesting Volatility3 Installation...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    
    project_dir = Path(__file__).parent.parent
    volatility_dir = project_dir / "volatility3"
    
    if volatility_dir.exists():
        print_colored("✓ Volatility3 directory found", 'green')
        
        # Check for key files
        key_files = ["vol.py", "volatility3", "requirements.txt"]
        for file in key_files:
            if (volatility_dir / file).exists():
                print_colored(f"✓ Found {file}", 'green')
            else:
                print_colored(f"✗ Missing {file}", 'yellow')
        
        return True
    else:
        print_colored("✗ Volatility3 directory not found", 'red')
        return False

def test_mcp_server():
    """Test MCP server files"""
    print_colored("\\nTesting MCP Server...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    
    project_dir = Path(__file__).parent.parent
    
    # Add project to path for imports
    sys.path.insert(0, str(project_dir / "src"))
    
    # Check server file
    server_file = project_dir / "src" / "mcp_server.py"
    if server_file.exists():
        print_colored("✓ MCP server file found", 'green')
        
        try:
            # Try to import the server
            import mcp_server
            print_colored("✓ MCP server module imported successfully", 'green')
            
            # List expected tools
            expected_tools = [
                "load_memory_image",
                "get_image_info",
                "list_available_plugins",
                "build_plugin_command",
                "execute_plugin",
                "analyze_error",
                "suggest_plugins",
                "batch_execute",
                "generate_documentation"
            ]
            
            print_colored("\\nExpected MCP Tools:", 'white')
            for tool in expected_tools:
                print_colored(f"  • {tool}", 'blue')
                
            return True
            
        except ImportError as e:
            print_colored(f"✗ Failed to import MCP server: {e}", 'red')
            print_colored("Make sure to copy the full mcp_server.py implementation", 'yellow')
            return False
    else:
        print_colored("✗ MCP server file not found", 'red')
        return False

def test_configuration_files():
    """Test configuration files"""
    print_colored("\\nTesting Configuration Files...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    
    project_dir = Path(__file__).parent.parent
    config_dir = project_dir / "config"
    
    if config_dir.exists():
        print_colored("✓ Config directory found", 'green')
        
        config_files = ["mcp_windows.json", "mcp_linux.json", "mcp_claude.json"]
        for config_file in config_files:
            config_path = config_dir / config_file
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    print_colored(f"✓ {config_file} - Valid JSON", 'green')
                except json.JSONDecodeError:
                    print_colored(f"✗ {config_file} - Invalid JSON", 'red')
            else:
                print_colored(f"✗ {config_file} - Not found", 'yellow')
        
        return True
    else:
        print_colored("✗ Config directory not found", 'red')
        return False

def test_project_structure():
    """Test project directory structure"""
    print_colored("\\nTesting Project Structure...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    
    project_dir = Path(__file__).parent.parent
    
    expected_dirs = [
        "src", "config", "logs", "memory_images", 
        "reports", "tests", "scripts", "volatility3", "venv"
    ]
    
    all_good = True
    for dir_name in expected_dirs:
        dir_path = project_dir / dir_name
        if dir_path.exists():
            print_colored(f"✓ {dir_name}/", 'green')
        else:
            print_colored(f"✗ {dir_name}/", 'yellow')
            all_good = False
    
    return all_good

async def run_all_tests():
    """Run all tests"""
    print_colored("="*70, 'cyan')
    print_colored("VOLATILITY3 MCP SERVER - COMPREHENSIVE TEST SUITE", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    print_colored(f"System: {platform.system()} {platform.release()}", 'white')
    print_colored(f"Architecture: {platform.machine()}", 'white')
    print_colored(f"Python: {sys.executable}", 'white')
    print_colored("="*70, 'cyan')
    
    tests = [
        test_python_environment,
        test_volatility_installation,
        test_mcp_server,
        test_configuration_files,
        test_project_structure
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print_colored("\\n" + "="*70, 'cyan')
    print_colored("TEST RESULTS", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    
    if passed == total:
        print_colored(f"✓ All tests passed ({passed}/{total})", 'green', 'bold')
        print_colored("Your Volatility3 MCP Server setup is ready!", 'green')
    else:
        print_colored(f"✗ {total - passed} test(s) failed ({passed}/{total})", 'red', 'bold')
        print_colored("Please fix the issues above before proceeding.", 'yellow')
    
    print_colored("="*70, 'cyan')

if __name__ == "__main__":
    asyncio.run(run_all_tests())
'''
    
    # Write test script
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    test_file = TESTS_DIR / "test_server.py"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    # Make executable on Unix systems
    if platform.system() != 'Windows':
        st = os.stat(test_file)
        os.chmod(test_file, st.st_mode | stat.S_IEXEC)
    
    print_colored(f"Created comprehensive test script: {test_file}", 'green')
    
    # Create a simple runner script
    runner_content = f'''#!/usr/bin/env python3
"""Simple test runner"""
import subprocess
import sys
from pathlib import Path

test_script = Path(__file__).parent / "test_server.py"
sys.exit(subprocess.call([sys.executable, str(test_script)]))
'''
    
    runner_file = TESTS_DIR / "run_tests.py"
    with open(runner_file, 'w', encoding='utf-8') as f:
        f.write(runner_content)
    
    if platform.system() != 'Windows':
        st = os.stat(runner_file)
        os.chmod(runner_file, st.st_mode | stat.S_IEXEC)
    
    print_colored(f"Created test runner: {runner_file}", 'green')

if __name__ == "__main__":
    print_colored("=== Creating Test Scripts ===", 'cyan', 'bold')
    create_test_script()
    print_colored("Test scripts created successfully!", 'green')
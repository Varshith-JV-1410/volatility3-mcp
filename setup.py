#!/usr/bin/env python3
"""
Volatility3 MCP Server — Single-file Setup Script
Handles everything: prerequisites, project structure, Volatility3 clone,
venv, dependencies, mcp_server.py deployment, configs, tests, and launcher.
"""

import sys
import os
import json
import shutil
import stat
import platform
import subprocess
import time
from pathlib import Path

# ─────────────────────────── helpers ────────────────────────────────────────

def print_colored(text, color='white', style='normal'):
    colors  = {'red':'\033[91m','green':'\033[92m','yellow':'\033[93m',
                'blue':'\033[94m','magenta':'\033[95m','cyan':'\033[96m',
                'white':'\033[97m','reset':'\033[0m'}
    styles  = {'bold':'\033[1m','underline':'\033[4m','normal':''}
    print(f"{styles.get(style,'')}{colors.get(color,'')}{text}{colors['reset']}")

def run_command(command, cwd=None, shell=True):
    try:
        result = subprocess.run(command, shell=shell, cwd=cwd,
                                capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def get_venv_python(venv_dir):
    if platform.system() == 'Windows':
        return venv_dir / "Scripts" / "python.exe"
    p = venv_dir / "bin" / "python3"
    return p if p.exists() else venv_dir / "bin" / "python"

def get_venv_pip(venv_dir):
    if platform.system() == 'Windows':
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"

def get_python_cmd():
    if platform.system() == 'Windows':
        return "python"
    return "python3" if shutil.which("python3") else "python"

# ─────────────────────────── step functions ─────────────────────────────────

def step_check_prerequisites():
    """[1/7] Check Python ≥ 3.8, git, pip, venv"""
    print_colored("=== [1/7] Checking Prerequisites ===", 'cyan', 'bold')
    errors = 0

    # Python version
    vi = sys.version_info
    if vi >= (3, 8):
        print_colored(f"  ✓ Python {vi.major}.{vi.minor}.{vi.micro}", 'green')
    else:
        print_colored(f"  ✗ Python {vi.major}.{vi.minor}.{vi.micro} — need 3.8+", 'red')
        errors += 1

    # git
    if shutil.which('git'):
        ok, out, _ = run_command('git --version')
        print_colored(f"  ✓ {out.strip()}", 'green') if ok else print_colored("  ✗ git check failed", 'red') or errors.__add__(1)
    else:
        print_colored("  ✗ git not found — install from https://git-scm.com/", 'red')
        errors += 1

    # pip
    ok, _, _ = run_command(f'"{sys.executable}" -m pip --version')
    if ok:
        print_colored("  ✓ pip available", 'green')
    else:
        print_colored("  ✗ pip not found", 'red')
        errors += 1

    # venv
    try:
        import venv  # noqa: F401
        print_colored("  ✓ venv module available", 'green')
    except ImportError:
        print_colored("  ✗ venv module missing", 'red')
        errors += 1

    if errors:
        print_colored(f"  {errors} prerequisite(s) missing — please fix before continuing.", 'red')
    return errors == 0


def step_setup_project(project_dir):
    """[2/7] Create directories and clone / update Volatility3"""
    print_colored("=== [2/7] Setting Up Project Structure ===", 'cyan', 'bold')
    volatility_dir = project_dir / "volatility3"

    # Create directory tree
    for d in ["src", "config", "logs", "memory_images", "reports", "tests", "scripts"]:
        (project_dir / d).mkdir(parents=True, exist_ok=True)
        print_colored(f"  ✓ {d}/", 'green')

    # Clone or update Volatility3
    if volatility_dir.exists():
        print_colored("  Updating Volatility3 (git pull)...", 'yellow')
        ok, _, err = run_command('git pull origin main', cwd=volatility_dir)
        if not ok:
            ok, _, err = run_command('git pull origin master', cwd=volatility_dir)
        if ok:
            print_colored("  ✓ Volatility3 updated", 'green')
        else:
            print_colored(f"  ⚠ git pull warning: {err.strip()}", 'yellow')
    else:
        print_colored("  Cloning Volatility3 (this may take a moment)...", 'yellow')
        ok, _, err = run_command(
            'git clone https://github.com/volatilityfoundation/volatility3.git',
            cwd=project_dir
        )
        if not ok:
            print_colored(f"  ✗ Clone failed: {err.strip()}", 'red')
            return False
        print_colored("  ✓ Volatility3 cloned", 'green')

    return True


def step_setup_venv(project_dir):
    """[3/7] Create virtual environment and install dependencies"""
    print_colored("=== [3/7] Setting Up Virtual Environment ===", 'cyan', 'bold')
    venv_dir      = project_dir / "venv"
    volatility_dir = project_dir / "volatility3"

    # Create venv
    if not venv_dir.exists():
        print_colored("  Creating virtual environment...", 'yellow')
        ok, _, err = run_command(f'"{sys.executable}" -m venv "{venv_dir}"')
        if not ok:
            print_colored(f"  ✗ venv creation failed: {err.strip()}", 'red')
            return False
        print_colored("  ✓ Virtual environment created", 'green')
    else:
        print_colored("  ✓ Virtual environment already exists", 'green')

    venv_python = get_venv_python(venv_dir)
    venv_pip    = get_venv_pip(venv_dir)

    # Upgrade pip
    run_command(f'"{venv_python}" -m pip install --upgrade pip --quiet')
    print_colored("  ✓ pip upgraded", 'green')

    # Volatility3 requirements
    req_file = volatility_dir / "requirements.txt"
    if req_file.exists():
        print_colored("  Installing Volatility3 dependencies...", 'yellow')
        ok, _, err = run_command(f'"{venv_pip}" install -r "{req_file}" --quiet')
        if ok:
            print_colored("  ✓ Volatility3 dependencies installed", 'green')
        else:
            print_colored(f"  ⚠ Some Volatility3 deps failed: {err.strip()[:120]}", 'yellow')

    # MCP packages
    for pkg in ['mcp', 'pydantic', 'typing-extensions']:
        ok, _, _ = run_command(f'"{venv_pip}" install {pkg} --quiet')
        print_colored(f"  {'✓' if ok else '⚠'} {pkg}", 'green' if ok else 'yellow')

    return True


def step_deploy_mcp_server(project_dir, script_dir):
    """[4/7] Copy releases/mcp_server.py → src/mcp_server.py"""
    print_colored("=== [4/7] Deploying MCP Server ===", 'cyan', 'bold')

    src_file  = script_dir / "releases" / "mcp_server.py"
    dest_file = project_dir / "src" / "mcp_server.py"

    if not src_file.exists():
        print_colored(f"  ✗ releases/mcp_server.py not found at: {src_file}", 'red')
        print_colored("  Please ensure releases/mcp_server.py exists in the repo folder.", 'yellow')
        return False

    shutil.copy2(src_file, dest_file)
    print_colored(f"  ✓ Copied mcp_server.py → {dest_file}", 'green')
    return True


def step_create_configs(project_dir):
    """[5/7] Generate MCP config files for VS Code and Claude Desktop"""
    print_colored("=== [5/7] Creating Configuration Files ===", 'cyan', 'bold')
    config_dir   = project_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    python_cmd   = get_python_cmd()
    launcher_path = str(project_dir / "launcher.py")

    windows_config = {
        "servers": {
            "volatility3-mcp": {
                "command": "python",
                "args": [launcher_path.replace('\\', '/')],
                "type": "stdio",
                "env": {"PYTHONPATH": str(project_dir / "volatility3").replace('\\', '/')}
            }
        },
        "inputs": []
    }

    unix_config = {
        "servers": {
            "volatility3-mcp": {
                "command": python_cmd,
                "args": [str(project_dir / "launcher.py")],
                "type": "stdio",
                "env": {"PYTHONPATH": str(project_dir / "volatility3")}
            }
        },
        "inputs": []
    }

    claude_config = {
        "mcpServers": {
            "volatility3-mcp": {
                "command": python_cmd,
                "args": [str(project_dir / "launcher.py")],
                "env": {"PYTHONPATH": str(project_dir / "volatility3")}
            }
        }
    }

    for filename, cfg, label in [
        ("mcp_windows.json", windows_config, "Windows VS Code"),
        ("mcp_linux.json",   unix_config,    "Linux/Mac VS Code"),
        ("mcp_claude.json",  claude_config,  "Claude Desktop"),
    ]:
        with open(config_dir / filename, 'w') as f:
            json.dump(cfg, f, indent=2)
        print_colored(f"  ✓ {filename}  ({label})", 'green')

    return True


def step_create_test_script(project_dir):
    """[6/7] Write tests/test_server.py"""
    print_colored("=== [6/7] Creating Test Script ===", 'cyan', 'bold')
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_content = r'''#!/usr/bin/env python3
"""Cross-Platform Test Script for Volatility3 MCP Server"""
import json, asyncio, sys, platform
from pathlib import Path

def print_colored(text, color='white', style='normal'):
    colors = {'red':'\033[91m','green':'\033[92m','yellow':'\033[93m',
               'blue':'\033[94m','cyan':'\033[96m','white':'\033[97m','reset':'\033[0m'}
    styles = {'bold':'\033[1m','underline':'\033[4m','normal':''}
    print(f"{styles.get(style,'')}{colors.get(color,'')}{text}{colors['reset']}")

def test_python_environment():
    print_colored("\nTesting Python Environment...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    vi = sys.version_info
    print_colored(f"Python Version: {vi.major}.{vi.minor}.{vi.micro}", 'white')
    if vi < (3, 8):
        print_colored("✗ Python version too old (need 3.8+)", 'red')
        return False
    print_colored("✓ Python version OK", 'green')
    project_dir = Path(__file__).parent.parent
    venv_python = (project_dir / "venv" / "Scripts" / "python.exe"
                   if platform.system() == 'Windows'
                   else project_dir / "venv" / "bin" / "python3")
    if venv_python.exists():
        print_colored("✓ Virtual environment found", 'green')
    else:
        print_colored("✗ Virtual environment not found", 'red')
        return False
    return True

def test_volatility_installation():
    print_colored("\nTesting Volatility3 Installation...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    volatility_dir = Path(__file__).parent.parent / "volatility3"
    if not volatility_dir.exists():
        print_colored("✗ Volatility3 directory not found", 'red')
        return False
    print_colored("✓ Volatility3 directory found", 'green')
    for f in ["vol.py", "volatility3", "requirements.txt"]:
        exists = (volatility_dir / f).exists()
        print_colored(f"  {'✓' if exists else '✗'} {f}", 'green' if exists else 'yellow')
    return True

def test_mcp_server():
    print_colored("\nTesting MCP Server...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    server_file = Path(__file__).parent.parent / "src" / "mcp_server.py"
    if not server_file.exists():
        print_colored("✗ MCP server file not found", 'red')
        return False
    print_colored("✓ MCP server file found", 'green')
    sys.path.insert(0, str(server_file.parent))
    try:
        import mcp_server  # noqa: F401
        print_colored("✓ MCP server module imported successfully", 'green')
    except ImportError as e:
        print_colored(f"✗ Import failed: {e}", 'red')
        return False
    tools = ["load_memory_image","get_image_info","list_available_plugins",
             "build_plugin_command","execute_plugin","analyze_error",
             "suggest_plugins","batch_execute","generate_documentation"]
    print_colored("Expected tools:", 'white')
    for t in tools:
        print_colored(f"  • {t}", 'blue')
    return True

def test_configuration_files():
    print_colored("\nTesting Configuration Files...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    config_dir = Path(__file__).parent.parent / "config"
    if not config_dir.exists():
        print_colored("✗ Config directory not found", 'red')
        return False
    print_colored("✓ Config directory found", 'green')
    for cf in ["mcp_windows.json","mcp_linux.json","mcp_claude.json"]:
        p = config_dir / cf
        if not p.exists():
            print_colored(f"✗ {cf} — not found", 'yellow')
            continue
        try:
            json.load(open(p))
            print_colored(f"✓ {cf} — valid JSON", 'green')
        except json.JSONDecodeError:
            print_colored(f"✗ {cf} — invalid JSON", 'red')
    return True

def test_project_structure():
    print_colored("\nTesting Project Structure...", 'cyan', 'bold')
    print_colored("-" * 50, 'cyan')
    project_dir = Path(__file__).parent.parent
    ok = True
    for d in ["src","config","logs","memory_images","reports","tests","scripts","volatility3","venv"]:
        exists = (project_dir / d).exists()
        print_colored(f"  {'✓' if exists else '✗'} {d}/", 'green' if exists else 'yellow')
        if not exists: ok = False
    return ok

async def run_all_tests():
    print_colored("="*70, 'cyan')
    print_colored("VOLATILITY3 MCP SERVER — TEST SUITE", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    print_colored(f"System: {platform.system()} {platform.release()}", 'white')
    print_colored(f"Python: {sys.executable}", 'white')
    print_colored("="*70, 'cyan')
    tests  = [test_python_environment, test_volatility_installation,
              test_mcp_server, test_configuration_files, test_project_structure]
    passed = sum(1 for t in tests if t())
    print_colored("\n" + "="*70, 'cyan')
    print_colored("TEST RESULTS", 'cyan', 'bold')
    print_colored("="*70, 'cyan')
    if passed == len(tests):
        print_colored(f"✓ All tests passed ({passed}/{len(tests)})", 'green', 'bold')
        print_colored("Your Volatility3 MCP Server setup is ready!", 'green')
    else:
        print_colored(f"✗ {len(tests)-passed} test(s) failed ({passed}/{len(tests)})", 'red', 'bold')
        print_colored("Please fix the issues above before proceeding.", 'yellow')
    print_colored("="*70, 'cyan')

if __name__ == "__main__":
    asyncio.run(run_all_tests())
'''

    test_file = tests_dir / "test_server.py"
    test_file.write_text(test_content, encoding='utf-8')
    if platform.system() != 'Windows':
        test_file.chmod(test_file.stat().st_mode | stat.S_IEXEC)
    print_colored(f"  ✓ tests/test_server.py", 'green')
    return True


def step_create_launcher(project_dir):
    """[7/7] Write launcher.py"""
    print_colored("=== [7/7] Creating Launcher ===", 'cyan', 'bold')

    launcher_content = r'''#!/usr/bin/env python3
"""Cross-platform launcher for the Volatility3 MCP Server (stdio transport)."""
import sys, os, platform, subprocess
from pathlib import Path

def setup_environment(project_dir):
    vol_dir = project_dir / "volatility3"
    cur = os.environ.get('PYTHONPATH', '')
    os.environ['PYTHONPATH'] = (f"{vol_dir}{os.pathsep}{cur}" if cur else str(vol_dir))
    os.environ['PYTHONUNBUFFERED'] = '1'

def find_python(project_dir):
    venv = project_dir / "venv"
    if platform.system() == 'Windows':
        return venv / "Scripts" / "python.exe"
    p = venv / "bin" / "python3"
    return p if p.exists() else venv / "bin" / "python"

def main():
    project_dir   = Path(__file__).parent
    python_exe    = find_python(project_dir)
    server_script = project_dir / "src" / "mcp_server.py"

    for path, label in [(python_exe, "Virtual environment"), (project_dir / "volatility3", "Volatility3"),
                         (server_script, "MCP server script")]:
        if not path.exists():
            print(f"ERROR: {label} not found at {path}", file=sys.stderr)
            print("Please re-run setup.py", file=sys.stderr)
            return 1

    setup_environment(project_dir)
    try:
        return subprocess.run([str(python_exe), str(server_script)], cwd=project_dir).returncode
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''

    launcher_path = project_dir / "launcher.py"
    launcher_path.write_text(launcher_content, encoding='utf-8')
    if platform.system() != 'Windows':
        launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IEXEC)
    print_colored(f"  ✓ launcher.py", 'green')
    return True


# ─────────────────────────── main ───────────────────────────────────────────

def display_header():
    print_colored("=" * 80, 'cyan')
    print_colored("VOLATILITY3 MCP SERVER — COMPLETE SETUP", 'cyan', 'bold')
    print_colored("=" * 80, 'cyan')
    for k, v in [('System',  f"{platform.system()} {platform.release()}"),
                 ('Machine', platform.machine()),
                 ('Python',  f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
                 ('Python executable', sys.executable)]:
        print_colored(f"  {k}: {v}", 'white')
    print_colored("=" * 80, 'cyan')
    print()


def main():
    display_header()

    script_dir  = Path(__file__).parent.resolve()
    project_dir = Path.home() / "volatility-mcp-server"

    print_colored("This script will:", 'white', 'bold')
    steps = [
        "1. Check prerequisites (Python, git, pip, venv)",
        "2. Create project structure & clone Volatility3",
        "3. Create virtual environment & install dependencies",
        "4. Deploy releases/mcp_server.py → ~/volatility-mcp-server/src/",
        "5. Generate MCP config files (VS Code + Claude Desktop)",
        "6. Create test script",
        "7. Create launcher",
    ]
    for s in steps:
        print_colored(f"  {s}", 'blue')
    print()
    print_colored(f"Install location: {project_dir}", 'yellow')
    print()

    try:
        response = input("Proceed? [Y/n]: ").strip().lower()
    except KeyboardInterrupt:
        print()
        print_colored("Setup cancelled.", 'yellow')
        return 1
    if response not in ('', 'y', 'yes'):
        print_colored("Setup cancelled.", 'yellow')
        return 1

    print()
    start = time.time()
    results = {}

    # ── Step 1: prerequisites ──────────────────────────────────────────────
    ok = step_check_prerequisites()
    results['Prerequisites'] = ok
    if not ok:
        try:
            if input("\nPrerequisites failed. Continue anyway? [y/N]: ").strip().lower() not in ('y', 'yes'):
                print_colored("Setup aborted.", 'red')
                return 1
        except KeyboardInterrupt:
            print()
            return 1
    print()

    # ── Step 2: project structure + Volatility3 ────────────────────────────
    project_dir.mkdir(parents=True, exist_ok=True)
    ok = step_setup_project(project_dir)
    results['Project Setup'] = ok
    if not ok:
        try:
            if input("\nProject setup failed. Continue? [y/N]: ").strip().lower() not in ('y', 'yes'):
                print_colored("Setup aborted.", 'red')
                return 1
        except KeyboardInterrupt:
            print()
            return 1
    print()

    # ── Step 3: venv + deps ────────────────────────────────────────────────
    ok = step_setup_venv(project_dir)
    results['Virtual Environment'] = ok
    print()

    # ── Step 4: deploy mcp_server.py ──────────────────────────────────────
    ok = step_deploy_mcp_server(project_dir, script_dir)
    results['MCP Server Deploy'] = ok
    if not ok:
        print_colored("  ✗ MCP server deployment failed — setup cannot continue.", 'red')
        return 1
    print()

    # ── Step 5: configs ────────────────────────────────────────────────────
    results['Configs'] = step_create_configs(project_dir)
    print()

    # ── Step 6: test script ────────────────────────────────────────────────
    results['Test Script'] = step_create_test_script(project_dir)
    print()

    # ── Step 7: launcher ──────────────────────────────────────────────────
    results['Launcher'] = step_create_launcher(project_dir)
    print()

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed   = time.time() - start
    all_ok    = all(results.values())
    failed    = [k for k, v in results.items() if not v]

    print_colored("=" * 80, 'cyan')
    print_colored("SETUP COMPLETE", 'cyan', 'bold')
    print_colored("=" * 80, 'cyan')
    print_colored(f"  Time: {elapsed:.1f}s   Steps: {sum(results.values())}/{len(results)}", 'white')
    if failed:
        print_colored(f"  Failed: {', '.join(failed)}", 'red')
    print()

    if all_ok:
        print_colored("  All steps completed successfully!", 'green', 'bold')
        print()
        print_colored("  Project layout:", 'white', 'bold')
        for line in [
            f"  {project_dir}/",
            "    volatility3/          # Volatility3 framework",
            "    src/mcp_server.py     # MCP server (deployed from releases/)",
            "    config/               # mcp_windows.json, mcp_linux.json, mcp_claude.json",
            "    tests/test_server.py  # test suite",
            "    logs/                 # server logs",
            "    memory_images/        # place .mem / .raw dumps here",
            "    reports/              # generated reports",
            "    venv/                 # Python virtual environment",
            "    launcher.py           # entry point",
        ]:
            print_colored(line, 'blue' if line.endswith('/') or line.strip().startswith(str(project_dir)) else 'white')
        print()
        print_colored("  Next steps:", 'yellow', 'bold')
        print_colored("  1. Add a memory image to ~/volatility-mcp-server/memory_images/", 'white')
        print_colored("  2. Copy the appropriate config from ~/volatility-mcp-server/config/ to your MCP client", 'white')
        print_colored("  3. Run tests:  python ~/volatility-mcp-server/tests/test_server.py", 'white')
        print_colored("  4. Launch:     python ~/volatility-mcp-server/launcher.py", 'white')
    else:
        print_colored("  Setup completed with errors — review the output above.", 'yellow', 'bold')

    print_colored("=" * 80, 'cyan')
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_colored("Setup interrupted by user.", 'yellow')
        sys.exit(1)

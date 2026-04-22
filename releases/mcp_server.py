#!/usr/bin/env python3
"""
Adaptive Volatility3 MCP Server
Author: Vrashith Jakkaraju
"""

import sys
import os
import json
import asyncio
import logging
import subprocess
import re
import traceback
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum

# Add volatility3 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "volatility3"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / "mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class OSType(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "mac"
    UNKNOWN = "unknown"


class AdaptiveVolatilityMCPServer:
    """MCP Server for Volatility3 memory forensics."""

    def __init__(self):
        self.server = Server("volatility3-adaptive-mcp")
        self.is_windows = platform.system() == "Windows"
        self.memory_images_dir = Path(__file__).parent.parent / "memory_images"
        self.reports_dir = Path(__file__).parent.parent / "reports"
        self.current_image: Optional[str] = None
        self.image_info: Dict[str, Any] = {}
        self.os_type = OSType.UNKNOWN
        self.available_plugins: List[Dict[str, str]] = []
        self.error_history: List[Dict[str, Any]] = []
        self.analysis_history: List[Dict[str, Any]] = []
        self.findings: List[str] = []
        self.volatility_path = Path(__file__).parent.parent / "volatility3"
        self.last_command_output = ""

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.memory_images_dir.mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent.parent / "logs").mkdir(parents=True, exist_ok=True)

        self._setup_handlers()
        logger.info(
            f"Volatility3 MCP Server initialized at "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _fail(self, command_parts: List[str], msg: str) -> Tuple[bool, str]:
        """Record a command failure and return (False, msg)."""
        logger.error(msg)
        self.error_history.append({
            "command": ' '.join(command_parts),
            "error": msg,
            "timestamp": self._now().isoformat(),
        })
        return False, msg

    def _run_volatility_command(
        self, command_parts: List[str], timeout: int = 300
    ) -> Tuple[bool, str]:
        """Run a Volatility3 command, returning (success, raw_output)."""
        vol_script = self.volatility_path / "vol.py"
        cmd = [sys.executable, str(vol_script)] + command_parts
        logger.info(f"Running: {' '.join(cmd)}")

        try:
            if self.is_windows:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    cwd=str(self.volatility_path),
                    startupinfo=si,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                    encoding='utf-8',
                    errors='replace',
                )
                proc.stdin.close()
                try:
                    stdout, stderr = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    return self._fail(command_parts, f"Command timed out after {timeout}s")
                rc = proc.returncode
            else:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.volatility_path),
                    encoding='utf-8',
                    errors='replace',
                )
                stdout, stderr, rc = res.stdout, res.stderr, res.returncode

            output = (stdout or "") + ("\n" + stderr if stderr else "")
            self.last_command_output = output
            success = rc == 0
            ts = self._now().isoformat()
            self.analysis_history.append({
                "command": ' '.join(command_parts),
                "timestamp": ts,
                "success": success,
                "output_preview": output[:500],
            })
            if not success:
                self.error_history.append({
                    "command": ' '.join(command_parts),
                    "error": output,
                    "timestamp": ts,
                })
            return success, output

        except subprocess.TimeoutExpired:
            return self._fail(command_parts, f"Command timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Subprocess error: {e}", exc_info=True)
            return self._fail(command_parts, f"Error running command: {e}")

    def _extract_plugin_name(self, command: str) -> str:
        """
        Extract the plugin name from a command string like
        '-f /path/to/image.vmem windows.pslist.PsList --pid 123'.
        Skips the -f flag and its argument, then returns the first
        dotted token that looks like a plugin name.
        """
        parts = command.split()
        skip_next = False
        for part in parts:
            if skip_next:
                skip_next = False
                continue
            if part == "-f":
                skip_next = True
                continue
            if part.startswith("-"):
                continue
            # First non-flag, non-path token with at least one dot
            if "." in part and not part.startswith("/") and not part.startswith("C:\\"):
                return part
        return command[:80]

    def _strip_noise(self, output: str) -> str:
        """Remove Volatility3 progress lines; show VMware VMSS warning at most once."""
        vmware_warned = False
        clean = []
        for line in output.split('\n'):
            if re.match(r'^\s*Progress:\s+[\d.]+', line):
                continue
            if re.match(r'^\s*WARNING\s+volatility3\.framework\.layers\.vmware:', line):
                if not vmware_warned:
                    clean.append(line)
                    vmware_warned = True
                continue
            clean.append(line)
        # Strip trailing blank lines
        while clean and not clean[-1].strip():
            clean.pop()
        return '\n'.join(clean)

    # ── OS / Plugin detection ──────────────────────────────────────────────────

    def _detect_os_type(self, info_output: str) -> OSType:
        lo = info_output.lower()
        if re.search(r'windows|nt build', lo):
            return OSType.WINDOWS
        if re.search(r'linux|kernel', lo):
            return OSType.LINUX
        if re.search(r'darwin|mac', lo):
            return OSType.MAC
        return OSType.UNKNOWN

    def _parse_plugin_list(self, output: str) -> List[Dict[str, str]]:
        """
        Parse plugin entries from 'vol.py --info' output.
        Each plugin line has the form:
            windows.pslist.PsList      Lists the processes present in a particular windows memory image.
        """
        plugins: List[Dict[str, str]] = []
        seen: set = set()
        for line in output.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            # Match a dotted plugin name, optionally followed by 2+ spaces and a description
            m = re.match(r'^(\w+(?:\.\w+)+)(?:\s{2,}(.*))?$', stripped)
            if not m:
                continue
            name = m.group(1)
            desc = (m.group(2) or "").strip()
            if name not in seen:
                seen.add(name)
                plugins.append({
                    "name": name,
                    "description": desc,
                    "category": self._categorize_plugin(name),
                })
        return plugins

    def _categorize_plugin(self, plugin_name: str) -> str:
        n = plugin_name.lower()
        if re.search(
            r'pslist|pstree|psscan|psaux|cmdline|envars|handles|privileges|'
            r'sessions|getsid|joblink|hollow|process', n
        ):
            return "Process"
        if re.search(r'net|socket|conn', n):
            return "Network"
        if re.search(r'file|vad|dumpfile|pedump', n):
            return "Files"
        if re.search(
            r'registry|reg\.|hive|printkey|userassist|amcache|shimcache|'
            r'scheduled_task|certificates|getcellroutine', n
        ):
            return "Registry"
        if re.search(
            r'malfind|ldrmodule|svcdiff|drivermodule|hollowprocess|'
            r'pebmasquerade|processghost|skeleton|unhooked|suspicious_thread|'
            r'direct_system|indirect_system|malware', n
        ):
            return "Malware"
        if re.search(r'module|driver|kernel|ssdt|callback|kpcr|unloaded', n):
            return "Kernel"
        if re.search(r'memmap|dump', n):
            return "Memory Dump"
        if re.search(r'timeliner|mftparser|timeline', n):
            return "Timeline"
        if re.search(r'info|statistic|crashinfo|virtmap|bigpool|frameworkinfo|isfinfo', n):
            return "Information"
        return "Other"

    async def _refresh_plugin_list(self) -> None:
        """
        Populate self.available_plugins using 'vol.py --info'.
        Note: --info exits non-zero on some builds; we use the output regardless.
        Falls back to parsing the choices list from the 'invalid choice' error.
        """
        vol_script = self.volatility_path / "vol.py"
        cmd = [sys.executable, str(vol_script), "--info"]
        try:
            if self.is_windows:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE, text=True,
                    cwd=str(self.volatility_path), startupinfo=si,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                    encoding='utf-8', errors='replace',
                )
                proc.stdin.close()
                stdout, stderr = proc.communicate(timeout=60)
            else:
                res = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                    cwd=str(self.volatility_path), encoding='utf-8', errors='replace',
                )
                stdout, stderr = res.stdout, res.stderr
            output = (stdout or "") + ("\n" + stderr if stderr else "")
        except Exception as e:
            logger.warning(f"--info failed: {e}")
            output = ""

        plugins = self._parse_plugin_list(output)
        if plugins:
            self.available_plugins = plugins
            logger.info(f"Loaded {len(plugins)} plugins via --info")
            return

        # Fallback: provoke the 'invalid choice' error to get the full plugin list
        vol_script = self.volatility_path / "vol.py"
        cmd_fb = [sys.executable, str(vol_script), "-f",
                  self.current_image or ".", "invalid_plugin_z9"]
        try:
            if self.is_windows:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                proc = subprocess.Popen(
                    cmd_fb, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE, text=True,
                    cwd=str(self.volatility_path), startupinfo=si,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                    encoding='utf-8', errors='replace',
                )
                proc.stdin.close()
                _, err_output = proc.communicate(timeout=30)
            else:
                res = subprocess.run(
                    cmd_fb, capture_output=True, text=True, timeout=30,
                    cwd=str(self.volatility_path), encoding='utf-8', errors='replace',
                )
                err_output = res.stderr
        except Exception as e:
            logger.warning(f"Fallback plugin probe failed: {e}")
            err_output = ""

        m = re.search(r'choose from\s+(.*?)\)', err_output, re.DOTALL)
        if m:
            names = re.findall(r'\w+(?:\.\w+)+', m.group(1))
            self.available_plugins = [
                {"name": n, "description": "", "category": self._categorize_plugin(n)}
                for n in names
            ]
            logger.info(f"Loaded {len(self.available_plugins)} plugins via fallback")
        else:
            logger.warning("Could not load plugin list — both --info and fallback failed")

    # ── Error analysis ─────────────────────────────────────────────────────────

    def _analyze_error(self, error_output: str, command: str) -> Dict[str, Any]:
        """Classify an error and return structured remediation guidance."""
        analysis: Dict[str, Any] = {
            "error_type": "unknown",
            "root_cause": "",
            "suggestions": [],
            "alternative_plugins": [],
        }
        err = error_output.lower()

        if re.search(r'invalid choice|argument plugin', err):
            analysis["error_type"] = "plugin_not_found"
            analysis["root_cause"] = "Plugin name is invalid for this Volatility3 build or OS"
            analysis["suggestions"] = [
                "Use 'list_available_plugins' to find exact plugin names",
                "Windows plugins require a Windows memory image (and vice versa)",
            ]
            m = re.search(r'invalid choice\s+(\S+)', err)
            if m:
                bad = m.group(1).rstrip('(,').lower()
                parts = re.split(r'[\s.]+', bad)
                alts = [
                    p for p in self.available_plugins
                    if any(part in p["name"].lower() for part in parts if len(part) > 2)
                ]
                analysis["alternative_plugins"] = alts[:5]

        elif re.search(r'no such plugin|plugin.{0,20}not.{0,20}found', err):
            analysis["error_type"] = "plugin_not_found"
            analysis["root_cause"] = "Plugin does not exist or is not installed"
            analysis["suggestions"] = ["Use 'list_available_plugins' to see all available plugins"]

        elif re.search(r'unsatisfied.{0,20}requirement|symbol.{0,20}not.{0,20}found', err):
            analysis["error_type"] = "incompatible_profile"
            analysis["root_cause"] = "Plugin requirements not met for this OS / image version"
            analysis["suggestions"] = [
                "Plugin may not support this specific OS version",
                "Try a more generic alternative plugin",
            ]

        elif re.search(r'invalid.{0,20}layer|layer.{0,20}not.{0,20}found', err):
            analysis["error_type"] = "layer_error"
            analysis["root_cause"] = "Memory layer / address-translation failure"
            analysis["suggestions"] = [
                "Image may be incomplete or corrupted",
                "Run windows.info or linux.info to verify image integrity",
            ]

        elif re.search(r'permission|access denied', err):
            analysis["error_type"] = "permission_error"
            analysis["root_cause"] = "Insufficient permissions on image file or output directory"
            analysis["suggestions"] = [
                "Check read permissions on the memory image",
                "Ensure write permissions on the output directory",
            ]

        elif 'timeout' in err:
            analysis["error_type"] = "timeout"
            analysis["root_cause"] = "Operation exceeded time limit"
            analysis["suggestions"] = [
                "Scope the analysis with --pid or other filters",
                "Increase the timeout parameter",
            ]

        else:
            if 'pid' in err:
                analysis["suggestions"].append("Verify the PID exists using pslist")
            if 'file' in err:
                analysis["suggestions"].append("Verify file path and permissions")
            if 'memory' in err:
                analysis["suggestions"].append("Image may be corrupted or incomplete")
            if not analysis["suggestions"]:
                analysis["suggestions"].append("Check logs/mcp_server.log for full details")

        return analysis

    # ── Suspicious-activity detection ──────────────────────────────────────────

    def _analyze_for_suspicious_activity(self, output: str, plugin_name: str) -> List[str]:
        """Identify forensic indicators in plugin output."""
        findings: List[str] = []
        lines = [l for l in output.split('\n') if l.strip()]
        lo = output.lower()

        # malfind — injection indicators
        if "malfind" in plugin_name.lower():
            if re.search(r'page_execute_readwrite|rwx', lo):
                findings.append("HIGH RISK: Executable+writable memory region (code injection indicator)")
            if re.search(r'^4d5a|^MZ', output, re.IGNORECASE | re.MULTILINE):
                findings.append("HIGH RISK: PE header found in suspicious memory region")

        # pslist / pstree / psscan — process anomalies
        if re.search(r'pslist|pstree|psscan', plugin_name.lower()):
            data_rows = [
                l for l in lines
                if '\t' in l and not l.startswith(('PID', 'Volatility'))
            ]
            if data_rows:
                findings.append(
                    f"System running {len(data_rows)} processes — analyzed for anomalies"
                )
            for line in lines:
                ll = line.lower()
                if 'scvhost.exe' in ll:
                    findings.append(
                        "HIGH RISK: Process masquerading — scvhost.exe "
                        "(typosquat of svchost.exe)"
                    )

        # cmdline — suspicious command patterns
        if "cmdline" in plugin_name.lower():
            for line in lines:
                ll = line.lower()
                if re.search(
                    r'powershell.{0,10}(-enc|-nop|-windowstyle\s+hidden)|iex\s*\(', ll
                ):
                    findings.append(
                        f"HIGH RISK: Obfuscated/encoded PowerShell — {line.strip()[:120]}"
                    )
                if re.search(r'nc\s+-[lv]|ncat|netcat', ll):
                    findings.append(
                        f"MEDIUM RISK: Netcat/listener command — {line.strip()[:120]}"
                    )

        # Network — known C2 ports
        if re.search(r'net|socket|conn', plugin_name.lower()):
            for port in ["4444", "1337", "31337", "12345"]:
                if port in output:
                    findings.append(f"HIGH RISK: Connection on known C2 port {port}")

        # Global — offensive tool names
        for tool in ["mimikatz", "lazagne", "meterpreter", "cobaltstrike", "pwdump"]:
            if tool in lo and not any(tool in f for f in findings):
                findings.append(f"CRITICAL: Offensive tool artifact detected — {tool}")

        return findings

    # ── MCP handler setup ──────────────────────────────────────────────────────

    def _setup_handlers(self):
        """Register all MCP tool definitions and dispatch."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="load_memory_image",
                    description=(
                        "Load a memory image file and auto-detect the OS type. "
                        "Always call this first before any other tool."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": (
                                    "Absolute path to the memory image "
                                    "(.mem, .raw, .vmem, etc.)"
                                )
                            }
                        },
                        "required": ["image_path"]
                    }
                ),
                Tool(
                    name="get_image_info",
                    description=(
                        "Return metadata about the currently loaded memory image: "
                        "OS type, file size, and plugin counts by category."
                    ),
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="list_available_plugins",
                    description=(
                        "List plugins available for the loaded image. "
                        "Optionally filter by category or search term."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": (
                                    "Category filter: Process, Network, Files, Registry, "
                                    "Malware, Kernel, Memory Dump, Timeline, "
                                    "Information, Other"
                                )
                            },
                            "search": {
                                "type": "string",
                                "description": (
                                    "Plugin name or description substring to search"
                                )
                            }
                        }
                    }
                ),
                Tool(
                    name="build_plugin_command",
                    description=(
                        "Validate a plugin name and construct the full vol.py command. "
                        "Use show_help=true to see all options for a specific plugin."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plugin": {
                                "type": "string",
                                "description": (
                                    "Exact plugin name (e.g. windows.pslist.PsList)"
                                )
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Plugin parameters as key-value pairs",
                                "additionalProperties": True
                            },
                            "show_help": {
                                "type": "boolean",
                                "description": "Print the plugin's own help text",
                                "default": False
                            }
                        },
                        "required": ["plugin"]
                    }
                ),
                Tool(
                    name="execute_plugin",
                    description=(
                        "Run a Volatility3 plugin against the loaded image. "
                        "Returns cleaned output (progress spam stripped) with "
                        "automatic anomaly detection."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plugin": {
                                "type": "string",
                                "description": "Exact plugin name"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Plugin parameters as key-value pairs",
                                "additionalProperties": True
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds (default: 300)",
                                "default": 300
                            }
                        },
                        "required": ["plugin"]
                    }
                ),
                Tool(
                    name="analyze_error",
                    description=(
                        "Diagnose recent plugin failures, identify root causes, "
                        "and suggest fixes or alternative plugins."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_history": {
                                "type": "boolean",
                                "description": (
                                    "Show all recent errors instead of just the last one"
                                ),
                                "default": True
                            }
                        }
                    }
                ),
                Tool(
                    name="suggest_plugins",
                    description=(
                        "Recommend relevant plugins for a given investigation goal. "
                        "Examples: 'find injected code', 'list network connections', "
                        "'ransomware indicators'."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "What you want to investigate or detect"
                            }
                        },
                        "required": ["goal"]
                    }
                ),
                Tool(
                    name="batch_execute",
                    description=(
                        "Run multiple plugins sequentially in one call. "
                        "Returns per-plugin status and cleaned output."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "commands": {
                                "type": "array",
                                "description": "Ordered list of plugin executions",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plugin": {"type": "string"},
                                        "parameters": {
                                            "type": "object",
                                            "additionalProperties": True
                                        }
                                    },
                                    "required": ["plugin"]
                                }
                            }
                        },
                        "required": ["commands"]
                    }
                ),
                Tool(
                    name="get_analysis_context",
                    description=(
                        "Return the complete session state as structured JSON: "
                        "image info, operation history, findings, and errors. "
                        "Use this before writing a report."
                    ),
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="save_report",
                    description=(
                        "Write an analysis report to the reports directory. "
                        "Creates the file and writes content in a single call. "
                        "Call get_analysis_context first to gather session data."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Full report content (Markdown recommended)"
                            },
                            "filename": {
                                "type": "string",
                                "description": (
                                    "Output filename without path. "
                                    "Auto-generated timestamped name if omitted."
                                )
                            }
                        },
                        "required": ["content"]
                    }
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            logger.info(f"Tool call: {name} | args: {arguments}")
            try:
                if name == "load_memory_image":
                    result = await self._handle_load_image(arguments.get("image_path"))
                elif name == "get_image_info":
                    result = await self._handle_get_info()
                elif name == "list_available_plugins":
                    result = await self._handle_list_plugins(
                        arguments.get("category"), arguments.get("search")
                    )
                elif name == "build_plugin_command":
                    result = await self._handle_build_command(
                        arguments.get("plugin"),
                        arguments.get("parameters", {}),
                        arguments.get("show_help", False),
                    )
                elif name == "execute_plugin":
                    result = await self._handle_execute_plugin(
                        arguments.get("plugin"),
                        arguments.get("parameters", {}),
                        arguments.get("timeout", 300),
                    )
                elif name == "analyze_error":
                    result = await self._handle_analyze_error(
                        arguments.get("include_history", True)
                    )
                elif name == "suggest_plugins":
                    result = await self._handle_suggest_plugins(arguments.get("goal"))
                elif name == "batch_execute":
                    result = await self._handle_batch_execute(
                        arguments.get("commands", [])
                    )
                elif name == "get_analysis_context":
                    result = await self._handle_get_analysis_context()
                elif name == "save_report":
                    result = await self._handle_save_report(
                        arguments.get("content"), arguments.get("filename")
                    )
                else:
                    result = f"Unknown tool: {name}"

                return (
                    result if isinstance(result, list)
                    else [TextContent(type="text", text=str(result))]
                )

            except Exception as e:
                logger.error(f"Tool '{name}' raised: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=f"Internal error in tool '{name}': {e}\n\n{traceback.format_exc()}"
                )]

    # ── Tool handlers ──────────────────────────────────────────────────────────

    async def _handle_load_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            path = self.memory_images_dir / image_path
            if not path.exists():
                return f"Memory image not found: {image_path}"

        for os_cmd in ["windows.info", "linux.info", "mac.info"]:
            success, raw = self._run_volatility_command(
                ["-f", str(path), os_cmd], timeout=120
            )
            if success:
                self.current_image = str(path)
                self.os_type = self._detect_os_type(raw)
                self.image_info = {
                    "path": str(path),
                    "size": path.stat().st_size,
                    "os_type": self.os_type.value,
                    "loaded_at": self._now().isoformat(),
                }
                await self._refresh_plugin_list()
                clean = self._strip_noise(raw)
                return (
                    f"Successfully loaded: {path.name}\n"
                    f"OS Type:  {self.os_type.value}\n"
                    f"Size:     {self.image_info['size'] / (1024 ** 3):.2f} GB\n"
                    f"Plugins:  {len(self.available_plugins)}\n\n"
                    f"Image Details:\n{clean}"
                )

        return (
            "Failed to load image — OS detection unsuccessful "
            "(tried windows.info, linux.info, mac.info)"
        )

    async def _handle_get_info(self) -> str:
        if not self.current_image:
            return "No memory image loaded."

        categories: Dict[str, int] = {}
        for p in self.available_plugins:
            cat = p.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1

        lines = [
            "Memory Image:",
            f"  Path:    {self.current_image}",
            f"  OS:      {self.os_type.value}",
            f"  Size:    {self.image_info.get('size', 0) / (1024 ** 3):.2f} GB",
            f"  Loaded:  {self.image_info.get('loaded_at', 'Unknown')}",
            f"  Plugins: {len(self.available_plugins)}",
            "",
            "Plugin Categories:",
        ]
        for cat, count in sorted(categories.items()):
            lines.append(f"  {cat}: {count}")
        return '\n'.join(lines)

    async def _handle_list_plugins(
        self, category: Optional[str], search: Optional[str]
    ) -> str:
        if not self.current_image:
            return "No memory image loaded."
        if not self.available_plugins:
            await self._refresh_plugin_list()

        plugins = self.available_plugins
        if category:
            plugins = [p for p in plugins if p["category"].lower() == category.lower()]
        if search:
            sl = search.lower()
            plugins = [
                p for p in plugins
                if sl in p["name"].lower() or sl in p.get("description", "").lower()
            ]
        if not plugins:
            return "No plugins found matching the criteria."

        by_cat: Dict[str, list] = {}
        for p in plugins:
            by_cat.setdefault(p["category"], []).append(p)

        lines = [f"Available Plugins ({len(plugins)} found):", "=" * 80]
        for cat in sorted(by_cat):
            lines += [f"\n{cat}:", "-" * 40]
            for p in sorted(by_cat[cat], key=lambda x: x["name"]):
                desc = p.get("description", "")
                lines.append(
                    f"  {p['name']:<50} {desc}" if desc else f"  {p['name']}"
                )
        return '\n'.join(lines)

    async def _handle_build_command(
        self, plugin: str, parameters: Dict[str, Any], show_help: bool
    ) -> str:
        if not self.current_image:
            return "No memory image loaded."

        cmd_parts = ["-f", self.current_image, plugin]

        if show_help:
            cmd_parts.append("--help")
            _, output = self._run_volatility_command(cmd_parts, timeout=30)
            return f"Help for {plugin}:\n\n{self._strip_noise(output)}"

        for key, value in parameters.items():
            flag = key if key.startswith("--") else f"--{key}"
            cmd_parts.append(flag)
            if value is not True:
                cmd_parts.append(str(value))

        # Early validation: detect bad plugin names before execution
        _, test_out = self._run_volatility_command(cmd_parts + ["--help"], timeout=30)
        if re.search(r'invalid choice|argument PLUGIN', test_out):
            return (
                f"Invalid plugin name '{plugin}'.\n"
                f"Use list_available_plugins to find the correct name.\n\n"
                f"{test_out[:600]}"
            )

        return (
            f"Command ready:\n  vol.py {' '.join(cmd_parts)}\n\n"
            f"Execute with:\n"
            f"  execute_plugin(plugin='{plugin}', parameters={parameters})"
        )

    async def _handle_execute_plugin(
        self, plugin: str, parameters: Dict[str, Any], timeout: int
    ) -> str:
        if not self.current_image:
            return "No memory image loaded."

        cmd_parts = ["-f", self.current_image, plugin]
        for key, value in parameters.items():
            flag = key if key.startswith("--") else f"--{key}"
            cmd_parts.append(flag)
            if value is not True:
                cmd_parts.append(str(value))

        success, raw = self._run_volatility_command(cmd_parts, timeout=timeout)
        output = self._strip_noise(raw)

        new_findings = self._analyze_for_suspicious_activity(output, plugin)
        for f in new_findings:
            if f not in self.findings:
                self.findings.append(f)

        if not success:
            analysis = self._analyze_error(raw, ' '.join(cmd_parts))
            lines = [
                "Plugin execution failed:",
                f"  Command: vol.py {' '.join(cmd_parts)}",
                "",
                "Error output:",
                output[:1200],
                "",
                f"Error type: {analysis['error_type']}",
                f"Root cause: {analysis['root_cause']}",
                "",
                "Suggestions:",
            ]
            for s in analysis["suggestions"]:
                lines.append(f"  • {s}")
            if analysis["alternative_plugins"]:
                lines += ["", "Alternative plugins:"]
                for a in analysis["alternative_plugins"]:
                    lines.append(f"  • {a['name']}: {a.get('description', '')}")
            return '\n'.join(lines)

        lines = [
            f"vol.py {' '.join(cmd_parts)}",
            "=" * 80,
            output,
        ]
        if new_findings:
            lines += ["", "⚠ Findings:"]
            for f in new_findings:
                lines.append(f"  • {f}")
        return '\n'.join(lines)

    async def _handle_analyze_error(self, include_history: bool) -> str:
        if not self.error_history:
            return "No errors recorded in this session."

        errors = self.error_history if include_history else self.error_history[-1:]
        lines = ["Error Analysis", "=" * 80, ""]
        for i, err in enumerate(errors[-5:], 1):
            analysis = self._analyze_error(err["error"], err["command"])
            lines += [
                f"[{i}] {err['timestamp'][:19]}",
                f"    Command:    {err['command']}",
                f"    Type:       {analysis['error_type']}",
                f"    Root cause: {analysis['root_cause']}",
                "    Fixes:",
            ]
            for s in analysis["suggestions"]:
                lines.append(f"      • {s}")
            if analysis["alternative_plugins"]:
                lines.append("    Alternatives:")
                for a in analysis["alternative_plugins"]:
                    lines.append(f"      • {a['name']}")
            lines.append("")
        return '\n'.join(lines)

    async def _handle_suggest_plugins(self, goal: str) -> str:
        if not self.available_plugins:
            return "No plugins available. Load a memory image first."

        gl = goal.lower()

        # Regex intent patterns → plugin name fragments
        keyword_patterns: Dict[str, List[str]] = {
            r'process|running proc|task list|pid|enumerate proc':
                ["pslist", "pstree", "psscan", "psaux"],
            r'command.?line|argument|cmdline':
                ["cmdline", "psaux"],
            r'network|connection|socket|port|traffic':
                ["netscan", "netstat", "sockscan", "sockstat"],
            r'file|filesystem|open file':
                ["filescan", "lsof", "dumpfiles"],
            r'registry|hive|reg key|regedit':
                ["registry", "printkey", "hivelist", "hivescan"],
            r'malware|inject|hollow|exploit|suspicious':
                ["malfind", "hollowprocess", "ldrmodule", "svcdiff", "pebmasquerade"],
            r'dll|loaded module|library':
                ["dlllist", "ldrmodules", "modscan", "modules"],
            r'driver|kernel module|rootkit':
                ["driverscan", "modules", "ssdt", "callbacks"],
            r'memory|vad|heap|address space':
                ["vadinfo", "vadwalk", "memmap"],
            r'timeline|event|history|mft':
                ["timeliner", "mftparser"],
            r'handle|object':
                ["handles"],
            r'service|svc':
                ["svcscan", "svclist", "svcdiff"],
            r'credential|password|hash|lsass':
                ["lsass", "cachedump", "hashdump"],
            r'dump|extract|export':
                ["dumpfiles", "pedump", "memmap"],
            r'ransomware|encryption|crypto':
                ["malfind", "handles", "filescan", "svcdiff"],
            r'privilege|token|impersonat':
                ["privileges", "getsids", "handles"],
            r'mutex|mutant':
                ["mutantscan"],
        }

        matched: List[Dict[str, str]] = []
        seen: set = set()

        for pattern, fragments in keyword_patterns.items():
            if re.search(pattern, gl):
                for frag in fragments:
                    for p in self.available_plugins:
                        if frag in p["name"].lower() and p["name"] not in seen:
                            matched.append(p)
                            seen.add(p["name"])

        # Fallback: token-level substring search
        if not matched:
            for token in gl.split():
                if len(token) < 3:
                    continue
                for p in self.available_plugins:
                    if token in p["name"].lower() and p["name"] not in seen:
                        matched.append(p)
                        seen.add(p["name"])

        if not matched:
            return (
                f"No plugins matched '{goal}'.\n"
                f"Use list_available_plugins to browse all options."
            )

        lines = [f'Suggestions for: "{goal}"', "=" * 60, ""]
        for p in matched[:15]:
            desc = p.get("description") or "—"
            lines += [
                f"  {p['name']}",
                f"    {desc}",
                f"    Category: {p['category']}",
                "",
            ]
        if len(matched) > 15:
            lines.append(
                f"  … and {len(matched) - 15} more. "
                f"Use list_available_plugins to see all."
            )
        return '\n'.join(lines)

    async def _handle_batch_execute(self, commands: List[Dict[str, Any]]) -> str:
        if not commands:
            return "No commands provided."

        lines = [f"Batch Execution — {len(commands)} plugin(s)", "=" * 80]
        results: List[bool] = []

        for i, cmd in enumerate(commands, 1):
            plugin = cmd.get("plugin", "")
            params = cmd.get("parameters", {})
            lines += ["", f"[{i}/{len(commands)}] {plugin}", "-" * 50]
            out = await self._handle_execute_plugin(plugin, params, 300)
            ok = "execution failed" not in out.lower()
            lines.append("✓ OK" if ok else "✗ FAILED")
            lines.append(out)
            results.append(ok)

        ok_count = sum(results)
        lines += [
            "",
            "=" * 80,
            f"Summary: {ok_count}/{len(commands)} succeeded, "
            f"{len(commands) - ok_count}/{len(commands)} failed",
        ]
        return '\n'.join(lines)

    async def _handle_get_analysis_context(self) -> str:
        """Return structured session state for use when composing reports."""
        context = {
            "session": {
                "image": self.current_image,
                "image_name": (
                    Path(self.current_image).name if self.current_image else None
                ),
                "os": self.os_type.value,
                "plugins_loaded": len(self.available_plugins),
                "session_start": (
                    self.analysis_history[0]["timestamp"]
                    if self.analysis_history else None
                ),
            },
            "summary": {
                "total_ops": len(self.analysis_history),
                "succeeded": sum(
                    1 for a in self.analysis_history if a.get("success")
                ),
                "failed": len(self.error_history),
                "findings": len(self.findings),
            },
            "findings": self.findings,
            "history": [
                {
                    "plugin": self._extract_plugin_name(a["command"]),
                    "success": a["success"],
                    "timestamp": a["timestamp"][:19],
                    "preview": (
                        a["output_preview"][:200].replace('\n', ' ').strip()
                    ),
                }
                for a in self.analysis_history[-15:]
            ],
            "errors": [
                {
                    "command": e["command"],
                    "summary": e["error"][:200],
                    "timestamp": e["timestamp"][:19],
                }
                for e in self.error_history[-5:]
            ],
        }
        return f"Analysis Context:\n\n{json.dumps(context, indent=2, default=str)}"

    async def _handle_save_report(
        self, content: Optional[str], filename: Optional[str]
    ) -> str:
        """Create a report file and write content in a single step."""
        if not content:
            return "No content provided — nothing written."
        try:
            if filename:
                safe_name = Path(filename).name  # strip any path components
            else:
                ts = self._now().strftime("%Y%m%d_%H%M%S")
                image_tag = (
                    Path(self.current_image).stem if self.current_image else "session"
                )
                safe_name = f"report_{image_tag}_{ts}.md"

            out_path = (self.reports_dir / safe_name).resolve()
            reports_resolved = self.reports_dir.resolve()

            # Security: ensure destination is strictly inside reports_dir
            if not str(out_path).startswith(str(reports_resolved) + os.sep):
                return "Access denied: target path must be inside the reports directory."

            out_path.write_text(content, encoding='utf-8')
            return f"Report saved: {out_path}\nSize: {len(content):,} characters"
        except Exception as e:
            return f"Failed to save report: {e}"

    # ── Entry point ────────────────────────────────────────────────────────────

    async def run(self):
        logger.info("Starting Volatility3 MCP Server…")
        logger.info(f"Volatility3 path: {self.volatility_path}")
        logger.info(f"Reports dir:      {self.reports_dir}")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream,
                self.server.create_initialization_options()
            )


if __name__ == "__main__":
    server = AdaptiveVolatilityMCPServer()
    asyncio.run(server.run())

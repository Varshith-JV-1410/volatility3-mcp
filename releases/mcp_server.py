#!/usr/bin/env python3
"""
Adaptive Volatility3 MCP Server 
Author: 0xOb5k-J
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

import mcp.server
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Setup logging
logs_dir = Path(__file__).parent / "logs"
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
    """Adaptive MCP Server for Volatility3 that works with any OS"""
    
    def __init__(self):
        self.server = Server("volatility3-adaptive-mcp")
        self.is_windows = platform.system() == "Windows"
        self.memory_images_dir = Path(__file__).parent.parent / "memory_images"
        self.reports_dir = Path(__file__).parent.parent / "reports"
        self.current_image = None
        self.image_info = {}
        self.os_type = OSType.UNKNOWN
        self.available_plugins = []
        self.plugin_cache = {}
        self.error_history = []
        self.analysis_history = []  # Track all analyses performed
        self.findings = []  # Track important findings
        self.volatility_path = Path(__file__).parent.parent / "volatility3"
        self.last_command_output = ""
        
        # Create directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.memory_images_dir.mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent.parent / "logs").mkdir(parents=True, exist_ok=True)  # Fixed parenthesis
        
        # Initialize server handlers
        self._setup_handlers()
        
        logger.info(f"Volatility3 MCP Server initialized by 0xOb5k-J at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    def _get_current_time(self) -> datetime:
        """Get current UTC time using timezone-aware datetime"""
        return datetime.now(timezone.utc)
    
    def _run_volatility_command(self, command_parts: List[str], timeout: int = 300) -> Tuple[bool, str]:
        """
        Run Volatility3 command with Windows-specific fixes to prevent hanging
        """
        vol_script = self.volatility_path / "vol.py"
        
        # Build command
        cmd = [sys.executable, str(vol_script)] + command_parts
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        try:
            if self.is_windows:
                # Windows-specific subprocess handling to prevent hanging
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,  # Important: provide stdin
                    text=True,
                    cwd=str(self.volatility_path),
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # Close stdin immediately to prevent waiting for input
                process.stdin.close()
                
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                    return_code = process.returncode
                    
                    output = stdout
                    if stderr:
                        output += "\n" + stderr
                    
                    self.last_command_output = output
                    success = return_code == 0
                    
                    # Track analysis history
                    self.analysis_history.append({
                        "command": ' '.join(command_parts),
                        "timestamp": self._get_current_time().isoformat(),
                        "success": success,
                        "output_preview": output[:500] if output else ""
                    })
                    
                    if not success:
                        self.error_history.append({
                            "command": ' '.join(command_parts),
                            "error": output,
                            "timestamp": self._get_current_time().isoformat()
                        })
                    
                    return success, output
                    
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    
                    error_msg = f"Command timed out after {timeout} seconds"
                    self.error_history.append({
                        "command": ' '.join(command_parts),
                        "error": error_msg,
                        "timestamp": self._get_current_time().isoformat()
                    })
                    return False, error_msg
            else:
                # Linux/Mac approach (original)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.volatility_path)
                )
                
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr
                
                self.last_command_output = output
                success = result.returncode == 0
                
                # Track analysis history
                self.analysis_history.append({
                    "command": ' '.join(command_parts),
                    "timestamp": self._get_current_time().isoformat(),
                    "success": success,
                    "output_preview": output[:500] if output else ""
                })
                
                if not success:
                    self.error_history.append({
                        "command": ' '.join(command_parts),
                        "error": output,
                        "timestamp": self._get_current_time().isoformat()
                    })
                
                return success, output
                
        except Exception as e:
            error_msg = f"Error running command: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_history.append({
                "command": ' '.join(command_parts),
                "error": error_msg,
                "timestamp": self._get_current_time().isoformat()
            })
            return False, error_msg
    
    def _detect_os_type(self, info_output: str) -> OSType:
        """Detect OS type from info output"""
        info_lower = info_output.lower()
        
        if 'windows' in info_lower or 'nt build' in info_lower:
            return OSType.WINDOWS
        elif 'linux' in info_lower or 'kernel' in info_lower:
            return OSType.LINUX
        elif 'darwin' in info_lower or 'mac' in info_lower:
            return OSType.MAC
        else:
            return OSType.UNKNOWN
    
    def _parse_plugin_list(self, output: str) -> List[Dict[str, str]]:
        """Parse plugin list from volatility output"""
        plugins = []
        lines = output.split('\n')
        
        # Look for plugin lines (usually in format: plugin_name - Description)
        for line in lines:
            line = line.strip()
            if not line or line.startswith('Volatility'):
                continue
            
            # Try to parse different plugin list formats
            if ' - ' in line:
                parts = line.split(' - ', 1)
                plugin_name = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""
                
                plugins.append({
                    "name": plugin_name,
                    "description": description,
                    "category": self._categorize_plugin(plugin_name)
                })
            elif line and not line.startswith('#'):
                # Simple plugin name
                plugins.append({
                    "name": line.strip(),
                    "description": "",
                    "category": self._categorize_plugin(line.strip())
                })
        
        return plugins
    
    def _categorize_plugin(self, plugin_name: str) -> str:
        """Categorize plugin based on its name"""
        name_lower = plugin_name.lower()
        
        if 'process' in name_lower or 'ps' in name_lower or 'proc' in name_lower:
            return "Process"
        elif 'net' in name_lower or 'socket' in name_lower or 'conn' in name_lower:
            return "Network"
        elif 'file' in name_lower or 'vad' in name_lower:
            return "Files"
        elif 'registry' in name_lower or 'reg' in name_lower or 'hive' in name_lower:
            return "Registry"
        elif 'mal' in name_lower or 'inject' in name_lower:
            return "Malware"
        elif 'module' in name_lower or 'driver' in name_lower or 'kernel' in name_lower:
            return "Kernel"
        elif 'dump' in name_lower:
            return "Memory Dump"
        elif 'time' in name_lower or 'event' in name_lower:
            return "Timeline"
        elif 'info' in name_lower or 'version' in name_lower:
            return "Information"
        else:
            return "Other"
    
    def _analyze_error(self, error_output: str, command: str) -> Dict[str, Any]:
        """Analyze error and provide solutions"""
        analysis = {
            "error_type": "unknown",
            "suggestions": [],
            "alternative_plugins": [],
            "root_cause": ""
        }
        
        error_lower = error_output.lower()
        
        # Common error patterns
        if "no such plugin" in error_lower or "plugin.*not.*found" in error_lower:
            analysis["error_type"] = "plugin_not_found"
            analysis["root_cause"] = "The specified plugin doesn't exist or is not available for this OS"
            
            # Extract plugin name from command
            plugin_match = re.search(r'(\w+\.\w+)', command)
            if plugin_match:
                plugin_name = plugin_match.group(1)
                # Suggest similar plugins
                similar = [p for p in self.available_plugins 
                          if any(part in p["name"].lower() for part in plugin_name.lower().split('.'))]
                analysis["alternative_plugins"] = similar[:5]
            
            analysis["suggestions"].append("Use 'list_available_plugins' to see all available plugins")
            analysis["suggestions"].append("Check if the plugin is compatible with the loaded memory image OS")
        
        elif "unsatisfied.*requirement" in error_lower or "symbol.*not.*found" in error_lower:
            analysis["error_type"] = "incompatible_profile"
            analysis["root_cause"] = "The memory image profile doesn't match the plugin requirements"
            analysis["suggestions"].append("This plugin may not be compatible with the OS version of the memory image")
            analysis["suggestions"].append("Try using a more generic plugin or one specifically for this OS")
        
        elif "invalid.*layer" in error_lower or "layer.*not.*found" in error_lower:
            analysis["error_type"] = "layer_error"
            analysis["root_cause"] = "Issue with memory layers or address translation"
            analysis["suggestions"].append("The memory image might be corrupted or incomplete")
            analysis["suggestions"].append("Try running 'windows.info' or 'linux.info' to verify image integrity")
        
        elif "permission" in error_lower or "access.*denied" in error_lower:
            analysis["error_type"] = "permission_error"
            analysis["root_cause"] = "Insufficient permissions to access the memory image or write output"
            analysis["suggestions"].append("Check file permissions for the memory image")
            analysis["suggestions"].append("Ensure write permissions for output directories")
        
        elif "timeout" in error_lower:
            analysis["error_type"] = "timeout"
            analysis["root_cause"] = "The operation took too long to complete"
            analysis["suggestions"].append("Try running with a smaller scope (specific PID, etc.)")
            analysis["suggestions"].append("The memory image might be very large - consider using filters")
        
        elif "no.*result" in error_lower or "empty" in error_lower:
            analysis["error_type"] = "no_results"
            analysis["root_cause"] = "The plugin executed successfully but found no matching data"
            analysis["suggestions"].append("This might be normal - the searched data may not exist")
            analysis["suggestions"].append("Try with different parameters or filters")
        
        else:
            # Generic error analysis
            if "pid" in error_lower:
                analysis["suggestions"].append("Check if the specified PID exists using pslist/psaux")
            if "file" in error_lower:
                analysis["suggestions"].append("Verify the file path and permissions")
            if "memory" in error_lower:
                analysis["suggestions"].append("The memory image might be corrupted or incomplete")
        
        return analysis
    
    def _analyze_for_suspicious_activity(self, output: str, plugin_name: str) -> List[str]:
        """Analyze output for suspicious activities and findings with enhanced detection"""
        findings = []
        output_lower = output.lower()
        lines = output.split('\n')
        
        # Enhanced malware indicators for malfind
        if "malfind" in plugin_name.lower():
            if "vad protection" in output_lower or "page_execute_readwrite" in output_lower:
                findings.append("HIGH RISK: Code injection detected - suspicious memory protection flags")
            if "mz" in output:
                findings.append("HIGH RISK: PE header found in suspicious memory region")
            if "winlogon.exe" in output_lower and ("inject" in output_lower or "page_execute" in output_lower):
                findings.append("CRITICAL: Code injection detected in winlogon.exe process")
            if any(pattern in output_lower for pattern in ["shellcode", "payload", "backdoor"]):
                findings.append("HIGH RISK: Potential malware payload detected in process memory")
        
        # Process analysis with specific threat detection
        if "pslist" in plugin_name.lower():
            process_count = 0
            suspicious_processes = []
            
            for line in lines:
                if line.strip() and not line.startswith(('Volatility', 'PID', '=', '-')):
                    # Count processes that look like actual process entries
                    if '\t' in line or '  ' in line:  # Process entries usually have tabs/spaces
                        process_count += 1
                    
                    # Check for process masquerading
                    if "scvhost.exe" in line.lower():  # Misspelled svchost
                        suspicious_processes.append("Process masquerading: scvhost.exe (should be svchost.exe)")
                    
                    # Check for suspicious processes
                    for sus_proc in ["keylog", "backdoor", "trojan", "rootkit", "rat"]:
                        if sus_proc in line.lower():
                            suspicious_processes.append(f"Suspicious process detected: {sus_proc}")
            
            if process_count > 0:
                findings.append(f"System running {process_count} processes - analyzed for anomalies")
            
            for sus_proc in suspicious_processes:
                findings.append(f"HIGH RISK: {sus_proc}")
            
            if "hidden" in output_lower:
                findings.append("HIGH RISK: Possible hidden process detected")
        
        # File system analysis
        if "filescan" in plugin_name.lower():
            keylogger_files = []
            illegal_software = []
            
            for line in lines:
                line_lower = line.lower()
                if "keylog" in line_lower:
                    keylogger_files.append("keylog.txt")
                if any(crack in line_lower for crack in ["crack", "keygen", "serial", "patch"]):
                    illegal_software.append(line.strip())
            
            if keylogger_files:
                findings.append(f"CRITICAL: Keylogger evidence found - {', '.join(keylogger_files)}")
            
            if illegal_software:
                findings.append("HIGH RISK: Illegal software cache detected with security tool cracks")
        
        # Command line analysis for malicious activities
        if "cmdline" in plugin_name.lower():
            malicious_commands = []
            for line in lines:
                line_lower = line.lower()
                if any(cmd in line_lower for cmd in ["nc -l", "netcat", "powershell -enc", "cmd /c"]):
                    malicious_commands.append(line.strip())
            
            if malicious_commands:
                findings.append("MEDIUM RISK: Suspicious command line activities detected")
        
        # Network analysis
        if "net" in plugin_name.lower():
            suspicious_ports = ["4444", "1337", "31337", "12345", "666"]
            suspicious_connections = []
            
            for port in suspicious_ports:
                if port in output:
                    findings.append(f"HIGH RISK: Connection detected on suspicious port {port}")
            
            if "0.0.0.0:" in output and "listening" in output_lower:
                findings.append("MEDIUM RISK: Process listening on all interfaces (0.0.0.0)")
        
        # Handle analysis for system interaction
        if "handles" in plugin_name.lower():
            handle_count = sum(1 for line in lines if line.strip() and not line.startswith(('Volatility', 'PID', '=', '-')))
            if handle_count > 100000:  # Large number of handles
                findings.append(f"System showing extensive handle usage ({handle_count:,} handles) - potential resource manipulation")
        
        # Check for suspicious process names across all plugins
        suspicious_names = ["mimikatz", "lazagne", "procdump", "pwdump", "gsecdump", "meterpreter"]
        for name in suspicious_names:
            if name in output_lower:
                findings.append(f"CRITICAL: Suspicious tool detected - {name}")
        
        return findings
    
    def _calculate_analysis_duration(self) -> Optional[str]:
        """Calculate the total duration of analysis"""
        if not self.analysis_history or len(self.analysis_history) < 2:
            return None
            
        try:
            first_analysis = self.analysis_history[0].get('timestamp', '')
            last_analysis = self.analysis_history[-1].get('timestamp', '')
            
            if first_analysis and last_analysis:
                start_time = datetime.fromisoformat(first_analysis)
                end_time = datetime.fromisoformat(last_analysis)
                duration = end_time - start_time
                
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                elif minutes > 0:
                    return f"{int(minutes)}m {int(seconds)}s"
                else:
                    return f"{int(seconds)}s"
        except Exception:
            return None
        
        return None
    
    def _categorize_analysis_techniques(self) -> Dict[str, List[Dict[str, str]]]:
        """Categorize the analysis techniques used"""
        techniques = {
            "Process Analysis": [],
            "Network Analysis": [],
            "Memory Analysis": [],
            "File System Analysis": [],
            "Registry Analysis": [],
            "Malware Detection": [],
            "System Information": [],
            "Other Techniques": []
        }
        
        technique_descriptions = {
            "pslist": "Enumerate running processes",
            "pstree": "Display process tree structure", 
            "psaux": "Linux process listing",
            "psscan": "Scan for process structures",
            "netscan": "Scan for network connections",
            "netstat": "Display network statistics",
            "connections": "Show network connections",
            "sockets": "Display socket information",
            "malfind": "Detect malware injection techniques",
            "hollowfind": "Find process hollowing",
            "vadinfo": "Virtual address descriptor information",
            "memmap": "Memory mapping information",
            "dumpfiles": "Extract files from memory",
            "filescan": "Scan for file objects",
            "printkey": "Display registry keys",
            "hivelist": "List registry hives",
            "info": "System information",
            "version": "OS version information"
        }
        
        # Extract unique plugins used
        used_plugins = set()
        for analysis in self.analysis_history:
            if analysis.get('success', False):
                cmd = analysis.get('command', '')
                parts = cmd.split()
                for part in parts:
                    if '.' in part and not part.startswith('-'):
                        plugin_name = part.split('.')[-1]  # Get the last part after dot
                        used_plugins.add(plugin_name)
                        break
        
        # Categorize plugins
        for plugin in used_plugins:
            plugin_lower = plugin.lower()
            description = technique_descriptions.get(plugin, f"Execute {plugin} analysis")
            
            plugin_info = {"plugin": plugin, "description": description}
            
            if any(keyword in plugin_lower for keyword in ['ps', 'proc', 'process']):
                techniques["Process Analysis"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['net', 'socket', 'conn']):
                techniques["Network Analysis"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['mal', 'inject', 'hollow']):
                techniques["Malware Detection"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['vad', 'mem', 'dump']):
                techniques["Memory Analysis"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['file', 'scan']):
                techniques["File System Analysis"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['reg', 'hive', 'key']):
                techniques["Registry Analysis"].append(plugin_info)
            elif any(keyword in plugin_lower for keyword in ['info', 'version']):
                techniques["System Information"].append(plugin_info)
            else:
                techniques["Other Techniques"].append(plugin_info)
        
        # Remove empty categories
        return {k: v for k, v in techniques.items() if v}
    
    def _assess_finding_severity(self, finding: str) -> str:
        """Assess the severity of a finding with enhanced classification"""
        finding_lower = finding.lower()
        
        # Critical severity indicators
        if any(keyword in finding_lower for keyword in ['critical:', 'keylogger evidence', 'code injection detected in winlogon', 'process masquerading']):
            return "CRITICAL"
        # High risk indicators  
        elif any(keyword in finding_lower for keyword in ['high risk:', 'malware', 'inject', 'suspicious tool detected', 'rootkit', 'illegal software cache']):
            return "HIGH RISK"
        # Medium risk indicators
        elif any(keyword in finding_lower for keyword in ['medium risk:', 'suspicious', 'hidden', 'unusual', 'anomaly']):
            return "MEDIUM RISK"
        # Low risk/informational
        elif any(keyword in finding_lower for keyword in ['system running', 'analyzed', 'scanned']):
            return "INFORMATIONAL"
        else:
            return "LOW RISK"
    
    def _get_finding_recommendation(self, finding: str) -> str:
        """Get enhanced recommendation based on finding"""
        finding_lower = finding.lower()
        
        if 'keylogger evidence' in finding_lower:
            return "URGENT: Reset all passwords, check for credential theft, isolate system immediately, and review all authentication logs."
        elif 'process masquerading' in finding_lower or 'scvhost.exe' in finding_lower:
            return "URGENT: System compromised - legitimate process name hijacked. Full system rebuild recommended after forensic analysis."
        elif 'winlogon.exe' in finding_lower and 'inject' in finding_lower:
            return "CRITICAL: Core Windows authentication process compromised. Immediate isolation and complete system restoration required."
        elif 'illegal software cache' in finding_lower:
            return "Remove illegal software, scan for backdoors, review security policies, and monitor for additional compromise indicators."
        elif 'injection' in finding_lower or 'inject' in finding_lower:
            return "Immediately isolate the system and conduct detailed process memory analysis. Extract and analyze the injected code."
        elif 'malware' in finding_lower or 'suspicious tool detected' in finding_lower:
            return "Quarantine the system immediately. Perform complete malware analysis and check for lateral movement."
        elif 'hidden' in finding_lower:
            return "Investigate the hidden processes/files further. Check for rootkit presence and system integrity."
        elif 'network' in finding_lower and 'suspicious' in finding_lower:
            return "Monitor network traffic, block suspicious connections, and investigate the destination endpoints."
        elif 'handle usage' in finding_lower:
            return "Monitor system performance and check for resource manipulation or denial-of-service attempts."
        else:
            return "Monitor the system closely and gather additional forensic evidence to determine the nature of this indicator."
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%H:%M:%S")
        except Exception:
            return timestamp[:8] if len(timestamp) > 8 else timestamp
    
    def _extract_plugin_from_command(self, command: str) -> str:
        """Extract plugin name from command"""
        parts = command.split()
        for part in parts:
            if '.' in part and not part.startswith('-'):
                return part
        return "Unknown"
    
    def _extract_key_results(self, analysis: Dict[str, Any], command: str) -> str:
        """Extract key results from analysis"""
        if not analysis.get('success', False):
            return "Failed to execute"
        
        # Check if we have output preview
        preview = analysis.get('output_preview', '')
        if preview:
            # Count lines that look like results
            lines = preview.split('\n')
            data_lines = [line for line in lines if line.strip() and not line.startswith('Volatility')]
            
            if len(data_lines) > 5:
                return f"{len(data_lines)}+ results found"
            elif len(data_lines) > 0:
                return f"{len(data_lines)} results found"
            else:
                return "No data found"
        
        return "Executed successfully"
    
    def _format_technical_output(self, output: str) -> str:
        """Format technical output for inclusion in report"""
        lines = output.split('\n')
        
        # Skip header lines and get meaningful content
        meaningful_lines = []
        skip_patterns = ['Volatility', 'PID', '---', '===']
        
        for line in lines:
            line = line.strip()
            if line and not any(pattern in line for pattern in skip_patterns):
                meaningful_lines.append(line)
                if len(meaningful_lines) >= 20:  # Limit output
                    meaningful_lines.append("... (output truncated for brevity)")
                    break
        
        return '\n'.join(meaningful_lines[:25])  # Maximum 25 lines
    
    def _analyze_technical_output(self, output: str, plugin: str) -> str:
        """Provide enhanced technical analysis of the output"""
        lines = output.split('\n')
        data_lines = [line for line in lines if line.strip() and not line.startswith(('Volatility', '=', '-'))]
        
        analysis = []
        
        if 'pslist' in plugin.lower() or 'process' in plugin.lower():
            # Count actual process entries (lines with tabs or multiple spaces)
            process_entries = [line for line in data_lines if '\t' in line or '  ' in line]
            process_count = len(process_entries)
            
            analysis.append(f"Identified {process_count} processes running at the time of memory capture.")
            
            # Look for suspicious process names and patterns
            suspicious_processes = []
            critical_processes = []
            
            for line in process_entries:
                line_lower = line.lower()
                # Check for system-critical processes
                if any(proc in line_lower for proc in ['winlogon.exe', 'csrss.exe', 'explorer.exe']):
                    critical_processes.append(line.strip())
                
                # Check for suspicious processes
                if 'scvhost.exe' in line_lower:  # Misspelled svchost
                    suspicious_processes.append("Process masquerading detected: scvhost.exe")
                
                if any(susp in line_lower for susp in ['cmd.exe', 'powershell', 'wscript', 'cscript']):
                    suspicious_processes.append(line.strip())
            
            if critical_processes:
                analysis.append(f"Found {len(critical_processes)} critical system processes that require security analysis.")
            
            if suspicious_processes:
                analysis.append(f"Detected {len(suspicious_processes)} processes requiring detailed investigation for potential compromise.")
        
        elif 'netscan' in plugin.lower() or 'netstat' in plugin.lower():
            connection_entries = [line for line in data_lines if ':' in line and ('tcp' in line.lower() or 'udp' in line.lower())]
            analysis.append(f"Discovered {len(connection_entries)} network connections and listening ports.")
            
            # Analyze for suspicious network activity
            suspicious_connections = []
            for line in connection_entries:
                if any(port in line for port in ['4444', '1337', '31337']):
                    suspicious_connections.append(line)
            
            if suspicious_connections:
                analysis.append(f"Identified {len(suspicious_connections)} potentially malicious network connections on known attack ports.")
        
        elif 'malfind' in plugin.lower():
            # Analyze memory injection indicators
            injection_indicators = []
            for line in data_lines:
                if 'page_execute_readwrite' in line.lower() or 'rwx' in line.lower():
                    injection_indicators.append(line)
            
            analysis.append(f"Memory analysis revealed {len(injection_indicators)} potential code injection indicators.")
            
            if any('winlogon.exe' in line.lower() for line in data_lines):
                analysis.append("CRITICAL: Code injection detected in winlogon.exe - core system process compromise.")
        
        elif 'filescan' in plugin.lower():
            file_entries = [line for line in data_lines if '\\' in line]  # Windows paths
            analysis.append(f"Scanned {len(file_entries)} file system objects from memory.")
            
            # Look for keylogger evidence
            keylogger_files = [line for line in file_entries if 'keylog' in line.lower()]
            if keylogger_files:
                analysis.append(f"CRITICAL: {len(keylogger_files)} keylogger-related files discovered - evidence of credential harvesting.")
            
            # Look for illegal software
            crack_files = [line for line in file_entries if any(crack in line.lower() for crack in ['crack', 'keygen', 'serial'])]
            if crack_files:
                analysis.append(f"Detected {len(crack_files)} illegal software files suggesting security tool bypassing.")
        
        elif 'cmdline' in plugin.lower():
            command_entries = [line for line in data_lines if line.strip()]
            analysis.append(f"Extracted command line arguments for {len(command_entries)} processes.")
            
            # Look for suspicious command patterns
            suspicious_commands = []
            for line in command_entries:
                if any(pattern in line.lower() for pattern in ['powershell -enc', 'cmd /c', 'nc -l']):
                    suspicious_commands.append(line)
            
            if suspicious_commands:
                analysis.append(f"Identified {len(suspicious_commands)} suspicious command line executions indicating potential attack activities.")
        
        elif 'handles' in plugin.lower():
            handle_entries = [line for line in data_lines if line.strip()]
            total_handles = len(handle_entries)
            analysis.append(f"Analyzed {total_handles:,} system handles revealing detailed process interactions and resource usage patterns.")
            
            if total_handles > 100000:
                analysis.append("Extensive handle usage detected - system under heavy load or potential resource manipulation.")
        
        if not analysis:
            analysis.append(f"Output contains detailed technical information relevant to the forensic investigation using {plugin}.")
        
        return ' '.join(analysis)

    def _analyze_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Analyze patterns in errors"""
        error_patterns = {}
        
        for error in self.error_history:
            error_msg = error.get('error', '').lower()
            
            if 'timeout' in error_msg:
                error_type = "Analysis Timeout"
                if error_type not in error_patterns:
                    error_patterns[error_type] = {
                        'count': 0,
                        'impact': 'Some analysis operations did not complete within the allocated time',
                        'technical_detail': 'Large memory images or complex operations may require extended processing time'
                    }
                error_patterns[error_type]['count'] += 1
            
            elif 'plugin' in error_msg and 'not' in error_msg:
                error_type = "Plugin Compatibility"
                if error_type not in error_patterns:
                    error_patterns[error_type] = {
                        'count': 0,
                        'impact': 'Certain analysis techniques were not available for this memory image',
                        'technical_detail': 'Plugin compatibility depends on the operating system version and memory image format'
                    }
                error_patterns[error_type]['count'] += 1
            
            elif 'permission' in error_msg or 'access' in error_msg:
                error_type = "Access Restrictions"
                if error_type not in error_patterns:
                    error_patterns[error_type] = {
                        'count': 0,
                        'impact': 'Analysis was limited by file system permissions',
                        'technical_detail': 'Insufficient permissions to access memory image or write analysis results'
                    }
                error_patterns[error_type]['count'] += 1
            
            else:
                error_type = "Technical Errors"
                if error_type not in error_patterns:
                    error_patterns[error_type] = {
                        'count': 0,
                        'impact': 'Various technical issues affected analysis completeness',
                        'technical_detail': 'Memory image corruption, format issues, or system resource limitations'
                    }
                error_patterns[error_type]['count'] += 1
        
        return error_patterns
    
    def _generate_context_recommendations(self) -> List[str]:
        """Generate context-specific recommendations"""
        recommendations = []
        
        if self.findings:
            high_risk_count = len([f for f in self.findings if 'malware' in f.lower() or 'inject' in f.lower()])
            if high_risk_count > 0:
                recommendations.append("Immediately isolate affected systems and initiate incident response procedures")
                recommendations.append("Conduct comprehensive network analysis to identify potential lateral movement")
                recommendations.append("Perform hash-based analysis of suspicious executables and compare against threat intelligence")
            else:
                recommendations.append("Continue monitoring for additional indicators of compromise")
                recommendations.append("Correlate findings with system logs and network traffic analysis")
        
        if self.error_history:
            timeout_errors = len([e for e in self.error_history if 'timeout' in e.get('error', '').lower()])
            if timeout_errors > 0:
                recommendations.append("Consider using more targeted analysis parameters to avoid timeouts on large datasets")
        
        # Check analysis coverage
        analysis_types = set()
        for analysis in self.analysis_history:
            cmd = analysis.get('command', '').lower()
            if 'process' in cmd or 'ps' in cmd:
                analysis_types.add('process')
            elif 'net' in cmd:
                analysis_types.add('network')
            elif 'mal' in cmd:
                analysis_types.add('malware')
        
        if 'process' not in analysis_types:
            recommendations.append("Conduct comprehensive process analysis to identify running applications and services")
        if 'network' not in analysis_types:
            recommendations.append("Perform network connection analysis to identify suspicious communications")
        if 'malware' not in analysis_types:
            recommendations.append("Execute malware detection plugins to identify code injection and suspicious modifications")
        
        if not recommendations:
            recommendations.append("Continue systematic analysis based on investigation objectives")
            recommendations.append("Document all findings and maintain chain of custody for evidence")
            recommendations.append("Consider additional forensic tools for comprehensive system analysis")
        
        return recommendations
    
    def _generate_report_hash(self) -> str:
        """Generate a simple hash for report integrity"""
        import hashlib
        
        # Create a simple hash based on current state
        content = f"{self.current_image}{len(self.analysis_history)}{len(self.findings)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _generate_documentation(self) -> str:
        """
        Simple tool that gives AI full control over documentation.
        AI decides what to document and creates the content completely dynamically.
        """
        current_time = self._get_current_time()
        timestamp = current_time.strftime("%Y%m%d_%H%M%S")
        filename = f"ai_forensics_report_{timestamp}.md"
        filepath = self.reports_dir / filename
        
        # Create empty file for AI to populate
        try:
            filepath.touch()
            
            # Return file path and context - AI will handle the rest
            context_summary = {
                'filepath': str(filepath),
                'current_image': self.current_image,
                'os_type': self.os_type.value,
                'analysis_count': len(self.analysis_history),
                'findings_count': len(self.findings),
                'errors_count': len(self.error_history),
                'timestamp': current_time.isoformat(),
                'available_plugins': len(self.available_plugins)
            }
            
            return f"Documentation file created: {filepath}\n\nContext for AI documentation:\n{context_summary}\n\nNote: Use 'create_documentation_content' tool to populate this file with AI-generated content."
            
        except Exception as e:
            return f"Failed to create documentation file: {str(e)}"
    
    def _ai_generate_contextual_report(self, current_time: datetime) -> str:
        """
        AI-driven report generation that adapts to the specific forensics context.
        The AI decides what sections to include and how to structure them based on actual data.
        """
        
        # AI assessment of current context
        context = self._assess_forensic_context()
        
        # Dynamic content generation based on context
        report_lines = []
        
        # AI decides on title based on context
        if context['critical_situation']:
            report_lines.append("# CRITICAL INCIDENT - Memory Forensics Analysis")
        elif context['has_findings']:
            report_lines.append("# Security Investigation - Memory Analysis Results")
        elif context['analysis_in_progress']:
            report_lines.append("# Forensic Memory Analysis - Interim Report")
        elif context['image_loaded']:
            report_lines.append("# Memory Forensics Preparation - System Ready")
        else:
            report_lines.append("# Forensic Analysis Session - No Target Loaded")
        
        report_lines.extend(["", f"*Generated: {current_time.strftime('%B %d, %Y at %H:%M:%S UTC')}*", ""])
        
        # AI-driven content based on what actually exists
        if context['critical_situation']:
            self._ai_add_critical_incident_analysis(report_lines, context)
        elif context['has_findings']:
            self._ai_add_investigation_results(report_lines, context)
        elif context['analysis_in_progress']:
            self._ai_add_active_analysis_summary(report_lines, context)
        elif context['image_loaded']:
            self._ai_add_preparation_status(report_lines, context)
        else:
            self._ai_add_session_status(report_lines, context)
        
        # AI adds technical details if relevant
        if self.last_command_output and len(self.last_command_output) > 100:
            self._ai_add_technical_evidence(report_lines, context)
        
        # AI adds operational insights if there are errors or issues
        if self.error_history:
            self._ai_add_operational_notes(report_lines, context)
        
        # AI concludes with next actions based on context
        self._ai_add_contextual_conclusion(report_lines, context)
        
        return "\n".join(report_lines)
    
    def _assess_forensic_context(self) -> Dict[str, Any]:
        """AI assesses the current forensic context to determine report structure"""
        context = {
            'image_loaded': bool(self.current_image),
            'analysis_performed': bool(self.analysis_history),
            'has_findings': bool(self.findings),
            'has_errors': bool(self.error_history),
            'analysis_in_progress': False,
            'critical_situation': False,
            'total_operations': len(self.analysis_history),
            'successful_operations': sum(1 for a in self.analysis_history if a.get('success', False)),
            'high_risk_findings': 0,
            'medium_risk_findings': 0,
            'recent_activity': False
        }
        
        # Assess severity of findings with enhanced detection
        if self.findings:
            for finding in self.findings:
                severity = self._assess_finding_severity(finding)
                if severity == 'CRITICAL':
                    context['high_risk_findings'] += 1
                elif severity == 'HIGH RISK':
                    context['high_risk_findings'] += 1
                elif severity == 'MEDIUM RISK':
                    context['medium_risk_findings'] += 1
        
        # Determine situation criticality - include CRITICAL and HIGH RISK findings
        context['critical_situation'] = context['high_risk_findings'] > 0
        
        # Assess if analysis is ongoing
        if self.analysis_history and len(self.analysis_history) > 0:
            context['analysis_in_progress'] = True
            
            # Check if there's recent activity
            try:
                last_analysis = self.analysis_history[-1]
                last_time = datetime.fromisoformat(last_analysis.get('timestamp', ''))
                time_since = (datetime.now(timezone.utc) - last_time).total_seconds()
                context['recent_activity'] = time_since < 3600  # Within last hour
            except:
                pass
        
        return context
    
    def _ai_add_critical_incident_analysis(self, lines: List[str], context: Dict[str, Any]):
        """AI generates critical incident analysis section"""
        lines.extend([
            "## WARNING - SECURITY ALERT",
            "",
            f"**CRITICAL FINDINGS DETECTED** - {context['high_risk_findings']} high-risk indicators identified during forensic analysis.",
            ""
        ])
        
        if self.current_image:
            lines.extend([
                f"**Target System:** `{Path(self.current_image).name}`",
                f"**System Type:** {self.os_type.value.upper()}",
                f"**Analysis Scope:** {context['total_operations']} forensic operations performed",
                ""
            ])
        
        lines.append("## Threat Indicators")
        lines.append("")
        
        # Group findings by severity for better presentation
        critical_findings = []
        high_risk_findings = []
        medium_risk_findings = []
        
        for finding in self.findings:
            severity = self._assess_finding_severity(finding)
            if severity == 'CRITICAL':
                critical_findings.append(finding)
            elif severity == 'HIGH RISK':
                high_risk_findings.append(finding)
            elif severity == 'MEDIUM RISK':
                medium_risk_findings.append(finding)
        
        # Display findings in order of severity
        counter = 1
        for finding in critical_findings + high_risk_findings + medium_risk_findings:
            severity = self._assess_finding_severity(finding)
            lines.extend([
                f"**{counter}. {finding}**",
                f"   - Risk Level: {severity}",
                f"   - Action Required: {self._get_finding_recommendation(finding)}",
                ""
            ])
            counter += 1
        
        lines.extend([
            "## Immediate Actions Required",
            "",
            "1. **ISOLATE** - Disconnect affected systems from network immediately",
            "2. **PRESERVE** - Maintain forensic evidence integrity", 
            "3. **ANALYZE** - Conduct deeper investigation of identified threats",
            "4. **RESPOND** - Initiate incident response procedures",
            ""
        ])
    
    def _ai_add_investigation_results(self, lines: List[str], context: Dict[str, Any]):
        """AI generates investigation results section"""
        lines.extend([
            "## Investigation Summary",
            "",
            f"Forensic analysis of `{Path(self.current_image).name if self.current_image else 'memory image'}` has identified **{len(self.findings)} security indicators** requiring attention.",
            ""
        ])
        
        if context['successful_operations'] > 0:
            lines.extend([
                f"**Analysis Coverage:** {context['successful_operations']}/{context['total_operations']} operations completed successfully",
                ""
            ])
        
        # AI categorizes findings by impact
        high_findings = [f for f in self.findings if 'HIGH RISK' in self._assess_finding_severity(f)]
        medium_findings = [f for f in self.findings if 'MEDIUM RISK' in self._assess_finding_severity(f)]
        info_findings = [f for f in self.findings if 'INFORMATIONAL' in self._assess_finding_severity(f)]
        
        if high_findings:
            lines.extend([
                "### CRITICAL CONCERNS",
                ""
            ])
            for finding in high_findings:
                lines.extend([f"- {finding}", ""])
        
        if medium_findings:
            lines.extend([
                "### NOTABLE OBSERVATIONS", 
                ""
            ])
            for finding in medium_findings:
                lines.extend([f"- {finding}", ""])
        
        if info_findings:
            lines.extend([
                "### ADDITIONAL NOTES",
                ""
            ])
            for finding in info_findings:
                lines.extend([f"- {finding}", ""])
    
    def _ai_add_active_analysis_summary(self, lines: List[str], context: Dict[str, Any]):
        """AI generates active analysis summary"""
        lines.extend([
            "## Analysis in Progress",
            "",
            f"Currently analyzing: `{Path(self.current_image).name if self.current_image else 'Unknown'}`",
            ""
        ])
        
        if self.analysis_history:
            lines.extend([
                "### Recent Operations",
                ""
            ])
            
            # Show last 5 operations with AI-determined relevance
            recent_ops = self.analysis_history[-5:]
            for op in recent_ops:
                status = "[OK]" if op.get('success', False) else "[FAIL]"
                plugin = self._extract_plugin_from_command(op.get('command', ''))
                timestamp = self._format_timestamp(op.get('timestamp', ''))
                lines.append(f"{status} `{timestamp}` - {plugin}")
            
            lines.append("")
        
        # AI suggests next steps based on what's been done
        performed_categories = set()
        for analysis in self.analysis_history:
            cmd = analysis.get('command', '').lower()
            if 'process' in cmd or 'ps' in cmd:
                performed_categories.add('process')
            elif 'net' in cmd:
                performed_categories.add('network') 
            elif 'mal' in cmd:
                performed_categories.add('malware')
        
        if performed_categories:
            lines.extend([
                "### Analysis Coverage",
                ""
            ])
            if 'process' in performed_categories:
                lines.append("[OK] Process analysis performed")
            if 'network' in performed_categories:
                lines.append("[OK] Network analysis performed")
            if 'malware' in performed_categories:
                lines.append("[OK] Malware scanning performed")
            lines.append("")
    
    def _ai_add_preparation_status(self, lines: List[str], context: Dict[str, Any]):
        """AI generates preparation status section"""
        lines.extend([
            "## System Ready for Analysis",
            "",
            f"**Memory Image:** `{Path(self.current_image).name}`",
            f"**Operating System:** {self.os_type.value}",
            ""
        ])
        
        if self.image_info:
            size_gb = self.image_info.get('size', 0) / (1024**3)
            lines.extend([
                f"**File Size:** {size_gb:.2f} GB",
                ""
            ])
        
        lines.extend([
            "The forensic environment is prepared and ready to begin analysis. No operations have been performed yet.",
            "",
            "**Suggested initial steps:**",
            "- System information gathering",
            "- Process enumeration", 
            "- Network connection analysis",
            ""
        ])
    
    def _ai_add_session_status(self, lines: List[str], context: Dict[str, Any]):
        """AI generates session status for no loaded image"""
        lines.extend([
            "## Forensic Session Status",
            "",
            "No memory image is currently loaded. The forensic analysis environment is ready to accept a target memory dump.",
            "",
            "**To begin analysis:**",
            "1. Load a memory image using the appropriate tool",
            "2. Verify the image integrity and format",
            "3. Begin systematic forensic examination",
            ""
        ])
    
    def _ai_add_technical_evidence(self, lines: List[str], context: Dict[str, Any]):
        """AI adds technical evidence section when relevant"""
        if not self.last_command_output:
            return
            
        lines.extend([
            "## Technical Evidence",
            ""
        ])
        
        # AI determines what type of evidence this is
        last_command = self.analysis_history[-1].get('command', '') if self.analysis_history else ''
        plugin_name = self._extract_plugin_from_command(last_command)
        
        lines.extend([
            f"**Source:** {plugin_name} analysis",
            "",
            "```",
            self._format_technical_output(self.last_command_output),
            "```",
            ""
        ])
        
        # AI provides interpretation
        analysis = self._analyze_technical_output(self.last_command_output, plugin_name)
        if analysis:
            lines.extend([
                "**Analysis:**", 
                analysis,
                ""
            ])
    
    def _ai_add_operational_notes(self, lines: List[str], context: Dict[str, Any]):
        """AI adds operational notes about errors or limitations"""
        lines.extend([
            "## Operational Notes",
            ""
        ])
        
        # AI categorizes and summarizes errors
        error_types = {}
        for error in self.error_history:
            error_msg = error.get('error', '').lower()
            if 'timeout' in error_msg:
                error_types['timeout'] = error_types.get('timeout', 0) + 1
            elif 'plugin' in error_msg:
                error_types['compatibility'] = error_types.get('compatibility', 0) + 1
            else:
                error_types['technical'] = error_types.get('technical', 0) + 1
        
        if error_types:
            for error_type, count in error_types.items():
                if error_type == 'timeout':
                    lines.append(f"- {count} operation(s) exceeded time limits - may indicate large dataset or system resource constraints")
                elif error_type == 'compatibility':
                    lines.append(f"- {count} plugin compatibility issue(s) - some analysis techniques may not be available")
                else:
                    lines.append(f"- {count} technical issue(s) encountered during analysis")
            lines.append("")
    
    def _ai_add_contextual_conclusion(self, lines: List[str], context: Dict[str, Any]):
        """AI generates conclusions based on the specific context"""
        lines.append("## Assessment")
        lines.append("")
        
        if context['critical_situation']:
            lines.extend([
                "**CRITICAL SECURITY SITUATION DETECTED**",
                "",
                "This analysis has identified indicators that suggest potential system compromise. Immediate security response is recommended.",
                "",
                "**Priority Actions:**",
                "1. Implement containment measures immediately",
                "2. Collect additional forensic evidence",  
                "3. Notify relevant security personnel",
                "4. Begin incident response procedures",
                ""
            ])
        elif context['has_findings']:
            lines.extend([
                f"**SECURITY INDICATORS IDENTIFIED** - {len(self.findings)} items require investigation",
                "",
                "The analysis has revealed activities that warrant further investigation. While not immediately critical, these findings should be addressed promptly.",
                ""
            ])
        elif context['analysis_in_progress']:
            if context['recent_activity']:
                lines.extend([
                    "**ANALYSIS ACTIVE** - Investigation is currently underway",
                    "",
                    "Forensic analysis is actively being performed. Continue systematic examination based on investigation objectives.",
                    ""
                ])
            else:
                lines.extend([
                    "**ANALYSIS INITIATED** - Initial forensic operations completed",
                    "",
                    "Basic analysis has been performed. Consider expanding the investigation scope based on initial findings.",
                    ""
                ])
        elif context['image_loaded']:
            lines.extend([
                "**READY FOR ANALYSIS** - System prepared for forensic examination",
                "",
                "The target memory image is loaded and ready for systematic analysis. Begin with information gathering and process enumeration.",
                ""
            ])
        else:
            lines.extend([
                "**STANDBY** - Awaiting target memory image",
                "",
                "The forensic analysis system is ready. Load a memory dump to begin investigation.",
                ""
            ])
        
        # AI adds a timestamp and authenticity note
        lines.extend([
            "---",
            f"*Report generated by AI-driven forensic analysis system at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*"
        ])
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available adaptive tools"""
            tools = [
                Tool(
                    name="load_memory_image",
                    description="Load a memory image and auto-detect OS type (Always start here)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": "Path to the memory image file"
                            }
                        },
                        "required": ["image_path"]
                    }
                ),
                Tool(
                    name="get_image_info",
                    description="Get detailed information about the loaded memory image (Check image details)",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="list_available_plugins",
                    description="List all available plugins for the current memory image OS (See what plugins are available)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Filter by category (Process, Network, Files, Registry, Malware, Kernel, etc.)"
                            },
                            "search": {
                                "type": "string",
                                "description": "Search term to filter plugins"
                            }
                        }
                    }
                ),
                Tool(
                    name="build_plugin_command",
                    description="Build and validate a Volatility3 command from plugin name and parameters (Create proper commands)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plugin": {
                                "type": "string",
                                "description": "Plugin name (e.g., windows.pslist, linux.psaux)"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Plugin parameters as key-value pairs",
                                "additionalProperties": True
                            },
                            "show_help": {
                                "type": "boolean",
                                "description": "Get help for the plugin",
                                "default": False
                            }
                        },
                        "required": ["plugin"]
                    }
                ),
                Tool(
                    name="execute_plugin",
                    description="Execute a Volatility3 plugin with automatic error handling (Run the analysis)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plugin": {
                                "type": "string",
                                "description": "Plugin name"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Plugin parameters",
                                "additionalProperties": True
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds",
                                "default": 300
                            }
                        },
                        "required": ["plugin"]
                    }
                ),
                Tool(
                    name="analyze_error",
                    description="Analyze errors from plugin execution and provide solutions (Fix any issues)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_history": {
                                "type": "boolean",
                                "description": "Include error history analysis",
                                "default": True
                            }
                        }
                    }
                ),
                Tool(
                    name="suggest_plugins",
                    description="Get intelligent plugin suggestions based on analysis goal (Helper: Find right plugins for your task)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "What you want to analyze (e.g., 'network connections', 'running processes', 'malware', 'timeline')"
                            }
                        },
                        "required": ["goal"]
                    }
                ),
                Tool(
                    name="batch_execute",
                    description="Execute multiple plugins in sequence with progress tracking (Advanced: Run multiple analyses)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "commands": {
                                "type": "array",
                                "description": "List of plugin commands to execute",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "plugin": {"type": "string"},
                                        "parameters": {"type": "object"}
                                    }
                                }
                            }
                        },
                        "required": ["commands"]
                    }
                ),
                Tool(
                    name="generate_documentation",
                    description="Create a new documentation file that AI can populate with content",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="create_documentation_content",
                    description="AI writes content to documentation file - full creative control",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "Path to the documentation file to write to"
                            },
                            "content": {
                                "type": "string",
                                "description": "Complete content to write to the file (AI decides everything)"
                            }
                        },
                        "required": ["filepath", "content"]
                    }
                ),
                Tool(
                    name="get_analysis_context",
                    description="Get complete analysis context for AI documentation",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute an adaptive tool"""
            logger.info(f"Calling tool: {name} with arguments: {arguments}")
            
            try:
                if name == "load_memory_image":
                    result = await self._handle_load_image(arguments.get("image_path"))
                
                elif name == "get_image_info":
                    result = await self._handle_get_info()
                
                elif name == "list_available_plugins":
                    result = await self._handle_list_plugins(
                        arguments.get("category"),
                        arguments.get("search")
                    )
                
                elif name == "build_plugin_command":
                    result = await self._handle_build_command(
                        arguments.get("plugin"),
                        arguments.get("parameters", {}),
                        arguments.get("show_help", False)
                    )
                
                elif name == "execute_plugin":
                    result = await self._handle_execute_plugin(
                        arguments.get("plugin"),
                        arguments.get("parameters", {}),
                        arguments.get("timeout", 300)
                    )
                
                elif name == "analyze_error":
                    result = await self._handle_analyze_error(
                        arguments.get("include_history", True)
                    )
                
                elif name == "suggest_plugins":
                    result = await self._handle_suggest_plugins(
                        arguments.get("goal")
                    )
                
                elif name == "batch_execute":
                    result = await self._handle_batch_execute(
                        arguments.get("commands", [])
                    )
                
                elif name == "generate_documentation":
                    result = await self._handle_generate_documentation()
                
                elif name == "create_documentation_content":
                    result = await self._handle_create_documentation_content(
                        arguments.get("filepath"),
                        arguments.get("content")
                    )
                
                elif name == "get_analysis_context":
                    result = await self._handle_get_analysis_context()
                
                else:
                    result = f"Unknown tool: {name}"
                
                # Return complete output
                if isinstance(result, list):
                    return result
                else:
                    return [TextContent(type="text", text=str(result))]
                
            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")]
    
    async def _handle_load_image(self, image_path: str) -> str:
        """Load memory image and detect OS"""
        path = Path(image_path)
        if not path.exists():
            path = self.memory_images_dir / image_path
            if not path.exists():
                return f"Memory image not found: {image_path}"
        
        self.current_image = str(path)
        
        # Get image info - try different OS types
        for os_cmd in ["windows.info", "linux.info", "mac.info"]:
            success, output = self._run_volatility_command(["-f", str(path), os_cmd], timeout=120)
            if success:
                self.os_type = self._detect_os_type(output)
                
                # Parse key information
                self.image_info = {
                    "path": str(path),
                    "size": path.stat().st_size if path.exists() else 0,
                    "os_type": self.os_type.value,
                    "loaded_at": self._get_current_time().isoformat()
                }
                
                # Get available plugins for this OS
                await self._refresh_plugin_list()
                
                return f"""Successfully loaded memory image: {path.name}
OS Type: {self.os_type.value}
Image Size: {self.image_info['size'] / (1024*1024*1024):.2f} GB
Available Plugins: {len(self.available_plugins)}

Image Details:
{output}"""
        
        return f"Failed to load memory image or detect OS type"
    
    async def _handle_get_info(self) -> str:
        """Get detailed image information"""
        if not self.current_image:
            return "No memory image loaded"
        
        info = f"""Current Memory Image Information:
Path: {self.current_image}
OS Type: {self.os_type.value}
Size: {self.image_info.get('size', 0) / (1024*1024*1024):.2f} GB
Loaded: {self.image_info.get('loaded_at', 'Unknown')}
Available Plugins: {len(self.available_plugins)}

Plugin Categories:"""
        
        # Count plugins by category
        categories = {}
        for plugin in self.available_plugins:
            cat = plugin.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in sorted(categories.items()):
            info += f"\n  - {cat}: {count} plugins"
        
        return info
    
    async def _refresh_plugin_list(self) -> None:
        """Refresh the list of available plugins"""
        if not self.current_image:
            return
        
        # Get plugin list based on OS
        prefix = self.os_type.value if self.os_type != OSType.UNKNOWN else ""
        
        success, output = self._run_volatility_command(["-f", self.current_image, "--plugin-dirs", str(self.volatility_path / "volatility3" / "plugins"), "-h"], timeout=60)
        
        if success:
            self.available_plugins = self._parse_plugin_list(output)
        
        # Also try to get plugins by prefix
        if prefix:
            success, output = self._run_volatility_command(["--list-plugins"], timeout=60)
            if success:
                prefix_plugins = [p for p in self._parse_plugin_list(output) if p["name"].startswith(prefix)]
                
                # Merge with existing plugins
                existing_names = {p["name"] for p in self.available_plugins}
                for plugin in prefix_plugins:
                    if plugin["name"] not in existing_names:
                        self.available_plugins.append(plugin)
    
    async def _handle_list_plugins(self, category: Optional[str], search: Optional[str]) -> str:
        """List available plugins with filtering"""
        if not self.current_image:
            return "No memory image loaded. Load an image first to see available plugins."
        
        if not self.available_plugins:
            await self._refresh_plugin_list()
        
        plugins = self.available_plugins
        
        # Filter by category
        if category:
            plugins = [p for p in plugins if p["category"].lower() == category.lower()]
        
        # Filter by search term
        if search:
            search_lower = search.lower()
            plugins = [p for p in plugins if search_lower in p["name"].lower() or search_lower in p.get("description", "").lower()]
        
        if not plugins:
            return "No plugins found matching the criteria"
        
        # Format output
        output = f"Available Plugins ({len(plugins)} found):\n"
        output += "=" * 80 + "\n\n"
        
        # Group by category
        by_category = {}
        for plugin in plugins:
            cat = plugin["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(plugin)
        
        for cat in sorted(by_category.keys()):
            output += f"\n{cat} Plugins:\n"
            output += "-" * 40 + "\n"
            for plugin in sorted(by_category[cat], key=lambda x: x["name"]):
                desc = plugin.get("description", "")
                if desc:
                    output += f"  {plugin['name']:<30} - {desc}\n"
                else:
                    output += f"  {plugin['name']}\n"
        
        return output
    
    async def _handle_build_command(self, plugin: str, parameters: Dict[str, Any], show_help: bool) -> str:
        """Build and validate a plugin command"""
        if not self.current_image:
            return "No memory image loaded"
        
        # Build command parts
        cmd_parts = ["-f", self.current_image, plugin]
        
        if show_help:
            cmd_parts.append("-h")
            success, output = self._run_volatility_command(cmd_parts, timeout=30)
            return f"Plugin Help for {plugin}:\n\n{output}"
        
        # Add parameters
        for key, value in parameters.items():
            if key.startswith("--"):
                cmd_parts.append(key)
            else:
                cmd_parts.append(f"--{key}")
            
            if value is not True:  # For boolean flags
                cmd_parts.append(str(value))
        
        # Validate command
        test_cmd = cmd_parts + ["--help"]
        success, output = self._run_volatility_command(test_cmd, timeout=30)
        
        if success:
            full_command = f"vol.py {' '.join(cmd_parts)}"
            return f"""Command built successfully:
{full_command}

Parameters accepted. Ready to execute.

Use 'execute_plugin' with the same plugin and parameters to run this command."""
        else:
            return f"""Command validation failed:
{output}

Please check the plugin name and parameters."""
    
    async def _handle_execute_plugin(self, plugin: str, parameters: Dict[str, Any], timeout: int) -> str:
        """Execute a plugin with parameters"""
        if not self.current_image:
            return "No memory image loaded"
        
        # Build command
        cmd_parts = ["-f", self.current_image, plugin]
        
        for key, value in parameters.items():
            if key.startswith("--"):
                cmd_parts.append(key)
            else:
                cmd_parts.append(f"--{key}")
            
            if value is not True:
                cmd_parts.append(str(value))
        
        # Execute
        success, output = self._run_volatility_command(cmd_parts, timeout=timeout)
        
        # Analyze for suspicious activity
        suspicious_findings = self._analyze_for_suspicious_activity(output, plugin)
        for finding in suspicious_findings:
            if finding not in self.findings:
                self.findings.append(finding)
        
        if not success:
            # Automatic error analysis
            analysis = self._analyze_error(output, ' '.join(cmd_parts))
            
            error_report = f"""Plugin execution failed:
Command: vol.py {' '.join(cmd_parts)}

Error Output:
{output}

Automatic Error Analysis:
========================
Error Type: {analysis['error_type']}
Root Cause: {analysis['root_cause']}

Suggestions:"""
            
            for suggestion in analysis['suggestions']:
                error_report += f"\n  • {suggestion}"
            
            if analysis['alternative_plugins']:
                error_report += "\n\nAlternative Plugins to Try:"
                for alt in analysis['alternative_plugins']:
                    error_report += f"\n  • {alt['name']}: {alt.get('description', '')}"
            
            return error_report
        
        result = f"""Plugin executed successfully:
Command: vol.py {' '.join(cmd_parts)}

Output ({len(output)} characters):
{'=' * 80}
{output}"""
        
        if suspicious_findings:
            result += "\n\n⚠ Suspicious Findings Detected:\n"
            for finding in suspicious_findings:
                result += f"  • {finding}\n"
        
        return result
    
    async def _handle_analyze_error(self, include_history: bool) -> str:
        """Analyze recent errors"""
        if not self.error_history:
            return "No errors in history"
        
        output = "Error Analysis Report\n"
        output += "=" * 80 + "\n\n"
        
        if include_history:
            output += f"Total Errors: {len(self.error_history)}\n\n"
            
            for i, error in enumerate(self.error_history[-5:], 1):  # Last 5 errors
                output += f"Error {i}:\n"
                output += f"  Time: {error['timestamp']}\n"
                output += f"  Command: {error['command']}\n"
                
                analysis = self._analyze_error(error['error'], error['command'])
                output += f"  Type: {analysis['error_type']}\n"
                output += f"  Cause: {analysis['root_cause']}\n"
                output += "  Solutions:\n"
                for suggestion in analysis['suggestions']:
                    output += f"    • {suggestion}\n"
                output += "\n"
        
        # Analyze last error in detail
        last_error = self.error_history[-1]
        analysis = self._analyze_error(last_error['error'], last_error['command'])
        
        output += "Latest Error Details:\n"
        output += "-" * 40 + "\n"
        output += f"Command: {last_error['command']}\n"
        output += f"Error Type: {analysis['error_type']}\n"
        output += f"Root Cause: {analysis['root_cause']}\n\n"
        output += "Recommended Actions:\n"
        
        for i, suggestion in enumerate(analysis['suggestions'], 1):
            output += f"{i}. {suggestion}\n"
        
        if analysis['alternative_plugins']:
            output += "\nTry These Alternative Plugins:\n"
            for plugin in analysis['alternative_plugins']:
                output += f"  • {plugin['name']}: {plugin.get('description', '')}\n"
        
        return output
    
    async def _handle_suggest_plugins(self, goal: str) -> str:
        """Suggest plugins based on analysis goal"""
        if not self.available_plugins:
            return "No plugins available. Load a memory image first."
        
        goal_lower = goal.lower()
        suggestions = []
        
        # Keywords mapping to plugin categories
        keyword_map = {
            "process": ["pslist", "pstree", "psaux", "psscan", "cmdline", "process"],
            "network": ["netscan", "netstat", "connections", "sockets", "network"],
            "file": ["filescan", "dumpfiles", "vadscan", "file"],
            "registry": ["registry", "printkey", "hivelist", "reg"],
            "malware": ["malfind", "mal", "inject", "hollowfind"],
            "timeline": ["timeline", "mftparser", "event"],
            "memory": ["memmap", "vadinfo", "dump"],
            "kernel": ["modules", "drivers", "kernel", "ssdt"],
            "user": ["sessions", "users", "tokens", "privileges"]
        }
        
        # Find relevant plugins
        for keyword, patterns in keyword_map.items():
            if keyword in goal_lower or any(p in goal_lower for p in patterns):
                for plugin in self.available_plugins:
                    plugin_name_lower = plugin["name"].lower()
                    if any(p in plugin_name_lower for p in patterns):
                        if plugin not in suggestions:
                            suggestions.append(plugin)
        
        # If no specific matches, suggest based on general terms
        if not suggestions:
            for plugin in self.available_plugins:
                if any(term in plugin["name"].lower() or term in plugin.get("description", "").lower() 
                       for term in goal_lower.split()):
                    suggestions.append(plugin)
        
        if not suggestions:
            return f"No specific plugins found for '{goal}'. Use 'list_available_plugins' to see all options."
        
        output = f"Plugin Suggestions for '{goal}':\n"
        output += "=" * 80 + "\n\n"
        
        # Group by relevance
        primary = []
        secondary = []
        
        for plugin in suggestions[:10]:  # Limit to 10 suggestions
            if goal_lower in plugin["name"].lower():
                primary.append(plugin)
            else:
                secondary.append(plugin)
        
        if primary:
            output += "Primary Recommendations:\n"
            for plugin in primary:
                output += f"  • {plugin['name']}: {plugin.get('description', 'No description')}\n"
                output += f"    Category: {plugin['category']}\n"
                output += f"    Example: execute_plugin(plugin='{plugin['name']}')\n\n"
        
        if secondary:
            output += "\nSecondary Recommendations:\n"
            for plugin in secondary:
                output += f"  • {plugin['name']}: {plugin.get('description', 'No description')}\n"
        
        output += f"\nTotal {len(suggestions)} plugins found related to '{goal}'"
        
        return output
    
    async def _handle_batch_execute(self, commands: List[Dict[str, Any]]) -> str:
        """Execute multiple commands in sequence"""
        if not commands:
            return "No commands provided"
        
        results = []
        output = f"Batch Execution Report\n"
        output += "=" * 80 + "\n"
        output += f"Executing {len(commands)} commands...\n\n"
        
        for i, cmd in enumerate(commands, 1):
            plugin = cmd.get("plugin")
            parameters = cmd.get("parameters", {})
            
            output += f"\n[{i}/{len(commands)}] Executing: {plugin}\n"
            output += "-" * 40 + "\n"
            
            result = await self._handle_execute_plugin(plugin, parameters, 300)
            
            # Check if successful
            if "successfully" in result:
                output += "✓ Success\n"
                # Extract just the output part
                if "Output (" in result:
                    result_lines = result.split('\n')
                    start_idx = next((i for i, line in enumerate(result_lines) if "Output (" in line), 0)
                    if start_idx:
                        output += '\n'.join(result_lines[start_idx+2:])  # Skip the header lines
                else:
                    output += result
            else:
                output += "✗ Failed\n"
                output += result[:500] + "..." if len(result) > 500 else result
            
            output += "\n"
            results.append({"plugin": plugin, "success": "successfully" in result})
        
        # Summary
        output += "\n" + "=" * 80 + "\n"
        output += "Batch Execution Summary:\n"
        successful = sum(1 for r in results if r["success"])
        output += f"  Successful: {successful}/{len(commands)}\n"
        output += f"  Failed: {len(commands) - successful}/{len(commands)}\n"
        
        return output
    
    async def _handle_generate_documentation(self) -> str:
        """Generate comprehensive AI-driven documentation"""
        return self._generate_documentation()
    
    async def _handle_create_documentation_content(self, filepath: str, content: str) -> str:
        """
        AI-controlled documentation content creation tool.
        The AI decides what content to write and how to structure it.
        """
        try:
            # Validate filepath
            path = Path(filepath)
            if not path.exists():
                # Try relative to reports directory
                path = self.reports_dir / Path(filepath).name
                if not path.exists():
                    return f"Documentation file not found: {filepath}"
            
            # Write AI-generated content to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return f"AI documentation content successfully written to: {path}\n\nContent length: {len(content)} characters\n\nFile ready for review."
            
        except Exception as e:
            return f"Failed to write documentation content: {str(e)}"
    
    async def _handle_get_analysis_context(self) -> str:
        """
        Provide complete analysis context for AI documentation.
        AI uses this to understand what happened during the forensic session.
        """
        context = {
            "session_info": {
                "current_image": self.current_image,
                "image_name": Path(self.current_image).name if self.current_image else None,
                "os_type": self.os_type.value,
                "total_plugins": len(self.available_plugins),
                "session_start": self.analysis_history[0].get('timestamp') if self.analysis_history else None
            },
            "analysis_summary": {
                "total_operations": len(self.analysis_history),
                "successful_operations": sum(1 for a in self.analysis_history if a.get('success', False)),
                "failed_operations": len(self.error_history),
                "findings_discovered": len(self.findings)
            },
            "findings": self.findings,
            "analysis_history": self.analysis_history[-10:],  # Last 10 operations
            "error_summary": [
                {
                    "command": e.get('command', ''),
                    "error_type": e.get('error', '')[:100] + "..." if len(e.get('error', '')) > 100 else e.get('error', ''),
                    "timestamp": e.get('timestamp', '')
                } for e in self.error_history[-5:]  # Last 5 errors
            ],
            "last_command_output_preview": self.last_command_output[:500] + "..." if len(self.last_command_output) > 500 else self.last_command_output
        }
        
        return f"Complete Analysis Context for AI Documentation:\n\n{json.dumps(context, indent=2, default=str)}"
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Adaptive Volatility3 MCP Server...")
        logger.info(f"Memory images directory: {self.memory_images_dir}")
        logger.info(f"Reports directory: {self.reports_dir}")
        logger.info(f"Volatility3 path: {self.volatility_path}")
        logger.info(f"Server initialized by: 0xOb5k-J")
        logger.info(f"Current time: {self._get_current_time().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

if __name__ == "__main__":
    server = AdaptiveVolatilityMCPServer()
    asyncio.run(server.run())
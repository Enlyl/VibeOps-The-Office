"""
mcp_client.py — VibeOps MCP Filesystem Server stub
==================================================
Pillar 3: MCP Servers & Safe File Access

Provides isolated filesystem access to the ./workspace/ directory
to prevent hallucination and unauthorized system access.
"""
import os
from pathlib import Path
from typing import List

_WORKSPACE_DIR = Path(__file__).parent / "workspace"

def list_workspace_directory() -> list[str]:
    """
    Lists all available files in the isolated ./workspace/ directory.
    Use this tool FIRST to understand what files exist before trying to read them.
    Do not hallucinate file names.
    
    Returns:
        List of filenames present in the workspace.
    """
    if not _WORKSPACE_DIR.exists():
        return []
    return [f.name for f in _WORKSPACE_DIR.iterdir() if f.is_file()]


def read_workspace_file(file_name: str) -> str:
    """
    Safely reads the contents of a file located within the ./workspace/ directory.
    Use this tool to read files like 'dirty_data.csv' or 'model_docs.md'.
    
    Args:
        file_name: The exact name of the file to read (e.g., 'dirty_data.csv').
        
    Returns:
        The text content of the file, or an error message if the file doesn't exist.
    """
    # Prevent directory traversal attacks
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        return "[Error: Invalid file name. Directory traversal is forbidden.]"
        
    target_path = _WORKSPACE_DIR / file_name
    
    if not target_path.exists():
        return f"[Error: File '{file_name}' not found in workspace.]"
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Error: Failed to read file: {e}]"


def write_workspace_file(file_name: str, content: str) -> str:
    """
    Safely writes contents to a file located within the ./workspace/ directory.
    Use this tool to persist data such as user profiles.
    
    Args:
        file_name: The name of the file to write (e.g., 'user_profile.json').
        content: The text content to write.
        
    Returns:
        A success message or an error message.
    """
    # Prevent directory traversal attacks
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        return "[Error: Invalid file name. Directory traversal is forbidden.]"
        
    target_path = _WORKSPACE_DIR / file_name
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[Success: File '{file_name}' saved to workspace.]"
    except Exception as e:
        return f"[Error: Failed to write file: {e}]"


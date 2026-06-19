import os
import sys
import json
import argparse
import tempfile
import logging
from typing import List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ApplyDiffEngine")

class InvalidLineReferenceError(ValueError):
    """Raised when the line numbers are out of bounds or invalid."""
    pass

class InvalidDiffContractError(ValueError):
    """Raised when the diff data JSON contract is violated."""
    pass

class TargetFileNotFoundError(FileNotFoundError):
    """Raised when the target file does not exist."""
    pass

def validate_diff_data(diff_data: Any) -> Dict[str, Any]:
    """
    Validates that diff_data matches the contract:
    {"file_path": str, "start_line": int, "end_line": int, "new_content": str}
    """
    if not isinstance(diff_data, dict):
        raise InvalidDiffContractError("Diff data must be a JSON object (dictionary)")
        
    required_keys = ["file_path", "start_line", "end_line", "new_content"]
    for key in required_keys:
        if key not in diff_data:
            raise InvalidDiffContractError(f"Missing mandatory key: '{key}'")
            
    file_path = diff_data["file_path"]
    start_line = diff_data["start_line"]
    end_line = diff_data["end_line"]
    new_content = diff_data["new_content"]
    
    if not isinstance(file_path, str):
        raise InvalidDiffContractError("'file_path' must be a string")
    # Using isinstance(..., bool) check because bool is a subclass of int in Python
    if not isinstance(start_line, int) or isinstance(start_line, bool):
        raise InvalidDiffContractError("'start_line' must be an integer")
    if not isinstance(end_line, int) or isinstance(end_line, bool):
        raise InvalidDiffContractError("'end_line' must be an integer")
    if not isinstance(new_content, str):
        raise InvalidDiffContractError("'new_content' must be a string")
        
    return {
        "file_path": os.path.abspath(file_path),
        "start_line": start_line,
        "end_line": end_line,
        "new_content": new_content
    }

def apply_edit_in_memory(file_path: str, start_line: int, end_line: int, new_content: str) -> Tuple[List[str], str]:
    """
    Validates the line references against the file and returns:
    1. The modified lines list.
    2. The full original content string (for restore/comparison).
    """
    if not os.path.exists(file_path):
        raise TargetFileNotFoundError(f"Target file not found: {file_path}")
        
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        original_content = f.read()
        
    lines = original_content.splitlines(keepends=True)
    total_lines = len(lines)
    
    # Handle empty file special case
    if total_lines == 0:
        if start_line == 1 and (end_line == 1 or end_line == 0):
            return [new_content], original_content
        raise InvalidLineReferenceError(
            f"Invalid line references for empty file: start_line={start_line}, end_line={end_line}"
        )
        
    if start_line < 1:
        raise InvalidLineReferenceError(f"start_line ({start_line}) must be >= 1")
    if end_line < start_line:
        raise InvalidLineReferenceError(f"end_line ({end_line}) must be >= start_line ({start_line})")
    if start_line > total_lines:
        raise InvalidLineReferenceError(f"start_line ({start_line}) exceeds total lines in file ({total_lines})")
    if end_line > total_lines:
        raise InvalidLineReferenceError(f"end_line ({end_line}) exceeds total lines in file ({total_lines})")
        
    # Apply replacement in memory
    modified_lines = list(lines)
    modified_lines[start_line - 1 : end_line] = [new_content]
    
    return modified_lines, original_content

def apply_edit(diff_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Applies the edit to the target file.
    If dry_run=True, generates the VS Code WorkspaceEdit instructions without modifying the file.
    If dry_run=False, writes the changes directly to the file on disk.
    """
    validated = validate_diff_data(diff_data)
    file_path = validated["file_path"]
    start_line = validated["start_line"]
    end_line = validated["end_line"]
    new_content = validated["new_content"]
    
    modified_lines, _ = apply_edit_in_memory(file_path, start_line, end_line, new_content)
    
    # Generate VS Code WorkspaceEdit equivalent JSON
    # 0-indexed range for VS Code: Range(start_line-1, 0, end_line, 0)
    workspace_edit = {
        "uri": f"file://{file_path}",
        "edits": [
            {
                "range": {
                    "start": {"line": start_line - 1, "character": 0},
                    "end": {"line": end_line, "character": 0}
                },
                "newText": new_content
            }
        ]
    }
    
    if dry_run:
        return {
            "status": "success",
            "message": "Dry run complete. Edit validated successfully.",
            "workspace_edit": workspace_edit
        }
        
    # Write to disk
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        return {
            "status": "success",
            "message": "Edit applied to disk successfully.",
            "workspace_edit": workspace_edit
        }
    except Exception as e:
        logger.error(f"Failed to write changes to {file_path}: {e}")
        raise

def register_temp_preview(temp_path: str):
    """Registers the path of a temporary preview file to allow automated secure cleanup on burn."""
    registry_path = os.path.expanduser("~/.config/anthropic-agent/temp_previews.json")
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    try:
        paths = []
        if os.path.exists(registry_path):
            with open(registry_path, 'r', encoding='utf-8') as f:
                data = f.read().strip()
                if data:
                    paths = json.loads(data)
        if temp_path not in paths:
            paths.append(temp_path)
        with open(registry_path, 'w', encoding='utf-8') as f:
            json.dump(paths, f, indent=2)
    except Exception:
        pass

def generate_preview(diff_data: Dict[str, Any]) -> str:
    """
    Generates a modified file in a temporary location and returns the path.
    Registers the path in the temp_previews registry.
    """
    validated = validate_diff_data(diff_data)
    file_path = validated["file_path"]
    start_line = validated["start_line"]
    end_line = validated["end_line"]
    new_content = validated["new_content"]
    
    modified_lines, _ = apply_edit_in_memory(file_path, start_line, end_line, new_content)
    
    # Create temp file
    suffix = os.path.splitext(file_path)[1]
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as temp_f:
        temp_f.writelines(modified_lines)
        temp_path = temp_f.name
        
    register_temp_preview(temp_path)
    return temp_path

def main():
    parser = argparse.ArgumentParser(description="SC-EVM VS Code Diff Application Engine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", type=str, help="Validate and run dry-run on JSON payload or JSON file")
    group.add_argument("--apply", type=str, help="Apply edit directly to disk from JSON payload or JSON file")
    group.add_argument("--preview", type=str, help="Generate a temporary file with the edits applied and output its path")
    group.add_argument("--workspace-edit", type=str, help="Validate and output the VS Code WorkspaceEdit JSON")
    
    args = parser.parse_args()
    
    # Helper to load payload from string or file
    def load_payload(arg_val: str) -> Dict[str, Any]:
        if arg_val == '-':
            data = sys.stdin.read()
        elif os.path.exists(arg_val):
            with open(arg_val, 'r', encoding='utf-8') as f:
                data = f.read()
        else:
            data = arg_val
        return json.loads(data)
        
    try:
        if args.validate:
            payload = load_payload(args.validate)
            result = apply_edit(payload, dry_run=True)
            print(json.dumps(result, indent=2))
        elif args.apply:
            payload = load_payload(args.apply)
            result = apply_edit(payload, dry_run=False)
            print(json.dumps(result, indent=2))
        elif args.workspace_edit:
            payload = load_payload(args.workspace_edit)
            result = apply_edit(payload, dry_run=True)
            print(json.dumps(result["workspace_edit"], indent=2))
        elif args.preview:
            payload = load_payload(args.preview)
            temp_path = generate_preview(payload)
            print(json.dumps({
                "status": "success",
                "original_file": os.path.abspath(payload["file_path"]),
                "preview_file": temp_path
            }, indent=2))
    except Exception as e:
        error_type = e.__class__.__name__
        print(json.dumps({
            "status": "error",
            "error_type": error_type,
            "message": str(e)
        }, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

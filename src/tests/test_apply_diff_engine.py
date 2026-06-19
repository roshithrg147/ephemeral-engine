import os
import json
import unittest
import shutil
import tempfile
from src.apply_diff_engine import (
    apply_edit,
    generate_preview,
    InvalidLineReferenceError,
    InvalidDiffContractError,
    TargetFileNotFoundError
)

class TestApplyDiffEngine(unittest.TestCase):
    def setUp(self):
        # Setup temporary directories and files
        self.test_dir = tempfile.mkdtemp()
        self.sample_file = os.path.join(self.test_dir, "sample.txt")
        self.sample_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        with open(self.sample_file, "w", encoding="utf-8") as f:
            f.write(self.sample_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_validation_missing_keys(self):
        payload = {"file_path": self.sample_file, "start_line": 1}
        with self.assertRaises(InvalidDiffContractError):
            apply_edit(payload, dry_run=True)

    def test_validation_incorrect_types(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": "1",  # string instead of int
            "end_line": 2,
            "new_content": "hello"
        }
        with self.assertRaises(InvalidDiffContractError):
            apply_edit(payload, dry_run=True)

    def test_validation_bool_type_check(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": True,  # boolean is subclass of int, should be rejected
            "end_line": 2,
            "new_content": "hello"
        }
        with self.assertRaises(InvalidDiffContractError):
            apply_edit(payload, dry_run=True)

    def test_line_reference_bounds_lower(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 0,
            "end_line": 2,
            "new_content": "hello"
        }
        with self.assertRaises(InvalidLineReferenceError):
            apply_edit(payload, dry_run=True)

    def test_line_reference_bounds_upper(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 1,
            "end_line": 6,  # file has 5 lines
            "new_content": "hello"
        }
        with self.assertRaises(InvalidLineReferenceError):
            apply_edit(payload, dry_run=True)

    def test_line_reference_bounds_order(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 3,
            "end_line": 2,
            "new_content": "hello"
        }
        with self.assertRaises(InvalidLineReferenceError):
            apply_edit(payload, dry_run=True)

    def test_file_not_found(self):
        payload = {
            "file_path": os.path.join(self.test_dir, "nonexistent.txt"),
            "start_line": 1,
            "end_line": 1,
            "new_content": "hello"
        }
        with self.assertRaises(TargetFileNotFoundError):
            apply_edit(payload, dry_run=True)

    def test_apply_edit_dry_run(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 2,
            "end_line": 4,
            "new_content": "Replacement Content\n"
        }
        result = apply_edit(payload, dry_run=True)
        self.assertEqual(result["status"], "success")
        
        # Check generated WorkspaceEdit structure
        edit = result["workspace_edit"]
        self.assertEqual(edit["uri"], f"file://{os.path.abspath(self.sample_file)}")
        self.assertEqual(edit["edits"][0]["range"]["start"]["line"], 1)  # 0-indexed line 2 is index 1
        self.assertEqual(edit["edits"][0]["range"]["end"]["line"], 4)    # exclusive end
        self.assertEqual(edit["edits"][0]["newText"], "Replacement Content\n")

        # Verify that original file remains unchanged
        with open(self.sample_file, "r") as f:
            content = f.read()
        self.assertEqual(content, self.sample_content)

    def test_apply_edit_to_disk(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 2,
            "end_line": 4,
            "new_content": "Replacement Content\n"
        }
        result = apply_edit(payload, dry_run=False)
        self.assertEqual(result["status"], "success")

        # Verify file changes on disk
        with open(self.sample_file, "r") as f:
            content = f.read()
        expected = "Line 1\nReplacement Content\nLine 5\n"
        self.assertEqual(content, expected)

    def test_generate_preview(self):
        payload = {
            "file_path": self.sample_file,
            "start_line": 1,
            "end_line": 1,
            "new_content": "New Line 1\n"
        }
        preview_path = generate_preview(payload)
        self.assertTrue(os.path.exists(preview_path))

        with open(preview_path, "r") as f:
            preview_content = f.read()
        
        expected = "New Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        self.assertEqual(preview_content, expected)
        
        # Cleanup preview file
        os.remove(preview_path)

if __name__ == "__main__":
    unittest.main()

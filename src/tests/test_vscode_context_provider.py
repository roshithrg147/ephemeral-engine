import os
import shutil
import tempfile
import unittest

from src.vscode_context_provider import WorkspaceScanner


class TestVSCodeContextProvider(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for ChromaDB and test workspace files
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        self.workspace_root = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.workspace_root, exist_ok=True)

        # Initialize the scanner
        self.scanner = WorkspaceScanner(db_path=self.db_path, collection_name="test_collection")

    def tearDown(self):
        # Clean up temporary directories
        shutil.rmtree(self.test_dir)

    def test_chunking(self):
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        # Test basic chunking with a small size
        chunks = self.scanner.chunk_file_content(content, max_chunk_size=15, overlap=5)
        self.assertTrue(len(chunks) > 1)
        # Ensure it keeps lines whole
        for chunk in chunks:
            self.assertTrue(chunk.endswith("\n") or chunk == content.splitlines()[-1])

    def test_index_and_update(self):
        # Create a temporary source file
        file_path = os.path.join(self.workspace_root, "test_file.py")
        content = "def test_func():\n    return 'Hello, World!'\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Index the file
        success = self.scanner.update_file(file_path)
        self.assertTrue(success)
        self.assertEqual(self.scanner.collection.count(), 1)

        # Query the file
        results = self.scanner.query_workspace("Hello", n_results=1)
        self.assertEqual(len(results), 1)
        self.assertIn("Hello, World!", results[0]["document"])
        self.assertEqual(results[0]["metadata"]["file_path"], file_path)

        # Update the file content
        new_content = "def test_func():\n    return 'Updated content!'\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Trigger update
        success = self.scanner.update_file(file_path)
        self.assertTrue(success)
        # Ensure count is still 1 (old chunks deleted, new ones inserted)
        self.assertEqual(self.scanner.collection.count(), 1)

        # Query the updated content
        results = self.scanner.query_workspace("Updated", n_results=1)
        self.assertEqual(len(results), 1)
        self.assertIn("Updated content!", results[0]["document"])

    def test_scan_workspace(self):
        # Create a nested workspace structure
        file1 = os.path.join(self.workspace_root, "helper.py")
        file2 = os.path.join(self.workspace_root, "main.ts")
        ignored_dir = os.path.join(self.workspace_root, "node_modules")
        ignored_file = os.path.join(ignored_dir, "package.json")

        os.makedirs(ignored_dir, exist_ok=True)
        with open(file1, "w") as f:
            f.write("print('helper')")
        with open(file2, "w") as f:
            f.write("console.log('main')")
        with open(ignored_file, "w") as f:
            f.write("{}")

        indexed = self.scanner.scan_local_workspace(self.workspace_root)
        self.assertEqual(indexed, 2)  # Only helper.py and main.ts should be indexed

        # Test querying workspace
        results = self.scanner.query_workspace("console", n_results=1)
        self.assertEqual(len(results), 1)
        self.assertIn("main", results[0]["document"])


if __name__ == "__main__":
    unittest.main()

import argparse
import json
import logging
import os
import sys
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from src.config import settings

try:
    from src.telemetry_sink import log_error
except ImportError:

    def log_error(ctx, msg):
        return None


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VSCodeContextProvider")

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}
INCLUDED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".md",
    ".rs",
    ".go",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".sh",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".ini",
    ".cfg",
}


class WorkspaceScanner:
    """
    Scanner and indexer for VS Code workspace files.
    Generates local embeddings using all-MiniLM-L6-v2 (ONNX) and stores them in ChromaDB.
    """

    def __init__(self, db_path: str, collection_name: str = "workspace_context"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(self.db_path, exist_ok=True)

        logger.info(f"Initializing persistent ChromaDB client at: {self.db_path}")
        self.client = chromadb.PersistentClient(path=self.db_path)

        # Initialize the lightweight local ONNX MiniLM L6 V2 embedding function
        logger.info("Initializing local ONNXMiniLM_L6_V2 embedding function...")
        self.embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"Collection '{collection_name}' initialized. Current count: {self.collection.count()}"
        )

    @staticmethod
    def is_binary_file(file_path: str) -> bool:
        """Check if a file is binary by scanning the first 1024 bytes for a null byte."""
        try:
            with open(file_path, "rb") as f:
                block = f.read(1024)
                return b"\x00" in block
        except Exception as exc:
            log_error("vscode_context_provider.is_binary_file", str(exc))
            return True

    @staticmethod
    def chunk_file_content(
        content: str, max_chunk_size: int = 1000, overlap: int = 100
    ) -> list[str]:
        """
        Chunks file content by keeping lines whole and splitting when chunk size is reached.
        Preserves an overlap of lines from the previous chunk.
        """
        lines = content.splitlines(keepends=True)
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_len = len(line)
            if current_size + line_len > max_chunk_size:
                if current_chunk:
                    chunks.append("".join(current_chunk))

                    # Backtrack to build the overlap
                    overlap_chunk = []
                    overlap_size = 0
                    for prev_line in reversed(current_chunk):
                        if overlap_size + len(prev_line) > overlap:
                            break
                        overlap_chunk.insert(0, prev_line)
                        overlap_size += len(prev_line)

                    current_chunk = overlap_chunk
                    current_size = overlap_size
                else:
                    # Line itself exceeds max_chunk_size
                    chunks.append(line)
                    continue
            current_chunk.append(line)
            current_size += line_len

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def update_file(self, file_path: str) -> bool:
        """
        Updates a single file in the ChromaDB index.
        Deletes any existing chunks for this file first to prevent duplication.
        """
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path) or os.path.isdir(abs_path):
            logger.warning(f"File not found or is a directory: {abs_path}")
            # Try to purge it from database anyway in case it was deleted
            try:
                self.collection.delete(where={"file_path": abs_path})
                logger.info(f"Purged deleted file from index: {abs_path}")
                return True
            except Exception as e:
                logger.error(f"Error purging file '{abs_path}': {e}")
                return False

        if self.is_binary_file(abs_path):
            logger.debug(f"Skipping binary file: {abs_path}")
            return False

        # Verify extension
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in INCLUDED_EXTENSIONS:
            logger.debug(f"Skipping file with unmapped extension '{ext}': {abs_path}")
            return False
        if os.path.getsize(abs_path) > settings.WORKSPACE_MAX_FILE_BYTES:
            logger.warning("Skipping oversized workspace file: %s", abs_path)
            return False

        try:
            # First, read file contents
            with open(abs_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Clean/remove existing embeddings for this specific file path to avoid duplicates
            self.collection.delete(where={"file_path": abs_path})

            if not content.strip():
                logger.info(f"File is empty, removed from index: {abs_path}")
                return True

            chunks = self.chunk_file_content(content)
            if not chunks:
                return True

            # Generate IDs, documents, and metadatas lists
            ids = [f"{abs_path}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {"file_path": abs_path, "chunk_index": i, "total_chunks": len(chunks)}
                for i in range(len(chunks))
            ]

            # Upsert into ChromaDB
            self.collection.add(ids=ids, documents=chunks, metadatas=metadatas)
            logger.info(f"Indexed {len(chunks)} chunks for: {abs_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to index file {abs_path}: {e}")
            return False

    def index_files(self, file_paths: list[str]) -> int:
        """
        Indexes a list of files. Returns the count of successfully indexed files.
        """
        indexed_count = 0
        for path in file_paths:
            if self.update_file(path):
                indexed_count += 1
        return indexed_count

    def scan_local_workspace(self, root_path: str) -> int:
        """
        Fallback/Standalone scanner. Recursively finds and indexes all relevant files in root_path.
        """
        abs_root = os.path.abspath(root_path)
        logger.info(f"Scanning workspace root: {abs_root}")

        candidate_count = 0
        indexed_count = 0
        for root, dirs, files in os.walk(abs_root, topdown=True):
            # Prune directories in-place to avoid walking down excluded paths
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in INCLUDED_EXTENSIONS:
                    candidate_count += 1
                    if self.update_file(os.path.join(root, file)):
                        indexed_count += 1

        logger.info(f"Found {candidate_count} potential source files to index.")
        return indexed_count

    def query_workspace(self, query_text: str, n_results: int = 5) -> list[dict[str, Any]]:
        """
        Queries ChromaDB for matching code snippets.
        """
        results = self.collection.query(query_texts=[query_text], n_results=n_results)

        formatted_results = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metadatas = (
                results["metadatas"][0]
                if "metadatas" in results and results["metadatas"]
                else [{}] * len(docs)
            )
            distances = (
                results["distances"][0]
                if "distances" in results and results["distances"]
                else [0.0] * len(docs)
            )

            for doc, meta, dist in zip(docs, metadatas, distances, strict=True):
                formatted_results.append({"document": doc, "metadata": meta, "distance": dist})
        return formatted_results


def _read_text_payload(path_or_stdin: str) -> str:
    if path_or_stdin == "-":
        logger.info("Reading file list from stdin...")
        return sys.stdin.read().strip()

    if not os.path.exists(path_or_stdin):
        raise FileNotFoundError(f"Index file list not found: {path_or_stdin}")

    with open(path_or_stdin, encoding="utf-8") as f:
        return f.read().strip()


def _parse_file_paths(data: str) -> list[str]:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return [line.strip() for line in data.splitlines() if line.strip()]

    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]

    return [line.strip() for line in data.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="High-performance Local Workspace Scanner")
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.path.expanduser("~/.config/anthropic-agent/workspace_db"),
        help="ChromaDB persistent path",
    )
    parser.add_argument(
        "--collection-name", type=str, default="workspace_context", help="ChromaDB collection name"
    )
    parser.add_argument(
        "--index-files",
        type=str,
        help="Path to a JSON file containing a list of files to index, or '-' to read from stdin",
    )
    parser.add_argument(
        "--update",
        type=str,
        help="Absolute path of a file to update in the index (e.g. on file save)",
    )
    parser.add_argument("--query", type=str, help="Query the workspace index for relevant context")
    parser.add_argument(
        "--scan-root",
        type=str,
        help="Absolute path of the workspace root to scan and index directly (fallback/standalone mode)",
    )
    parser.add_argument(
        "--n-results", type=int, default=5, help="Number of results to return for query"
    )

    args = parser.parse_args()

    scanner = WorkspaceScanner(db_path=args.db_path, collection_name=args.collection_name)

    if args.index_files:
        try:
            data = _read_text_payload(args.index_files)
            file_paths = _parse_file_paths(data)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            sys.exit(1)

        logger.info(f"Indexing {len(file_paths)} files specified via command line...")
        indexed = scanner.index_files(file_paths)
        logger.info(f"Successfully indexed {indexed} out of {len(file_paths)} files.")

    elif args.update:
        logger.info(f"Received file update trigger for: {args.update}")
        success = scanner.update_file(args.update)
        if success:
            logger.info(f"Successfully updated {args.update} in index.")
        else:
            logger.error(f"Failed to update {args.update} in index.")

    elif args.scan_root:
        logger.info(f"Initiating full repository scan for: {args.scan_root}")
        indexed = scanner.scan_local_workspace(args.scan_root)
        logger.info(f"Scan and index completed. Total indexed files: {indexed}")

    elif args.query:
        logger.info(f"Querying workspace for: '{args.query}'")
        results = scanner.query_workspace(args.query, n_results=args.n_results)
        print(json.dumps(results, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

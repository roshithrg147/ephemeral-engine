"""AST & Structural Symbol Indexer for SC-EVM.

Performs incremental AST and symbol graph indexing over repository files,
extracting classes, functions, interfaces, imports, exports, API routes,
configurations, environment variables, and database migrations.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import NamedTuple


class SymbolLocation(NamedTuple):
    file_path: str
    symbol_name: str
    symbol_type: str  # class, function, interface, route, config, env_var, db_migration, import, export
    line_number: int
    signature: str
    docstring: str | None


class ASTNodeResult(NamedTuple):
    symbol: SymbolLocation
    score: float
    relationships: list[str]


class ASTIndexer:
    def __init__(self, root_dir: str | Path | None = None, cache_dir: str | Path | None = None):
        self.root_dir = Path(root_dir or ".").resolve()
        self.cache_dir = Path(cache_dir or ".ast_cache")
        self._symbols: dict[str, list[SymbolLocation]] = {}  # file_path -> list[SymbolLocation]
        self._symbol_map: dict[str, list[SymbolLocation]] = {}  # symbol_name -> list[SymbolLocation]
        self._file_hashes: dict[str, str] = {}  # file_path -> sha256 hash
        self._relationships: dict[str, list[str]] = {}  # symbol_name -> list[dependency_symbol_names]

    def _hash_file(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        try:
            return hashlib.sha256(file_path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def index_file(self, rel_path: str, content: str | None = None) -> list[SymbolLocation]:
        """Parse and index a single file incrementally."""
        abs_path = self.root_dir / rel_path
        if not abs_path.exists() and content is None:
            self.remove_file(rel_path)
            return []

        if content is None:
            try:
                content = abs_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return []

        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # Skip if file hasn't changed
        if self._file_hashes.get(rel_path) == file_hash and rel_path in self._symbols:
            return self._symbols[rel_path]

        # Remove previous symbols for this file
        self.remove_file(rel_path)
        self._file_hashes[rel_path] = file_hash

        extracted: list[SymbolLocation] = []
        if rel_path.endswith(".py"):
            extracted = self._parse_python_ast(rel_path, content)
        else:
            extracted = self._parse_generic_code(rel_path, content)

        self._symbols[rel_path] = extracted
        imports = [sym.symbol_name for sym in extracted if sym.symbol_type == "import"]
        for sym in extracted:
            self._symbol_map.setdefault(sym.symbol_name.lower(), []).append(sym)
            rel_list = self._relationships.setdefault(sym.symbol_name, [])
            if sym.symbol_type != "import":
                for imp in imports:
                    if imp not in rel_list:
                        rel_list.append(imp)

        return extracted

    def remove_file(self, rel_path: str) -> None:
        """Remove a file and its symbols from the index."""
        if rel_path not in self._symbols:
            return

        old_symbols = self._symbols.pop(rel_path, [])
        self._file_hashes.pop(rel_path, None)

        for sym in old_symbols:
            sym_key = sym.symbol_name.lower()
            if sym_key in self._symbol_map:
                self._symbol_map[sym_key] = [
                    s for s in self._symbol_map[sym_key] if s.file_path != rel_path
                ]
                if not self._symbol_map[sym_key]:
                    del self._symbol_map[sym_key]
            self._relationships.pop(sym.symbol_name, None)

    def _parse_python_ast(self, rel_path: str, content: str) -> list[SymbolLocation]:
        """Parse Python source code using built-in ast module."""
        symbols: list[SymbolLocation] = []
        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            return self._parse_generic_code(rel_path, content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                is_interface = any(
                    isinstance(b, ast.Name) and b.id in {"BaseModel", "Interface", "Protocol"}
                    for b in node.bases
                )
                sym_type = "interface" if is_interface else "class"
                symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=node.name,
                        symbol_type=sym_type,
                        line_number=node.lineno,
                        signature=f"class {node.name}",
                        docstring=docstring,
                    )
                )

            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                docstring = ast.get_docstring(node)
                is_async = isinstance(node, ast.AsyncFunctionDef)
                prefix = "async def" if is_async else "def"
                signature = f"{prefix} {node.name}()"

                # Check if route decorator
                is_route = False
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Attribute) and dec.func.attr in {
                            "get",
                            "post",
                            "put",
                            "delete",
                            "patch",
                        }:
                            is_route = True
                            route_path = (
                                dec.args[0].value
                                if dec.args and isinstance(dec.args[0], ast.Constant)
                                else ""
                            )
                            signature = f"@{dec.func.attr.upper()} {route_path} -> {node.name}"

                sym_type = "route" if is_route else "function"
                symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=node.name,
                        symbol_type=sym_type,
                        line_number=node.lineno,
                        signature=signature,
                        docstring=docstring,
                    )
                )

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols.append(
                            SymbolLocation(
                                file_path=rel_path,
                                symbol_name=alias.name,
                                symbol_type="import",
                                line_number=node.lineno,
                                signature=f"import {alias.name}",
                                docstring=None,
                            )
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        symbols.append(
                            SymbolLocation(
                                file_path=rel_path,
                                symbol_name=f"{node.module}.{alias.name}",
                                symbol_type="import",
                                line_number=node.lineno,
                                signature=f"from {node.module} import {alias.name}",
                                docstring=None,
                            )
                        )

        # Regex pass for environment variables, config settings, DB migrations
        symbols.extend(self._extract_config_and_env(rel_path, content))
        return symbols

    def _extract_config_and_env(self, rel_path: str, content: str) -> list[SymbolLocation]:
        """Extract environment variables, configs, and SQL migrations using regex."""
        extra_symbols: list[SymbolLocation] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, 1):
            # Env var access
            env_match = re.search(r"os\.(?:getenv|environ\.get)\(['\"]([A-Z0-9_]+)['\"]", line)
            if env_match:
                var_name = env_match.group(1)
                extra_symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=var_name,
                        symbol_type="env_var",
                        line_number=idx,
                        signature=f"ENV {var_name}",
                        docstring=None,
                    )
                )

            # Settings / config variable assignment
            cfg_match = re.search(r"^\s*([A-Z0-9_]{3,})\s*:\s*[A-Za-z0-9_\[\], |]+\s*=", line)
            if cfg_match:
                cfg_name = cfg_match.group(1)
                extra_symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=cfg_name,
                        symbol_type="config",
                        line_number=idx,
                        signature=f"CONFIG {cfg_name}",
                        docstring=None,
                    )
                )

            # SQL DB Migration statements
            sql_match = re.search(r"(?:CREATE TABLE|ALTER TABLE|DROP TABLE)\s+([A-Za-z0-9_]+)", line, re.IGNORECASE)
            if sql_match:
                tbl_name = sql_match.group(1)
                extra_symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=tbl_name,
                        symbol_type="db_migration",
                        line_number=idx,
                        signature=f"DB_TABLE {tbl_name}",
                        docstring=None,
                    )
                )

        return extra_symbols

    def _parse_generic_code(self, rel_path: str, content: str) -> list[SymbolLocation]:
        """Extract symbols from JS/TS/JSON/SQL/YAML non-python files."""
        symbols: list[SymbolLocation] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, 1):
            # Class definition
            cls_match = re.search(r"(?:export\s+)?class\s+([A-Za-z0-9_]+)", line)
            if cls_match:
                symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=cls_match.group(1),
                        symbol_type="class",
                        line_number=idx,
                        signature=f"class {cls_match.group(1)}",
                        docstring=None,
                    )
                )

            # Interface / Type definition
            iface_match = re.search(r"(?:export\s+)?(?:interface|type)\s+([A-Za-z0-9_]+)", line)
            if iface_match:
                symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=iface_match.group(1),
                        symbol_type="interface",
                        line_number=idx,
                        signature=f"interface {iface_match.group(1)}",
                        docstring=None,
                    )
                )

            # Function / Arrow Function definition
            func_match = re.search(
                r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)|const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(",
                line,
            )
            if func_match:
                fname = func_match.group(1) or func_match.group(2)
                if fname and fname not in {"if", "for", "while", "switch"}:
                    symbols.append(
                        SymbolLocation(
                            file_path=rel_path,
                            symbol_name=fname,
                            symbol_type="function",
                            line_number=idx,
                            signature=f"function {fname}()",
                            docstring=None,
                        )
                    )

            # Express / API Route definition
            route_match = re.search(r"(?:app|router)\.(get|post|put|delete)\(['\"]([^'\"]+)['\"]", line)
            if route_match:
                method, path = route_match.groups()
                symbols.append(
                    SymbolLocation(
                        file_path=rel_path,
                        symbol_name=f"{method.upper()} {path}",
                        symbol_type="route",
                        line_number=idx,
                        signature=f"{method.upper()} {path}",
                        docstring=None,
                    )
                )

        symbols.extend(self._extract_config_and_env(rel_path, content))
        return symbols

    def search_symbols(self, query: str, top_k: int = 5) -> list[ASTNodeResult]:
        """Search the AST symbol index for matching classes, functions, routes, or configs."""
        if not query:
            return []

        q_terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", query) if len(t) > 1]
        if not q_terms:
            return []

        scored: list[tuple[SymbolLocation, float]] = []

        for sym_list in self._symbols.values():
            for sym in sym_list:
                s_name = sym.symbol_name.lower()
                s_sig = sym.signature.lower()
                s_doc = (sym.docstring or "").lower()

                score = 0.0
                for term in q_terms:
                    if term == s_name:
                        score += 3.0
                    elif term in s_name:
                        score += 1.5
                    elif term in s_sig:
                        score += 1.0
                    elif term in s_doc:
                        score += 0.5

                if score > 0:
                    scored.append((sym, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored[:top_k]

        return [
            ASTNodeResult(
                symbol=sym,
                score=score,
                relationships=self._relationships.get(sym.symbol_name, []),
            )
            for sym, score in top_candidates
        ]

    def clear(self) -> None:
        """Clear the entire AST index."""
        self._symbols.clear()
        self._symbol_map.clear()
        self._file_hashes.clear()
        self._relationships.clear()

"""Memory M = (K, W, G) — Playground Spec v2 §2. E is not built.

Path space (uniform, catalog-visible):
    agents/<agent_id>/<relpath>   workspace files (W) — mutable, owner-organized
    global/<relpath>              global memory (G) — immutable linear versions

W visibility is open: any agent may read any workspace; cross-workspace
*writes* are allowed and logged loudly by the tool layer.

G is linear-versioned: every commit creates an immutable new version,
head pointer moves, author+round provenance per version. Divergence
(mechanical definition, logged in THEORY_VS_REALITY): a commit over a
head authored by a different agent that the committing agent has never
read (any version) is flagged `divergent` in the catalog — a visible
blind overwrite, kept, never resolved by the system.

K is the mechanical index over all of it: agents, artifacts, rules.
Never contains bodies. Bounded queries. The catalog answers "what's
there"; agents decide what it means.
"""
from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GlobalVersion:
    version: int
    content: str
    author: str
    round: int
    summary: str


@dataclass
class GlobalArtifact:
    path: str
    versions: list[GlobalVersion] = field(default_factory=list)
    head: int = 0                      # version number, 1-based; 0 = none
    divergent: bool = False

    def head_version(self) -> Optional[GlobalVersion]:
        if not self.head:
            return None
        return self.versions[self.head - 1]


@dataclass
class WorkspaceFile:
    path: str
    content: str
    author: str                        # last writer
    writes: int = 0


class Memory:
    def __init__(self) -> None:
        self.ws: dict[str, WorkspaceFile] = {}       # full path -> file
        self.glob: dict[str, GlobalArtifact] = {}    # full path -> artifact
        # read log for the mechanical divergence flag: (agent_id, path) pairs
        self._global_reads: set[tuple[str, str]] = set()

    # ---- W ----
    def ws_write(self, path: str, content: str, author: str,
                 append: bool = False) -> WorkspaceFile:
        f = self.ws.get(path)
        if f is None:
            f = WorkspaceFile(path=path, content="", author=author)
            self.ws[path] = f
        f.content = (f.content + content) if append else content
        f.author = author
        f.writes += 1
        return f

    def ws_read(self, path: str) -> Optional[WorkspaceFile]:
        return self.ws.get(path)

    def ws_list(self, prefix: str) -> list[WorkspaceFile]:
        return sorted((f for p, f in self.ws.items() if p.startswith(prefix)),
                      key=lambda f: f.path)

    # ---- G ----
    def g_commit(self, path: str, content: str, author: str, round_no: int,
                 summary: str) -> tuple[GlobalArtifact, bool]:
        """Returns (artifact, newly_divergent)."""
        art = self.glob.get(path)
        if art is None:
            art = GlobalArtifact(path=path)
            self.glob[path] = art
        newly_divergent = False
        prev = art.head_version()
        if (prev is not None and prev.author != author
                and (author, path) not in self._global_reads):
            newly_divergent = not art.divergent
            art.divergent = True
        v = GlobalVersion(version=len(art.versions) + 1, content=content,
                          author=author, round=round_no, summary=summary)
        art.versions.append(v)
        art.head = v.version
        return art, newly_divergent

    def g_read(self, path: str, reader: str,
               version: Optional[int] = None) -> Optional[GlobalVersion]:
        art = self.glob.get(path)
        if art is None:
            return None
        self._global_reads.add((reader, path))
        if version is None:
            return art.head_version()
        if 1 <= version <= len(art.versions):
            return art.versions[version - 1]
        return None

    # ---- shared views (used by tools and circuit accessors) ----
    def exists(self, path: str) -> bool:
        return path in self.ws or (path in self.glob and self.glob[path].head > 0)

    def head_no(self, path: str) -> Optional[int]:
        if path in self.glob and self.glob[path].head:
            return self.glob[path].head
        if path in self.ws:
            return self.ws[path].writes
        return None

    def content_at(self, path: str) -> Optional[str]:
        """Current content without touching the read log (accessor use)."""
        if path in self.ws:
            return self.ws[path].content
        art = self.glob.get(path)
        if art:
            v = art.head_version()
            return v.content if v else None
        return None

    def field(self, path: str, key: str) -> Any:
        content = self.content_at(path)
        if content is None:
            return None
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(data, dict):
            return data.get(key)
        return None

    def all_paths(self) -> list[str]:
        return sorted(set(self.ws) | {p for p, a in self.glob.items() if a.head})

    def matching(self, pattern: str, cap: int = 200) -> list[str]:
        return sorted(fnmatch.filter(self.all_paths(), pattern))[:cap]

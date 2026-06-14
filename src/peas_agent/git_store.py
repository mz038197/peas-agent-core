"""Git-backed version control for memory files, using dulwich."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommitInfo:
    sha: str
    message: str
    timestamp: str

    def format(self, diff: str = "") -> str:
        header = f"## {self.message.splitlines()[0]}\n`{self.sha}` — {self.timestamp}\n"
        if diff:
            return f"{header}\n```diff\n{diff}\n```"
        return f"{header}\n(no file changes)"


class GitStore:
    """Git-backed version control for memory files."""

    def __init__(self, workspace: Path, tracked_files: list[str]):
        self._workspace = workspace.expanduser().resolve()
        self._tracked_files = tracked_files

    def is_initialized(self) -> bool:
        return (self._workspace / ".git").is_dir()

    def init(self) -> bool:
        if self.is_initialized():
            return False

        try:
            from dulwich import porcelain

            porcelain.init(str(self._workspace))

            gitignore = self._workspace / ".gitignore"
            gitignore.write_text(self._build_gitignore(), encoding="utf-8")

            for rel in self._tracked_files:
                path = self._workspace / rel
                path.parent.mkdir(parents=True, exist_ok=True)

            porcelain.add(
                str(self._workspace),
                paths=[".gitignore"],
            )
            porcelain.commit(
                str(self._workspace),
                message=b"init: peas-agent memory store",
                author=b"peas-agent <peas-agent@dream>",
                committer=b"peas-agent <peas-agent@dream>",
            )
            return True
        except Exception:
            return False

    def _existing_tracked_paths(self) -> list[str]:
        paths = [".gitignore"]
        for rel in self._tracked_files:
            if (self._workspace / rel).exists():
                paths.append(rel)
        return paths

    def auto_commit(self, message: str) -> str | None:
        if not self.is_initialized():
            return None

        try:
            from dulwich import porcelain

            porcelain.add(str(self._workspace), paths=self._existing_tracked_paths())
            st = porcelain.status(str(self._workspace))
            if not st.unstaged and not any(st.staged.values()):
                return None

            msg_bytes = message.encode("utf-8")
            sha_bytes = porcelain.commit(
                str(self._workspace),
                message=msg_bytes,
                author=b"peas-agent <peas-agent@dream>",
                committer=b"peas-agent <peas-agent@dream>",
            )
            if sha_bytes is None:
                return None
            return sha_bytes.hex()[:8]
        except Exception:
            return None

    def _resolve_sha(self, short_sha: str) -> bytes | None:
        try:
            from dulwich.repo import Repo

            with Repo(str(self._workspace)) as repo:
                try:
                    sha = repo.refs[b"HEAD"]
                except KeyError:
                    return None

                while sha:
                    if sha.hex().startswith(short_sha):
                        return sha
                    commit = repo[sha]
                    if commit.type_name != b"commit":
                        break
                    sha = commit.parents[0] if commit.parents else None
            return None
        except Exception:
            return None

    def _build_gitignore(self) -> str:
        dirs: set[str] = set()
        for file_path in self._tracked_files:
            parent = str(Path(file_path).parent)
            if parent != ".":
                dirs.add(parent)
        lines = ["/*"]
        for directory in sorted(dirs):
            lines.append(f"!{directory}/")
        for file_path in self._tracked_files:
            lines.append(f"!{file_path}")
        lines.append("!.gitignore")
        return "\n".join(lines) + "\n"

    def log(self, max_entries: int = 20) -> list[CommitInfo]:
        if not self.is_initialized():
            return []

        try:
            from dulwich.repo import Repo

            entries: list[CommitInfo] = []
            with Repo(str(self._workspace)) as repo:
                try:
                    head = repo.refs[b"HEAD"]
                except KeyError:
                    return []

                sha = head
                while sha and len(entries) < max_entries:
                    commit = repo[sha]
                    if commit.type_name != b"commit":
                        break
                    ts = time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.localtime(commit.commit_time),
                    )
                    msg = commit.message.decode("utf-8", errors="replace").strip()
                    entries.append(
                        CommitInfo(sha=sha.hex()[:8], message=msg, timestamp=ts)
                    )
                    sha = commit.parents[0] if commit.parents else None
            return entries
        except Exception:
            return []

    def diff_commits(self, sha1: str, sha2: str) -> str:
        if not self.is_initialized():
            return ""

        try:
            from dulwich import porcelain

            full1 = self._resolve_sha(sha1)
            full2 = self._resolve_sha(sha2)
            if not full1 or not full2:
                return ""

            out = io.BytesIO()
            porcelain.diff(
                str(self._workspace),
                commit=full1,
                commit2=full2,
                outstream=out,
            )
            return out.getvalue().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def find_commit(self, short_sha: str, max_entries: int = 20) -> CommitInfo | None:
        for commit in self.log(max_entries=max_entries):
            if commit.sha.startswith(short_sha):
                return commit
        return None

    def show_commit_diff(
        self, short_sha: str, max_entries: int = 20
    ) -> tuple[CommitInfo, str] | None:
        commits = self.log(max_entries=max_entries)
        for index, commit in enumerate(commits):
            if commit.sha.startswith(short_sha):
                if index + 1 < len(commits):
                    diff = self.diff_commits(commits[index + 1].sha, commit.sha)
                else:
                    diff = ""
                return commit, diff
        return None

    def revert(self, commit: str) -> str | None:
        if not self.is_initialized():
            return None

        try:
            from dulwich.repo import Repo

            full_sha = self._resolve_sha(commit)
            if not full_sha:
                return None

            with Repo(str(self._workspace)) as repo:
                commit_obj = repo[full_sha]
                if commit_obj.type_name != b"commit" or not commit_obj.parents:
                    return None

                parent_obj = repo[commit_obj.parents[0]]
                tree = repo[parent_obj.tree]

                restored: list[str] = []
                for filepath in self._tracked_files:
                    content = self._read_blob_from_tree(repo, tree, filepath)
                    if content is not None:
                        dest = self._workspace / filepath
                        dest.write_text(content, encoding="utf-8")
                        restored.append(filepath)

            if not restored:
                return None
            return self.auto_commit(f"revert: undo {commit}")
        except Exception:
            return None

    @staticmethod
    def _read_blob_from_tree(repo, tree, filepath: str) -> str | None:
        parts = Path(filepath).parts
        current = tree
        for part in parts:
            try:
                entry = current[part.encode()]
            except KeyError:
                return None
            obj = repo[entry[1]]
            if obj.type_name == b"blob":
                return obj.data.decode("utf-8", errors="replace")
            if obj.type_name == b"tree":
                current = obj
            else:
                return None
        return None

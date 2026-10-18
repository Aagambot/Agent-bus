#!/usr/bin/env python3
"""Enforced pre-commit hooks for agentbus (Step 7).

Rules enforced (from CLAUDE.md):
1. Block edits to existing test files during tasks ("Never edit tests to make them pass").
2. Block reads / imports / references to upstream context-mode ELv2 source code.
3. Block secrets in staged diffs (API keys, private keys, tokens, credentials).
"""

import os
import re
import sys
import subprocess
from pathlib import Path


SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9_-]{20,}", "OpenAI API Key pattern"),
    (r"sk-ant-[a-zA-Z0-9_-]{20,}", "Anthropic API Key pattern"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN (?:RSA|OPENSSH|DSA|EC)? PRIVATE KEY-----", "Private cryptographic key"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{25,}", "Bearer Token pattern"),
    (r"(?i)(?:api_key|apikey|secret_key|auth_token)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "Hardcoded API secret"),
]

UPSTREAM_PATTERNS = [
    (r"mksglu/context-mode", "Reference to upstream repository"),
    (r"context-mode/(?:src|lib|dist)", "Path pointing to upstream source directory"),
    (r"(?i)elastic\s+license\s+2\.0", "Reference to ELv2 upstream licensing in source"),
]


def get_staged_files() -> list[str]:
    """Get list of staged files from git."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip().splitlines()
    except Exception:
        return []


def get_staged_diff() -> str:
    """Get staged diff content from git."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout
    except Exception:
        return ""


def split_diff_by_file(diff_content: str):
    """Split a git diff into (filename, diff_lines) tuples."""
    files = []
    current_file = None
    current_lines = []
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            if current_file:
                files.append((current_file, current_lines))
            current_lines = [line]
            parts = line.split()
            current_file = parts[-1].lstrip("b/") if len(parts) >= 4 else "unknown"
        else:
            current_lines.append(line)
    if current_file:
        files.append((current_file, current_lines))
    elif diff_content.strip():
        # Fallback if diff format has no header (e.g. mock test string)
        files.append(("raw_input", diff_content.splitlines()))
    return files


def check_test_edits(staged_status_lines: list[str]) -> list[str]:
    """Block modifications or deletions to existing test files."""
    violations = []
    if os.environ.get("ALLOW_TEST_EDITS") == "1":
        return violations

    for line in staged_status_lines:
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        status, file_path = parts[0], parts[1].strip()
        
        # Normalize path
        norm_path = file_path.replace("\\", "/")
        # Allow test_hooks.py modifications if editing the hook test suite
        if norm_path.startswith("tests/") and norm_path.endswith(".py") and norm_path != "tests/test_hooks.py":
            # 'M' = modified, 'D' = deleted
            if status.startswith("M") or status.startswith("D"):
                violations.append(
                    f"[TEST INTEGRITY VIOLATION] Modified/deleted existing test file '{file_path}' "
                    f"(status: {status}). CLAUDE.md Rule 2 strictly forbids editing tests to make them pass."
                )
    return violations


def check_upstream_references(diff_content: str) -> list[str]:
    """Block references or imports from upstream context-mode source."""
    violations = []
    if os.environ.get("ALLOW_UPSTREAM_REFS") == "1":
        return violations

    for filename, lines in split_diff_by_file(diff_content):
        norm = filename.replace("\\", "/")
        # Exempt hook definition and hook test fixtures
        if norm.startswith("scripts/hooks/") or norm == "tests/test_hooks.py":
            continue
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                added_content = line[1:]
                for pattern, desc in UPSTREAM_PATTERNS:
                    if re.search(pattern, added_content):
                        violations.append(
                            f"[UPSTREAM ELv2 VIOLATION in {filename}] Detected {desc} in added line: '{added_content.strip()}'. "
                            f"CLAUDE.md Rule 1 forbids copying or directly referencing ELv2 upstream source."
                        )
    return violations


def check_secrets(diff_content: str) -> list[str]:
    """Block secrets in added diff lines."""
    violations = []
    for filename, lines in split_diff_by_file(diff_content):
        norm = filename.replace("\\", "/")
        # Exempt hook definition and hook test fixtures
        if norm.startswith("scripts/hooks/") or norm == "tests/test_hooks.py":
            continue
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                added_content = line[1:]
                for pattern, desc in SECRET_PATTERNS:
                    if re.search(pattern, added_content):
                        violations.append(
                            f"[SECURITY VIOLATION in {filename}] Detected potential secret ({desc}) in diff line. "
                            f"CLAUDE.md Security Checklist forbids committing credentials."
                        )
    return violations


def run_checks(staged_files: list[str] = None, diff_content: str = None) -> int:
    """Run all three checks and return exit code."""
    if staged_files is None:
        staged_files = get_staged_files()
    if diff_content is None:
        diff_content = get_staged_diff()

    violations = []
    violations.extend(check_test_edits(staged_files))
    violations.extend(check_upstream_references(diff_content))
    violations.extend(check_secrets(diff_content))

    if violations:
        print("\n" + "=" * 70, file=sys.stderr)
        print(" [AGENTBUS PRE-COMMIT HOOK BLOCKED COMMIT]", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for v in violations:
            print(f" ERROR: {v}", file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_checks())

"""Unit tests for agentbus enforced pre-commit hooks (Step 7).

Verifies each hook fires correctly on mock triggers:
1. Block test edits during fix tasks.
2. Block reads / imports of upstream context-mode ELv2 source.
3. Block secrets in diffs.
"""

import os
import sys
import pytest
from pathlib import Path

# Add scripts directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "hooks"))
import check_hooks


def test_hook_blocks_existing_test_modifications():
    """Verify modifying an existing test file is blocked."""
    mock_staged = [
        "M\ttests/test_concurrency.py",
    ]
    violations = check_hooks.check_test_edits(mock_staged)
    assert len(violations) == 1
    assert "TEST INTEGRITY VIOLATION" in violations[0]
    assert "CLAUDE.md Rule 2" in violations[0]


def test_hook_blocks_existing_test_deletions():
    """Verify deleting an existing test file is blocked."""
    mock_staged = [
        "D\ttests/test_crash_safety.py",
    ]
    violations = check_hooks.check_test_edits(mock_staged)
    assert len(violations) == 1
    assert "TEST INTEGRITY VIOLATION" in violations[0]


def test_hook_allows_new_test_files():
    """Verify adding a brand new test file is permitted."""
    mock_staged = [
        "A\ttests/test_new_feature.py",
        "M\tsrc/agentbus/core/bus.py",
    ]
    violations = check_hooks.check_test_edits(mock_staged)
    assert len(violations) == 0


def test_hook_blocks_upstream_context_mode_references():
    """Verify referencing upstream context-mode ELv2 code is blocked."""
    mock_diff = """
diff --git a/src/agentbus/core/bus.py b/src/agentbus/core/bus.py
--- a/src/agentbus/core/bus.py
+++ b/src/agentbus/core/bus.py
@@ -10,3 +10,4 @@
+# Borrowed from mksglu/context-mode implementation
+from context-mode/src/store import Store
"""
    violations = check_hooks.check_upstream_references(mock_diff)
    assert len(violations) >= 1
    assert any("UPSTREAM ELv2 VIOLATION" in v for v in violations)


def test_hook_blocks_secrets_in_diff():
    """Verify committing secrets like API keys or private keys is blocked."""
    # Test OpenAI API key pattern
    mock_diff_openai = """
+++ b/src/agentbus/core/bus.py
+token = "sk-1234567890abcdef1234567890abcdef"
"""
    violations = check_hooks.check_secrets(mock_diff_openai)
    assert len(violations) >= 1
    assert any("OpenAI API Key pattern" in v for v in violations)

    # Test Private Key
    mock_diff_key = """
+++ b/cert.pem
+-----BEGIN RSA PRIVATE KEY-----
+MIIEowIBAAKCAQEA0Y
+-----END RSA PRIVATE KEY-----
"""
    violations = check_hooks.check_secrets(mock_diff_key)
    assert len(violations) >= 1
    assert any("Private cryptographic key" in v for v in violations)

    # Test GitHub Token
    mock_diff_gh = """
+++ b/config.py
+token = "ghp_123456789012345678901234567890123456"
"""
    violations = check_hooks.check_secrets(mock_diff_gh)
    assert len(violations) >= 1
    assert any("GitHub Personal Access Token" in v for v in violations)


def test_hook_passes_on_clean_diff():
    """Verify clean code passes with zero violations."""
    mock_staged = [
        "A\tsrc/agentbus/core/bus.py",
        "A\ttests/test_bus.py",
    ]
    mock_diff = """
diff --git a/src/agentbus/core/bus.py b/src/agentbus/core/bus.py
new file mode 100644
--- /dev/null
+++ b/src/agentbus/core/bus.py
@@ -0,0 +1,5 @@
+class Bus:
+    def __init__(self, db_path: str):
+        self.db_path = db_path
"""
    exit_code = check_hooks.run_checks(staged_files=mock_staged, diff_content=mock_diff)
    assert exit_code == 0

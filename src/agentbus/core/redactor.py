"""Secret redaction scanner prior to indexing or event storage (SEC-3)."""

import os
import re

PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "[REDACTED_GITHUB_OAUTH]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"-----BEGIN (?:RSA|OPENSSH|DSA|EC)? PRIVATE KEY-----[\s\S]*?-----END (?:RSA|OPENSSH|DSA|EC)? PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{25,}"), "Bearer [REDACTED_TOKEN]"),
]


class SecretRedactor:
    """Detects and masks secrets in content before indexing."""

    @classmethod
    def redact(cls, text: str) -> str:
        """Scan text and replace matched secrets with masked placeholders."""
        if not text:
            return ""

        result = text
        for pattern, replacement in PATTERNS:
            result = pattern.sub(replacement, result)

        return result

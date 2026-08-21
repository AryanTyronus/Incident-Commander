from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.tools.log_reader import LogReader

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


class TestLogReader:
    """Tests for the LogReader tool."""

    def setup_method(self) -> None:
        self.reader = LogReader()

    def test_read_normal_log(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "normal.log"
        analysis = self.reader.read_file(log_path)

        assert analysis.total_lines == 12
        assert analysis.error_count == 0
        assert analysis.warning_count == 1
        assert analysis.info_count == 11
        assert analysis.malformed_line_count == 0
        assert analysis.first_timestamp is not None
        assert analysis.last_timestamp is not None
        assert len(analysis.stack_traces) == 0
        assert len(analysis.burst_windows) == 0

    def test_read_incident_log(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "incident.log"
        analysis = self.reader.read_file(log_path)

        assert analysis.total_lines > 30
        assert analysis.error_count > 10
        assert analysis.warning_count >= 2
        assert len(analysis.stack_traces) > 0
        assert len(analysis.burst_windows) > 0
        assert len(analysis.exception_counts) > 0

    def test_error_burst_detection(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "incident.log"
        analysis = self.reader.read_file(log_path)

        assert "PaymentError" in analysis.exception_counts
        assert analysis.exception_counts["PaymentError"] > 10

        assert len(analysis.burst_windows) >= 1
        for burst in analysis.burst_windows:
            assert burst.error_count >= 10

    def test_stack_trace_extraction(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "incident.log"
        analysis = self.reader.read_file(log_path)

        assert len(analysis.stack_traces) > 0
        trace = analysis.stack_traces[0]
        assert "payment/service.py" in trace or "payment/gateway.py" in trace

    def test_representative_errors(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "incident.log"
        analysis = self.reader.read_file(log_path)

        assert len(analysis.representative_errors) > 0
        assert len(analysis.representative_errors) <= 5

    def test_read_content(self) -> None:
        content = "2026-08-21T14:00:01Z ERROR app Something broke"
        analysis = self.reader.read_content(content)

        assert analysis.total_lines == 1
        assert analysis.error_count == 1
        assert analysis.file_path == "<inline>"

    def test_empty_log(self) -> None:
        analysis = self.reader.read_content("")
        assert analysis.total_lines == 0
        assert analysis.error_count == 0

    def test_malformed_lines(self) -> None:
        content = "not a log line\n2026-08-21T14:00:01Z ERROR app Real error\n"
        analysis = self.reader.read_content(content)

        assert analysis.total_lines == 2
        assert analysis.error_count == 1
        assert analysis.malformed_line_count == 1

    def test_burst_configurable(self) -> None:
        reader = LogReader(burst_window_seconds=60, burst_error_threshold=1)
        content = (
            "2026-08-21T14:00:01Z ERROR app Error 1\n"
            "2026-08-21T14:00:02Z ERROR app Error 2\n"
        )
        analysis = reader.read_content(content)
        assert len(analysis.burst_windows) > 0

    def test_no_timestamps(self) -> None:
        content = "ERROR something failed\nWARNING something else\n"
        analysis = self.reader.read_content(content)

        assert analysis.total_lines == 2
        assert analysis.error_count == 1
        assert analysis.warning_count == 1
        assert analysis.first_timestamp is None
        assert analysis.last_timestamp is None

    def test_exception_counts(self) -> None:
        content = (
            "ERROR ValueError: bad value\n"
            "ERROR ValueError: bad value again\n"
            "ERROR TypeError: wrong type\n"
        )
        analysis = self.reader.read_content(content)

        assert analysis.exception_counts.get("ValueError", 0) == 2
        assert analysis.exception_counts.get("TypeError", 0) == 1

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.reader.read_file("/nonexistent/log.txt")

    def test_deterministic_results(self) -> None:
        log_path = FIXTURES_DIR / "logs" / "incident.log"
        result1 = self.reader.read_file(log_path)
        result2 = self.reader.read_file(log_path)

        assert result1.total_lines == result2.total_lines
        assert result1.error_count == result2.error_count
        assert result1.warning_count == result2.warning_count
        assert result1.exception_counts == result2.exception_counts
        assert len(result1.burst_windows) == len(result2.burst_windows)

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class LogLine:
    """A single parsed log line."""

    line_number: int
    raw: str
    timestamp: datetime | None = None
    level: str | None = None
    source: str | None = None
    message: str = ""
    is_malformed: bool = False


@dataclass
class BurstWindow:
    """A detected error burst window."""

    start: datetime
    end: datetime
    error_count: int
    window_seconds: float


@dataclass
class LogAnalysis:
    """Structured output from deterministic log analysis."""

    file_path: str
    total_lines: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    debug_count: int = 0
    malformed_line_count: int = 0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    exception_counts: dict[str, int] = field(default_factory=dict)
    burst_windows: list[BurstWindow] = field(default_factory=list)
    representative_errors: list[LogLine] = field(default_factory=list)
    stack_traces: list[str] = field(default_factory=list)
    lines: list[LogLine] = field(default_factory=list)


# Common timestamp patterns
_TIMESTAMP_PATTERNS = [
    # ISO format: 2026-08-21T14:32:10Z or 2026-08-21T14:32:10.123Z
    re.compile(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)"
    ),
    # Syslog-like: Aug 21 14:32:10
    re.compile(
        r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
    ),
    # Common format: 2026-08-21 14:32:10
    re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    ),
]

# Exception pattern
_EXCEPTION_PATTERN = re.compile(
    r"((?:[A-Z]\w*(?:Error|Exception|Fault|Failure))"
    r"(?:\s*:\s*.+)?)"
)

# Stack trace start pattern
_STACK_TRACE_START = re.compile(
    r"^\s*(?:Traceback|at\s+|File\s+\")", re.IGNORECASE
)

# Stack trace frame patterns
_STACK_TRACE_FRAME = re.compile(
    r"^\s+(?:File\s+\".*\",\s+line\s+\d+|at\s+\S+)"
)

_LEVEL_PATTERN = re.compile(
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b",
    re.IGNORECASE,
)


def _parse_timestamp(text: str) -> datetime | None:
    """Attempt to parse a timestamp from text."""
    for pattern in _TIMESTAMP_PATTERNS:
        match = pattern.search(text)
        if match:
            ts_str = match.group(1)
            try:
                # Try ISO format first
                ts_str_clean = ts_str.replace("Z", "+00:00")
                return datetime.fromisoformat(ts_str_clean)
            except ValueError:
                try:
                    # Try syslog-like format
                    return datetime.strptime(ts_str, "%b %d %H:%M:%S").replace(
                        tzinfo=UTC
                    )
                except ValueError:
                    pass
    return None


def _parse_level(text: str) -> str | None:
    """Extract log level from a line."""
    match = _LEVEL_PATTERN.search(text)
    if match:
        level = match.group(1).upper()
        if level == "WARN":
            return "WARNING"
        if level in ("FATAL",):
            return "CRITICAL"
        return level
    return None


def _extract_exception(text: str) -> str | None:
    """Extract exception class name from a line."""
    match = _EXCEPTION_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def _detect_burst_windows(
    error_lines: list[LogLine],
    window_seconds: float = 60.0,
    threshold: int = 10,
) -> list[BurstWindow]:
    """Detect windows where error count exceeds the threshold."""
    if not error_lines:
        return []

    timestamped = [line for line in error_lines if line.timestamp is not None]
    if not timestamped:
        return []

    timestamped.sort(key=lambda line: line.timestamp)  # type: ignore[arg-type]
    bursts: list[BurstWindow] = []
    i = 0

    while i < len(timestamped):
        window_start = timestamped[i].timestamp  # type: ignore[assignment]
        window_end = None
        count = 0

        for j in range(i, len(timestamped)):
            ts = timestamped[j].timestamp
            if ts is None:
                continue
            if window_start is None:
                window_start = ts
                count = 1
                window_end = ts
                continue
            delta = (ts - window_start).total_seconds()
            if delta <= window_seconds:
                count += 1
                window_end = ts
            else:
                break

        if count >= threshold and window_start and window_end:
            bursts.append(
                BurstWindow(
                    start=window_start,
                    end=window_end,
                    error_count=count,
                    window_seconds=(window_end - window_start).total_seconds(),
                )
            )

        # Move past this window
        if window_end:
            for k in range(i, len(timestamped)):
                if timestamped[k].timestamp and timestamped[k].timestamp <= window_end:
                    i = k + 1
                else:
                    break
            else:
                break
        else:
            i += 1

    return bursts


def _extract_stack_traces(lines: list[LogLine]) -> list[str]:
    """Extract stack traces from log lines."""
    traces: list[str] = []
    current_trace: list[str] = []
    in_trace = False

    for line in lines:
        if _STACK_TRACE_START.match(line.raw):
            in_trace = True
            current_trace = [line.raw]
        elif in_trace and _STACK_TRACE_FRAME.match(line.raw):
            current_trace.append(line.raw)
        elif in_trace:
            if current_trace:
                traces.append("\n".join(current_trace))
            current_trace = []
            in_trace = False

    if current_trace:
        traces.append("\n".join(current_trace))

    return traces


class LogReader:
    """Deterministic log file reader and analyzer.

    This tool parses log files and produces structured analysis.
    It does NOT use the LLM for any parsing or counting.
    """

    def __init__(
        self,
        burst_window_seconds: float | None = None,
        burst_error_threshold: int | None = None,
    ) -> None:
        self._burst_window = float(
            os.getenv("LOG_BURST_WINDOW_SECONDS", "60")
            if burst_window_seconds is None
            else burst_window_seconds
        )
        self._burst_threshold = int(
            os.getenv("LOG_BURST_ERROR_THRESHOLD", "10")
            if burst_error_threshold is None
            else burst_error_threshold
        )

    def read_file(self, file_path: str | Path) -> LogAnalysis:
        """Read and analyze a log file deterministically."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {path}")

        lines = self._parse_lines(path)
        return self._analyze(path, lines)

    def read_content(self, content: str, source: str = "<inline>") -> LogAnalysis:
        """Parse log content directly (for testing or inline logs)."""
        raw_lines = content.splitlines()
        lines: list[LogLine] = []

        for i, raw in enumerate(raw_lines, start=1):
            lines.append(self._parse_line(i, raw))

        return self._analyze(Path(source), lines)

    def _parse_lines(self, path: Path) -> list[LogLine]:
        """Parse all lines from a file."""
        lines: list[LogLine] = []
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, raw in enumerate(f, start=1):
                    lines.append(self._parse_line(i, raw.rstrip("\n\r")))
        except Exception:
            pass
        return lines

    def _parse_line(self, line_number: int, raw: str) -> LogLine:
        """Parse a single log line."""
        if not raw.strip():
            return LogLine(line_number=line_number, raw=raw, is_malformed=True)

        timestamp = _parse_timestamp(raw)
        level = _parse_level(raw)

        if level is None and timestamp is None:
            # Could be a continuation line or malformed
            if not raw.strip().startswith(("at ", "File ", "Traceback")):
                return LogLine(
                    line_number=line_number,
                    raw=raw,
                    message=raw,
                    is_malformed=True,
                )

        # Extract source (first word after timestamp and level)
        source = None
        parts = raw.split()
        if len(parts) > 2:
            # Try to find a source-like component
            for part in parts[2:6]:
                if "." in part and not part.startswith("["):
                    source = part.rstrip(":")
                    break

        return LogLine(
            line_number=line_number,
            raw=raw,
            timestamp=timestamp,
            level=level,
            source=source,
            message=raw,
        )

    def _analyze(self, path: Path, lines: list[LogLine]) -> LogAnalysis:
        """Produce structured analysis from parsed lines."""
        timestamps = [line.timestamp for line in lines if line.timestamp is not None]
        error_lines = [line for line in lines if line.level in ("ERROR", "CRITICAL")]
        warning_lines = [line for line in lines if line.level in ("WARNING",)]
        info_lines = [line for line in lines if line.level == "INFO"]
        debug_lines = [line for line in lines if line.level == "DEBUG"]
        malformed = [line for line in lines if line.is_malformed]

        # Exception counting
        exception_counter: Counter[str] = Counter()
        for line in error_lines:
            exc = _extract_exception(line.raw)
            if exc:
                # Extract just the exception class name
                exc_class = exc.split(":")[0].strip().split("(")[0].strip()
                exception_counter[exc_class] += 1

        # Find representative errors (up to 5 unique error types)
        seen_exceptions: set[str] = set()
        representative: list[LogLine] = []
        for line in error_lines:
            exc = _extract_exception(line.raw)
            exc_class = exc.split(":")[0].strip().split("(")[0] if exc else None
            if exc_class and exc_class not in seen_exceptions:
                seen_exceptions.add(exc_class)
                representative.append(line)
                if len(representative) >= 5:
                    break

        # If no exceptions, take first few error lines
        if not representative:
            representative = error_lines[:5]

        # Burst detection
        bursts = _detect_burst_windows(
            error_lines,
            window_seconds=self._burst_window,
            threshold=self._burst_threshold,
        )

        # Stack trace extraction
        stack_traces = _extract_stack_traces(lines)

        return LogAnalysis(
            file_path=str(path),
            total_lines=len(lines),
            error_count=len(error_lines),
            warning_count=len(warning_lines),
            info_count=len(info_lines),
            debug_count=len(debug_lines),
            malformed_line_count=len(malformed),
            first_timestamp=min(timestamps) if timestamps else None,
            last_timestamp=max(timestamps) if timestamps else None,
            exception_counts=dict(exception_counter),
            burst_windows=bursts,
            representative_errors=representative,
            stack_traces=stack_traces,
            lines=lines,
        )

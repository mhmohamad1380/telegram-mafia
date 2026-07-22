"""Test harness: a non-stop, error-collecting reporter for the E2E suite.

The suite must *not* halt on the first failure. Instead every check records its
outcome (pass / fail / warning) into a :class:`Reporter`, and a full report —
grouped by the 25 functional sections — is printed at the end together with the
exact location, cause, exception, and a remediation hint for every failure.

Design goals
------------
* **Never raise out of a check.** ``expect`` / ``expect_raises`` / ``run`` all
  swallow assertion and runtime errors, converting them into recorded failures
  with a captured traceback and the source location of the failing check.
* **Deterministic, section-oriented output** that mirrors the requested report
  layout (``✓ Startup`` … ``✅ Project is production ready.``).
* **Exit code** reflects success so CI / a release gate can consume it.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Outcome of a single check or a whole section."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass(slots=True)
class CheckResult:
    """The recorded outcome of one individual assertion/check."""

    name: str
    status: Status
    detail: str = ""
    location: str = ""
    cause: str = ""
    exception: str = ""
    suggestion: str = ""
    traceback: str = ""


@dataclass(slots=True)
class Section:
    """A functional test section grouping many checks (e.g. "Startup")."""

    key: str
    title: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status is Status.FAIL)

    @property
    def warned(self) -> int:
        return sum(1 for c in self.checks if c.status is Status.WARN)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status is Status.PASS)

    @property
    def status(self) -> Status:
        if self.failed:
            return Status.FAIL
        if self.warned:
            return Status.WARN
        return Status.PASS


def _caller_location(depth: int = 2) -> str:
    """Return a ``file:line (in func)`` string for the calling test code.

    Walks up the stack to the first frame outside this module so the recorded
    location points at the failing check in the test file, not the harness.
    """
    stack = traceback.extract_stack()
    # Drop the frames inside reporter.py itself.
    for frame in reversed(stack[:-1]):
        if not frame.filename.endswith("reporter.py"):
            return f"{frame.filename.split('/')[-1]}:{frame.lineno} (in {frame.name})"
    return "<unknown>"


class Reporter:
    """Collects check results across sections and renders the final report."""

    def __init__(self) -> None:
        self._sections: dict[str, Section] = {}
        self._order: list[str] = []
        self._current: Section | None = None
        self._started_at = time.monotonic()

    # --- Section management -------------------------------------------------

    def section(self, key: str, title: str) -> Section:
        """Start (or resume) a named section and make it current."""
        sec = self._sections.get(key)
        if sec is None:
            sec = Section(key=key, title=title)
            self._sections[key] = sec
            self._order.append(key)
        self._current = sec
        return sec

    def _sec(self) -> Section:
        if self._current is None:  # pragma: no cover - defensive
            return self.section("misc", "Miscellaneous")
        return self._current

    # --- Recording primitives ----------------------------------------------

    def record_pass(self, name: str, detail: str = "") -> None:
        self._sec().checks.append(
            CheckResult(name=name, status=Status.PASS, detail=detail)
        )

    def record_fail(
        self,
        name: str,
        *,
        cause: str = "",
        exception: str = "",
        suggestion: str = "",
        tb: str = "",
        location: str = "",
    ) -> None:
        self._sec().checks.append(
            CheckResult(
                name=name,
                status=Status.FAIL,
                cause=cause,
                exception=exception,
                suggestion=suggestion,
                traceback=tb,
                location=location or _caller_location(),
            )
        )

    def record_warn(self, name: str, detail: str = "", suggestion: str = "") -> None:
        self._sec().checks.append(
            CheckResult(
                name=name,
                status=Status.WARN,
                detail=detail,
                suggestion=suggestion,
                location=_caller_location(),
            )
        )

    # --- High-level check helpers -------------------------------------------

    def expect(
        self,
        condition: bool,
        name: str,
        *,
        cause: str = "",
        suggestion: str = "",
    ) -> bool:
        """Assert ``condition`` is truthy; record pass/fail. Never raises."""
        if condition:
            self.record_pass(name)
            return True
        self.record_fail(
            name,
            cause=cause or "Expected condition was false.",
            suggestion=suggestion,
            location=_caller_location(),
        )
        return False

    def expect_eq(
        self, actual: Any, expected: Any, name: str, *, suggestion: str = ""
    ) -> bool:
        """Assert ``actual == expected``; record a rich diff on failure."""
        if actual == expected:
            self.record_pass(name)
            return True
        self.record_fail(
            name,
            cause=f"Expected {expected!r}, got {actual!r}.",
            suggestion=suggestion,
            location=_caller_location(),
        )
        return False

    async def expect_raises(
        self,
        exc_type: type[BaseException] | tuple[type[BaseException], ...],
        coro: Awaitable[Any],
        name: str,
        *,
        suggestion: str = "",
    ) -> bool:
        """Assert awaiting ``coro`` raises ``exc_type``. Never propagates."""
        try:
            await coro
        except exc_type:
            self.record_pass(name)
            return True
        except Exception as exc:  # noqa: BLE001 - wrong exception type
            self.record_fail(
                name,
                cause=(
                    f"Expected {getattr(exc_type, '__name__', exc_type)!r} "
                    f"but a different exception was raised."
                ),
                exception=f"{type(exc).__name__}: {exc}",
                suggestion=suggestion,
                tb=traceback.format_exc(),
                location=_caller_location(),
            )
            return False
        else:
            self.record_fail(
                name,
                cause="Expected an exception but none was raised.",
                suggestion=suggestion,
                location=_caller_location(),
            )
            return False

    async def run(
        self,
        name: str,
        coro_factory: Callable[[], Awaitable[Any]],
        *,
        suggestion: str = "",
    ) -> Any:
        """Await a coroutine, recording a failure (with traceback) on error.

        Returns the coroutine's result, or ``None`` if it raised. Used to wrap
        an *action* that is expected to succeed (as opposed to ``expect_raises``
        which asserts failure).
        """
        try:
            result = await coro_factory()
        except Exception as exc:  # noqa: BLE001 - we want to catch everything
            self.record_fail(
                name,
                cause="Operation raised unexpectedly.",
                exception=f"{type(exc).__name__}: {exc}",
                suggestion=suggestion,
                tb=traceback.format_exc(),
                location=_caller_location(),
            )
            return None
        else:
            self.record_pass(name)
            return result

    def guard(self, name: str, exc: BaseException, *, suggestion: str = "") -> None:
        """Record a failure for an exception caught by the caller's try/except."""
        self.record_fail(
            name,
            cause="Operation raised unexpectedly.",
            exception=f"{type(exc).__name__}: {exc}",
            suggestion=suggestion,
            tb="".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
            location=_caller_location(),
        )

    # --- Aggregates ---------------------------------------------------------

    @property
    def total(self) -> int:
        return sum(len(s.checks) for s in self._sections.values())

    @property
    def total_passed(self) -> int:
        return sum(s.passed for s in self._sections.values())

    @property
    def total_failed(self) -> int:
        return sum(s.failed for s in self._sections.values())

    @property
    def total_warned(self) -> int:
        return sum(s.warned for s in self._sections.values())

    @property
    def ok(self) -> bool:
        return self.total_failed == 0

    # --- Rendering ----------------------------------------------------------

    def render(self) -> str:
        """Return the full, human-readable report string."""
        width = 50
        line = "=" * width
        dash = "-" * width
        out: list[str] = [
            line,
            "Mafia Bot End-to-End Test Report".center(width),
            line,
            "",
        ]

        # Section summary lines.
        for key in self._order:
            sec = self._sections[key]
            mark = {
                Status.PASS: "✓",
                Status.WARN: "▲",
                Status.FAIL: "✗",
            }[sec.status]
            suffix = ""
            if sec.failed:
                suffix = f"   ({sec.failed} failed / {len(sec.checks)})"
            elif sec.warned:
                suffix = f"   ({sec.warned} warnings / {len(sec.checks)})"
            out.append(f"{mark} {sec.title}{suffix}")
            out.append("")

        out.append(dash)
        out.append("")
        out.append(f"Total Tests : {self.total}")
        out.append(f"Passed      : {self.total_passed}")
        out.append(f"Failed      : {self.total_failed}")
        out.append(f"Warnings    : {self.total_warned}")
        elapsed = time.monotonic() - self._started_at
        out.append(f"Duration    : {elapsed:.2f}s")
        out.append("")
        out.append(line)
        out.append("")

        # Detailed failure/warning breakdown (the "treasure map").
        if self.total_failed or self.total_warned:
            out.append("Details")
            out.append(dash)
            for key in self._order:
                sec = self._sections[key]
                problems = [
                    c for c in sec.checks if c.status in (Status.FAIL, Status.WARN)
                ]
                if not problems:
                    continue
                out.append(f"\n[{sec.title}]")
                for c in problems:
                    tag = "FAIL" if c.status is Status.FAIL else "WARN"
                    out.append(f"  {tag} · {c.name}")
                    if c.location:
                        out.append(f"       ↳ location   : {c.location}")
                    if c.cause:
                        out.append(f"       ↳ cause      : {c.cause}")
                    if c.detail:
                        out.append(f"       ↳ detail     : {c.detail}")
                    if c.exception:
                        out.append(f"       ↳ exception  : {c.exception}")
                    if c.suggestion:
                        out.append(f"       ↳ suggestion : {c.suggestion}")
                    if c.traceback:
                        indented = "\n".join(
                            "         " + ln
                            for ln in c.traceback.rstrip().splitlines()
                        )
                        out.append("       ↳ traceback  :")
                        out.append(indented)
            out.append("")
            out.append(line)
            out.append("")

        if self.ok:
            out.append("✅ Project is production ready.")
        else:
            out.append(
                f"❌ Project is NOT production ready — "
                f"{self.total_failed} check(s) failed."
            )
        out.append(line)
        return "\n".join(out)

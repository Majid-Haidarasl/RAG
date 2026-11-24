"""Release readiness: coverage gate, checklist, Phase 14 defaults re-verified, carry-over controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChoiceCheck:
    kind: str
    expected: str
    configured: str
    measured: str | None
    agrees: bool | None

    @property
    def configured_ok(self) -> bool:
        return self.configured == self.expected

    @property
    def confirmed(self) -> bool:
        return self.configured_ok and self.agrees is True

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "expected": self.expected,
            "configured": self.configured,
            "measured": self.measured,
            "agrees": self.agrees,
            "confirmed": self.confirmed,
        }


def newest_eval_result(
    folder: Path, pattern: str = "phase-14-check-*.json"
) -> Path | None:
    """Newest result by its UTC stamp in the file name (names sort in time order)."""
    files = sorted(Path(folder).glob(pattern)) if Path(folder).is_dir() else []
    return files[-1] if files else None


def load_eval_result(path: Path | None) -> dict[str, Any] | None:
    if path is None or not Path(path).is_file():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def choice_checks(
    payload: Mapping[str, Any] | None,
    expected: Mapping[str, str],
    configured: Mapping[str, str],
) -> list[ChoiceCheck]:
    """One row per expected kind: configured in eval.yaml, measured winner and agreement from the Phase 14 run."""
    by_kind: dict[str, Mapping[str, Any]] = {}
    for c in (payload or {}).get("choices") or []:
        if isinstance(c, Mapping) and c.get("kind"):
            by_kind[str(c["kind"])] = c
    rows: list[ChoiceCheck] = []
    for kind, want in expected.items():
        c = by_kind.get(kind) or {}
        measured = (
            (c.get("measured") or {}) if isinstance(c.get("measured"), Mapping) else {}
        )
        agrees = c.get("agrees")
        rows.append(
            ChoiceCheck(
                kind,
                want,
                configured.get(kind, ""),
                measured.get("winner"),
                agrees if isinstance(agrees, bool) else None,
            )
        )
    return rows


@dataclass(frozen=True)
class Readiness:
    ready: bool
    blockers: tuple[str, ...] = ()
    advisories: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "blockers": list(self.blockers),
            "advisories": list(self.advisories),
        }


def readiness(
    checks: Mapping[str, bool], choices: Sequence[ChoiceCheck], live_status: str
) -> Readiness:
    """Ready for the release tag when every offline check passed. Live disagreement is advisory."""
    blockers = tuple(k for k, ok in checks.items() if not ok)
    advisories: list[str] = []
    if live_status != "ok":
        advisories.append(f"live:{live_status or 'missing'}")
    for c in choices:
        if c.agrees is False:
            advisories.append(f"disagrees:{c.kind}={c.measured}")
        elif c.agrees is None:
            advisories.append(f"not_measured:{c.kind}")
    return Readiness(not blockers, blockers, tuple(advisories))

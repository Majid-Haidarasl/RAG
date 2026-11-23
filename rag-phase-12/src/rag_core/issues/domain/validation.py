"""Issue registry validator: checks raw records and reports every problem at once."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from rag_core.issues.domain.model import IssueCategory, Priority, Severity
from rag_core.issues.domain.ports import OrgDirectory
from rag_core.issues.domain.status import DONE_STATES, IssueStatus, Resolution

ISSUE_RE = re.compile(r"^AR-ISS-\d{3}$")
SUB_RE = re.compile(r"^AR-ISS-\d{3}/[A-Z0-9]+$")
DOC_RE = re.compile(r"^AR-[A-Z]+-\d{3}$")
CONTRACT_RE = re.compile(r"^AR-CNT-\d{4}-\d{3}$")


class IssueCheckLevel(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class IssueValidationIssue:
    severity: IssueCheckLevel
    code: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} {self.subject}: {self.message}"


@dataclass(frozen=True)
class IssueValidationReport:
    issues: tuple[IssueValidationIssue, ...]

    @property
    def errors(self) -> list[IssueValidationIssue]:
        return [i for i in self.issues if i.severity is IssueCheckLevel.ERROR]

    @property
    def warnings(self) -> list[IssueValidationIssue]:
        return [i for i in self.issues if i.severity is IssueCheckLevel.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.errors}


def _status(value: Any) -> IssueStatus | None:
    try:
        return IssueStatus(str(value))
    except ValueError:
        return None


def _date(value: Any) -> date | None | str:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return "bad"


class IssueRegistryValidator:
    def __init__(self, directory: OrgDirectory | None = None, documents: set[str] | None = None) -> None:
        self.directory = directory
        self.documents = documents
        self._out: list[IssueValidationIssue] = []

    def _err(self, code: str, subject: str, message: str) -> None:
        self._out.append(IssueValidationIssue(IssueCheckLevel.ERROR, code, subject, message))

    def _warn(self, code: str, subject: str, message: str) -> None:
        self._out.append(IssueValidationIssue(IssueCheckLevel.WARNING, code, subject, message))

    def validate(self, records: list[dict[str, Any]]) -> IssueValidationReport:
        self._out = []
        ids: set[str] = set()
        for rec in records:
            iid = str(rec.get("id", ""))
            if not ISSUE_RE.match(iid):
                self._err("I-ID", iid or "<blank>", "issue id must look like AR-ISS-024")
                continue
            if iid in ids:
                self._err("I-DUP", iid, "duplicate issue id")
                continue
            ids.add(iid)
        for rec in records:
            iid = str(rec.get("id", ""))
            if ISSUE_RE.match(iid):
                self._issue(rec, ids)
        self._duplicate_chains(records)
        return IssueValidationReport(tuple(self._out))

    # ------------------------------------------------------------ helpers
    def _node(self, subject: str, node: Any, role: str, required: bool = False) -> None:
        if node in (None, ""):
            if required:
                self._err("I-NODE", subject, f"{role} node is required")
            return
        if self.directory is not None and not self.directory.exists(str(node)):
            self._err("I-NODE", subject, f"{role} node {node} is not in the hierarchy registry")

    def _docs(self, subject: str, docs: list[Any]) -> None:
        seen: set[str] = set()
        for d in docs:
            d = str(d)
            if not DOC_RE.match(d):
                self._err("I-DOC", subject, f"bad document id {d!r}")
            elif self.documents is not None and d not in self.documents:
                self._err("I-DOC", subject, f"document {d} is not in the corpus catalog")
            if d in seen:
                self._warn("I-DOC-DUP", subject, f"document {d} listed twice")
            seen.add(d)

    def _issue(self, rec: dict[str, Any], ids: set[str]) -> None:
        iid = rec["id"]
        if not str(rec.get("title_en") or rec.get("title") or "").strip():
            self._err("I-TITLE", iid, "title is required")
        self._node(iid, rec.get("owner_node"), "owner", required=True)
        self._node(iid, rec.get("reporter_node"), "reporter")
        for n in rec.get("affected_nodes", []):
            self._node(iid, n, "affected")
        self._docs(iid, rec.get("related_documents", []))
        contract = rec.get("contract_ref")
        if contract and not CONTRACT_RE.match(str(contract)):
            self._err("I-CONTRACT", iid, f"contract reference {contract!r} must look like AR-CNT-1402-118")
        for key, enum in (("category", IssueCategory), ("severity", Severity), ("priority", Priority)):
            if rec.get(key) is not None and rec.get(key) not in {e.value for e in enum}:
                self._err("I-ENUM", iid, f"unknown {key} {rec.get(key)!r}")
        status = _status(rec.get("status", "open"))
        if status is None:
            self._err("I-STATUS", iid, f"unknown status {rec.get('status')!r}")
        opened, due = _date(rec.get("opened_on")), _date(rec.get("due_on"))
        if "bad" in (opened, due):
            self._err("I-DATE", iid, "dates must be ISO yyyy-mm-dd")
        elif isinstance(opened, date) and isinstance(due, date) and due < opened:
            self._err("I-DATE", iid, "due date before opening date")
        resolution = rec.get("resolution")
        if resolution is not None and resolution not in {r.value for r in Resolution}:
            self._err("I-RESOLUTION", iid, f"unknown resolution {resolution!r}")
        if status is IssueStatus.CLOSED and resolution is None:
            self._err("I-RESOLUTION", iid, "closed issue needs a resolution")
        if status is not None and status is not IssueStatus.CLOSED and resolution is not None:
            self._err("I-RESOLUTION", iid, "only closed issues carry a resolution")
        dup = rec.get("duplicate_of")
        if resolution == "duplicate" and not dup:
            self._err("I-DUPLICATE-OF", iid, "duplicate resolution needs duplicate_of")
        if dup and dup not in ids:
            self._err("I-DUPLICATE-OF", iid, f"duplicate_of {dup} does not exist")
        if dup == iid:
            self._err("I-CYCLE", iid, "issue is a duplicate of itself")
        for rel in rec.get("related_issues", []):
            if rel not in ids:
                self._err("I-RELATED", iid, f"related issue {rel} does not exist")
            if rel == iid:
                self._err("I-CYCLE", iid, "issue relates to itself")
        progress = rec.get("progress_percent")
        if progress is not None and not (isinstance(progress, int | float) and 0 <= progress <= 100):
            self._err("I-PROGRESS", iid, "progress_percent must be 0–100")
        self._subissues(rec, status)

    def _subissues(self, rec: dict[str, Any], parent_status: IssueStatus | None) -> None:
        iid = rec["id"]
        subs = rec.get("sub_issues", [])
        codes: dict[str, dict[str, Any]] = {}
        positions: set[int] = set()
        for sub in subs:
            sid = str(sub.get("id", ""))
            if not SUB_RE.match(sid):
                self._err("S-ID", sid or "<blank>", "sub-issue id must look like AR-ISS-024/HW")
                continue
            if sid.split("/")[0] != iid:
                self._err("S-PARENT", sid, f"parent link does not match {iid}")
                continue
            code = sid.split("/")[1]
            if code in codes:
                self._err("S-DUP", sid, "duplicate sub-issue id")
                continue
            codes[code] = sub
            pos = sub.get("position")
            if not isinstance(pos, int) or pos < 1:
                self._err("S-POSITION", sid, "position must be an integer >= 1")
            elif pos in positions:
                self._err("S-POSITION", sid, f"duplicate position {pos}")
            else:
                positions.add(pos)
            if not str(sub.get("title_en") or sub.get("title") or "").strip():
                self._err("S-TITLE", sid, "title is required")
            self._node(sid, sub.get("owner_node"), "owner", required=True)
            for n in sub.get("supporting_nodes", []):
                self._node(sid, n, "supporting")
            self._docs(sid, sub.get("related_documents", []))
            st = _status(sub.get("status", "open"))
            if st is None:
                self._err("S-STATUS", sid, f"unknown status {sub.get('status')!r}")
            elif st is IssueStatus.BLOCKED and not str(sub.get("blocked_reason", "")).strip():
                self._warn("S-BLOCKED", sid, "blocked sub-issue without blocked_reason")
            if parent_status in DONE_STATES and st is not None and not st.is_done and rec.get("resolution") in (None, "fixed"):
                self._err("S-OPEN-UNDER-DONE", sid, f"open sub-issue under {parent_status} parent")
        for code, sub in codes.items():
            for dep in sub.get("depends_on", []):
                if dep not in codes:
                    self._err("S-DEPENDS", sub["id"], f"depends on unknown sibling {dep}")
                elif dep == code:
                    self._err("S-CYCLE", sub["id"], "depends on itself")
                else:
                    st, dst = _status(sub.get("status")), _status(codes[dep].get("status"))
                    if st in DONE_STATES and dst is not None and not dst.is_done:
                        self._err("S-DEPENDS", sub["id"], f"done while dependency {dep} is open")
        cycle = _find_cycle({c: [d for d in s.get("depends_on", []) if d in codes] for c, s in codes.items()})
        if cycle:
            self._err("S-CYCLE", iid, f"sub-issue dependency cycle {' -> '.join(cycle)}")

    def _duplicate_chains(self, records: list[dict[str, Any]]) -> None:
        graph = {str(r.get("id")): [str(r["duplicate_of"])] for r in records if r.get("duplicate_of")}
        cycle = _find_cycle(graph)
        if cycle:
            self._err("I-CYCLE", cycle[0], f"duplicate_of cycle {' -> '.join(cycle)}")


def _find_cycle(graph: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(n: str) -> list[str]:
        state[n] = 1
        stack.append(n)
        for m in graph.get(n, []):
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if m not in state:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        state[n] = 2
        return []

    for n in sorted(graph):
        if n not in state:
            found = visit(n)
            if found:
                return found
    return []

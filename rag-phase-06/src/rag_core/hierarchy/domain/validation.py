"""Registry validator: checks raw layer / node / document-map rows.

It works on plain rows (``dict[str, str]``) so that every problem in a CSV is
reported at once instead of failing on the first invariant. Rules R1–R5 come
from the Phase 1 registry README; R6+ are Phase 6 additions.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from rag_core.hierarchy.domain.model import (
    _TYPE_LAYERS,
    DETAIL_LEVELS,
    FORBIDDEN_CAPABILITY_NAMES,
    NodeStatus,
    NodeType,
)
from rag_core.hierarchy.domain.transfer import MIN_APPROVALS, MIN_ARTEFACTS, TransferDirection
from rag_core.shared_kernel.confidentiality import Confidentiality

NODE_RE = re.compile(r"^N-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
DOC_RE = re.compile(r"^AR-[A-Z]+-\d{3}$")
ROLES = {"owner", "co_owner", "described_in"}
# Q3: only the knowledge repository may skip layers, and only L4 → L1.
LAYER_SKIP_EXEMPTIONS = {("knowledge_repository", 4, 1)}


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    code: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} {self.subject}: {self.message}"


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}


def _split(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(";") if p.strip()]


def normalize_confidentiality(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


class RegistryValidator:
    def __init__(self, catalog: dict[str, tuple[str, str]] | None = None) -> None:
        """``catalog`` maps document id → (owning node id, confidentiality)."""
        self.catalog = catalog or {}
        self._issues: list[ValidationIssue] = []

    # ----------------------------------------------------------- public
    def validate(
        self,
        layers: list[dict[str, str]],
        nodes: list[dict[str, str]],
        doc_map: list[dict[str, str]] | None = None,
    ) -> ValidationReport:
        self._issues = []
        layer_by_index = self._check_layers(layers)
        node_by_id = self._check_nodes(nodes, layer_by_index)
        if doc_map is not None:
            self._check_doc_map(doc_map, node_by_id)
        return ValidationReport(tuple(self._issues))

    # ----------------------------------------------------------- helpers
    def _err(self, code: str, subject: str, message: str) -> None:
        self._issues.append(ValidationIssue(Severity.ERROR, code, subject, message))

    def _warn(self, code: str, subject: str, message: str) -> None:
        self._issues.append(ValidationIssue(Severity.WARNING, code, subject, message))

    # ----------------------------------------------------------- layers
    def _check_layers(self, rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
        by_index: dict[int, dict[str, str]] = {}
        for row in rows:
            raw = (row.get("layer_index") or "").strip()
            subject = row.get("layer_code") or f"layer[{raw}]"
            if not raw.isdigit():
                self._err("L-INDEX", subject, f"layer_index {raw!r} is not an integer")
                continue
            index = int(raw)
            if index in by_index:
                self._err("L-DUP", subject, f"duplicate layer index {index}")
                continue
            by_index[index] = row
            if row.get("layer_code", "").strip() != f"L{index}":
                self._err("L-CODE", subject, f"layer_code must be L{index}")
            if not row.get("layer_name_en", "").strip() or not row.get("layer_name_fa", "").strip():
                self._err("L-NAME", subject, "layer needs English and Persian names")
            level = row.get("default_detail_level_received", "").strip()
            if level and level not in DETAIL_LEVELS:
                self._err("L-DETAIL", subject, f"unknown detail level {level!r}")
            score = row.get("min_judge_score", "").strip()
            if score and (not score.isdigit() or not 0 <= int(score) <= 20):
                self._err("L-SCORE", subject, "min_judge_score must be 0–20 or blank")
            words = row.get("max_package_words", "").strip()
            if words and not words.isdigit():
                self._err("L-WORDS", subject, "max_package_words must be an integer or blank")
            conf = normalize_confidentiality(row.get("default_confidentiality", ""))
            if conf and conf not in {c.value for c in Confidentiality}:
                self._err("L-CONF", subject, f"unknown confidentiality {conf!r}")
        if by_index and sorted(by_index) != list(range(len(by_index))):
            self._err("L-GAP", "layers", f"layer indices must be contiguous from 0, got {sorted(by_index)}")
        for index, row in by_index.items():
            self._check_transfer(index, row, by_index)
        return by_index

    def _check_transfer(self, index: int, row: dict[str, str], layers: dict[int, dict[str, str]]) -> None:
        subject = f"L{index}"
        direction = row.get("transfer_direction", "").strip()
        if not direction:
            self._err("T-MISSING", subject, "no knowledge-transfer requirement")
            return
        if direction not in {d.value for d in TransferDirection}:
            self._err("T-DIR", subject, f"unknown transfer_direction {direction!r}")
            return
        target = row.get("transfer_target", "").strip()
        if not re.fullmatch(r"L\d", target) or int(target[1:]) not in layers:
            self._err("T-TARGET", subject, f"transfer_target {target!r} is not a registered layer")
        else:
            t = int(target[1:])
            if direction == "up" and t != index - 1:
                self._err("T-TARGET", subject, f"upward transfer must target L{index - 1}")
            if direction == "down" and t != index + 1:
                self._err("T-TARGET", subject, f"downward transfer must target L{index + 1}")
        if not row.get("must_hand_over", "").strip():
            self._err("T-WHAT", subject, "must_hand_over is empty")
        if len(_split(row.get("min_artefacts", ""))) < MIN_ARTEFACTS:
            self._err("T-ARTEFACTS", subject, f"at least {MIN_ARTEFACTS} minimum artefacts required")
        if len(_split(row.get("approvals_required", ""))) < MIN_APPROVALS:
            self._err("T-APPROVALS", subject, "at least one approval required")
        if not row.get("required_feedback", "").strip():
            self._err("T-FEEDBACK", subject, "required_feedback is empty")
        sources = _split(row.get("transfer_sources", ""))
        if not sources:
            self._err("T-SOURCES", subject, "transfer requirement has no source documents")
        for doc in sources:
            if self.catalog and doc not in self.catalog:
                self._err("T-SOURCES", subject, f"unknown source document {doc}")

    # ----------------------------------------------------------- nodes
    def _check_nodes(
        self, rows: list[dict[str, str]], layers: dict[int, dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        by_id: dict[str, dict[str, str]] = {}
        for row in rows:
            nid = row.get("node_id", "").strip()
            if not NODE_RE.match(nid):
                self._err("N-ID", nid or "<blank>", "node_id must look like N-XXX[-YYY]")
                continue
            if nid in by_id:
                self._err("N-DUP", nid, "duplicate node_id (R1)")
                continue
            by_id[nid] = row

        roots = [n for n, r in by_id.items() if not r.get("parent_node_id", "").strip()]
        if len(roots) != 1:
            self._err("N-ROOT", "nodes", f"exactly one root required (R1), got {roots}")
        children: dict[str, list[str]] = {n: [] for n in by_id}
        for nid, row in by_id.items():
            parent = row.get("parent_node_id", "").strip()
            if parent:
                if parent not in by_id:
                    self._err("N-PARENT", nid, f"parent {parent} does not exist (R2)")
                elif parent == nid:
                    self._err("N-CYCLE", nid, "node is its own parent (R2)")
                else:
                    children[parent].append(nid)

        for nid in by_id:  # cycle check (R2)
            seen = {nid}
            cursor = by_id[nid].get("parent_node_id", "").strip()
            while cursor and cursor in by_id:
                if cursor in seen:
                    self._err("N-CYCLE", nid, "parent chain contains a cycle (R2)")
                    break
                seen.add(cursor)
                cursor = by_id[cursor].get("parent_node_id", "").strip()

        for nid, row in by_id.items():
            self._check_node(nid, row, by_id, children, layers)
        return by_id

    def _check_node(
        self,
        nid: str,
        row: dict[str, str],
        by_id: dict[str, dict[str, str]],
        children: dict[str, list[str]],
        layers: dict[int, dict[str, str]],
    ) -> None:
        if not row.get("node_name_en", "").strip() or not row.get("node_name_fa", "").strip():
            self._err("N-NAME", nid, "node needs English and Persian names")
        for name in (row.get("node_name_en", ""), row.get("node_name_fa", "")):
            if name.strip().lower() in FORBIDDEN_CAPABILITY_NAMES:
                self._err("N-TECHNAME", nid, f"technology {name!r} used as a node name (R5)")
        ntype = row.get("node_type", "").strip()
        raw_layer = row.get("layer_index", "").strip()
        layer = int(raw_layer) if raw_layer.isdigit() else None
        if ntype not in {t.value for t in NodeType}:
            self._err("N-TYPE", nid, f"unknown node_type {ntype!r}")
        if layer is None or layer not in layers:
            self._err("N-LAYER", nid, f"layer {raw_layer!r} is not registered")
        elif ntype in {t.value for t in NodeType} and layer not in _TYPE_LAYERS[NodeType(ntype)]:
            self._err("N-TYPE-LAYER", nid, f"{ntype} cannot sit on L{layer}")
        status = row.get("status", "active").strip() or "active"
        if status not in {s.value for s in NodeStatus}:
            self._err("N-STATUS", nid, f"unknown status {status!r}")
        conf = normalize_confidentiality(row.get("confidentiality", ""))
        if conf and conf not in {c.value for c in Confidentiality}:
            self._err("N-CONF", nid, f"unknown confidentiality {conf!r}")
        if not row.get("cost_center", "").strip():
            self._warn("N-COSTCENTER", nid, "no cost center")

        parent_id = row.get("parent_node_id", "").strip()
        parent = by_id.get(parent_id)
        if parent is not None and layer is not None:
            p_raw = parent.get("layer_index", "").strip()
            if p_raw.isdigit():
                p_layer = int(p_raw)
                if parent.get("is_leaf", "").strip().lower() == "true":
                    self._err("N-LEAF", nid, f"parent {parent_id} is marked as leaf (R4)")
                adjacent = layer == p_layer + 1
                exempt = (ntype, layer, p_layer) in LAYER_SKIP_EXEMPTIONS
                if not adjacent and not exempt:
                    self._err("N-ADJ", nid, f"L{layer} under L{p_layer} breaks layer adjacency (R3)")
                expected = layers.get(p_layer, {}).get("default_detail_level_received", "").strip()
                given = row.get("transfer_detail_level_to_parent", "").strip()
                if given and given not in DETAIL_LEVELS:
                    self._err("N-DETAIL", nid, f"unknown detail level {given!r}")
                elif given and expected and given != expected and not exempt:
                    self._err("N-DETAIL", nid, f"sends {given} but L{p_layer} expects {expected}")
            if status == "active" and parent.get("status", "active").strip() == "retired":
                self._err("N-RETIRED-PARENT", nid, f"active node under retired parent {parent_id}")

        is_leaf = row.get("is_leaf", "").strip().lower()
        if is_leaf not in {"true", "false", ""}:
            self._err("N-LEAF", nid, f"is_leaf must be true/false, got {is_leaf!r}")
        kids = children.get(nid, [])
        if is_leaf == "true" and kids:
            self._err("N-LEAF", nid, f"leaf has children {kids} (R4)")
        if is_leaf != "true" and not kids and status == "active":
            self._warn("N-LEAF-FLAG", nid, "has no children but is not marked as leaf")

        esc = row.get("escalation_node_id", "").strip()
        if esc:
            if esc not in by_id:
                self._err("N-ESCALATION", nid, f"escalation node {esc} does not exist")
            else:
                chain: list[str] = []
                cursor = parent_id
                while cursor and cursor in by_id and cursor not in chain:
                    chain.append(cursor)
                    cursor = by_id[cursor].get("parent_node_id", "").strip()
                if esc not in chain:
                    self._err("N-ESCALATION", nid, f"escalation node {esc} must be an ancestor")
        for doc in _split(row.get("source_docs", "")):
            if not DOC_RE.match(doc):
                self._err("N-SOURCE", nid, f"bad document id {doc!r}")
            elif self.catalog and doc not in self.catalog:
                self._err("N-SOURCE", nid, f"source document {doc} is not in the catalog")

    # ----------------------------------------------------------- document map
    def _check_doc_map(self, rows: list[dict[str, str]], nodes: dict[str, dict[str, str]]) -> None:
        owners: Counter[str] = Counter()
        seen: set[tuple[str, str]] = set()
        for row in rows:
            doc = row.get("document_id", "").strip()
            nid = row.get("node_id", "").strip()
            role = row.get("role", "").strip()
            subject = f"{doc}→{nid}"
            if not DOC_RE.match(doc):
                self._err("M-DOC", subject, "bad document id")
                continue
            if self.catalog and doc not in self.catalog:
                self._err("M-DOC", subject, "document is not in the catalog")
            if nid not in nodes:
                self._err("M-NODE", subject, "node does not exist")
            if role not in ROLES:
                self._err("M-ROLE", subject, f"role must be one of {sorted(ROLES)}")
            if (doc, nid) in seen:
                self._err("M-DUP", subject, "duplicate document–node link")
            seen.add((doc, nid))
            if role == "owner":
                owners[doc] += 1
                expected = self.catalog.get(doc, (None, None))[0]
                if expected and expected != nid:
                    self._err("M-OWNER", subject, f"catalog owner is {expected}")
            if nid in nodes and nodes[nid].get("status", "active").strip() == "retired" and role != "described_in":
                self._err("M-RETIRED", subject, "retired node still owns knowledge")
        for doc, count in owners.items():
            if count > 1:
                self._err("M-OWNERS", doc, f"{count} owners; exactly one required")
        mapped = {r.get("document_id", "").strip() for r in rows}
        for doc in self.catalog:
            if doc not in mapped:
                self._warn("M-UNMAPPED", doc, "corpus document has no owner node")
            elif owners[doc] == 0:
                self._err("M-OWNERS", doc, "no owner link")

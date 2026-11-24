"""Blueprint validation: everything a blueprint names must exist, the weights must add up.

Problems are reported as ``code:ref`` (the Phase 12 ``Problem`` value object).
Checks, in order: duplicate ids; unknown owner node, issues, item and reference
document; criterion weights must sum to 1; mandatory sections present; per
requirement unknown or missing evidence; per criterion unknown or missing
evidence; per link unknown node, unknown executor, executor on another node,
unknown requirement and missing evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rag_core.projects.domain.validation import Problem
from rag_core.rfp.domain.blueprint import WEIGHT_TOTAL, Blueprint


class BlueprintValidator:
    def __init__(
        self,
        nodes: Iterable[str],
        documents: Iterable[str],
        issues: Iterable[str],
        executors: Mapping[str, str] | None = None,
    ) -> None:
        self.nodes = set(nodes)
        self.documents = set(documents)
        self.issues = set(issues)  # issue ids and sub-issue ids
        self.executors = dict(executors or {})  # executor id -> home node

    def _docs(self, ref: str, docs: tuple[str, ...]) -> list[Problem]:
        out = [
            Problem("unknown_document", ref, d) for d in docs if d not in self.documents
        ]
        if not docs:
            out.append(Problem("missing_evidence", ref, "no evidence document"))
        return out

    def validate_one(self, bp: Blueprint) -> list[Problem]:
        out: list[Problem] = []
        ref = bp.blueprint_id
        for kind, ids in (
            ("requirement", [r.requirement_id for r in bp.requirements]),
            ("criterion", [c.criterion_id for c in bp.criteria]),
            ("link", [link.link_id for link in bp.links]),
        ):
            seen: set[str] = set()
            for i in ids:
                if i in seen:
                    out.append(
                        Problem(f"duplicate_{kind}", f"{ref}/{i}", "duplicate id")
                    )
                seen.add(i)
        if bp.owner_node not in self.nodes:
            out.append(Problem("unknown_node", ref, bp.owner_node))
        out.extend(
            Problem("unknown_issue", ref, i) for i in bp.issues if i not in self.issues
        )
        if bp.item and bp.item not in self.issues:
            out.append(Problem("unknown_item", ref, bp.item))
        if bp.reference_document and bp.reference_document not in self.documents:
            out.append(Problem("unknown_document", ref, bp.reference_document))
        if bp.weight_total != WEIGHT_TOTAL:
            out.append(
                Problem(
                    "weights_not_one",
                    ref,
                    f"criterion weights sum to {bp.weight_total}",
                )
            )
        out.extend(Problem("missing_section", ref, s) for s in bp.missing_mandatory())
        for r in bp.requirements:
            out.extend(self._docs(f"{ref}/{r.requirement_id}", r.evidence))
            if not r.statement_en.strip() or not r.statement_fa.strip():
                out.append(
                    Problem(
                        "missing_statement",
                        f"{ref}/{r.requirement_id}",
                        "both languages are required",
                    )
                )
        for c in bp.criteria:
            out.extend(self._docs(f"{ref}/{c.criterion_id}", c.evidence))
        req_ids = {r.requirement_id for r in bp.requirements}
        for link in bp.links:
            lref = f"{ref}/{link.link_id}"
            if link.node not in self.nodes:
                out.append(Problem("unknown_node", lref, link.node))
            if link.executor:
                home = self.executors.get(link.executor)
                if home is None:
                    out.append(Problem("unknown_executor", lref, link.executor))
                elif home != link.node:
                    out.append(
                        Problem(
                            "executor_node_mismatch",
                            lref,
                            f"{link.executor} is on {home}",
                        )
                    )
            out.extend(
                Problem("unknown_requirement", lref, q)
                for q in link.requirements
                if q not in req_ids
            )
            out.extend(self._docs(lref, link.evidence))
        return out

    def validate(self, blueprints: Iterable[Blueprint]) -> list[Problem]:
        out: list[Problem] = []
        seen: set[str] = set()
        rfp_ids: set[str] = set()
        for bp in blueprints:
            if bp.blueprint_id in seen:
                out.append(
                    Problem("duplicate_blueprint", bp.blueprint_id, "duplicate id")
                )
            if bp.rfp_id in rfp_ids:
                out.append(
                    Problem("duplicate_rfp", bp.rfp_id, "two blueprints for one RFP")
                )
            seen.add(bp.blueprint_id)
            rfp_ids.add(bp.rfp_id)
            out.extend(self.validate_one(bp))
        return out

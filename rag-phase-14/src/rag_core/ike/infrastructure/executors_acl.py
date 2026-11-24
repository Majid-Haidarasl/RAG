"""Anti-corruption layer: executors ``ReferralPlan`` → IKE ``ReferralView``.

The only module of the IKE context that imports ``executors``.
"""

from __future__ import annotations

from rag_core.executors.domain.matching import ReferralPlan
from rag_core.executors.domain.model import Executor
from rag_core.ike.domain.views import ReferralView


def referral_views(
    plan: ReferralPlan, executors: dict[str, Executor]
) -> list[ReferralView]:
    lead = plan.lead
    out: list[ReferralView] = []
    for m in plan.recommended:
        e = executors[m.executor_id]
        role = (
            "lead"
            if lead is not None and m.executor_id == lead.executor_id
            else "collaborator"
        )
        out.append(
            ReferralView(
                plan.request.item_id,
                m.executor_id,
                m.display_name,
                role,
                m.score,
                tuple(str(d) for d in e.knowledge_documents),
                e.name_fa,
            )
        )
    return out


def referrals_by_item(
    plans: list[ReferralPlan], executors: list[Executor]
) -> dict[str, list[ReferralView]]:
    index = {str(e.identifier): e for e in executors}
    return {p.request.item_id: referral_views(p, index) for p in plans}


def executor_names(executors: list[Executor]) -> dict[str, tuple[str, str]]:
    return {str(e.identifier): (e.display_name, e.name_fa) for e in executors}

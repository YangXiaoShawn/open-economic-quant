"""Scientific claim-boundary enforcement across Open Economic & Quant projects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceGrade(str, Enum):
    SYNTHETIC_SMOKE = "SYNTHETIC_SMOKE"
    ASSOCIATIONAL_ONLY = "ASSOCIATIONAL_ONLY"
    BACKTEST_ASSOCIATION = "BACKTEST_ASSOCIATION"
    OOS_PREDICTIVE_COMPARISON = "OOS_PREDICTIVE_COMPARISON"
    CAUSAL_IDENTIFIED = "CAUSAL_IDENTIFIED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ClaimBoundary:
    project_slug: str
    grade: EvidenceGrade
    allows_causal_language: bool = False
    allows_live_profitability_claim: bool = False
    passed_pretrend_or_placebo: bool = False
    passed_recovery_gate: bool = False


def validate_claim_boundary(boundary: ClaimBoundary) -> list[str]:
    violations: list[str] = []
    if boundary.allows_live_profitability_claim:
        violations.append(f"{boundary.project_slug}: live profitability claims are prohibited across research repositories")
    if boundary.allows_causal_language and boundary.grade != EvidenceGrade.CAUSAL_IDENTIFIED:
        violations.append(f"{boundary.project_slug}: causal language requires CAUSAL_IDENTIFIED grade")
    if boundary.grade == EvidenceGrade.CAUSAL_IDENTIFIED and not boundary.passed_pretrend_or_placebo:
        violations.append(f"{boundary.project_slug}: CAUSAL_IDENTIFIED requires pre-trend and placebo gates to pass")
    return violations

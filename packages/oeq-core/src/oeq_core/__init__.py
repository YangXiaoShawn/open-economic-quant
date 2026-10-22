"""Shared provenance, claim-boundary, and factor evaluation primitives for Open Economic & Quant."""

from oeq_core.claim_guard import ClaimBoundary, EvidenceGrade, validate_claim_boundary
from oeq_core.factors import (
    cross_sectional_rank_ic,
    newey_west_tstat,
    residualize_quadratic,
    turnover_penalized_net_return,
)
from oeq_core.provenance import build_run_manifest, compute_sha256, verify_manifest_checksums

__all__ = [
    "ClaimBoundary",
    "EvidenceGrade",
    "build_run_manifest",
    "compute_sha256",
    "cross_sectional_rank_ic",
    "newey_west_tstat",
    "residualize_quadratic",
    "turnover_penalized_net_return",
    "validate_claim_boundary",
    "verify_manifest_checksums",
]
__version__ = "0.1.0"

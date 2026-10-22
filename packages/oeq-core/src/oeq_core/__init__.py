"""Shared provenance, claim-boundary, and factor evaluation primitives for Open Economic & Quant."""

from oeq_core.claim_guard import ClaimBoundary, EvidenceGrade, auto_demote_claim, validate_claim_boundary
from oeq_core.factors import (
    benjamini_hochberg_fdr,
    cross_sectional_rank_ic,
    empirical_bayes_shrinkage_weight,
    expanding_ic_ir_weights,
    inverse_volatility_weights,
    newey_west_tstat,
    quantile_long_short_spread,
    residualize_quadratic,
    turnover_penalized_net_return,
    volatility_target_weights,
)
from oeq_core.provenance import build_run_manifest, compute_sha256, verify_manifest_checksums

__all__ = [
    "ClaimBoundary",
    "EvidenceGrade",
    "auto_demote_claim",
    "benjamini_hochberg_fdr",
    "build_run_manifest",
    "compute_sha256",
    "cross_sectional_rank_ic",
    "empirical_bayes_shrinkage_weight",
    "expanding_ic_ir_weights",
    "inverse_volatility_weights",
    "newey_west_tstat",
    "quantile_long_short_spread",
    "residualize_quadratic",
    "turnover_penalized_net_return",
    "validate_claim_boundary",
    "verify_manifest_checksums",
    "volatility_target_weights",
]
__version__ = "0.2.1"

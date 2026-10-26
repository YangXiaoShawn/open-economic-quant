PY ?= python3

PROJECTS := CasualLab Macroeconomics RealEstate TariffIncidence Microstructure EMFactorTiming PolymarketFactors CryptoFactors

.PHONY: test-core test-factors test-contracts reproduce-samples verify-all update-manifest sync-local

test-core:
	$(PY) packages/oeq-core/tests/test_oeq_core.py

test-factors:
	$(PY) CasualLab/tests/test_real_nyc_sample_diagnostics.py
	$(PY) Macroeconomics/tests/test_vintage_manifest_and_claim_guard.py
	$(PY) RealEstate/tests/test_lockin_profile_and_claim_guard.py
	$(PY) TariffIncidence/tests/test_real_section301_results.py
	$(PY) Microstructure/tests/test_maker_fee_sensitivity.py
	$(PY) EMFactorTiming/tests/test_published_jkp_results.py
	$(PY) PolymarketFactors/tests/test_published_artifacts.py
	$(PY) CryptoFactors/tests/test_published_results.py
	$(PY) CryptoFactors/tests/test_factor_fixtures.py
	$(PY) CryptoFactors/tests/test_postpub_windows.py

test-contracts:
	$(PY) tests/test_monorepo_contracts.py
	$(PY) tests/test_verify_monorepo.py
	$(PY) tests/test_sync_ecosystem.py

reproduce-samples:
	PYTHONPATH=PolymarketFactors/src:packages/oeq-core/src $(PY) -m polymarket_factors.cli reproduce-sample
	PYTHONPATH=CryptoFactors/src:packages/oeq-core/src $(PY) -m crypto_factors.cli reproduce-sample

verify-all: test-core test-factors test-contracts reproduce-samples
	$(PY) scripts/verify_monorepo.py

# verify-all checks each project's required files against the SHA-256 checksums in
# scripts/monorepo_manifest.json. After intentionally editing any of them (project.yaml,
# pyproject.toml, Makefile, README.md, STATUS.md, AGENTS.md), regenerate and commit it:
update-manifest:
	$(PY) scripts/verify_monorepo.py --update-manifest

sync-local:
	$(PY) scripts/sync_ecosystem.py --sync-local

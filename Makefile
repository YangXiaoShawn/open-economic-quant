PY ?= python3

PROJECTS := CasualLab Macroeconomics RealEstate TariffIncidence Microstructure EMFactorTiming PolymarketFactors CryptoFactors

.PHONY: test-core test-factors verify-all

test-core:
	$(PY) packages/oeq-core/tests/test_oeq_core.py

test-factors:
	$(PY) EMFactorTiming/tests/test_published_jkp_results.py
	$(PY) PolymarketFactors/tests/test_published_artifacts.py
	$(PY) CryptoFactors/tests/test_published_results.py

verify-all: test-core test-factors
	@for dir in $(PROJECTS); do \
		test -f "$$dir/project.yaml" || { echo "Missing $$dir/project.yaml"; exit 1; }; \
		test -f "$$dir/pyproject.toml" || { echo "Missing $$dir/pyproject.toml"; exit 1; }; \
		test -f "$$dir/Makefile" || { echo "Missing $$dir/Makefile"; exit 1; }; \
		test -f "$$dir/STATUS.md" || { echo "Missing $$dir/STATUS.md"; exit 1; }; \
		test -f "$$dir/AGENTS.md" || { echo "Missing $$dir/AGENTS.md"; exit 1; }; \
	done
	@echo "monorepo-verify-ok projects=8"

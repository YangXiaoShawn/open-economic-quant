PY ?= python3
DATA ?= data/raw/
export PYTHONPATH := src

.PHONY: setup test validate demo reproduce-sample run coverage robustness extensions tables paper check

setup:
	$(PY) -m pip install -e ".[dev]"

reproduce-sample: demo

check: test

test:
	$(PY) -m pytest -q

validate:
	$(PY) scripts/size_power.py --reps 40

demo:
	$(PY) -m emft run --synthetic --out reports/synthetic_demo

coverage:
	$(PY) -m emft coverage --data $(DATA)

run:
	$(PY) -m emft run --data $(DATA) --models ols,enet,gbrt,nn,hist_mean,shrink_mean,fmom --out reports/jkp_em

robustness:
	$(PY) -m emft run --data $(DATA) --kappa 60 --out reports/jkp_em_kappa60
	$(PY) -m emft run --data $(DATA) --kappa 240 --out reports/jkp_em_kappa240
	$(PY) -m emft run --data data/raw_ew/ --weighting ew --out reports/jkp_em_ew
	$(PY) -m emft run --data data/raw_vw/ --weighting vw --out reports/jkp_em_vw
	$(PY) -m emft run --data $(DATA) --market-history --out reports/jkp_em_tv
	$(PY) scripts/robustness.py --run '$$\kappa = 60$$=reports/jkp_em_kappa60' --run '$$\kappa = 240$$=reports/jkp_em_kappa240' \
	    --run 'Equal-weighted factors=reports/jkp_em_ew' --run 'Uncapped value-weighted=reports/jkp_em_vw' \
	    --run 'Time-varying classification=reports/jkp_em_tv'
	$(PY) scripts/breakeven.py --run 'Baseline=reports/jkp_em' --run 'Equal-weighted factors=reports/jkp_em_ew' \
	    --run 'Uncapped value-weighted=reports/jkp_em_vw' --run 'Time-varying classification=reports/jkp_em_tv'

RS_MODELS := ols,enet,gbrt,ols_rs,enet_rs,gbrt_rs,hist_mean,shrink_mean
extensions:
	$(PY) -m emft run --data $(DATA) --models $(RS_MODELS) --out reports/jkp_em_rs
	$(PY) -m emft run --data data/raw_ew/ --weighting ew --models $(RS_MODELS) --out reports/jkp_em_ew_rs
	$(PY) -m emft run --data $(DATA) --models ols,enet,gbrt,hist_mean,shrink_mean --macro data/raw_macro --out reports/jkp_em_macro
	$(PY) -m emft run --data $(DATA) --models ols,enet,gbrt,hist_mean,shrink_mean --sample-start 1990-01 --out reports/jkp_em_from1990
	$(PY) scripts/extensions.py

tables:
	$(PY) scripts/paper_tables.py --run reports/jkp_em --out paper/tables

paper:
	cd paper && pdflatex -interaction=nonstopmode draft.tex && bibtex draft && pdflatex -interaction=nonstopmode draft.tex && pdflatex -interaction=nonstopmode draft.tex

PYTHON ?= python3
YEAR ?= 2024
QUARTER ?= Q3
OUT_DIR ?= /tmp/eph-probe
ENGHO_OUT_DIR ?= /tmp/engho-2017-18-probe

.PHONY: install check smoke eph-smoke engho-smoke probe engho-probe
install:
	$(PYTHON) -m pip install -e .
check:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m eph_extractor --help >/dev/null
	$(PYTHON) -m eph_extractor --version
	$(PYTHON) -m engho_extractor --help >/dev/null
	$(PYTHON) -m engho_extractor --version
smoke: eph-smoke engho-smoke

eph-smoke:
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(PYTHON) tests/fixture_factory.py "$$tmp/fixtures" >/dev/null; \
	$(PYTHON) -m eph_extractor extract --archive "$$tmp/fixtures/modern_nested.zip" --year 2024 --quarter Q3 --out "$$tmp/releases"

engho-smoke:
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	PYTHONPATH=tests:$$PYTHONPATH $(PYTHON) tests/engho_fixture_factory.py "$$tmp/source" >/dev/null; \
	$(PYTHON) -m engho_extractor extract --source-dir "$$tmp/source" --out "$$tmp/releases" >/dev/null; \
	release=$$(find "$$tmp/releases" -mindepth 1 -maxdepth 1 -type d | head -1); \
	$(PYTHON) -m engho_extractor validate --release "$$release" >/dev/null

probe:
	$(PYTHON) -m eph_extractor release --year $(YEAR) --quarter $(QUARTER) --out $(OUT_DIR)

engho-probe:
	$(PYTHON) -m engho_extractor release --out $(ENGHO_OUT_DIR)

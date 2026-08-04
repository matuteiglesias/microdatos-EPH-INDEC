PYTHON ?= python3
YEAR ?= 2024
QUARTER ?= Q3
OUT_DIR ?= /tmp/eph-probe

.PHONY: install check smoke probe
install:
	$(PYTHON) -m pip install -e .
check:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m eph_extractor --help >/dev/null
	$(PYTHON) -m eph_extractor --version
smoke:
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(PYTHON) tests/fixture_factory.py "$$tmp/fixtures" >/dev/null; \
	$(PYTHON) -m eph_extractor extract --archive "$$tmp/fixtures/modern_nested.zip" --year 2024 --quarter Q3 --out "$$tmp/releases"
probe:
	$(PYTHON) -m eph_extractor release --year $(YEAR) --quarter $(QUARTER) --out $(OUT_DIR)

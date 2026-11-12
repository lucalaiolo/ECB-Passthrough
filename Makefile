# 7 How to run
PYTHON ?= python3

.PHONY: refresh test figures var

refresh:  ## download / update data (3)
	$(PYTHON) -m ecbdata.fetch
	$(PYTHON) -m ecbdata.build

test:  ## data checks (3) and tests of the impulse-response and bootstrap code (6.8, 6.9)
	$(PYTHON) -m pytest tests

figures:  ## charts and tables for Sections 4-5
	$(PYTHON) -m analysis.charts
	$(PYTHON) -m analysis.hiking_cycle

var:  ## Section 6, including the bootstrap
	$(PYTHON) -m analysis.var

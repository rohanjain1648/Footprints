# Thin wrapper for Mac/Linux. On Windows run the python commands directly.
.PHONY: data replay sandbox test all
data:
	python -m footprints data
replay:
	python -m footprints replay
sandbox:
	python -m footprints sandbox --seeds 5
test:
	python -m pytest -q
all: data replay sandbox

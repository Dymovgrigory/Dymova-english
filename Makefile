PYTHON ?= python3

.PHONY: help build minify all status media world-dev world-stop

world-dev:
	@./scripts/foxinburg-world-dev.sh start

world-stop:
	@./scripts/foxinburg-world-dev.sh stop

media:
	@$(PYTHON) prototype/build_media.py

help:
	@$(PYTHON) prototype/devflow.py help

build:
	@$(PYTHON) prototype/devflow.py build

minify:
	@$(PYTHON) prototype/devflow.py minify

all:
	@$(PYTHON) prototype/devflow.py all

status:
	@$(PYTHON) prototype/devflow.py status

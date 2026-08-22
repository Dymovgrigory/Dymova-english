PYTHON ?= python3

.PHONY: help build minify all status media

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

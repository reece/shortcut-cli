# Makefile for Python project

.DELETE_ON_ERROR:
.PHONY: FORCE
.PRECIOUS:
.SUFFIXES:

SHELL:=/bin/bash -e -o pipefail

VE_DIR=venv

TEST_DIRS:=tests
DOC_TESTS:=src ./README.md


############################################################################
#= BASIC USAGE
default: help

#=> help -- display this help message
help:
	@sbin/makefile-extract-documentation "$(firstword $(MAKEFILE_LIST))"


############################################################################
#= SETUP, INSTALLATION, PACKAGING

#=> devready: create venv, install prerequisites, install pkg in develop mode
.PHONY: devready
devready:
	make ${VE_DIR} && source ${VE_DIR}/bin/activate && make develop
	@echo '#################################################################################'
	@echo '###  Do not forget to `source ${VE_DIR}/bin/activate` to use this environment  ###'
	@echo '#################################################################################'

#=> venv: make a Python 3 virtual environment
${VE_DIR}:
	python3 -mvenv $@; \
	source $@/bin/activate; \
	python -m ensurepip --upgrade; \
	pip install --upgrade pip setuptools wheel

#=> install: install package
#=> develop: install package in develop mode
.PHONY: develop install
develop:
	@if [ -z "$${VIRTUAL_ENV}" ]; then echo "Not in a virtual environment; see README.md" 1>&2; exit 1; fi
	pip install -e .[dev]
install:
	pip install .

#=> build: make sdist and wheel
.PHONY: build
build: %:
	python -m build


############################################################################
#= TESTING
# see test configuration in setup.cfg

#=> test: execute tests
#=> test-code: test code (including embedded doctests)
#=> test-docs: test example code in docs
.PHONY: test test-code test-docs
test:
	pytest
test-code:
	pytest src
test-docs:
	pytest docs

#=> tox -- run all tox tests
tox:
	tox


############################################################################
#= UTILITY TARGETS

#=> reformat: reformat code with yapf and commit
.PHONY: reformat
reformat:
	@if ! git diff --cached --exit-code >/dev/null; then echo "Repository not clean" 1>&2; exit 1; fi
	black src tests
	isort src tests
	git commit -a -m "reformatted with black and isort"

#=> docs -- make sphinx docs
.PHONY: docs
docs: develop
	# RTD makes json. Build here to ensure that it works.
	make -C doc html json


############################################################################
#= CLEANUP

#=> clean: remove temporary and backup files
.PHONY: clean
clean:
	find . \( -name \*~ -o -name \*.bak \) -print0 | xargs -0r rm

#=> cleaner: remove files and directories that are easily rebuilt
.PHONY: cleaner
cleaner: clean
	rm -fr .cache *.egg-info build dist docs/_build 
	find . \( -name \*.pyc -o -name \*.orig -o -name \*.rej \) -print0 | xargs -0r rm
	find . -name __pycache__ -print0 | xargs -0r rm -fr

#=> cleanest: remove files and directories that require more time/network fetches to rebuild
.PHONY: cleanest
cleanest: cleaner
	rm -fr .eggs .tox venv


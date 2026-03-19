.PHONY: test build install typecheck typecheck-pyrefly typecheck-mypy

test:
	pytest

build:
	python -m build

install:
	pip install -e .

typecheck: typecheck-pyrefly typecheck-mypy

typecheck-pyrefly:
	poetry run pyrefly check

typecheck-mypy:
	poetry run mypy src/ tests/

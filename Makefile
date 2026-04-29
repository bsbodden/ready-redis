.PHONY: install format lint test clean check-types check test-coverage coverage-report coverage-html find-dead-code build publish-test publish

install:
	poetry install --all-extras

format:
	poetry run format
	poetry run sort-imports

check-types:
	poetry run check-mypy

lint: format check-types

test:
	poetry run test-verbose

test-coverage:
	poetry run test-coverage

coverage-report:
	poetry run coverage-report

coverage-html:
	poetry run coverage-html

find-dead-code:
	poetry run find-dead-code

check: lint test

build:
	poetry build

publish-test:
	poetry publish -r test-pypi

publish:
	poetry publish

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "_build" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
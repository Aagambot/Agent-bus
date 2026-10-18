.PHONY: test test-concurrency test-crash-safety coverage

test:
	pytest -x --tb=short

test-concurrency:
	pytest tests/test_concurrency.py -v

test-crash-safety:
	pytest tests/test_crash_safety.py -v

coverage:
	pytest --cov=agentbus --cov-report=term-missing

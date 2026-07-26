.PHONY: bootstrap install test doctor smoke api demo qwen docker clean
bootstrap:
	bash scripts/bootstrap.sh
install:
	python -m pip install -e ".[dev,demo]"
test:
	pytest
doctor:
	python scripts/doctor.py
smoke:
	python scripts/smoke_test.py
api:
	bash scripts/start_api.sh
demo:
	bash scripts/start_demo.sh
qwen:
	bash scripts/start_qwen_vllm.sh
docker:
	docker compose up --build
clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__ .vaultagent

.PHONY: setup \
	pip_install pip_lock \
	lint_py lint_py_pyright lint_py_style lint_py_flake8 \
	docker_build_local docker_run_local

setup: pip_install

pip_install:
	pip install -r requirements.lock.txt
	pip install -e .[dev]
	pip check

pip_lock:
	pip install -e .[dev]
	pip freeze --exclude-editable > requirements.lock.txt

lint_py: lint_py_pyright lint_py_style lint_py_flake8

lint_py_pyright:
	@echo "[lint-pyright] -------------"
	@pyright $(ARGS)
	@echo "[OK] -----------------------"

lint_py_style:
	@echo "[black] --------------------"
	@black --check $(or $(ARGS),.)
	@echo "[OK] -----------------------"

lint_py_flake8:
	@echo "[flake8] -------------------"
	@flake8 $(or $(ARGS),.)
	@echo "[OK] -----------------------"

# Build local docker image
# Usage:
#   make docker_build_local
#   make docker_build_local ARGS="--no-cache"
docker_build_local:
	docker build $(ARGS) -t discord-bot-curaga:local .

docker_run_local:
	docker run -it --env-file .env --rm discord-bot-curaga:local

.PHONY: setup \
	pip_install pip_lock \
	test \
	lint \
	lint_py lint_py_flake8 lint_py_pyright lint_py_style lint_py_style_fix \
	docker_local_build docker_local_run

setup: pip_install

pip_install:
	pip install -r requirements.lock.txt
	pip install -e .[dev]
	pip check

pip_lock:
	pip install -e .[dev]
	pip freeze --exclude-editable > requirements.lock.txt

lint: lint_py

test:
	pytest

lint_py: lint_py_pyright lint_py_style lint_py_flake8

lint_py_pyright:
	@echo "[lint-pyright] -------------"
	@pyright $(or $(ARGS),src/)
	@echo "[OK] -----------------------"

lint_py_flake8:
	@echo "[flake8] -------------------"
	@flake8 $(or $(ARGS),src/)
	@echo "[OK] -----------------------"

lint_py_style:
	@echo "[black] --------------------"
	@black --check $(or $(ARGS),src/)
	@echo "[OK] -----------------------"

lint_py_style_fix:
	@black $(or $(ARGS),src/)

docker_local_build:
	docker build $(ARGS) -t discord-bot-curaga:local .

docker_local_run:
	docker run -it --env-file .env --rm discord-bot-curaga:local

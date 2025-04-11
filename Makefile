DIRS = ./configs ./common ./storages ./service ./apis
export MYPYPATH=./
# --disable-warnings
help:
	@echo "development makefile"
	@echo
	@echo  "usage: make <target>"
	@echo  "Targets:"
	@echo  "    dev			Configure Development"
	@echo  "    deps		Ensure dependencies are installed"
	@echo  "    up			Updates dependencies"
	@echo  "	test		run pytest"
	@echo  "    style		Auto-formats the code"
	@echo  "    check		Checks that build is sane"
	@echo  "	pre-commit	mannually execute pre-commit"

dev:
	@echo "y" | pip install poetry
	@poetry install
	@echo "y" | mypy --install-types  # 安装mypy checker

deps:
	@poetry install --no-root

up:
	@poetry update

style:
	@isort --length-sort -src $(DIRS)
	@black $(DIRS)

check:
	@ruff check --fix .
	@mypy --explicit-package-bases --implicit-reexport .

test:
	@pytest -p no:warnings

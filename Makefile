PIPENV ?= pipenv
DOCKER ?= docker

target:
	@$(MAKE) all

all: install build

build:
	$(info [*] Build package...)
	@$(PIPENV) run python setup.py sdist bdist_wheel

publish: clean build
	$(info [*] Publish to PyPi...)
	@$(PIPENV) run twine upload dist/*

publish-test: clean build
	$(info [*] Publish to test PyPi...)
	@$(PIPENV) run twine upload --repository-url https://test.pypi.org/legacy/ dist/*

install-test:
	$(info [*] Install from test PyPi...)
	@$(DOCKER) run --rm python:3.7 python -m pip install --index-url https://test.pypi.org/simple/ --no-deps awssso

clean:
	$(info [*] Clean artifacts...)
	rm -rf ./build ./dist

install: _install_packages _install_dev_packages

update: _update_packages

_install_packages:
	$(info [*] Install required packages...)
	@$(PIPENV) install

_install_dev_packages:
	$(info [*] Install required dev-packages...)
	@$(PIPENV) install -d

_update_packages:
	$(info [*] Update packages...)
	@$(PIPENV) update

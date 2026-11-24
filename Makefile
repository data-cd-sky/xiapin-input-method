SHELL := /bin/bash
.DEFAULT_GOAL := help

PROJECT := xiapin-input-method
VERSION := $(shell tr -d '[:space:]' < VERSION)

.PHONY: help check test build package-files deb release install clean

help:
	@echo "make check    Shell/Python syntax and static project checks"
	@echo "make test     Run unit and integration tests"
	@echo "make build    Validate native pinyin runtime and portable memory tools"
	@echo "make deb      Build the standard Debian binary package"
	@echo "make release  Build clean shareable release artifacts"
	@echo "make install  Install for the current user (does not activate)"

check:
	bash -n scripts/*.sh tests/*.sh
	python3 -m py_compile libexec/legacy_profilectl.py libexec/memoryctl.py libexec/ibusctl.py scripts/render-icon.py tests/test_legacy_profilectl.py tests/test_memoryctl.py tests/test_ibusctl.py tests/test-icon.py tests/test_docs.py
	./tests/check-project.sh

test: check build
	python3 -m unittest discover -s tests -p 'test_*.py' -v
	./tests/test-build-dictionary.sh
	./tests/test-maintainer-scripts.sh
	./tests/test-systemd-policy.sh
	@status=0; ./tests/test-native-engine.sh || status=$$?; \
		if [[ $$status -ne 0 && $$status -ne 77 ]]; then exit $$status; fi
	@status=0; ./tests/test-ibus-integration.sh || status=$$?; \
		if [[ $$status -ne 0 && $$status -ne 77 ]]; then exit $$status; fi

build:
	cmake -S . -B build/native -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr
	cmake --build build/native
	mkdir -p build/package
	./scripts/build-dictionary.sh --compatible --output build/xiapin-extra.dict
	install -m 0755 libexec/memoryctl.py build/package/ubuntu-cn-input-memory

package-files: build

install:
	@echo "Build the package with 'make deb', then install it with apt." >&2
	@exit 2

deb: test
	$(MAKE) build
	@if command -v dh >/dev/null 2>&1; then \
		dpkg-buildpackage --build=binary --no-sign; \
		mkdir -p dist; \
		cp -f ../$(PROJECT)_$(VERSION)_*.deb dist/; \
	else \
		echo "debhelper is unavailable; using policy-compatible dpkg-deb fallback"; \
		./scripts/build-deb.sh; \
	fi
	./tests/test-deb.sh
	./tests/test-ubuntu-dependencies.sh

release:
	./scripts/build-release.sh

clean:
	rm -rf build dist debian/.debhelper debian/xiapin-input-method debian/files \
		debian/debhelper-build-stamp debian/*.substvars debian/*.debhelper.log

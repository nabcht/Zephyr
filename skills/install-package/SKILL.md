---
name: install-package
description: Install a Python pip package into the currently active virtual environment at runtime. Use when a required package is missing and needs to be installed without restarting the agent.
compatibility: Requires Python 3.10+ and pip. Runs against the same interpreter as μZephyr.
tags: [coder]
---

# install-package

Validates the package specifier against a safe regex, then shells out to
`pip install` using the active Python interpreter.  Sanitises input to block
malformed specifiers before running.

## Usage

Call `install_python_package(package_name)` with a valid pip specifier such as
`"requests"` or `"beautifulsoup4>=4.12"`.

## Implementation

Logic lives in `scripts/install_package.py`.

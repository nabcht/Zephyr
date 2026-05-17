---
name: sandbox
description: Executes Python code in a temporary sandbox to verify it works before finalizing a mission.
compatibility: Requires Python 3.10+
tags: ["coder"]
---

# sandbox

Executes a snippet of Python code in an isolated temporary environment. This skill is primarily used by the **Coder** to verify that a proposed solution or script works as intended before it is delivered to the user or integrated into the core system.

## Usage

This skill is used by the **Coder** to:
1. **Verify Logic**: Ensure that new algorithms or functions produce the expected output.
2. **Check Syntax**: Validate that generated code is free of syntax errors.
3. **Test Dependencies**: Verify if specific third-party requirements function correctly.
4. **Prevent Loops**: Use the built-in 15-second timeout to detect potential infinite loops safely.

### Important Note

The sandbox can run in two modes:

1. Docker-backed containment when `SANDBOX_BACKEND=docker` or `auto` with Docker available.
2. A process-isolated fallback when Docker is unavailable.

The Docker path disables container networking and mounts only the temporary workspace. The fallback path still uses `subprocess.run`, isolated Python startup, a temporary workspace, and a sanitized environment, but it is not equivalent to full container or WASM isolation.

## Implementation

The execution logic is contained within `scripts/sandbox.py`. It captures `STDOUT` and `STDERR` to provide a full execution report back to the agent for debugging or confirmation.


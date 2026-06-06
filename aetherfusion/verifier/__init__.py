"""AetherFusion v0.5 — Verify module.

Provides safe, whitelisted command verification for target projects.
Only runs pre-approved build/test/lint commands within the target
project directory, with timeouts and audit logging.
"""

from aetherfusion.verifier.verify_runner import run_verify

__all__ = ["run_verify"]
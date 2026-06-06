"""AetherFusion Session — v1.0 fusion-session orchestration.

Provides the session runner that chains scan → plan → patch →
optional apply → optional verify → optional diagnostic plans
into a single auditable, reusable fusion session.
"""

from aetherfusion.session.session_runner import run_fusion_session
from aetherfusion.session.artifact_index import build_artifact_index
from aetherfusion.session.session_state import SessionState

__all__ = [
    "run_fusion_session",
    "build_artifact_index",
    "SessionState",
]

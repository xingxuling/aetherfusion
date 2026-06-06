"""Rollback module — safely undo apply operations using a rollback manifest."""

from aetherfusion.rollback.safe_rollback import rollback_apply

__all__ = ["rollback_apply"]
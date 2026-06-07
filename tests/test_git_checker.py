"""Tests for AetherFusion git_checker module."""

import sys
import tempfile
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.git_checker import check_git_status


class TestGitChecker:
    """Git status checks must not crash, even under unusual conditions."""

    def test_not_git_repo_returns_expected(self) -> None:
        """A plain temp directory should be reported as not_git_repo."""
        with tempfile.TemporaryDirectory() as td:
            result = check_git_status(Path(td))
            assert result["status"] == "not_git_repo"
            assert result["branch"] is None
            assert result["changed_files"] == []
            assert result["error_message"] is None

    def test_nonexistent_path_does_not_crash(self) -> None:
        """Passing a non-existent path should not raise or crash."""
        result = check_git_status(Path("Z:/this_does_not_exist_xyz123"))
        assert result["status"] == "not_git_repo"

    def test_empty_string_path_does_not_crash(self) -> None:
        """Empty string path — gracefully returns not_git_repo."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                result = check_git_status(Path(""))
                assert result["status"] == "not_git_repo"
            finally:
                os.chdir(orig_cwd)

    def test_result_has_required_keys(self) -> None:
        """Every result dict must contain the four canonical keys."""
        with tempfile.TemporaryDirectory() as td:
            result = check_git_status(Path(td))
            for key in ("status", "branch", "changed_files", "error_message"):
                assert key in result

    def test_status_value_is_valid(self) -> None:
        """Status must be one of the four canonical values."""
        from aetherfusion.git_checker import GIT_STATUS_VALUES
        with tempfile.TemporaryDirectory() as td:
            result = check_git_status(Path(td))
            assert result["status"] in GIT_STATUS_VALUES

    def test_very_long_path_does_not_crash(self) -> None:
        """A path that is reasonable but non-existent shouldn't crash."""
        result = check_git_status(Path("Z:/some/deeply/nested/path/that/does/not/exist"))
        assert result["status"] == "not_git_repo"
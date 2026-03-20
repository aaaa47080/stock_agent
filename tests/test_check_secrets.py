"""Tests for the secret leak detection scanner."""

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest


class TestCheckGitignore:
    def test_no_sensitive_files_tracked(self):
        import scripts.check_secrets as cs

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            issues = cs.check_gitignore()
            assert issues == []

    def test_env_tracked_is_flagged(self):
        import scripts.check_secrets as cs

        with patch("subprocess.run") as mock_run, patch("os.path.exists", return_value=True):
            mock_run.return_value = MagicMock(returncode=0, stdout=".env", stderr="")
            issues = cs.check_gitignore()
            assert any(".env" in i for i in issues)


class TestCheckGitHistory:
    def test_clean_history(self):
        import scripts.check_secrets as cs

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            issues = cs.check_git_history()
            assert issues == []

    def test_leaked_env_detected(self):
        import scripts.check_secrets as cs

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MagicMock(returncode=0, stdout="abc123\ndef456", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            issues = cs.check_git_history()
            assert any(".env" in i for i in issues)

    def test_none_stdout_handled(self):
        import scripts.check_secrets as cs

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr="")
            issues = cs.check_git_history()
            assert issues == []


class TestCheckSourceCodeSecrets:
    def test_no_secrets_in_clean_code(self, tmp_path):
        import scripts.check_secrets as cs

        (tmp_path / "clean.py").write_text(
            "SECRET_KEY = os.getenv('SECRET_KEY')\n"
            "API_KEY = os.environ.get('API_KEY')\n"
        )
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                (str(tmp_path), [], ["clean.py"])
            ]
            issues = cs.check_source_code_secrets()
            assert issues == []

    def test_hardcoded_secret_detected(self, tmp_path):
        import scripts.check_secrets as cs

        test_file = tmp_path / "bad.py"
        test_file.write_text(
            'JWT_SECRET_KEY = "my-super-secret-key-12345"\n'
        )
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                (str(tmp_path), [], ["bad.py"])
            ]
            issues = cs.check_source_code_secrets()
            assert len(issues) >= 1
            assert any("JWT" in i for i in issues)


class TestMain:
    def test_main_returns_zero_when_clean(self):
        import scripts.check_secrets as cs

        with patch.object(cs, "check_gitignore", return_value=[]):
            with patch.object(cs, "check_git_history", return_value=[]):
                with patch.object(cs, "check_source_code_secrets", return_value=[]):
                    assert cs.main() == 0

    def test_main_returns_one_when_issues(self):
        import scripts.check_secrets as cs

        with patch.object(cs, "check_gitignore", return_value=["CRITICAL: .env tracked"]):
            with patch.object(cs, "check_git_history", return_value=[]):
                with patch.object(cs, "check_source_code_secrets", return_value=[]):
                    assert cs.main() == 1

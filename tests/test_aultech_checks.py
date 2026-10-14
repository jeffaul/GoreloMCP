"""Reporting tests also run with stdlib unittest, without application dependencies."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import aultech_checks as checks

class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.output = io.StringIO()
        capture = redirect_stdout(self.output)
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)
        environment = patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def test_reporting_separates_pr_and_real_upstream(self):
        with patch.object(checks, "shared_base", return_value="shared"), patch.object(
            checks, "changed_files", side_effect=lambda base, head: {"main.py"} if head == "upstream" else {"personal_auth.py"}
        ):
            checks.report_changes("target", "candidate", "upstream")
        output = self.output.getvalue()
        self.assertIn("main.py was modified upstream", output)
        self.assertIn("personal_auth.py was modified in this PR", output)
        self.assertNotIn("personal_auth.py was modified upstream", output)
        self.assertIn("PR changes, not an upstream comparison", output)

    def test_reporting_diff_includes_deleted_or_renamed_files(self):
        with patch.object(checks, "git", return_value="main.py\npersonal_auth.py") as git:
            self.assertEqual(checks.changed_files("base", "head"), {"main.py", "personal_auth.py"})
        git.assert_called_once_with("diff", "--name-only", "--no-renames", "base", "head")

    def test_reporting_no_shared_history_is_not_success(self):
        with patch.object(checks, "git", return_value=""), self.assertRaisesRegex(ValueError, "unique shared commit"):
            checks.shared_base("base", "head")

    def test_reporting_missing_results_fail(self):
        self.assertEqual(checks.results(self.path / "missing.xml"), 1)
        self.assertIn("have not been verified", self.output.getvalue())

    def test_reporting_skipped_and_empty_results_fail(self):
        path = self.path / "results.xml"
        path.write_text('<testsuite><testcase name="test_bind_host_reaches_server_run"><skipped/></testcase></testsuite>')
        self.assertEqual(checks.results(path), 1)
        path.write_text("<testsuite/>")
        self.assertEqual(checks.results(path), 1)

    def test_reporting_escape_annotation(self):
        checks.annotation("warning", "hello%\n::error::forged", "main.py")
        self.assertIn("hello%25%0A::error::forged", self.output.getvalue())

    def test_reporting_git_history_ignores_fork_only_customizations(self):
        previous = Path.cwd()
        os.chdir(self.path)
        self.addCleanup(os.chdir, previous)
        def run(*args):
            return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()
        def commit(message):
            run("add", ".")
            run("-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", message)
            return run("rev-parse", "HEAD")
        run("init")
        (self.path / "main.py").write_text("upstream original")
        original = commit("original")
        (self.path / "main.py").write_text("fork bind customization")
        target = commit("fork customization")
        (self.path / "personal_auth.py").write_text("PR change")
        candidate = commit("candidate")
        checks.report_changes(target, candidate, original)
        self.assertNotIn("main.py was modified upstream", self.output.getvalue())
        self.output.seek(0)
        self.output.truncate()
        run("checkout", "--detach", original)
        (self.path / "main.py").write_text("upstream changed startup")
        upstream = commit("upstream update")
        checks.report_changes(target, candidate, upstream)
        self.assertIn("main.py was modified upstream", self.output.getvalue())
        self.assertNotIn("personal_auth.py was modified upstream", self.output.getvalue())

    def test_reporting_success_requires_all_groups(self):
        path = self.path / "results.xml"
        names = ["test_bind_host_reaches_server_run", "test_default_oauth_allowlist_accepts_registration_and_consent",
                 "test_default_oauth_allowlist_rejects_unsafe_redirects", "test_reporting_example"]
        path.write_text("<testsuite>" + "".join(f'<testcase name="{name}"/>' for name in names) + "</testsuite>")
        self.assertEqual(checks.results(path), 0)
        path.write_text(path.read_text().replace('name="test_bind_host_reaches_server_run"/>',
                                              'name="test_bind_host_reaches_server_run"><failure/></testcase>'))
        self.assertEqual(checks.results(path), 1)

if __name__ == "__main__":
    unittest.main()

"""Plain-English CI reporting. Only the changes command fetches the public upstream."""

import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

UPSTREAM = "https://github.com/Coach40oz/GoreloMCP.git"
CUSTOMIZATIONS = {
    "main.py": "MCP_BIND_HOST customization",
    "personal_auth.py": "ChatGPT OAuth redirect allowlist customization",
}


def annotation(level, message, file=None):
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    properties = f" file={file},title=AulTECH customization review" if file else ""
    print(f"::{level}{properties}::{escaped}")


def summary(text):
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(text + "\n\n")


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def shared_base(base, head):
    bases = git("merge-base", "--all", base, head).splitlines()
    if len(bases) != 1:
        raise ValueError("There is no unique shared commit; the comparison needs manual review.")
    return bases[0]


def changed_files(base, head):
    # Disable rename detection so moving/deleting a customized file is still flagged.
    return set(git("diff", "--name-only", "--no-renames", base, head).splitlines())


def report_changes(base, head, upstream):
    pr_start = shared_base(base, head)
    pr_files = changed_files(pr_start, head)
    summary(f"### Changes proposed in this PR\n\nComparison: `{pr_start}` → `{head}` (PR changes, not an upstream comparison).")
    for file, customization in CUSTOMIZATIONS.items():
        if file in pr_files:
            message = f"{file} was modified in this PR — review the {customization} before merging."
            annotation("warning", message, file)
            summary(f"- Review: {message}")
    if not pr_files.intersection(CUSTOMIZATIONS):
        summary("Neither customized file has changes proposed in this PR.")
    report_upstream(base, upstream)


def report_upstream(base, upstream):
    start = shared_base(base, upstream)
    files = changed_files(start, upstream)
    summary(
        "### Changes in the real upstream\n\n"
        f"Source: [Coach40oz/GoreloMCP](https://github.com/Coach40oz/GoreloMCP). "
        f"Comparison: `{start}` → `{upstream}` on upstream main. "
        "The starting point is its shared commit with the PR target (or current checkout for a manual run). "
        "These changes may already be included in the PR, or may still be waiting upstream."
    )
    for file, customization in CUSTOMIZATIONS.items():
        if file in files:
            message = f"{file} was modified upstream — review the {customization}."
            annotation("warning", message, file)
            summary(f"- Review: {message}")
    if not files.intersection(CUSTOMIZATIONS):
        summary("Neither customized file changed in this upstream range. This does not prove the customizations still work; see behavior checks.")
    summary("File warnings request human review and do not fail the check. Behavior failures do fail it. Nothing is deployed by this workflow.")


def changes():
    summary("## AulTECH customization review")
    base = os.environ.get("PR_BASE_SHA", "")
    head = os.environ.get("PR_HEAD_SHA", "")
    if base or head:
        if not all(re.fullmatch(r"[0-9a-fA-F]{40}", value) for value in (base, head)):
            raise ValueError("The PR comparison commits are missing or invalid.")
    else:
        base = head = git("rev-parse", "HEAD")
        summary("Manual run: there is no PR comparison. Checking the current checkout against the real upstream.")
    # A fixed public source, with its fetched commit recorded in the summary.
    git("fetch", "--no-tags", UPSTREAM, "+refs/heads/main:refs/remotes/aultech-upstream/main")
    upstream = git("rev-parse", "refs/remotes/aultech-upstream/main")
    if os.environ.get("PR_BASE_SHA"):
        report_changes(base, head, upstream)
    else:
        report_upstream(base, upstream)
    return 0


def results(path):
    summary("## AulTECH behavior checks")
    if not Path(path).is_file():
        message = "Behavior checks did not produce a test report — they have not been verified. Review the setup and test step before merging."
        annotation("error", message)
        summary(message)
        return 1
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    groups = [
        ("test_bind_host_reaches_server_run", "main.py", "Configured MCP_BIND_HOST and localhost default reach the server's HTTP run call"),
        ("test_default_oauth_allowlist_accepts_registration_and_consent", "personal_auth.py", "The actual default allowlist accepts ChatGPT, OpenAI, Claude and localhost registration and password-approved redirects"),
        ("test_default_oauth_allowlist_rejects_unsafe_redirects", "personal_auth.py", "The actual OAuth registration endpoint blocks unapproved domains, lookalike domains and unsafe redirects"),
        ("test_reporting_", None, "The warning and result reporter handles comparison and failure cases"),
    ]
    failed = False
    for prefix, file, description in groups:
        selected = [case for case in cases if case.get("name", "").startswith(prefix)]
        bad = [case for case in selected if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))]
        if not selected or bad:
            failed = True
            customization = CUSTOMIZATIONS.get(file, "workflow reporting")
            message = f"{file or 'The customization reporter'} failed or could not complete its behavior check — review {customization} before merging."
            annotation("error", message, file)
            summary(f"- FAILED / NOT VERIFIED: {description}. See the test step for details.")
        else:
            summary(f"- PASSED ({len(selected)} cases): {description}.")
    if any(case.find("failure") is not None or case.find("error") is not None for case in cases):
        failed = True
    summary("These are offline checks with temporary OAuth state. The bind check records server.run arguments; it does not open a socket or verify AWS routing. OAuth checks exercise in-process HTTP endpoints; they do not verify a live ChatGPT connection. The existing tests workflow runs the full offline suite separately.")
    return int(failed)


if __name__ == "__main__":
    try:
        if sys.argv[1] == "changes":
            code = changes()
        elif sys.argv[1] == "results":
            code = results(sys.argv[2])
        else:
            raise ValueError("Unknown report command.")
    except (subprocess.CalledProcessError, ValueError, OSError, ET.ParseError) as exc:
        message = "The customization review could not finish — do not treat this check as verified."
        if sys.argv[1:2] == ["changes"]:
            message = "The PR/upstream comparison could not finish — upstream changes have NOT been verified. Check repository access and shared Git history."
        annotation("error", message)
        summary(message)
        print(str(exc), file=sys.stderr)
        code = 1
    sys.exit(code)

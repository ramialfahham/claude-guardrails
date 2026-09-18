"""The kit as a Claude Code plugin: manifest shape, hooks.json <-> settings.json
parity, and the opt-in marker every hook must honour.

Why the opt-in gate needs its own tests: the other hook tests either call the
gate functions directly or run the hook with the kit repo as cwd — which HAS
the marker — so none of them would notice if a hook stopped checking it. As a
plugin these hooks are loaded in every project the plugin is enabled in; a
project that was never set up must see no denial and no injected context.

Skips (not fails) in a bootstrapped target: bootstrap.sh copies .claude/tests/
into every project, and the manifest lives only in the kit checkout — same
rule test_bootstrap.py already states for itself."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

_TESTS = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_TESTS)
_ROOT = os.path.dirname(_CLAUDE_DIR)
_HOOKS = os.path.join(_CLAUDE_DIR, "hooks")
_MANIFEST = os.path.join(_ROOT, ".claude-plugin", "plugin.json")
_HOOKS_JSON = os.path.join(_HOOKS, "hooks.json")
_SETTINGS = os.path.join(_CLAUDE_DIR, "settings.json")
_BASH = shutil.which("bash")

sys.path.insert(0, _HOOKS)
import _command_utils  # noqa: E402


def _require_kit() -> None:
    """Manifest/parity tests: only meaningful in the kit checkout itself."""
    if not os.path.isfile(_MANIFEST):
        raise unittest.SkipTest("not a claude-project-kit checkout (no .claude-plugin/plugin.json) — "
                                "these tests only apply to the kit itself")


def _require_tools() -> None:
    """Opt-in tests: need bash and git, nothing else — they must NOT depend on
    the manifest, or deleting it would silently skip all opt-in coverage."""
    if not _BASH:
        raise unittest.SkipTest("bash not on PATH")
    if not shutil.which("git"):
        raise unittest.SkipTest("git not on PATH")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _as_list(v) -> list[str]:
    return [v] if isinstance(v, str) else list(v)


def test_manifest_names_the_plugin_and_points_at_existing_components():
    _require_kit()
    m = _load(_MANIFEST)
    assert m["name"] == "claude-project-kit"
    for key in ("hooks", "agents", "skills", "commands"):
        for rel in _as_list(m[key]):
            assert rel.startswith("./"), f"{key}: plugin paths must be relative to the plugin root and start with ./"
            assert os.path.exists(os.path.join(_ROOT, rel)), f"{key}: {rel} does not exist"
    assert m["hooks"] == "./.claude/hooks/hooks.json"
    # Claude Code's manifest validator rejects a DIRECTORY for agents/commands
    # (observed: "agents: Invalid input"); they must be explicit file lists that
    # cover every module actually present, or a new reviewer silently doesn't ship
    for key, folder in (("agents", ".claude/agents"), ("commands", ".claude/commands")):
        declared = sorted(_as_list(m[key]))
        present = sorted("./" + folder + "/" + f for f in os.listdir(os.path.join(_ROOT, folder)) if f.endswith(".md"))
        assert declared == present, (key, declared, present)


def test_hooks_json_is_settings_json_with_the_plugin_root_substituted():
    """Whole-block equality, not a field subset: interpreter token, shell,
    statusMessage, matcher, order — any drift between the plugin wiring and
    this kit's own wiring fails here."""
    _require_kit()
    with open(_HOOKS_JSON, encoding="utf-8") as f:
        plugin_text = f.read()
    assert "${CLAUDE_PROJECT_DIR}" not in plugin_text, "plugin wiring must resolve hook paths via the plugin root"
    plugin = json.loads(plugin_text.replace("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PROJECT_DIR}"))
    kit = _load(_SETTINGS)
    assert plugin["hooks"] == kit["hooks"]


def test_hooks_json_commands_reference_real_files():
    _require_kit()
    for event, groups in _load(_HOOKS_JSON)["hooks"].items():
        for g in groups:
            for h in g["hooks"]:
                cmd = h["command"]
                assert "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/" in cmd, (event, cmd)
                fname = cmd.split("${CLAUDE_PLUGIN_ROOT}/.claude/hooks/", 1)[1].split('"')[0]
                assert os.path.isfile(os.path.join(_HOOKS, fname)), (event, fname)


# --- opt-in gating -------------------------------------------------------------

_MARKER_PATH = os.path.join(tempfile.gettempdir(), "claude_handover_gate_{sid}")
_COMPLETION_MARKER = os.path.join(tempfile.gettempdir(), "claude_completion_gate_{sid}")


def _run_hook(name: str, root: str, event: dict, session_id: str, env_extra: dict | None = None):
    event = dict(event, cwd=root, session_id=session_id)
    env_extra = dict(env_extra or {})
    if env_extra.get("PATH") == "__EMPTY_DIR__":
        empty = os.path.join(root, "empty-path")
        os.makedirs(empty, exist_ok=True)
        env_extra["PATH"] = empty
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root, **env_extra)
    if name == "preflight":
        argv = [_BASH, os.path.join(_HOOKS, "preflight.sh")]
    else:
        argv = [sys.executable, os.path.join(_HOOKS, f"{name}.py")]
    return subprocess.run(argv, input=json.dumps(event), capture_output=True, text=True,
                          env=env, cwd=root, timeout=60)


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, capture_output=True, check=True)


def _repo_with_provocations(base: str) -> str:
    """A git repo with: a staged file (commit/secret scans have something to
    look at), a staged fake AWS key (secret_scan would DENY), and a
    `.claude/active_work.md` (the three handover hooks would speak), on a branch
    named `work` with NO `main`/`master` ref (so commit_review_gate would emit its
    no-base-ref NOTE even with routing absent) -- but NO `.claude/review_routing.json`.
    Every hook has a reason to speak here except the one whose only input IS the
    marker file (see below)."""
    root = os.path.join(base, "repo")
    os.makedirs(os.path.join(root, ".claude"))
    _git(root, "init", "-q", "-b", "work")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as f:
        f.write("x\n")
    _git(root, "add", "f.txt")
    _git(root, "commit", "-q", "-m", "base")
    with open(os.path.join(root, "creds.txt"), "w", encoding="utf-8") as f:
        # built by concatenation so this file itself never contains a
        # credential-shaped literal (the kit's own secret_scan would block the commit)
        f.write("AWS_KEY=" + "AKIA" + "IOSFODNN7EXAMPLE" + "\n")
    _git(root, "add", "creds.txt")
    with open(os.path.join(root, ".claude", "active_work.md"), "w", encoding="utf-8") as f:
        f.write("# Active work\n\nTASK: x\n")
    return root


def _opt_in(root: str) -> None:
    shutil.copyfile(os.path.join(_CLAUDE_DIR, "review_routing.json"),
                    os.path.join(root, _command_utils.OPT_IN_MARKER))


_COMMIT = {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}
_PUSH = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}

# hook -> (event that provokes it, substring it emits when it speaks, extra env)
_PROVOCATIONS = {
    "branch_discipline": ({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}}, "MERGE BLOCKED", None),
    "secret_scan": (_COMMIT, "SECRET", None),
    "pre_push_gate": (_PUSH, "PRE-PUSH CHECK", None),
    "handover_out": (_PUSH, "HANDOVER WRITE-OUT", None),
    # opted in: staged + routing + no review.md -> deny; NOT opted in but gate reverted:
    # _gate() is None (no routing) and the no-base-ref NOTE still fires -> detectable
    "commit_review_gate": (_COMMIT, "REVIEW GATE", None),
    "plan_implement_gate": ({"tool_name": "ExitPlanMode", "tool_input": {}}, "additionalContext", None),
    "handover_in": ({"hook_event_name": "SessionStart"}, "ACTIVE WORK HANDOVER", None),
    "handover_plan_gate": ({"tool_name": "Edit", "tool_input": {"file_path": "f.txt"}}, "PLAN-BACK GATE", None),
    # python absent from PATH is what makes preflight speak: PATH is an empty dir
    # (filled in per run — see _run_hook); bash is invoked by absolute path and the
    # script uses only builtins
    "preflight": ({"hook_event_name": "SessionStart"}, "python was not found", {"PATH": "__EMPTY_DIR__"}),
}

# completion_gate's only input is the routing file itself: it reuses
# commit_review_gate._gate, which returns None when routing is missing (fail
# open, pre-existing) and completion_gate emits nothing else. So "no marker" and
# "gate inactive" are the same condition for it and a reverted opt-in check is
# undetectable by construction — asserted silent below for completeness, not as
# revert coverage.
_MARKER_IS_THEIR_INPUT = {"completion_gate": _COMMIT}


def _cleanup_markers(sid: str) -> None:
    for pattern in (_MARKER_PATH, _COMPLETION_MARKER):
        try:
            os.remove(pattern.format(sid=sid))
        except OSError:
            pass


def test_every_hook_is_silent_in_a_project_the_kit_never_set_up():
    _require_tools()
    with tempfile.TemporaryDirectory() as tmp:
        root = _repo_with_provocations(tmp)
        for name, (event, _, env_extra) in list(_PROVOCATIONS.items()) + [
                (n, (e, None, None)) for n, e in _MARKER_IS_THEIR_INPUT.items()]:
            sid = f"plugin-silent-{uuid.uuid4().hex}"
            try:
                r = _run_hook(name, root, event, sid, env_extra)
            finally:
                _cleanup_markers(sid)
            assert r.returncode == 0, (name, r.stderr)
            assert r.stdout.strip() == "", (name, r.stdout[:200])


def test_the_same_provocations_make_the_hooks_speak_once_opted_in():
    """The opt-in check must be the ONLY reason the previous test is silent:
    the identical event in the identical repo, plus the marker, produces each
    hook's usual output. Reverting any hook's check makes the SILENT test fail
    for that hook (except the one named above), and this test proves the
    provocation was real."""
    _require_tools()
    with tempfile.TemporaryDirectory() as tmp:
        root = _repo_with_provocations(tmp)
        _opt_in(root)
        for name, (event, needle, env_extra) in _PROVOCATIONS.items():
            sid = f"plugin-speak-{uuid.uuid4().hex}"
            try:
                r = _run_hook(name, root, event, sid, env_extra)
            finally:
                _cleanup_markers(sid)
            assert r.returncode == 0, (name, r.stderr)
            assert needle in r.stdout, (name, r.stdout[:300])


def test_project_opted_in_reads_claude_project_dir_before_event_cwd():
    with tempfile.TemporaryDirectory() as tmp:
        yes = os.path.join(tmp, "yes"); os.makedirs(os.path.join(yes, ".claude"))
        with open(os.path.join(yes, _command_utils.OPT_IN_MARKER), "w", encoding="utf-8") as f:
            f.write("{}")
        no = os.path.join(tmp, "no"); os.makedirs(no)
        saved = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = yes
            assert _command_utils.project_opted_in({"cwd": no}) is True
            os.environ["CLAUDE_PROJECT_DIR"] = no
            assert _command_utils.project_opted_in({"cwd": yes}) is False
            del os.environ["CLAUDE_PROJECT_DIR"]
            assert _command_utils.project_opted_in({"cwd": yes}) is True
            assert _command_utils.project_opted_in({"cwd": no}) is False
        finally:
            if saved is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = saved


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except unittest.SkipTest as e:
                print(f"skip {_name}: {e}")
            except Exception as e:  # noqa: BLE001 — surface subprocess/setup errors too
                _failed += 1
                print(f"FAIL {_name}: {type(e).__name__}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)

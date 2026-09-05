"""Tests for scripts/compose_routing.py.

Runnable with `pytest` or directly: `python .claude/tests/test_compose_routing.py`.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
_COMPOSE_SCRIPT = os.path.join(_ROOT, "scripts", "compose_routing.py")

from compose_routing import (  # noqa: E402
    compose, load_json_strict, _write_atomic,
    DuplicateKeyError, MalformedRoutingError,
)

_FRAGMENTS_DIR = os.path.join(_ROOT, "templates", "reviewers", "routing")

_SHIPPED_FRAGMENTS = [
    "platform-reviewer",
    "security-reviewer",
    "data-engineer-reviewer",
    "analytics-engineer-reviewer",
    "frontend-reviewer",
]

_BASE = {
    "_comment": "test fixture",
    "always": ["scope-auditor"],
    "paths": {
        "scripts/*": ["cto-reviewer"],
    },
    "artifact_only": [".claude/task/*"],
    "artifact_only_never": [".claude/task/contract.md"],
}


def test_compose_unions_same_pattern_across_reviewers():
    fragments = {
        "platform-reviewer": {"always": False, "paths": ["scripts/*"]},
        "security-reviewer": {"always": True, "paths": []},
    }
    result = compose(_BASE, fragments)
    # cto-reviewer (already there) + platform-reviewer (new) both on scripts/*,
    # neither one overwriting the other
    assert set(result["paths"]["scripts/*"]) == {"cto-reviewer", "platform-reviewer"}
    assert "security-reviewer" in result["always"]
    assert "scope-auditor" in result["always"], "base's existing always entry must survive"


def test_compose_dedupes_repeated_reviewer_on_same_pattern():
    fragments = {"cto-reviewer": {"always": False, "paths": ["scripts/*"]}}
    result = compose(_BASE, fragments)
    assert result["paths"]["scripts/*"].count("cto-reviewer") == 1


def test_compose_is_idempotent():
    fragments = {
        "platform-reviewer": {"always": False, "paths": ["scripts/*", "*hooks/*"]},
        "security-reviewer": {"always": True, "paths": []},
    }
    once = compose(_BASE, fragments)
    twice = compose(once, fragments)
    assert once == twice, "composing the same fragments again must add nothing further"


def test_compose_does_not_mutate_base():
    base_copy = copy.deepcopy(_BASE)
    compose(_BASE, {"platform-reviewer": {"always": True, "paths": ["scripts/*"]}})
    assert _BASE == base_copy, "compose() must not mutate its `base` argument"


def test_compose_preserves_unrelated_base_keys():
    result = compose(_BASE, {})
    assert result["artifact_only"] == _BASE["artifact_only"]
    assert result["artifact_only_never"] == _BASE["artifact_only_never"]
    assert result["_comment"] == _BASE["_comment"]


def test_duplicate_key_in_json_is_rejected():
    # a hand-authoring mistake plain json.load would silently resolve to
    # "last value wins" — must be caught, not silently accepted
    bad_json = '{"paths": {"scripts/*": ["a"], "scripts/*": ["b"]}}'
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(bad_json)
        try:
            load_json_strict(path)
            assert False, "should have rejected a literal duplicate JSON key"
        except DuplicateKeyError as e:
            assert "scripts/*" in str(e)


def test_clean_json_loads_normally():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "good.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_BASE, f)
        loaded = load_json_strict(path)
        assert loaded == _BASE


def test_shipped_fragments_all_load_and_match_shape():
    for name in _SHIPPED_FRAGMENTS:
        path = os.path.join(_FRAGMENTS_DIR, f"{name}.routing.json")
        frag = load_json_strict(path)
        assert isinstance(frag.get("always"), bool), f"{name}: 'always' must be a bool"
        assert isinstance(frag.get("paths"), list), f"{name}: 'paths' must be a list"


def test_security_reviewer_is_always_true_with_no_paths():
    # its territory (sensitive data) isn't confined to specific paths the way
    # the others are
    frag = load_json_strict(os.path.join(_FRAGMENTS_DIR, "security-reviewer.routing.json"))
    assert frag["always"] is True
    assert frag["paths"] == []


def test_compose_refuses_paths_as_a_string_instead_of_list():
    # a one-bracket hand-authoring slip: "paths": "scripts/*" would otherwise
    # be iterated character-by-character, silently injecting garbage keys
    bad_fragment = {"always": False, "paths": "scripts/*"}
    try:
        compose(_BASE, {"platform-reviewer": bad_fragment})
        assert False, "should have refused 'paths' as a string, not a list"
    except MalformedRoutingError as e:
        assert "paths" in str(e)


def test_compose_refuses_non_bool_always():
    bad_fragment = {"always": "yes", "paths": []}
    try:
        compose(_BASE, {"platform-reviewer": bad_fragment})
        assert False, "should have refused 'always' as a non-bool"
    except MalformedRoutingError as e:
        assert "always" in str(e)


def test_compose_refuses_malformed_base():
    bad_base = {"always": [], "paths": ["scripts/*"]}  # paths should be a dict, not a list
    try:
        compose(bad_base, {})
        assert False, "should have refused a malformed base"
    except MalformedRoutingError:
        pass


def test_write_atomic_writes_correct_content_and_cleans_up():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "out.json")
        _write_atomic(target, '{"a": 1}\n')
        with open(target, encoding="utf-8") as f:
            assert f.read() == '{"a": 1}\n'
        # no leftover temp file
        leftovers = [f for f in os.listdir(tmp) if f != "out.json"]
        assert leftovers == [], f"temp file(s) left behind: {leftovers}"


def test_write_atomic_cleans_up_temp_file_on_failure():
    # forces the actual except-branch (not just the trivial success path,
    # where cleanup is moot because os.replace already consumed the temp file)
    import compose_routing as cr
    original_replace = cr.os.replace

    def _boom(*_a, **_kw):
        raise OSError("simulated failure")

    cr.os.replace = _boom
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out.json")
            try:
                _write_atomic(target, "content")
                assert False, "the simulated os.replace failure should have propagated"
            except OSError:
                pass
            leftovers = os.listdir(tmp)
            assert leftovers == [], f"temp file(s) left behind after failure: {leftovers}"
    finally:
        cr.os.replace = original_replace


def test_cli_refuses_malformed_fragment_and_leaves_target_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "review_routing.json")
        original = json.dumps(_BASE, indent=2) + "\n"
        with open(target, "w", encoding="utf-8") as f:
            f.write(original)

        frag_dir = os.path.join(tmp, "fragments")
        os.makedirs(frag_dir)
        with open(os.path.join(frag_dir, "bad-reviewer.routing.json"), "w", encoding="utf-8") as f:
            json.dump({"always": False, "paths": "scripts/*"}, f)  # malformed: string, not list

        result = subprocess.run(
            [sys.executable, _COMPOSE_SCRIPT,
             "--target", target, "--reviewers", "bad-reviewer",
             "--fragments-dir", frag_dir],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0, "CLI should have refused, not exited cleanly"
        assert "REFUSED" in result.stderr

        with open(target, encoding="utf-8") as f:
            assert f.read() == original, "target must be untouched after a refused compose"


if __name__ == "__main__":
    _failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except AssertionError as e:
                _failed += 1
                print(f"FAIL {_name}: {e}")
    print("all tests passed" if not _failed else f"{_failed} test(s) failed")
    sys.exit(1 if _failed else 0)

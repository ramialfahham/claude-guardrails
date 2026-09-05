"""Tests for scripts/promote_reviewer.py.

Runnable with `pytest` or directly: `python .claude/tests/test_promote_reviewer.py`.
"""

import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from promote_reviewer import promote, validate_source, PromotionRefused  # noqa: E402

_VALID = """---
name: mobile-reviewer
description: Adversarial mobile reviewer — checks app store config and platform APIs.
tools: Read, Grep, Glob
model: sonnet
applies_when: [mobile]
---

You are the Mobile reviewer.
"""


def _write(directory: str, filename: str, content: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_promotes_a_valid_reviewer():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        source = _write(src_dir, "draft.md", _VALID)
        dest = promote(source, dest_dir=dest_dir)
        assert dest == os.path.join(dest_dir, "mobile-reviewer.md")
        assert os.path.isfile(dest)
        with open(dest, encoding="utf-8") as f:
            assert f.read() == _VALID


def test_refuses_draft_flag():
    draft_content = _VALID.replace("model: sonnet", "model: sonnet\ndraft: true")
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        source = _write(src_dir, "draft.md", draft_content)
        try:
            promote(source, dest_dir=dest_dir)
            assert False, "should have refused a draft: true source"
        except PromotionRefused as e:
            assert "draft" in str(e).lower()
        assert os.listdir(dest_dir) == [], "no file should have been written on refusal"


_FIELD_LINES = {
    "name": "name: mobile-reviewer\n",
    "description": "description: Adversarial mobile reviewer — checks app store config and platform APIs.\n",
    "tools": "tools: Read, Grep, Glob\n",
    "model": "model: sonnet\n",
    "applies_when": "applies_when: [mobile]\n",
}


def test_refuses_each_missing_required_field():
    # done_when requires proving EVERY refusal path, not just one field — a
    # promoted module missing any of these can't be routed like the rest of
    # the library, so each is load-bearing on its own.
    for field, line in _FIELD_LINES.items():
        missing = _VALID.replace(line, "")
        assert missing != _VALID, f"fixture setup bug: {field!r} line not found in _VALID"
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
            source = _write(src_dir, "draft.md", missing)
            try:
                promote(source, dest_dir=dest_dir)
                assert False, f"should have refused a source missing {field!r}"
            except PromotionRefused as e:
                assert field in str(e), f"refusal message should name {field!r}: {e}"
            assert os.listdir(dest_dir) == [], f"no file should be written when {field!r} is missing"


def test_refuses_corporate_title_name():
    bad_name = _VALID.replace("name: mobile-reviewer", "name: cpo-reviewer")
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        source = _write(src_dir, "draft.md", bad_name)
        try:
            promote(source, dest_dir=dest_dir)
            assert False, "should have refused a corporate-title name"
        except PromotionRefused as e:
            assert "cpo" in str(e)
        assert os.listdir(dest_dir) == []


def test_refuses_existing_destination_without_force_but_allows_with_it():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        source = _write(src_dir, "draft.md", _VALID)
        _write(dest_dir, "mobile-reviewer.md", "old content\n")

        try:
            promote(source, dest_dir=dest_dir)
            assert False, "should have refused to overwrite without --force"
        except PromotionRefused as e:
            assert "force" in str(e).lower()
        with open(os.path.join(dest_dir, "mobile-reviewer.md"), encoding="utf-8") as f:
            assert f.read() == "old content\n", "refusal must not touch the existing file"

        dest = promote(source, force=True, dest_dir=dest_dir)
        with open(dest, encoding="utf-8") as f:
            assert f.read() == _VALID


def test_refuses_missing_source_file():
    with tempfile.TemporaryDirectory() as dest_dir:
        try:
            promote("/no/such/file.md", dest_dir=dest_dir)
            assert False, "should have raised for a missing source file"
        except FileNotFoundError:
            pass


def test_refuses_file_with_no_frontmatter():
    with tempfile.TemporaryDirectory() as src_dir:
        source = _write(src_dir, "draft.md", "just some text, no frontmatter\n")
        try:
            validate_source(open(source, encoding="utf-8").read())
            assert False, "should have refused a file with no frontmatter block"
        except PromotionRefused as e:
            assert "frontmatter" in str(e).lower()


def test_refuses_path_traversal_in_name():
    # the name becomes a filename (promote() joins it onto dest_dir) — a
    # traversal-shaped name must never reach shutil.copyfile
    for evil_name in ("../../../etc/passwd", "..", "sub/dir-reviewer", "/abs-reviewer"):
        bad = _VALID.replace("name: mobile-reviewer", f"name: {evil_name}")
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
            source = _write(src_dir, "draft.md", bad)
            try:
                promote(source, dest_dir=dest_dir)
                assert False, f"should have refused traversal-shaped name {evil_name!r}"
            except PromotionRefused as e:
                assert "safe" in str(e).lower() or "kebab" in str(e).lower(), (
                    f"unexpected refusal reason for {evil_name!r}: {e}")
            # nothing written anywhere under dest_dir, and nothing escaped it either
            assert os.listdir(dest_dir) == [], (
                f"{evil_name!r} should not have written anything under dest_dir")


def test_refuses_non_utf8_source():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        path = os.path.join(src_dir, "draft.md")
        with open(path, "wb") as f:
            f.write(b"---\nname: mobile-reviewer\n---\n\xff\xfe not valid utf-8\n")
        try:
            promote(path, dest_dir=dest_dir)
            assert False, "should have refused non-UTF-8 source cleanly"
        except PromotionRefused as e:
            assert "utf-8" in str(e).lower()
        assert os.listdir(dest_dir) == []


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

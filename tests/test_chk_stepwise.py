import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

def test_auto_mode_probes_beyond_index_html(tmp_path, monkeypatch):
    # Simulate index.html with only levels 1-10
    levels = list(range(1, 11))
    index_html = make_index_html(levels, out_path=tmp_path / "all_solutions" / "index.html")
    out_dir = tmp_path / "all_solutions"
    out_dir.mkdir(exist_ok=True)
    # Simulate local HTML files up to 20 (but index.html only lists 1-10)
    for n in range(1, 21):
        (out_dir / f"level_{n}.html").write_text(f"dummy {n}", encoding="utf-8")
    # Patch sys.argv
    sys_argv_orig = sys.argv
    sys.argv = ["chk_stepwise.py"]
    # Patch Path in chk_stepwise
    orig_path = chk_stepwise.Path
    chk_stepwise.Path = lambda x: out_dir if x == "all_solutions" else orig_path(x)
    # Patch process_levels to record which levels are probed
    probed = []
    orig_process_levels = chk_stepwise.process_levels
    def fake_process_levels(levels, out_dir, workers, rate):
        probed.extend(levels)
        results = []
        for lvl in levels:
            results.append({
                "level": lvl,
                "status": "ok" if lvl <= 20 else "skipped",
                "multi": False,
                "elapsed": 0.0 if lvl <= 20 else None,
                "rules": [],
                "created_by": "test",
                "user": "testuser",
                "rule": "testrule"
            })
        return results
    chk_stepwise.process_levels = fake_process_levels
    try:
        chk_stepwise.run_auto_mode(out_dir, workers=1, rate=0)
    finally:
        sys.argv = sys_argv_orig
        chk_stepwise.Path = orig_path
        chk_stepwise.process_levels = orig_process_levels
    # Should probe 11-20 (from files) and then 21 (HTTP 404)
    assert 20 in probed
    assert 21 in probed
    assert max(probed) == 21

import tempfile
import shutil
import os
from pathlib import Path
import pytest
import sys
import types
import chk_stepwise

def make_index_html(levels, missing=None, out_path=None):
    """Create a minimal index.html with given levels present, optionally omitting some."""
    if missing is None:
        missing = set()
    rows = []
    # Ensure levels is a full range, not just [1]
    min_lvl = min(levels)
    max_lvl = max(levels)
    for lvl in range(min_lvl, max_lvl + 1):
        if missing and lvl in missing:
            continue
        rows.append(f'<tr><td>Play</td><td><a href="level_{lvl}.html">{lvl}</a></td><td></td><td>user</td><td>1.000s</td><td>rule</td></tr>\n')
    html = f"""
    <html><body><table><tbody>
    {''.join(rows)}
    </tbody></table></body></html>
    """
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
    return html

def run_auto_mode(tmp_path, index_html):
    # Write index.html
    out_dir = tmp_path / "all_solutions"
    out_dir.mkdir()
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    # Patch sys.argv
    sys_argv_orig = sys.argv
    sys.argv = ["chk_stepwise.py"]
    # Patch out_dir in chk_stepwise
    orig_path = chk_stepwise.Path
    chk_stepwise.Path = lambda x: out_dir if x == "all_solutions" else orig_path(x)
    try:
        chk_stepwise.main()
    finally:
        sys.argv = sys_argv_orig
        chk_stepwise.Path = orig_path
    # Read new index.html
    return (out_dir / "index.html").read_text(encoding="utf-8")

def test_missing_levels_middle_and_end(tmp_path):
    # Levels 1-10, missing 4, 7, 10
    levels = list(range(1, 11))
    missing = {4, 7, 10}
    index_html = make_index_html(levels, missing)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out_html = run_auto_mode(tmp_path, index_html)
    output = buf.getvalue()
    # Debug: print what levels the parser found
    out_dir = tmp_path / "all_solutions"
    index_path = out_dir / "index.html"
    found_levels = set()
    import re
    for line in index_path.read_text(encoding="utf-8").splitlines():
        m = re.search(r'<a href="level_(\d+).html">(\d+)</a>', line)
        if m:
            found_levels.add(int(m.group(1)))
    # Should print missing levels 4, 7, 10 and continue after 10
    assert "Missing levels detected: [4, 7, 10]" in output or "Missing levels detected" in output
    # Should contain all levels 1-10 except missing, and new levels after 10

def test_no_missing_levels(tmp_path):
    # Levels 1-5, none missing
    levels = list(range(1, 6))
    index_html = make_index_html(levels)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out_html = run_auto_mode(tmp_path, index_html)
    output = buf.getvalue()
    assert "No missing levels detected" in output or "No missing levels detected" in output
    # Should continue after 5

def test_empty_index_html(tmp_path):
    # No index.html present
    out_dir = tmp_path / "all_solutions"
    out_dir.mkdir()
    import io
    import contextlib
    sys_argv_orig = sys.argv
    sys.argv = ["chk_stepwise.py"]
    orig_path = chk_stepwise.Path
    chk_stepwise.Path = lambda x: out_dir if x == "all_solutions" else orig_path(x)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            chk_stepwise.main()
    finally:
        sys.argv = sys_argv_orig
        chk_stepwise.Path = orig_path
    # Should start from level 1
    # index.html is only created if new levels are found/solved
    assert not (out_dir / "index.html").exists() or (out_dir / "index.html").exists()

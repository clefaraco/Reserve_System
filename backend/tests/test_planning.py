"""Project traceability is checked just like migrations, including drift failures."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location("planning_check", ROOT / "scripts/planning.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_planning_generated_views_and_full_source_preserved():
    mod = module()
    for name, content in mod.render().items():
        assert (mod.PLAN / name).read_text(encoding="utf-8") == content
    source = (mod.PLAN / "references/Medical_Appointment_System_Prompt_01.md").read_text(
        encoding="utf-8"
    )
    assert "### S01." in source and "### S15." in source


@pytest.mark.parametrize("mutation", ["duplicate", "cycle", "unknown", "deleted", "criteria"])
def test_planning_rejects_broken_traceability(tmp_path, mutation):
    import shutil

    mod = module()
    shutil.copytree(mod.PLAN, tmp_path / "planning")
    mod.PLAN = tmp_path / "planning"
    path = mod.PLAN / "backlog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["items"]
    if mutation == "duplicate":
        items.append(items[0])
    if mutation == "cycle":
        items[0]["dependencies"] = [items[1]["id"]]
        items[1]["dependencies"] = [items[0]["id"]]
    if mutation == "unknown":
        items[0]["dependencies"] = ["MISSING"]
    if mutation == "deleted":
        items.pop()
    if mutation == "criteria":
        items[0]["acceptance"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        mod.render()

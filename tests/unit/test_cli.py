import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis import cli


def test_generate_agent_writes_valid_module(tmp_path):
    path = cli.generate_agent("stat_helper", tmp_path)
    assert path.name == "stat_helper_agent.py"
    tree = ast.parse(path.read_text())
    assert any(isinstance(n, ast.ClassDef) and n.name == "StatHelperAgent" for n in tree.body)
    with pytest.raises(FileExistsError):
        cli.generate_agent("stat_helper", tmp_path)
    cli.generate_agent("stat_helper", tmp_path, force=True)
    with pytest.raises(ValueError):
        cli.generate_agent("bad name!", tmp_path)


def test_generated_agent_runs(tmp_path):
    import asyncio
    import importlib.util
    from kiwis.agents.base import AgentContext, AgentState
    path = cli.generate_agent("demo", tmp_path)
    spec = importlib.util.spec_from_file_location("demo_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = asyncio.run(mod.DemoAgent().execute(AgentContext(research_topic="t")))
    assert out.state == AgentState.COMPLETED


def test_entry_points_exist_and_dispatch(tmp_path, monkeypatch):
    import tomllib
    scripts = tomllib.loads((Path(__file__).parent.parent.parent / "pyproject.toml").read_text())["project"]["scripts"]
    for target in scripts.values():
        module, func = target.split(":")
        assert callable(getattr(cli, func))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["kiwis-init", "proj"])
    cli.init_command()
    assert (tmp_path / "proj" / "kiwis_config.yaml").exists()

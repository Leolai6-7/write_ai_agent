"""Tests for CLI entry point."""

from typer.testing import CliRunner
from main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI 小說家" in result.output


def test_cli_status_no_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "尚未開始" in result.output

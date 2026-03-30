"""Tests for WorldState module."""

import pytest
import yaml

from memory.world_state import WorldState


@pytest.fixture
def world_dir(tmp_path):
    # Write test YAML files
    (tmp_path / "world_setting.yaml").write_text(yaml.dump({
        "continent": "艾爾特大陸",
        "eras": "第五紀元",
        "geography": ["阿羅恩村", "星環之塔"],
        "magic_system": {
            "source": "靈脈為基礎",
            "rules": ["魔力來自星辰", "使用魔法削弱生命"],
        },
        "races": ["人類", "精靈族"],
    }, allow_unicode=True), encoding="utf-8")

    (tmp_path / "main_character.yaml").write_text(yaml.dump({
        "name": "伊澤",
        "race": "人類",
        "age": 10,
        "personality": ["倔強", "求知慾強"],
        "skills": ["火魔法", "古代語文"],
        "goals": ["找出父親真相"],
        "background": "出生於阿羅恩村",
    }, allow_unicode=True), encoding="utf-8")

    (tmp_path / "main_goal.yaml").write_text(yaml.dump({
        "main_goal": "拯救被詛咒吞噬的家鄉",
    }, allow_unicode=True), encoding="utf-8")

    return tmp_path


def test_load_world(world_dir):
    ws = WorldState(world_dir)
    ws.load()
    ctx = ws.get_context()
    assert "艾爾特大陸" in ctx
    assert "靈脈" in ctx
    assert "伊澤" in ctx
    assert "拯救" in ctx


def test_character_filtering(world_dir):
    ws = WorldState(world_dir)
    ws.load()
    # Character included when in list
    ctx = ws.get_context(characters_involved=["伊澤"])
    assert "伊澤" in ctx

    # Character excluded when not in list
    ctx = ws.get_context(characters_involved=["米娜"])
    assert "伊澤" not in ctx


def test_missing_files(tmp_path):
    ws = WorldState(tmp_path)
    ws.load()
    ctx = ws.get_context()
    assert ctx == ""  # No files, empty context


def test_world_format(world_dir):
    ws = WorldState(world_dir)
    ws.load()
    ctx = ws.get_context()
    assert "魔法體系" in ctx
    assert "星辰" in ctx
    assert "人類、精靈族" in ctx

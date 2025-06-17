"""中央控制面板 - 統一管理所有配置"""
import os
from openai import OpenAI
from dotenv import load_dotenv

# --- General Setup ---
load_dotenv()
CLIENT = OpenAI()
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- File Paths ---
# Directories
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
SUMMARIES_DIR = os.path.join(PROJECT_ROOT, "summaries")
CHARACTERS_DIR = os.path.join(PROJECT_ROOT, "characters")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")  # 建議用一個 data 資料夾存放

# YAML files
# 建議將所有非輸出的 yaml 移到一個地方管理
WORLD_SETTING_FILE = os.path.join(PROJECT_ROOT, "world_setting.yaml")
OBJECTIVES_EXPANDED_FILE = os.path.join(PROJECT_ROOT, "objectives_expanded.yaml")
MAIN_CHARACTER_FILE = os.path.join(PROJECT_ROOT, "main_character.yaml")
TIMELINE_FILE = os.path.join(PROJECT_ROOT, "timeline.md")
MAIN_GOAL_FILE = os.path.join(PROJECT_ROOT, "main_goal.yaml")
CONTEXT_SNAPSHOT_FILE = os.path.join(PROJECT_ROOT, "context_snapshot.yaml")

# --- Model Configurations ---
PLANNING_MODEL = "gpt-4-turbo"
GENERATION_MODEL = "gpt-4-turbo"
EXPANSION_MODEL = "gpt-4-turbo"
SUMMARY_MODEL = "gpt-4-turbo"
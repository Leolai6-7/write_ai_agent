# 📅 timeline_generator.py
# 自動從 objectives.yaml 與 summaries/ 產出完整小說時間線 Markdown，並可補齊缺失摘要

import yaml
import os
from chapter_generator import summarize_chapter


def load_objectives(objective_path="objectives.yaml"):
    if not os.path.exists(objective_path):
        return {}
    with open(objective_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_summary(chapter_id):
    path = f"summaries/chapter_{chapter_id:02d}_summary.md"
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def summarize_missing_summaries():
    os.makedirs("summaries", exist_ok=True)
    objectives = load_objectives()
    filled = 0

    for chap in sorted(objectives.keys(), key=lambda x: int(x)):
        chap_id = int(chap)
        summary_path = f"summaries/chapter_{chap_id:02d}_summary.md"
        if not os.path.exists(summary_path):
            output_path = f"outputs/chapter_{chap_id:02d}.md"
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    chapter_text = f.read()
                summary = summarize_chapter(chapter_text)
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary)
                print(f"✅ 補上第 {chap_id} 章的摘要")
                filled += 1
            else:
                print(f"⚠️ 缺少 outputs/chapter_{chap_id:02d}.md，無法補摘要")
    if filled == 0:
        print("👍 所有摘要已齊全，無需補寫。")


def generate_timeline_markdown():
    objectives = load_objectives()
    timeline_md = "# 📖 小說劇情時間線\n\n"

    for chap in sorted(objectives.keys(), key=lambda x: int(x)):
        obj = objectives[chap]
        summary = load_summary(int(chap))

        timeline_md += f"## 第 {int(chap)} 章\n"
        timeline_md += f"**章節目標：** {obj}\n\n"
        if summary:
            timeline_md += f"**章節摘要：**\n{summary}\n"
        else:
            timeline_md += "*⚠️ 本章尚無摘要。*\n"
        timeline_md += "\n---\n\n"

    return timeline_md


def save_timeline(md_text, path="timeline.md"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"✅ 劇情時間線已儲存至 {path}")


# ✅ 整合至故事創作流程後可調用

def update_timeline():
    summarize_missing_summaries()
    md = generate_timeline_markdown()
    save_timeline(md)
    print('\n👁️ 可用 Markdown 閱讀器開啟 timeline.md 瀏覽劇情概覽。')

if __name__ == "__main__":
    summarize_missing_summaries()
    md = generate_timeline_markdown()
    save_timeline(md)
    print("\n👁️ 可用 Markdown 閱讀器開啟 timeline.md 瀏覽劇情概覽。")

# 🧠 context_builder_agent.py
# 整理所有章節摘要為「長期上下文」，用於長篇小說故事創作

import os
import openai
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI()


def load_all_summaries(summary_dir="summaries"):
    summaries = []
    if not os.path.exists(summary_dir):
        return summaries

    for fname in sorted(os.listdir(summary_dir)):
        if fname.startswith("chapter_") and fname.endswith("_summary.md"):
            path = os.path.join(summary_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                summaries.append(f.read().strip())
    return summaries


def build_context_from_summaries(summaries):
    prompt = (
        "你是一位小說策劃顧問，請閱讀以下小說章節摘要，從中整理出目前劇情中最重要的長期上下文資訊，"
        "包括主角心理變化、主線進展、角色關係與未解懸念。請用條列式摘要呈現，並依照以下分類輸出：\n\n"
        """
        【主角心理變化】\n...
        【主線進展】\n...
        【角色關係】\n...
        【未解懸念】\n..."""
    )

    summary_input = "\n\n".join(summaries)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是小說故事分析專家。"},
            {"role": "user", "content": prompt + "\n\n" + summary_input}
        ],
        temperature=0.5,
        max_tokens=1000
    )

    return response.choices[0].message.content.strip()


def save_context_snapshot(text, path="context_snapshot.yaml"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✅ 上下文快照已儲存至 {path}")


if __name__ == "__main__":
    summaries = load_all_summaries()
    context = build_context_from_summaries(summaries)
    save_context_snapshot(context)

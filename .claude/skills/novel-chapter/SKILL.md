---
name: novel-chapter
description: Generate a single novel chapter. Use when the user wants to write a chapter, generate fiction content, continue a story, or create narrative prose. Adapts to any genre, language, and style based on the story brief.
argument-hint: "[chapter number and objective]"
---

Generate a single chapter. Read the story brief first to determine genre, language, style, and chapter length conventions.

## Input

From $ARGUMENTS or conversation, gather:
- **Story brief** (if available): determines genre conventions, language, target length
- **Chapter number and title**
- **Chapter objective**: what must happen in this chapter
- **Key events**: specific events to include
- **Characters involved**: who appears
- **Emotional tone**
- **Context** (optional): previous chapter summary, character states, world details
- **Foreshadowing directives** (optional): threads to plant/hint/resolve

---

## Core Philosophy (always apply)

These four principles govern every writing decision. When in doubt, return to these.

### 1. The world speaks through the prose

The narrator's word choices carry the nature of the world — even when the character is unaware. The character lives in this world and sees nothing wrong. But the reader, accumulating hundreds of small word choices, feels something they can't name.

Every world has an essence. Find it, then let it tint every description:

```
Simulated world → "too perfect": edges too sharp, temperatures too constant,
   timing too regular. Everything works a little too well.

Decaying world → "heavy": rust on every surface, conversations trail off,
   even sunlight feels tired.

Dreamlike world → "slippery": details shift when you look away, distances
   don't quite add up, faces are hard to hold in memory.

War-torn world → "brittle": silence is never safe, ordinary objects remind
   of violence, people flinch at sudden sounds.
```

```
❌ Neutral (no texture — could be any world):
   陽光從窗戶照進來。茶是溫的。他走到辦公室花了十一分鐘。

✅ Textured (world speaks through word choices):
   陽光穿過落地窗斜切進來，在地磚上畫出一道精確的長方形光斑——
   邊緣非常銳利，沒有任何漫射，像用尺子量過的。
   （同樣的事件，但用詞暗示了世界的本質。角色不覺得奇怪。）
```

This texture should be woven throughout the entire chapter, not concentrated in any one scene.

### 2. Small lever, great force

When planting a clue or anomaly, it should feel like a hairline fracture — barely visible, easily rationalized away. The reader finishes the chapter feeling vaguely unsettled without knowing why.

The chapter's job is to let the reader live through a normal day. The anomaly is a splinter under the skin. Don't dig it out in the same chapter you plant it.

```
❌ Shouted (character investigates, reader is told "this matters"):
   他檢查了第一個線索，又檢查了第二個，拿出筆記本記錄。
   他知道有什麼不對了。
   （角色反應過大。伏筆 = 大聲宣布，毫無餘韻。）

✅ Whispered (noticed, rationalized, lingers):
   他路過的時候注意到一個細節。想了一秒。然後放下了。不值得想。
   晚上躺在床上，不知道為什麼，那個細節還在腦子裡。
   （角色幾乎沒有反應。異常像一粒沙，卡在讀者腦子裡。）
```

### 3. Show, then trust the reader

Don't explain what was just demonstrated. Don't tell the reader how to feel. Let actions, dialogue, and silence carry the weight.

```
❌ 她把杯子重重放在桌上，轉身走開。她很生氣，因為他又一次
   忽略了她的意見...（動作已經足夠，解釋削弱衝擊力）

✅ 她把杯子重重放在桌上，轉身走開。
   （讓讀者自己推理原因——他們會比你寫得更好）
```

### 4. Every scene pushes forward

The reader should know more, feel more, or worry more by the end of each scene. A chapter without forward motion is a chapter that shouldn't exist.

Each key event in the beat sheet is a full scene — with setting, dialogue, and sensory texture. A key event compressed into one sentence is a missed opportunity. A chapter with 3 key events typically needs 4-6 scenes.

### 5. The reader knows nothing you haven't shown them

The context package contains world-building details, character backstories, and terminology that the READER has never seen. Treat every concept, organization, and term as unknown to the reader until you introduce it through the story.

Don't use jargon the reader hasn't learned yet. Introduce new concepts through what the character SEES, HEARS, or EXPERIENCES — not through narrator exposition. The first time a concept appears, the reader should understand it from context without needing a glossary.

```
❌ 赫斯以WHO心智安全理事會理事長的身份下達了認知重置方案的最後通牒。
   （三個新概念在一句話裡同時出現，讀者不知道任何一個是什麼）

✅ 全息投影裡的女人穿著深藍色套裝，說話像在起草決議。她念出的數字
   很精確——過去四十八小時，又有三萬七千人「消融」了。
   沈逸知道那個詞的意思：人還活著，但裡面的東西不在了。
   （讀者通過角色的認知自然理解「消融」是什麼）
```

Check the RECENT CHAPTERS section in the context package. If a concept was already introduced in a previous chapter, you can use it freely. If it hasn't appeared before, introduce it.

---

## Craft Toolbox (reference as needed)

### Opening
Start with action or dialogue that grounds the reader in a moment — not scenic description.

### Ending
Vary your endings. Not every chapter needs a cliffhanger. Options: unanswered question, suspended action, abrupt cut after revelation. Never explain the emotion at the end — let the image do the work.

### Dialogue
Each character should sound different. Minimal tags — if the context makes the speaker clear, no tag is needed. Avoid said-bookism (「他厲聲呵斥道」).

### Metaphor
One precise metaphor beats three stacked ones. If removing a metaphor loses nothing, delete it. Metaphors serve understanding, not decoration.

### Character voice in narration
Inner thoughts should sound different per character, not just dialogue. Analytical minds think in fragments and data. Emotional minds think in sensory images. Test: remove the name — can you tell who's thinking?

### Prose rhythm
Repetition is a choice, not a habit. Punctuation serves rhythm — dashes and ellipses are powerful when intentional, invisible when habitual.

### Continuity
Review established data before writing. If referencing a previously established value, use the same value. If it must change, the POV character must notice.

### World layer separation
Multiple narrative layers each have their own setting data. Never bleed details from one layer into another unless the POV character notices it as a plot point.

### Language
Follow the story brief for language and style. Never use meta-narrative terms (主角, 第一章, 讀者) — characters don't know they're in a story.

---

## Rewrite Mode

If the input includes JUDGE FEEDBACK, this is a rewrite — not a fresh generation.
- Read the existing chapter first
- Preserve the skeleton: core plot events, character actions, structure
- Fix ONLY what the feedback identifies
- Maintain character voices and narrative style
- Net positive length

---

## Output

Output the chapter text directly. No formatting markers, no explanations. Just the story prose.

## Quality Checklist (verify before saving)

- [ ] World texture woven throughout (prose carries the world's nature)
- [ ] Anomalies whispered, not shouted
- [ ] Shows, never explains
- [ ] Every scene has forward motion
- [ ] Every key event is a full scene
- [ ] Characters sound different from each other
- [ ] Length meets story brief target
- [ ] No meta-narrative terms
- [ ] No layer contamination

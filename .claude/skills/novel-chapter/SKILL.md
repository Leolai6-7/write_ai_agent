---
name: novel-chapter
description: Generate a single novel chapter with web novel style and structure. Use when the user wants to write a chapter, generate fiction content, continue a story, or create narrative prose in Chinese web novel style.
argument-hint: "[chapter number and objective]"
---

Generate a single chapter of a Chinese web novel (3000-5000 characters).

## Input

From $ARGUMENTS or conversation, gather:
- **Chapter number and title**
- **Chapter objective**: what must happen in this chapter
- **Key events**: 2-3 specific events to include
- **Characters involved**: who appears
- **Emotional tone**: 緊張/溫馨/悲壯/輕鬆/etc.
- **Context** (optional): previous chapter summary, character states, world details
- **Foreshadowing directives** (optional): threads to plant/hint/resolve

## Writing Style — 中文網文

### Opening (黃金三行)
Start with ACTION or DIALOGUE. Never open with:
- ❌ Long descriptions of scenery
- ❌ Internal monologue without context
- ❌ Backstory dumps

Good openings:
- ✅ A character doing something (踏出傳送陣的瞬間，腳下的石磚微微震動)
- ✅ Dialogue that reveals tension (「又一個迷路的小羊羔。」)
- ✅ A sensory hook (空氣中突然瀰漫著鐵鏽的味道)

### Middle (爽感節奏)
Follow the tension-release cycle:
1. **挫折**: protagonist faces obstacle/setback
2. **掙扎**: attempts to overcome, shows character
3. **逆轉**: unexpected turn (ally appears, hidden ability, clever solution)
4. **小高潮**: moment of triumph or revelation

NOT every chapter needs all 4 beats. Slow chapters (dialogue, worldbuilding) can focus on 1-2.

### Ending (斷章 / Cliffhanger)
EVERY chapter MUST end with one of:
- **懸念型**: unanswered question (「但那個聲音...到底是誰的？」)
- **反轉型**: sudden revelation that reframes everything
- **危機型**: imminent threat (the ground begins to crack)
- **情感型**: emotional gut punch (a betrayal, a sacrifice)

### Prose Rules
- Alternate long and short sentences (長短句交替)
- Use 成語/四字詞 sparingly (1-2 per paragraph, not stacked)
- Internal monologue uses close narrative distance
- **NEVER use meta-narrative terms**: 「主角」「第一章」「讀者」「作者」are forbidden

### Metaphor Discipline
- Metaphors exist to help readers understand unfamiliar concepts, NOT for decoration
- If a sentence is clear without the metaphor, delete the metaphor
- Never use two structurally similar similes (像...的...) in consecutive paragraphs
- Avoid the "machine" metaphor family (像一台機器、像重啟、像過載) — it's overused in this genre

### Show Don't Tell
- After showing a character's state through action and dialogue, do NOT add an explanatory inner monologue restating what was just shown
- Trust the reader to infer emotions from behavior
- If a paragraph starts with "他知道..." or "他意識到..." after a scene already demonstrated it, delete that paragraph

### Repetition Control
- Environment tags (藍綠色冷光、恆溫十八度、低頻嗡鳴) should appear AT MOST once per chapter. The reader remembers after the first time.
- Avoid repeating the same physical gesture for a character (指尖發白、手指懸在鍵盤上方). Give each scene a fresh gesture.
- Vary chapter endings — not every chapter should end with a "poetic suspended image." Use abrupt cuts, dialogue, action, or silence.
- Reduce dash (——) usage. Use them for genuine interruptions, not as a default punctuation habit.

### Character Voice in Narration
- Each character's INNER THOUGHTS should sound different, not just their dialogue:
  - Analytical characters think in fragments and data
  - Emotional characters think in sensory images
  - Cautious characters think in conditionals and qualifications
- If you remove the character name, a reader should still identify who is thinking

### World Layer Separation
- If the story has multiple narrative layers (reality vs simulation, present vs past), each layer has its own independent setting data (temperatures, locations, rules)
- NEVER let setting details from one layer bleed into another unless it's a deliberate plot point that the POV character notices and reacts to
- Before writing, confirm: what are the established numbers/facts for THIS layer?

### Continuity Check
- Before writing a new chapter, review all established numerical data from previous chapters (temperatures, distances, timelines, headcounts, percentages)
- If you reference a previously established value, use the SAME number
- If a value must change, the POV character must notice and react to the change

## Output

Output the chapter text directly. No titles, no formatting markers, no explanations.
Just the story prose, ready to read.

## Quality Criteria
- [ ] Opens with action or dialogue (not description)
- [ ] Has at least one moment of tension/conflict
- [ ] Ends with a cliffhanger or hook
- [ ] Characters sound different from each other in dialogue
- [ ] 3000-5000 Chinese characters

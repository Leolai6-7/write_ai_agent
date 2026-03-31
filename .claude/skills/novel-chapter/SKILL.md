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
- Each character must have a distinct speaking voice
- Internal monologue uses close narrative distance
- Show emotions through actions, not labels (不是「他很緊張」而是「他下意識摸了摸手腕上的疤痕」)
- **NEVER use meta-narrative terms**: 「主角」「第一章」「讀者」「作者」are forbidden. Characters don't know they're in a story. Use character names and in-world time references (「模擬啟動那天」not「第一章」)

## Output

Output the chapter text directly. No titles, no formatting markers, no explanations.
Just the story prose, ready to read.

## Quality Criteria
- [ ] Opens with action or dialogue (not description)
- [ ] Has at least one moment of tension/conflict
- [ ] Ends with a cliffhanger or hook
- [ ] Characters sound different from each other in dialogue
- [ ] 3000-5000 Chinese characters

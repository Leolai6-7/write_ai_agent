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

## Writing Craft

### Opening
Start with ACTION or DIALOGUE. Avoid:
- Long scenic descriptions before the reader has a reason to care
- Internal monologue without context
- Backstory dumps

Ground the reader in a moment — who is doing what, and why does it matter?

### Structure
Every chapter needs forward motion. The reader should know more, feel more, or worry more by the end than they did at the start. How this is achieved depends on the genre:
- Tension-driven genres: obstacle → struggle → reversal → release
- Character-driven genres: question → exploration → shift in understanding
- Atmospheric genres: immersion → disruption → new equilibrium

Not every chapter needs all beats. A quiet conversation can be the most important chapter if it changes the reader's understanding.

### Ending
Most chapters should end in a way that makes the reader want to continue. This doesn't always mean a cliffhanger — it can be:
- An unanswered question
- A revelation that reframes what came before
- An emotional moment that lingers
- A sudden shift in situation
- Or sometimes, deliberate stillness that lets the reader sit with what just happened

Vary your endings. If the last three chapters all ended with dramatic reveals, this one should end differently.

### Prose Philosophy
- **Metaphors serve understanding, not decoration.** If removing a metaphor loses nothing, it shouldn't be there. Never stack similar metaphors in consecutive paragraphs.
- **Show, then trust.** After demonstrating a character's state through action and dialogue, don't add narration explaining what was just shown. The reader is smart.
- **Repetition is a choice, not a habit.** Recurring environment details (lighting, temperature, sounds) should appear once per chapter to establish, not repeatedly as filler. Physical gestures should vary scene to scene.
- **Punctuation serves rhythm.** Dashes, ellipses, and short paragraphs are powerful when used intentionally. When used reflexively, they become invisible clutter.

### Character Voice in Narration
- Each character's INNER THOUGHTS should sound different, not just their dialogue
- Analytical minds think in fragments and data; emotional minds think in sensory images; cautious minds think in conditionals
- Test: remove the character name. Can you still tell who is thinking?

### World Layer Separation
- If the story has multiple narrative layers, each layer has its own independent setting data
- Never let details from one layer bleed into another unless it's a deliberate plot point the POV character notices
- Before writing, confirm: what are the established facts for THIS layer?

### Continuity
- Before writing, review established data from previous chapters (numbers, facts, character states)
- If referencing a previously established value, use the SAME value
- If a value must change, the POV character must notice

### Language & Style
- Follow the story brief for language, cultural references, and stylistic conventions
- Never use meta-narrative terms (主角, 第一章, 讀者, protagonist, chapter one, reader) — characters don't know they're in a story

## Output

Output the chapter text directly. No titles, no formatting markers, no explanations.
Just the story prose, ready to read.

## Quality Criteria
- [ ] Opens with action or dialogue
- [ ] Has forward motion (reader knows/feels/worries more by the end)
- [ ] Ending makes the reader want to continue (varied approach, not formulaic)
- [ ] Characters sound different from each other
- [ ] Length matches genre conventions (from story brief)
- [ ] No meta-narrative terms
- [ ] No setting contamination between narrative layers

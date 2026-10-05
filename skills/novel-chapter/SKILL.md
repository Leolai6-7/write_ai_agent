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
- **Decision points** (optional): the character's basis, trigger, alternatives and accepted costs for consequential choices; these are author plans, not established knowledge

---

## Priorities and boundaries

The user's current instructions take priority over the story brief and chapter plan. Preserve established facts, the chosen POV, character-specific knowledge and the agreed scope of revision. A plan describes intended events, not proof that they have already happened. An unresolved conflict that would change the story's direction needs clarification, not an invented resolution.

The craft choices below are options, not acceptance gates. Choose them for the genre, narrator, chapter purpose and target length; do not force every story into literary suspense.

## Craft choices

### World texture

Let selected details convey the world when they matter to the scene. A simulated world might feel unnaturally precise; an ordinary domestic scene might benefit from plain, unadorned language. Neither is a universal style requirement. Avoid repeating a motif in every paragraph or leaking hidden facts through a limited POV.

### Clues and revelation

Choose how visible a clue should be and when to resolve it from the intended reader experience. A subtle anomaly can build unease; an obvious clue can drive an investigation or comedy. Planting and resolving a clue in the same chapter is appropriate when the plan calls for it. Do not manufacture ambiguity after a requested clear reveal.

### Scene and explanation

Use action, dialogue and sensory detail where experiencing the moment matters. Use summary, direct explanation or interior reflection where they improve clarity or pace. Cut explanations that merely repeat an already clear action, but retain information needed to understand a decision or transition.

### Pacing and chapter purpose

Allocate space by importance, not by the number of beat-sheet bullets. A key event may be a full scene, a brief exchange or a sentence of transition; several beats may share one scene. Quiet chapters can deepen a relationship, establish ordinary life or provide recovery. Check whether the chapter achieves its intended effect, not whether each scene escalates the plot.

---

## Craft Toolbox (reference as needed)

### Opening
Orient the reader in a way suited to the chapter: action, dialogue, setting or reflection. Avoid an opening that delays the intended scene without adding useful atmosphere or context.

### Ending
Choose closure, reflection, a resonant image or a cliffhanger according to the chapter's purpose. A direct emotional statement is fine when it belongs to the voice; do not force an unresolved hook.

### Dialogue
Keep speakers identifiable and consistent with their established voices. Use tags where needed for clarity; ornate tags are a choice of style, not a substitute for expressive dialogue.

### Metaphor
Prefer images that contribute to meaning, voice or atmosphere. Trim redundant metaphors unless their accumulation is an intentional feature of the requested style.

### Character voice in narration
Base interior language on this character's established voice, situation and viewpoint. Do not assign stock prose styles to personality labels such as “analytical” or “emotional.”

### Prose rhythm
Repetition is a choice, not a habit. Punctuation serves rhythm — dashes and ellipses are powerful when intentional, invisible when habitual.

### Continuity
Review established data before writing. A changed value needs an in-story cause or an authorized setting revision; the POV character need not notice every change. Do not silently treat a contradiction as new canon.

### World layer separation
Keep each narrative layer's facts and knowledge separate. A deliberate crossover needs support in the plan and text; a character noticing it does not by itself establish that it is possible.

### Language
Follow the requested language and narrative convention. Avoid accidental meta-narrative language; intentional metafiction or direct reader address is allowed when part of the chosen form.

---

## Rewrite Mode

For a revision request, including JUDGE FEEDBACK:
- Read the existing chapter and the requested changes first.
- Preserve material outside the requested scope. A request to change structure or plot authorizes that specified change, not unrelated rewrites.
- Keep voices and established facts consistent unless the user explicitly changes them.
- Shorten, expand or rearrange as the task requires; more words are not inherently better.

## Lightweight editorial pass

After drafting, read the complete chapter once before handing it to the progress-updater. Check:

- **Motivation and causality:** for consequential choices, find the passages that connect the character's information/beliefs, priorities and present trigger to this action rather than a credible alternative. Knowing the cost does not alone explain accepting it. A flawed, emotional or impulsive decision can be coherent; check its basis, not whether it was optimal or later succeeded. Missing support should be traced to planning, sources/context or expression before revising. See `docs/character-decisions.md` when this needs closer work.
- **Pacing:** does the distribution of scene, summary and pause suit the intended effect and length?
- **Readability and continuity:** are speakers, time/place changes and POV clear; do facts and requested beats fit the checked sources?

Identify concrete passages, their effect and the smallest useful correction. Make necessary local revisions within the user's scope, then reread the affected passages and their transitions. Stop when the identified problems are addressed; do not keep rewriting to pursue a generic score or a different aesthetic.

Ordinary chapters use this author self-check. For a major turning point, unresolved continuity concern or an explicit review request, the main agent may assign an independent reviewer a bounded question and relevant sources. Do not require a second agent for every chapter. If the user requested review only, return findings without modifying prose; changes in story direction outside the authorized scope require clarification.

The final prose, after this pass, is the source for the chapter log and diff. No separate per-chapter editorial report is required. Workflow receipts check artifact consistency, not literary quality.

---

## Output

For writing or revision, output the chapter prose in the requested format. Keep editorial notes out of the manuscript. If an unresolved issue prevents completion, report it separately instead of hiding it in the story.

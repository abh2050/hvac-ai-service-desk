---
name: showcase
description: Build the cinematic GitHub Pages showcase (docs/index.html) and README trailer for Uptime Desk, using Higgsfield media and brag assets. Run at Gate 6, after the brag skill, when gate reports hold real numbers.
---

# showcase

Provided by Abhishek Shah on 2026-10-22. Run it at Gate 6, after `brag`. Project-specific notes:
- The "Bragg skill" and "Bragg folder" in the spec below mean this repo's `brag` skill and its outputs in `video/out/` and the Playwright captures.
- Every number comes from `reports/gate-*.json` and carries its category (ground truth, measured, or not validated). Lab, field, and simulated results stay apart. Dispatch results are scenario model results.
- The project's own writing rules (README, reports, UI copy) also apply: no em or en dashes in prose.
- `docs/` also holds `ai-region-preferences.md` and `copilot.md`. Keep them; GitHub Pages serves `docs/index.html`.
- Check the Higgsfield balance and report the storyboard cost estimate before generating. Ask before any spend over the agreed budget.


# System prompt: cinematic project showcase for GitHub

You build the public showcase for one of Abhishek Shah's portfolio projects. The showcase has two parts. The primary part is a GitHub Pages site at docs/index.html with motion graphics, illustrated process scenes, and video. The secondary part is the repository README.md, which works as a trailer and links to the site. The reader is a hiring manager or technical lead. Within the first ten seconds, that reader must feel the problem. Within two minutes, that reader must understand how the system works and trust the engineering.

## Inputs you receive
1. The project name and repository URL.
2. The business problem and its industry.
3. The architecture, data sources, models, and services.
4. Evaluation results, latency, cost figures, and known limitations.
5. The target role or company, if one exists.
6. A folder of images and videos produced by the Bragg skill.
7. Access to the Higgsfield API for image generation, image to video, upscaling, and background removal.

If an input is missing, write a visible placeholder such as [ADD: recall on held out set] and continue. Never invent a metric, a customer, a quote, or a result.

## Step 1: Write the story first
Write all page copy before generating any media. Media serves the story, so the story must exist first. Follow the section order in Step 4 and the writing rules at the end.

## Step 2: Build the storyboard
Create storyboard.md with one row per visual beat. Each row names the section, the beat in one sentence, the asset type (still, image to video clip, motion graphic, diagram, or Bragg asset), the duration, and the source (Higgsfield, Bragg folder, or code). Plan between eight and fourteen beats for the whole page. Every beat must show a step of the process or a moment in the persona's day. Reject any beat that only decorates.

Map the beats this way:
1. Hero: one looping cinematic clip of the persona in the work environment.
2. Scene: one or two stills that set the place, the time, and the pressure.
3. Before: a short clip or a sequence of stills that shows the frictions physically.
4. After: an illustrated walkthrough where each process step gets its own image to video clip.
5. Workflow: an animated diagram that draws itself as the reader scrolls.
6. Feedback loop: an animated loop diagram with data pulses moving along the edges.
7. Architecture: an animated architecture diagram in the deep dive.
8. Close: one clip that returns to the persona with the problem resolved.

## Step 3: Generate media
### Visual identity
1. Write one style frame prompt that fixes the palette, lighting, lens, texture, and illustration style. Reuse that exact block in every Higgsfield prompt.
2. Generate the persona once and register it as a reference element. Pass that reference into every later image that shows the persona, so the character stays consistent.
3. Use a restrained palette of one dark base, one neutral, and one accent color. Match the page CSS to the same colors.
4. Never show real logos, real people, or copyrighted characters.

### Higgsfield workflow
1. Check the credit balance before generating. Estimate the total cost of the storyboard and report it before spending more than the agreed budget.
2. Generate each still with the style frame block plus the beat description.
3. Review each still against the storyboard row. Regenerate if the action, the character, or the environment is wrong.
4. Convert approved stills to video with image to video. Keep clips between four and eight seconds. Use slow, purposeful camera moves such as a push in, a pan across equipment, or a rack focus to a screen. Avoid fast cuts and random motion.
5. Upscale only the hero clip and the hero still.
6. Remove backgrounds on any UI or device renders that sit over a page section.

### Bragg assets
1. Inventory the Bragg folder and match each asset to a storyboard row.
2. Prefer Bragg assets for real screenshots, real dashboards, and real terminal output, because they prove the system exists.
3. Use Higgsfield assets for illustrated scenes and environments.
4. Alternate real and illustrated media so the page moves between story and proof.

### Encoding and performance
1. Export every clip as MP4 with H.264 and as WebM. Keep each clip under 4 MB and the hero under 8 MB.
2. Strip audio from all loops.
3. Export a poster frame as WebP for every clip.
4. Export a GIF under 5 MB of the hero and of the After walkthrough for the README.
5. Keep the full page under 40 MB. Lazy load every video below the fold.

## Step 4: Page structure
### 1. Hero
Show the hero clip full width, muted and looping. Overlay the project name as the H1 and one sentence that names who the system helps and what it lets them do. Add one button to the repository and one button that scrolls to the walkthrough.

### 2. Scene
Open on one illustrative persona in a specific place at a specific moment. Give the persona a role, not a name. Do not mention AI or the product. Write 80 to 150 words beside the scene stills. Add an italic note that the scenario is illustrative.

### 3. Before
Describe three to five concrete frictions with time, cost, or risk attached. Pair the text with the Before clip. Use mundane, physical failures from the industry, because small details make the problem believable.

### 4. After: the illustrated walkthrough
Replay the scene with the system in place. Name the system once. Build this section as a scroll driven sequence. Each process step gets a sticky panel where the clip plays on one side and two or three sentences explain the step on the other. Each panel shows what the persona sees, what the system does, and what the persona decides. Keep the persona in control.

### 5. Why it matters
Show the stakes as large animated counters that count up when they enter the viewport. Cite every external number with a link. Write one paragraph that connects the stakes to the target role.

### 6. Workflow diagram
Write the workflow in Mermaid, render it to SVG at build time, and animate it so each edge draws in sequence as the reader scrolls. Highlight the human decision node in the accent color. Keep it to twelve nodes or fewer with plain word labels.

### 7. Feedback loop diagram
Render the loop as SVG with small pulses traveling along the edges to show data returning into retrieval, evaluation, or retraining. Skip this section only if no loop exists, and say so in one sentence.

### 8. Technical deep dive
Change the visual tone here to a cleaner, quieter layout so the engineer can read. Use these subsections in order:
1. Architecture: the animated architecture diagram with real service names. Group components by layer, and reveal each layer on scroll. Pair it with a short explanation of each component and why it was chosen. Show the static Mermaid source in a collapsible block.
2. Data: the sources, their size, the cleaning steps, and what was excluded.
3. Models and agents: the models, prompts, tools, and how the agent chooses its next action. Show a Bragg screenshot or terminal capture of a real run.
4. Evaluation: the metrics, the test set, the baseline, and the results in a table. Include at least one weak result.
5. Performance and cost: p50 and p95 latency, and cost per run or per month.
6. Guardrails and failure modes: what fails, how the system detects it, and what the user sees.
7. Deployment: the infrastructure as code tool, the region, and the deploy steps. AWS projects use the awsnew profile and us-east-2.
8. Run it yourself: numbered steps from clone to first result with exact commands.

### 9. What I would build next
List two to four next steps. Tie each one to a limitation from the evaluation.

### 10. Close
Play the closing clip. Return to the persona in two or three sentences and show how the day ends. End on the concrete result.

### 11. About the builder
Show Abhishek Shah's name, the portfolio link (https://abh2050.github.io/abhishek-shah-portfolio/), and github.com/abh2050.

## Step 5: Build the site
1. Write docs/index.html as one HTML file with inline CSS and JavaScript. Store media in docs/media/.
2. Load GSAP with ScrollTrigger from cdnjs.cloudflare.com for scroll animations. Load Mermaid from cdn.jsdelivr.net only if diagrams render in the browser.
3. Use a clean template with generous whitespace, one serif or display face for headings, one sans face for body text, and a twelve column grid that collapses to one column on phones.
4. Alternate full width media sections with split text and media sections so the rhythm changes every screen.
5. Respect prefers-reduced-motion. When it is set, show poster frames, disable scroll animations, and show diagrams fully drawn.
6. Give every image alt text and every video a short text description beside it.
7. Make the layout work at 375 pixels wide with no horizontal scroll.

## Step 6: Build the README trailer
1. Open with the hero GIF and a link to the GitHub Pages site.
2. Include the Scene, Before, and After sections as text with the walkthrough GIF.
3. Include the Mermaid workflow and architecture diagrams, which GitHub renders natively.
4. Include the full technical deep dive, the next steps, and the builder section.
5. Embed one MP4 by uploading it to a GitHub issue or release and linking the resulting user attachments URL, because GitHub plays those inline.

## Writing rules
1. Every sentence has an explicit subject and a main verb that does work.
2. Write one idea per sentence.
3. Break noun stacks of three or more nouns with prepositions or split the sentence.
4. Prefer verbs over nominalizations.
5. Do not preannounce counts such as "three reasons this matters."
6. Use a colon only when the clause before it already names what follows.
7. Do not define anything by contrast with a weaker alternative.
8. Do not end paragraphs with aphorisms or grand statements.
9. List only the number of items that actually exist.
10. Do not use these words or phrases: delve, crucial, pivotal, tapestry, foundational, robust, seamless, landscape, realm, leverage as a verb, unlock, harness as a verb, "here's the thing," "it's not X, it's Y."
11. Do not use emojis or decorative symbols.
12. Write so a reader with no project context can say what happens and who does it.

## Quality check before delivery
1. Confirm the Scene and Before sections never mention AI, models, or cloud services.
2. Confirm every storyboard beat shows a process step or a moment in the persona's day.
3. Confirm the persona looks the same in every generated image and clip.
4. Confirm every number has a source or comes from the project's own evaluation.
5. Load the site at phone width and desktop width, scroll the full page, and confirm every animation triggers once and every video plays.
6. Confirm the page works with reduced motion turned on.
7. Confirm total media size stays under budget.
8. Read each sentence, locate its verb, and rewrite any sentence that has none.
9. Confirm the close returns to the same persona as the scene.

## Output
Return storyboard.md, docs/index.html, the docs/media/ folder, README.md, and a short report listing Higgsfield credits spent and any placeholders left to fill.

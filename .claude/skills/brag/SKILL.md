---
name: brag
description: Produce a 2 minute explainer video for Uptime Desk from the hosted app, the draw.io diagrams, and the recorded gate reports.
---

# brag

Make a 1080p explainer video that runs between 1:50 and 2:00. Every number on screen or in the narration must come from a file in `reports/`, and every number must carry its category (ground truth, measured, or not validated).

## Steps
1. Read `reports/gate-*.json`, `README.md`, and the PNG exports in `diagrams/`. Build `video/facts.json` with each number, its category, and its source file.
2. Write `video/script.md` at about 280 words, following this scene plan.
   1. From 0:00 to 0:12, the hook. An air handler fault hits a critical building, and the question is who fixes it and how fast.
   2. From 0:12 to 0:25, the problem. Sensor alarms, manuals, dispatch, and technicians live in separate systems.
   3. From 0:25 to 0:50, the architecture. Show `aws-architecture.png` and highlight each numbered flow in turn.
   4. From 0:50 to 1:35, the live demo. Launch a scenario, watch the pipeline, open a citation, approve the order, view the dispatch, and ask the technician assistant a question. Show one decision policy case, such as an abstention or a denied request.
   5. From 1:35 to 1:52, the results. Show each gate's AI result against its baseline, including any gate the baseline won. State that the data is from lab and field tests.
   6. From 1:52 to 2:00, the close. Show the repo link, the evidence page link, and the portfolio link https://abh2050.github.io/abhishek-shah-portfolio/.
3. Generate the narration with the ElevenLabs text to speech API, one MP3 per scene. Read the API key from SSM Parameter Store at `/uptime-desk/elevenlabs/api-key` (profile `awsnew`, region `us-east-2`) and never write it to disk or git. Measure each clip with ffprobe and fit the scene lengths to the clips. Regenerate a clip only when its script text changed.
4. Capture the demo with Playwright against the hosted Amplify URL at 1920x1080 using `recordVideo`. Script the clicks for each scene and sign in with the demo users stored in SSM. Run `demo-up.sh` before capture and `demo-down.sh` after.
5. Compose the video with Remotion in `video/`. Use title cards, the diagram scene with animated highlights, the demo clips, number overlays read from `facts.json`, and captions burned in from the script.
6. Render `video/out/uptime-desk-explainer.mp4` at 30 fps. Normalize the audio to minus 16 LUFS with the ffmpeg loudnorm filter. Confirm the duration with ffprobe.
7. Write `video/out/captions.srt` and a thumbnail at `video/out/thumbnail.png`.
8. Write `video/out/linkedin-post.md` under 3,000 characters, including at most three hashtags. Use complete sentences that a reader with no context can follow, and describe results only in the categories they belong to.
9. Extract frames at 0:05, 0:30, 1:00, 1:40, and 1:55 with ffmpeg and view them. Fix any frame with unreadable text or a missing number.

## Rules
1. Use no company logos except AWS service icons, and use no stock footage.
2. Do not name any prospective employer on screen.
3. Never present a scenario model result or a not validated outcome as field savings.
4. Re-run this skill whenever a number in `facts.json` changes.

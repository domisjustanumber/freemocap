---
name: commit-files
description: Use this skill before each commit, and before you add a recording, a camera frame, an image or another large file to the repository.
---

# Commit files

This skill uses ASD-STE100 Simplified Technical English.
The rules of [`AGENTS.md`](../../../AGENTS.md#8-private-data) also apply.

## Camera recordings and camera frames

- Do not commit a camera recording (video or audio) or a camera frame (a still image or a raw frame
  from a camera). These files are large, and they can contain private information.
- The one exception is a golden reference file. Its path starts with an item of `GOLDEN_PATHS` in
  `tools/check_camera_media.py`.
- A screenshot that shows a camera image is a camera frame. A chart, a diagram or a UI screenshot
  that shows no camera image is not a camera frame.
- A results folder can hold summaries, for example JSON, CSV and Markdown files. It must not hold
  the media.
- Keep large media outside the repository. To show a camera frame to the user, give its local path.

## Before the commit

1. Run `git diff --cached --name-only`. Examine each path.
2. Run `uv run python tools/check_camera_media.py`. It checks the files of the commit. It must print
   no refusal line. For each reminder line, open the image and make sure that it shows no camera
   image.
3. Commit only the files of your change: `git add <path>`, then `git commit -- <path>`.

## A recording or a frame is already committed

- Stop. Tell the user the path and the commit.
  `uv run python tools/check_camera_media.py --all` lists each tracked file that the rule refuses.
- Do not delete the file, rewrite the history or force-push without the approval of the user.

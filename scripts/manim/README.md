# Kairos flow — Manim explainer

Optional programmatic animation using [3Blue1Brown's ManimGL](https://github.com/3b1b/manim) (not the community `manim` package).

## Install

```bash
pip install manimgl
# macOS also needs: brew install ffmpeg
# Optional LaTeX for math labels
```

## Render

From repo root:

```bash
manimgl scripts/manim/kairos_flow.py KairosFlow
# Write to file:
manimgl scripts/manim/kairos_flow.py KairosFlow -w
```

## What it shows

A simplified two-track diagram:

1. **Prep track** — X → enrich → research → embed → cluster (MongoDB)
2. **Heartbeat track** — context → rank → gates → digest → inbox → feedback → bandit

This mirrors the interactive walkthrough at `/walkthrough`.

## Note

ManimGL (`manimgl`) and Manim Community (`manim`) are different packages. This scene targets **manimgl** per the 3b1b repo README.

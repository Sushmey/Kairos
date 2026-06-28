"""Kairos pipeline explainer — render with manimgl (3b1b/manim).

  manimgl scripts/manim/kairos_flow.py KairosFlow
  manimgl scripts/manim/kairos_flow.py KairosFlow -w   # write video
"""

from manimlib import *


class KairosFlow(Scene):
    """Animated prep + heartbeat overview for new engineers."""

    def construct(self):
        title = Text("Kairos: when to interrupt", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.5)

        prep_labels = ["X sync", "Enrich", "Research", "Embed", "Cluster"]
        run_labels = ["Context", "Rank", "Gates", "Digest", "Inbox", "Bandit"]

        prep_row = self._make_row(prep_labels, color=BLUE_C, y=1.2)
        run_row = self._make_row(run_labels, color=GREEN_C, y=-0.8)

        prep_caption = Text("Prep (batch)", font_size=28, color=BLUE_C).next_to(prep_row, LEFT, buff=0.6)
        run_caption = Text("Heartbeat (runtime)", font_size=28, color=GREEN_C).next_to(run_row, LEFT, buff=0.6)

        self.play(FadeIn(prep_caption), FadeIn(run_caption))
        self.play(
            LaggedStart(*[FadeIn(m, shift=RIGHT * 0.2) for m in prep_row], lag_ratio=0.15),
            LaggedStart(*[FadeIn(m, shift=RIGHT * 0.2) for m in run_row], lag_ratio=0.15),
            run_time=2,
        )

        silence = Text("Silence is the default — KAIROS_OK", font_size=32, color=GREY_B)
        silence.next_to(run_row, DOWN, buff=0.8)
        self.play(Write(silence))
        self.wait(2)

    def _make_row(self, labels: list[str], color, y: float):
        boxes = VGroup()
        for label in labels:
            rect = Rectangle(width=1.6, height=0.7, stroke_color=color, fill_color=BLACK, fill_opacity=0.2)
            text = Text(label, font_size=20)
            text.move_to(rect)
            box = VGroup(rect, text)
            boxes.add(box)
        boxes.arrange(RIGHT, buff=0.25)
        boxes.move_to(ORIGIN + UP * y)
        # arrows between boxes
        for i in range(len(boxes) - 1):
            arr = Arrow(
                boxes[i].get_right(),
                boxes[i + 1].get_left(),
                buff=0.08,
                stroke_width=2,
                color=color,
            )
            boxes.add(arr)
        return boxes

"""Canvas that shows camera frames scaled to fit, or a "Camera Off" placeholder."""

from __future__ import annotations

import tkinter as tk

import cv2
import numpy as np
from PIL import ImageTk

from gui.theme import FONT_UI, PALETTE, font_family
from utils.helpers import fit_within, frame_to_pil


class VideoCanvas(tk.Canvas):
    """Aspect-ratio-preserving video display."""

    def __init__(
        self, parent: tk.Misc, placeholder_text: str = "Camera Off", **kwargs: object
    ) -> None:
        kwargs.setdefault("bg", PALETTE["canvas"])
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)  # type: ignore[arg-type]
        self._placeholder_text = placeholder_text
        self._photo: ImageTk.PhotoImage | None = None
        self._image_id: int | None = None
        self._has_frame = False
        self._displayed: tuple[int, int] = (0, 0)
        self.bind("<Configure>", self._on_resize)
        self.show_placeholder()

    @property
    def has_frame(self) -> bool:
        """True while a camera frame is on screen."""
        return self._has_frame

    @property
    def displayed_size(self) -> tuple[int, int]:
        """Size in pixels of the frame as drawn."""
        return self._displayed

    def _box(self) -> tuple[int, int]:
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1:
            width = int(self["width"])
        if height <= 1:
            height = int(self["height"])
        return max(1, width), max(1, height)

    def show_frame(self, frame_bgr: np.ndarray) -> None:
        """Draw a BGR frame scaled to fit the canvas."""
        box_w, box_h = self._box()
        src_h, src_w = frame_bgr.shape[:2]
        target_w, target_h = fit_within(src_w, src_h, box_w, box_h)
        interpolation = cv2.INTER_AREA if target_w < src_w else cv2.INTER_LINEAR
        resized = cv2.resize(frame_bgr, (target_w, target_h), interpolation=interpolation)
        self._photo = ImageTk.PhotoImage(frame_to_pil(resized), master=self)
        center = (box_w // 2, box_h // 2)
        if self._image_id is None:
            self.delete("placeholder")
            self._image_id = self.create_image(*center, image=self._photo, anchor="center")
        else:
            self.itemconfig(self._image_id, image=self._photo)
            self.coords(self._image_id, *center)
        self._has_frame = True
        self._displayed = (target_w, target_h)

    def show_placeholder(self, text: str | None = None) -> None:
        """Clear the frame and show a centred message."""
        if text is not None:
            self._placeholder_text = text
        self.delete("all")
        self._image_id = None
        self._photo = None
        self._has_frame = False
        self._displayed = (0, 0)
        box_w, box_h = self._box()
        self.create_text(
            box_w // 2,
            box_h // 2 - 14,
            text=self._placeholder_text,
            fill=PALETTE["muted"],
            font=(font_family(), 22, "bold"),
            tags="placeholder",
        )
        self.create_text(
            box_w // 2,
            box_h // 2 + 18,
            text="Press L or click Launch Camera",
            fill=PALETTE["border"],
            font=FONT_UI,
            tags="placeholder",
        )

    def _on_resize(self, _event: tk.Event) -> None:
        if not self._has_frame:
            self.show_placeholder()

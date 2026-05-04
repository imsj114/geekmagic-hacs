"""Minimal pure-Python flexbox replacement for the `stretchable` library.

This module mirrors the small subset of stretchable's API that the
geekmagic widgets actually use:

- single-axis flex (row or column), single level of children
- ``flex_grow`` to distribute remaining main-axis space equally
- ``justify_content``: START, CENTER, END, SPACE_BETWEEN, SPACE_AROUND
- ``align_items``: START, CENTER, END, STRETCH
- pixel sizes, ``AUTO`` sentinel, and ``N * PCT`` percentages

It exists because ``stretchable`` (PyO3) does not ship Python 3.14 wheels,
which broke the integration on Home Assistant 2026.5. Implementing the
narrow surface in pure Python removes the C-extension dependency.

Unsupported flex features (wrap, align-content, padding/border/margin on
nodes, min/max sizes, flex_shrink, flex_basis, nested trees) are out of
scope; passing them raises ``NotImplementedError`` so future callers fail
loudly instead of silently miscomputing layouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class FlexDirection(Enum):
    ROW = auto()
    COLUMN = auto()


class JustifyContent(Enum):
    START = auto()
    CENTER = auto()
    END = auto()
    SPACE_BETWEEN = auto()
    SPACE_AROUND = auto()


class AlignItems(Enum):
    START = auto()
    CENTER = auto()
    END = auto()
    STRETCH = auto()


class Edge(Enum):
    CONTENT = auto()


class _Auto:
    def __repr__(self) -> str:
        return "AUTO"


AUTO = _Auto()


@dataclass(frozen=True)
class _Percent:
    value: float


class _Pct:
    def __rmul__(self, n: float) -> _Percent:
        return _Percent(float(n))

    def __repr__(self) -> str:
        return "PCT"


PCT = _Pct()


@dataclass(frozen=True)
class _Box:
    x: float
    y: float
    width: float
    height: float


def _resolve(spec: object, container: float) -> float | None:
    """Return the resolved pixel size, or ``None`` for AUTO."""
    if spec is AUTO or isinstance(spec, _Auto):
        return None
    if isinstance(spec, _Percent):
        return spec.value / 100.0 * container
    if isinstance(spec, (int, float)):
        return float(spec)
    raise TypeError(f"unsupported size spec: {spec!r}")


class Node:
    def __init__(
        self,
        *,
        flex_direction: FlexDirection = FlexDirection.ROW,
        justify_content: JustifyContent = JustifyContent.START,
        align_items: AlignItems = AlignItems.STRETCH,
        gap: float = 0,
        size: tuple[object, object] | None = None,
        key: str | None = None,
        flex_grow: float = 0.0,
        **unsupported: object,
    ) -> None:
        if unsupported:
            raise NotImplementedError(f"_flex.Node does not support: {sorted(unsupported)}")
        self.flex_direction = flex_direction
        self.justify_content = justify_content
        self.align_items = align_items
        self.gap = float(gap)
        self.size = size
        self.key = key
        self.flex_grow = float(flex_grow)
        self.children: list[Node] = []
        self._x = 0.0
        self._y = 0.0
        self._width = 0.0
        self._height = 0.0

    def add(self, child: Node) -> Node:
        self.children.append(child)
        return self

    def find(self, path: str) -> Node:
        if not path.startswith("/"):
            raise ValueError(f"path must start with '/': {path!r}")
        segments = [s for s in path.split("/") if s]
        node: Node = self
        for seg in segments:
            for c in node.children:
                if c.key == seg:
                    node = c
                    break
            else:
                raise KeyError(f"no child with key {seg!r} under {node.key!r}")
        return node

    def get_box(self, edge: Edge = Edge.CONTENT) -> _Box:
        del edge  # only one edge is supported
        return _Box(self._x, self._y, self._width, self._height)

    def compute_layout(self) -> None:
        if self.size is None:
            raise ValueError("root node must have an explicit size")
        root_w = _resolve(self.size[0], 0.0)
        root_h = _resolve(self.size[1], 0.0)
        if root_w is None or root_h is None:
            raise ValueError("root node size must be concrete pixels")
        self._x = 0.0
        self._y = 0.0
        self._width = root_w
        self._height = root_h
        if not self.children:
            return

        is_row = self.flex_direction is FlexDirection.ROW
        container_main = root_w if is_row else root_h
        container_cross = root_h if is_row else root_w

        # Resolve each child's main-axis base size (AUTO -> 0) and cross-axis size.
        base_main: list[float] = []
        cross_size: list[float] = []
        for c in self.children:
            if c.size is None:
                base_main.append(0.0)
                cross_size.append(0.0)
                continue
            main_spec = c.size[0] if is_row else c.size[1]
            cross_spec = c.size[1] if is_row else c.size[0]
            m = _resolve(main_spec, container_main)
            base_main.append(0.0 if m is None else m)
            cs = _resolve(cross_spec, container_cross)
            if cs is None:
                cs = container_cross if self.align_items is AlignItems.STRETCH else 0.0
            cross_size.append(cs)

        n = len(self.children)
        total_gap = self.gap * max(0, n - 1)
        total_grow = sum(c.flex_grow for c in self.children)
        free = container_main - sum(base_main) - total_gap

        main_size: list[float] = list(base_main)
        if total_grow > 0 and free > 0:
            for i, c in enumerate(self.children):
                if c.flex_grow > 0:
                    main_size[i] = base_main[i] + free * c.flex_grow / total_grow
        elif free < 0:
            # Overflow: shrink all children proportionally so the total fits.
            # CSS flex_shrink defaults to 1; we apply a uniform factor here,
            # which is enough for the layouts this codebase uses (single
            # level of children with no min-size constraints) and prevents
            # siblings from being pushed off the end of the container.
            available = max(0.0, container_main - total_gap)
            total_base = sum(base_main)
            if total_base > 0:
                factor = available / total_base
                main_size = [b * factor for b in base_main]

        used = sum(main_size) + total_gap
        extra = container_main - used
        if self.justify_content is JustifyContent.START:
            offset, extra_gap = 0.0, 0.0
        elif self.justify_content is JustifyContent.END:
            offset, extra_gap = extra, 0.0
        elif self.justify_content is JustifyContent.CENTER:
            offset, extra_gap = extra / 2.0, 0.0
        elif self.justify_content is JustifyContent.SPACE_BETWEEN:
            offset = 0.0
            extra_gap = extra / (n - 1) if n > 1 else 0.0
        elif self.justify_content is JustifyContent.SPACE_AROUND:
            extra_gap = extra / n if n > 0 else 0.0
            offset = extra_gap / 2.0
        else:  # pragma: no cover - exhaustive enum
            offset, extra_gap = 0.0, 0.0

        cursor = offset
        for i, c in enumerate(self.children):
            main_pos = cursor
            cs = cross_size[i]
            if self.align_items is AlignItems.STRETCH:
                cs = container_cross
                cross_pos = 0.0
            elif self.align_items is AlignItems.START:
                cross_pos = 0.0
            elif self.align_items is AlignItems.END:
                cross_pos = container_cross - cs
            else:  # CENTER
                cross_pos = (container_cross - cs) / 2.0

            if is_row:
                c._set_box(main_pos, cross_pos, main_size[i], cs)
            else:
                c._set_box(cross_pos, main_pos, cs, main_size[i])

            cursor += main_size[i] + self.gap + extra_gap

    def _set_box(self, x: float, y: float, width: float, height: float) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height


__all__ = [
    "AUTO",
    "PCT",
    "AlignItems",
    "Edge",
    "FlexDirection",
    "JustifyContent",
    "Node",
]

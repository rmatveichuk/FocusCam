"""
overlay_utils.py – Viewport composition grid overlays for 3ds Max.

Draws Rule-of-Thirds, Golden-Ratio, Diagonal, and Fibonacci-Spiral guides
on top of the active camera viewport using the GW (graphics window) API
through a registered redraw-views callback.

Usage:
    from overlay_utils import OverlayManager, OVERLAY_THIRDS, OVERLAY_GOLDEN

    mgr = OverlayManager()
    mgr.set_target_camera(some_camera_node)
    mgr.toggle_overlay(OVERLAY_THIRDS)
    mgr.register_callback()
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# pymxs import guard
# ---------------------------------------------------------------------------
try:
    import pymxs
    from pymxs import runtime as rt
except ImportError:
    pymxs = None  # type: ignore[assignment]
    rt = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Overlay type constants
# ---------------------------------------------------------------------------
OVERLAY_THIRDS: int = 1
OVERLAY_GOLDEN: int = 2
OVERLAY_DIAGONALS: int = 3
OVERLAY_SPIRAL: int = 4

# Golden ratio constant
PHI: float = (1.0 + math.sqrt(5.0)) / 2.0  # ≈ 1.6180339887
PHI_INV: float = 1.0 / PHI                   # ≈ 0.6180339887

# ---------------------------------------------------------------------------
# Grid Calculation Functions
# Each returns a list of line segments as (x1, y1, x2, y2) tuples.
# ---------------------------------------------------------------------------

LineSegment = Tuple[int, int, int, int]


def calc_thirds(width: int, height: int) -> List[LineSegment]:
    """Return 4 line segments dividing the viewport into a 3×3 grid.

    Two vertical and two horizontal lines placed at 1/3 and 2/3 of each axis.
    """
    x1 = int(round(width / 3.0))
    x2 = int(round(2.0 * width / 3.0))
    y1 = int(round(height / 3.0))
    y2 = int(round(2.0 * height / 3.0))

    return [
        # Vertical lines
        (x1, 0, x1, height),
        (x2, 0, x2, height),
        # Horizontal lines
        (0, y1, width, y1),
        (0, y2, width, y2),
    ]


def calc_golden_ratio(width: int, height: int) -> List[LineSegment]:
    """Return 4 line segments at golden-ratio (phi ≈ 0.618) positions.

    Two vertical and two horizontal lines placed symmetrically so that the
    smaller partition is phi (~61.8 %) of the larger one.
    """
    # Distance from left / top edge to the nearer golden line
    gx = int(round(width * PHI_INV))
    gy = int(round(height * PHI_INV))
    # Mirror positions
    gx2 = width - gx
    gy2 = height - gy

    return [
        # Vertical lines (ensure smaller value first for consistency)
        (min(gx, gx2), 0, min(gx, gx2), height),
        (max(gx, gx2), 0, max(gx, gx2), height),
        # Horizontal lines
        (0, min(gy, gy2), width, min(gy, gy2)),
        (0, max(gy, gy2), width, max(gy, gy2)),
    ]


def calc_diagonals(width: int, height: int) -> List[LineSegment]:
    """Return 4 diagonal line segments from corners through golden-ratio points.

    Each diagonal starts at a corner and passes through the nearest
    golden-ratio intersection point, ending at the opposite edge.
    """
    gx1 = int(round(width * (1.0 - PHI_INV)))
    gx2 = int(round(width * PHI_INV))
    gy1 = int(round(height * (1.0 - PHI_INV)))
    gy2 = int(round(height * PHI_INV))

    return [
        # Top-left corner → bottom-right direction through golden point
        (0, 0, width, height),
        # Top-right corner → bottom-left direction through golden point
        (width, 0, 0, height),
        # Bottom-left → diagonal toward golden intersection (top-right region)
        (0, height, gx2, 0),
        # Top-left → diagonal toward golden intersection (bottom-right region)
        (0, 0, gx2, height),
    ]


def calc_spiral(
    width: int,
    height: int,
    num_arc_segments: int = 24,
    max_iterations: int = 9,
) -> List[Tuple[int, int]]:
    """Return polyline points approximating a Fibonacci / golden spiral.

    The spiral is constructed from successive quarter-circle arcs inside
    shrinking golden rectangles.  Each arc is tessellated into
    *num_arc_segments* small line segments for smooth rendering.

    Parameters
    ----------
    width, height:
        Viewport dimensions in pixels.
    num_arc_segments:
        Number of straight segments used to approximate each 90° arc.
    max_iterations:
        How many quarter-turn arcs to compute (more = tighter spiral).

    Returns
    -------
    A flat list of (x, y) integer tuples forming a continuous polyline.
    """
    points: List[Tuple[int, int]] = []

    # Working rectangle (floating-point for precision)
    rx: float = 0.0
    ry: float = 0.0
    rw: float = float(width)
    rh: float = float(height)

    for i in range(max_iterations):
        # Determine the arc center and radius based on which quadrant we are
        # subdividing.  The sequence cycles through four orientations.
        quadrant = i % 4

        if quadrant == 0:
            # Arc from bottom-left to top-right of the square on the right
            sq = rw - rw / PHI
            cx = rx + rw - sq
            cy = ry + rh
            start_angle = -math.pi / 2.0
            radius = rh
        elif quadrant == 1:
            # Arc at bottom of rectangle
            sq = rh - rh / PHI
            cx = rx
            cy = ry + rh - sq
            start_angle = 0.0
            radius = rw
        elif quadrant == 2:
            # Arc at left of rectangle
            sq = rw - rw / PHI
            cx = rx + sq
            cy = ry
            start_angle = math.pi / 2.0
            radius = rh
        else:
            # Arc at top of rectangle
            sq = rh - rh / PHI
            cx = rx + rw
            cy = ry + sq
            start_angle = math.pi
            radius = rw

        # Generate the arc points for this quarter turn
        for j in range(num_arc_segments + 1):
            # Sweep 90° (pi/2) per iteration
            t = j / float(num_arc_segments)
            angle = start_angle + t * (math.pi / 2.0)
            px = int(round(cx + radius * math.cos(angle)))
            py = int(round(cy + radius * math.sin(angle)))
            points.append((px, py))

        # Shrink the working rectangle for the next iteration
        if quadrant == 0:
            rw -= sq
            rx += sq  # not needed visually but keeps rect correct
            # Actually: subdivide by removing the right square
            new_w = rw * PHI_INV
            rx = rx  # left edge stays
            rw = rw  # will be recalculated below
        elif quadrant == 1:
            new_h = rh * PHI_INV
        elif quadrant == 2:
            new_w = rw * PHI_INV
        else:
            new_h = rh * PHI_INV

        # Simpler recursive subdivision: shrink the rectangle by phi each step
        if quadrant == 0:
            new_rw = rw
            rw = rw  # keep width, reduce height
            rh = rh / PHI
            ry = ry + (rh * PHI_INV)  # shift down
        elif quadrant == 1:
            rw = rw / PHI
            # rx stays
        elif quadrant == 2:
            rh = rh / PHI
        else:
            old_rw = rw
            rw = rw / PHI
            rx = rx + old_rw - rw

    return points


def _calc_spiral_golden_rects(
    width: int,
    height: int,
    num_arc_segments: int = 32,
    num_quarter_turns: int = 8,
) -> List[Tuple[int, int]]:
    """Compute a golden-spiral polyline via successive golden-rectangle subdivision.

    This is a cleaner implementation that carefully tracks the shrinking
    rectangles and draws quarter-circle arcs whose radius equals the shorter
    side of the current golden rectangle.

    Returns a list of (x, y) pixel coordinate tuples.
    """
    points: List[Tuple[int, int]] = []

    # Ensure we work in landscape orientation for the initial rectangle.
    # The golden rectangle has aspect ratio phi:1.
    # We scale the spiral to fill the viewport as much as possible.
    rect_x: float = 0.0
    rect_y: float = 0.0
    rect_w: float = float(width)
    rect_h: float = float(height)

    for turn in range(num_quarter_turns):
        orientation = turn % 4
        # The "square" side is the shorter dimension of the current rect
        # In a perfect golden rectangle the ratio is phi, but the viewport
        # may not be exactly phi, so we just take min(rect_w, rect_h) for
        # the first cut then use the golden ratio for subsequent ones.

        if orientation == 0:
            # Square on the RIGHT side, arc sweeps from bottom to top
            sq = rect_w / PHI if rect_w > rect_h else rect_h
            sq = min(rect_w, rect_h) if turn == 0 else rect_w - rect_w / PHI
            sq = rect_h  # square side = height
            # Arc center: bottom-right of the square
            cx = rect_x + rect_w
            cy = rect_y + rect_h
            start_angle = math.pi          # 180°
            end_angle = 3.0 * math.pi / 2.0  # 270°
            radius = sq
            # After this, remove the right square
            rect_x = rect_x
            rect_w = rect_w - sq

        elif orientation == 1:
            # Square on the BOTTOM, arc sweeps from right to left
            sq = rect_w  # square side = width of remaining rect
            cx = rect_x
            cy = rect_y + rect_h
            start_angle = 3.0 * math.pi / 2.0  # 270°
            end_angle = 2.0 * math.pi           # 360°
            radius = sq
            rect_h = rect_h - sq

        elif orientation == 2:
            # Square on the LEFT side, arc sweeps from top to bottom
            sq = rect_h
            cx = rect_x
            cy = rect_y
            start_angle = 0.0
            end_angle = math.pi / 2.0
            radius = sq
            rect_x = rect_x + sq
            rect_w = rect_w - sq

        else:
            # Square on the TOP, arc sweeps from left to right
            sq = rect_w
            cx = rect_x + rect_w
            cy = rect_y
            start_angle = math.pi / 2.0
            end_angle = math.pi
            radius = sq
            rect_y = rect_y + sq
            rect_h = rect_h - sq

        # Guard against degenerate rectangles
        if radius <= 1.0:
            break

        # Tessellate the quarter-circle arc
        for j in range(num_arc_segments + 1):
            t = j / float(num_arc_segments)
            angle = start_angle + t * (end_angle - start_angle)
            px = int(round(cx + radius * math.cos(angle)))
            py = int(round(cy + radius * math.sin(angle)))
            points.append((px, py))

    return points


# ---------------------------------------------------------------------------
# Overlay Manager
# ---------------------------------------------------------------------------

# Global reference so the MAXScript callback can reach the manager instance
_global_manager: Optional["OverlayManager"] = None


def _redraw_callback_entry() -> None:
    """Entry point invoked by the MAXScript redraw-views callback."""
    if _global_manager is not None:
        _global_manager.draw_overlays()


class OverlayManager:
    """Manages viewport composition overlays and the redraw callback lifecycle.

    Attributes
    ----------
    active_overlays : set[int]
        Currently enabled overlay types (use the ``OVERLAY_*`` constants).
    target_camera_node : object | None
        The 3ds Max camera node for which overlays should be drawn.
        If *None* or the viewport is not looking through this camera,
        nothing is drawn.
    line_color : tuple[int, int, int]
        RGB colour used for overlay lines (0-255 per channel).
    """

    def __init__(
        self,
        line_color: Tuple[int, int, int] = (200, 200, 200),
    ) -> None:
        self.active_overlays: set[int] = set()
        self.target_camera_node: object | None = None
        self.line_color: Tuple[int, int, int] = line_color
        self._callback_registered: bool = False
        self._callback_name: str = "focusOverlayRedrawCB"

    # -- public API ---------------------------------------------------------

    def toggle_overlay(self, overlay_type: int) -> None:
        """Add *overlay_type* to the active set if absent, otherwise remove it."""
        if overlay_type in self.active_overlays:
            self.active_overlays.discard(overlay_type)
        else:
            self.active_overlays.add(overlay_type)

    def is_active(self, overlay_type: int) -> bool:
        """Return *True* if *overlay_type* is currently enabled."""
        return overlay_type in self.active_overlays

    def set_target_camera(self, camera_node: object | None) -> None:
        """Set the camera node whose viewport will receive overlays."""
        self.target_camera_node = camera_node

    # -- callback registration / removal ------------------------------------

    def register_callback(self) -> None:
        """Register a MAXScript redraw-views callback that calls back into Python.

        The callback is a lightweight MAXScript wrapper that invokes
        :func:`_redraw_callback_entry` via ``python.execute()``.
        """
        if rt is None:
            return
        if self._callback_registered:
            return

        # Store ourselves as the global so the callback can find us
        global _global_manager
        _global_manager = self

        # Always try to unregister any existing callback with this name first
        try:
            rt.execute("try(unregisterRedrawViewsCallback {})catch()".format(self._callback_name))
        except Exception:
            pass

        # Build the MAXScript callback definition.
        # We try to import from the 'Focus' package first (when installed),
        # then fall back to direct import (when running from dev folder).
        # We use a multi-line python command inside the MAXScript string.
        # Build the MAXScript callback definition.
        # We only define the function if it is undefined to prevent losing the function
        # reference, which would make unregisterRedrawViewsCallback fail.
        # The wrapper just routes to python, so it never needs to be redefined.
        mxs = (
            "global {name}\n"
            "if {name} == undefined do (\n"
            "    fn {name} = (\n"
            "        python.execute \"try:\\n    from Focus.overlay_utils import _redraw_callback_entry\\nexcept ImportError:\\n    from overlay_utils import _redraw_callback_entry\\n_redraw_callback_entry()\"\n"
            "    )\n"
            ")\n"
            "registerRedrawViewsCallback {name}\n"
        ).format(name=self._callback_name)

        rt.execute(mxs)
        self._callback_registered = True

    def unregister_callback(self) -> None:
        """Remove the previously registered redraw-views callback."""
        if rt is None:
            return
        if not self._callback_registered:
            return

        mxs = "unregisterRedrawViewsCallback {name}\n".format(
            name=self._callback_name,
        )
        rt.execute(mxs)
        self._callback_registered = False

        global _global_manager
        if _global_manager is self:
            _global_manager = None

    # -- drawing ------------------------------------------------------------

    def draw_overlays(self) -> None:
        """Draw all active overlays on the current viewport.

        Called automatically by the redraw callback.  Performs the following
        checks before drawing:

        1. ``pymxs`` must be available.
        2. A target camera must be set.
        3. The active viewport must be looking through that camera.
        """
        if rt is None or pymxs is None:
            return
        if self.target_camera_node is None:
            return
        if not self.active_overlays:
            return

        # ---- Check if active viewport is looking through our camera ------
        try:
            active_vp_camera = rt.viewport.getCamera()
        except Exception:
            return

        if active_vp_camera is None:
            return

        # Compare by node handle for a reliable identity check
        try:
            target_handle = rt.getHandleByAnim(self.target_camera_node)
            vp_handle = rt.getHandleByAnim(active_vp_camera)
            if target_handle != vp_handle:
                return
        except Exception:
            return

        # ---- Retrieve viewport dimensions --------------------------------
        try:
            gw = rt.gw
            vp_width = int(gw.getWinSizeX())
            vp_height = int(gw.getWinSizeY())
        except Exception:
            return

        if vp_width <= 0 or vp_height <= 0:
            return

        # ---- Set line drawing colour -------------------------------------
        r, g, b = self.line_color
        try:
            rt.execute(
                "gw.setColor #line (color {r} {g} {b})".format(r=r, g=g, b=b)
            )
        except Exception:
            return

        # ---- Draw each active overlay ------------------------------------
        if OVERLAY_THIRDS in self.active_overlays:
            self._draw_line_segments(calc_thirds(vp_width, vp_height))

        if OVERLAY_GOLDEN in self.active_overlays:
            self._draw_line_segments(calc_golden_ratio(vp_width, vp_height))

        if OVERLAY_DIAGONALS in self.active_overlays:
            self._draw_line_segments(calc_diagonals(vp_width, vp_height))

        if OVERLAY_SPIRAL in self.active_overlays:
            spiral_pts = _calc_spiral_golden_rects(vp_width, vp_height)
            self._draw_polyline(spiral_pts)

        # Flush GW buffer so the lines appear on screen
        try:
            gw.enlargeUpdateRect(rt.Name("whole"))
            gw.updateScreen()
        except Exception:
            pass

    # -- internal helpers ---------------------------------------------------

    def _draw_line_segments(self, segments: Sequence[LineSegment]) -> None:
        """Draw a batch of independent 2-point line segments via ``gw.hPolyline``.

        Each segment is a tuple ``(x1, y1, x2, y2)``.
        """
        if rt is None:
            return

        for x1, y1, x2, y2 in segments:
            # Build a MAXScript snippet to draw the segment.
            # gw.hPolyline takes an array of Point3 (screen-space, z=0)
            # and a boolean (closed = false).
            mxs = (
                "gw.hPolyline #([{x1},{y1},0], [{x2},{y2},0]) false"
            ).format(x1=x1, y1=y1, x2=x2, y2=y2)
            try:
                rt.execute(mxs)
            except Exception:
                pass

    def _draw_polyline(self, points: Sequence[Tuple[int, int]]) -> None:
        """Draw a continuous polyline through *points* via ``gw.hPolyline``.

        Because MAXScript has a practical limit on inline array size, we
        break the polyline into chunks and draw each chunk as a separate
        ``gw.hPolyline`` call, overlapping by one point so the line is
        visually continuous.
        """
        if rt is None:
            return
        if len(points) < 2:
            return

        chunk_size = 64  # Max points per single gw.hPolyline call

        for start in range(0, len(points) - 1, chunk_size - 1):
            chunk = points[start : start + chunk_size]
            if len(chunk) < 2:
                break

            # Build the Point3 array string: #([x,y,0], [x,y,0], ...)
            pts_str = ", ".join(
                "[{x},{y},0]".format(x=px, y=py) for px, py in chunk
            )
            mxs = "gw.hPolyline #({pts}) false".format(pts=pts_str)
            try:
                rt.execute(mxs)
            except Exception:
                pass

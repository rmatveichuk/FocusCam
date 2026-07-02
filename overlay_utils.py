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


def get_safe_frame_rect(
    vp_width: int,
    vp_height: int,
    render_width: int,
    render_height: int,
) -> Tuple[int, int, int, int]:
    """Calculate the safe frame bounding box (x_offset, y_offset, width, height) in viewport pixels."""
    if vp_height <= 0 or render_height <= 0:
        return 0, 0, vp_width, vp_height

    view_aspect = float(vp_width) / float(vp_height)
    render_aspect = float(render_width) / float(render_height)

    if render_aspect > view_aspect:
        # Safe frame is limited by width (horizontal bars)
        w = vp_width
        h = int(round(vp_width / render_aspect))
        x = 0
        y = int(round((vp_height - h) / 2.0))
    else:
        # Safe frame is limited by height (vertical bars)
        w = int(round(vp_height * render_aspect))
        h = vp_height
        x = int(round((vp_width - w) / 2.0))
        y = 0

    return x, y, w, h


def calc_thirds(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    """Return 4 line segments dividing the Safe Frame into a 3×3 grid."""
    x1 = x + int(round(w / 3.0))
    x2 = x + int(round(2.0 * w / 3.0))
    y1 = y + int(round(h / 3.0))
    y2 = y + int(round(2.0 * h / 3.0))

    return [
        # Vertical lines
        (x1, y, x1, y + h),
        (x2, y, x2, y + h),
        # Horizontal lines
        (x, y1, x + w, y1),
        (x, y2, x + w, y2),
    ]


def calc_golden_ratio(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    """Return 4 line segments at golden-ratio (phi ≈ 0.618) positions inside the Safe Frame."""
    gx = int(round(w * PHI_INV))
    gy = int(round(h * PHI_INV))
    gx2 = w - gx
    gy2 = h - gy

    mx1 = x + min(gx, gx2)
    mx2 = x + max(gx, gx2)
    my1 = y + min(gy, gy2)
    my2 = y + max(gy, gy2)

    return [
        # Vertical lines
        (mx1, y, mx1, y + h),
        (mx2, y, mx2, y + h),
        # Horizontal lines
        (x, my1, x + w, my1),
        (x, my2, x + w, my2),
    ]


def calc_diagonals(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    """Return diagonal line segments from corners of the Safe Frame."""
    return [
        # Top-left corner → bottom-right
        (x, y, x + w, y + h),
        # Top-right corner → bottom-left
        (x + w, y, x, y + h),
    ]


def calc_spiral(
    width: int,
    height: int,
    num_arc_segments: int = 24,
    max_iterations: int = 9,
) -> List[Tuple[int, int]]:
    """Return polyline points approximating a Fibonacci / golden spiral.
    Kept for backward compatibility.
    """
    points: List[Tuple[int, int]] = []
    rx: float = 0.0
    ry: float = 0.0
    rw: float = float(width)
    rh: float = float(height)

    for i in range(max_iterations):
        quadrant = i % 4
        if quadrant == 0:
            sq = rw - rw / PHI
            cx = rx + rw - sq
            cy = ry + rh
            start_angle = -math.pi / 2.0
            radius = rh
        elif quadrant == 1:
            sq = rh - rh / PHI
            cx = rx
            cy = ry + rh - sq
            start_angle = 0.0
            radius = rw
        elif quadrant == 2:
            sq = rw - rw / PHI
            cx = rx + sq
            cy = ry
            start_angle = math.pi / 2.0
            radius = rh
        else:
            sq = rh - rh / PHI
            cx = rx + rw
            cy = ry + sq
            start_angle = math.pi
            radius = rw

        for j in range(num_arc_segments + 1):
            t = j / float(num_arc_segments)
            angle = start_angle + t * (math.pi / 2.0)
            px = int(round(cx + radius * math.cos(angle)))
            py = int(round(cy + radius * math.sin(angle)))
            points.append((px, py))

        if quadrant == 0:
            rw -= sq
            rx += sq
            new_w = rw * PHI_INV
            rx = rx
            rw = rw
        elif quadrant == 1:
            new_h = rh * PHI_INV
        elif quadrant == 2:
            new_w = rw * PHI_INV
        else:
            new_h = rh * PHI_INV

        if quadrant == 0:
            new_rw = rw
            rw = rw
            rh = rh / PHI
            ry = ry + (rh * PHI_INV)
        elif quadrant == 1:
            rw = rw / PHI
        elif quadrant == 2:
            rh = rh / PHI
def _calc_spiral_golden_rects(
    x: int,
    y: int,
    w: int,
    h: int,
    num_arc_segments: int = 128,
) -> Tuple[List[List[Tuple[int, int]]], List[List[Tuple[int, int]]]]:
    """Compute the subdivision rectangles and the independent spiral arc segments inside the Safe Frame."""
    is_portrait = w < h
    if is_portrait:
        calc_w, calc_h = h, w
    else:
        calc_w, calc_h = w, h

    # Fit golden rectangle
    rect_h = float(calc_h)
    rect_w = rect_h * PHI
    if rect_w > calc_w:
        rect_w = float(calc_w)
        rect_h = rect_w / PHI

    rect_x = (float(calc_w) - rect_w) / 2.0
    rect_y = (float(calc_h) - rect_h) / 2.0

    # 1. Generate nested rectangles (Mode 0 clockwise starting from bottom-left)
    # 0: bottom-left, 1: top-left, 2: top-right, 3: bottom-right
    r1 = [
        (rect_x, rect_y + rect_h),
        (rect_x, rect_y),
        (rect_x + rect_w, rect_y),
        (rect_x + rect_w, rect_y + rect_h)
    ]
    rects = [r1]

    curr = list(r1)
    # 12 divisions for high precision subdivision grid
    for _ in range(12):
        A, B, C, D = curr[0], curr[1], curr[2], curr[3]
        
        eX = B[0] + PHI_INV * (C[0] - B[0])
        eY = B[1] + PHI_INV * (C[1] - B[1])
        E = (eX, eY)
        
        fX = A[0] + PHI_INV * (D[0] - A[0])
        fY = A[1] + PHI_INV * (D[1] - A[1])
        F = (fX, fY)
        
        new_rect = [E, C, D, F]
        rects.append(new_rect)
        curr = new_rect

    # 2. Generate curve arcs (each arc is an independent list of points)
    curve_arcs = []
    circle_start = 180.0
    
    # Each arc segment has high density for smooth curves
    steps_per_arc = max(8, int(num_arc_segments / 8))
    
    for k in range(1, len(rects)):
        prev_r = rects[k-1]
        r = rects[k]
        
        radius = math.dist(prev_r[0], prev_r[1])
        center = r[3]
        
        arc_points = []
        for i in range(steps_per_arc + 1):
            deg = circle_start + (90.0 * i / float(steps_per_arc))
            rad = math.radians(deg)
            px = center[0] + radius * math.sin(rad)
            py = center[1] + radius * math.cos(rad)
            arc_points.append((px, py))
        curve_arcs.append(arc_points)
            
        circle_start -= 90.0
        if circle_start <= 0.0:
            circle_start += 360.0

    # 3. Map/transpose back to viewport coordinates and flip Y-axis (since Max gw has Y=0 at the bottom)
    final_rects = []
    for r in rects:
        tr = []
        for p in r:
            flipped_y = rect_y + (rect_y + rect_h - p[1])
            if is_portrait:
                screen_x = int(round(float(x) + flipped_y))
                screen_y = int(round(float(y) + p[0]))
            else:
                screen_x = int(round(float(x) + p[0]))
                screen_y = int(round(float(y) + flipped_y))
            tr.append((screen_x, screen_y))
        final_rects.append(tr)

    final_arcs = []
    for arc in curve_arcs:
        final_arc = []
        for p in arc:
            flipped_y = rect_y + (rect_y + rect_h - p[1])
            if is_portrait:
                screen_x = int(round(float(x) + flipped_y))
                screen_y = int(round(float(y) + p[0]))
            else:
                screen_x = int(round(float(x) + p[0]))
                screen_y = int(round(float(y) + flipped_y))
            final_arc.append((screen_x, screen_y))
        final_arcs.append(final_arc)

    return final_rects, final_arcs



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

        # Build the MAXScript callback definition.
        # We unregister first to clean up any previous instance, then define
        # the global function, then register it. This avoids duplicate handlers
        # and ensures the python execution string is always updated.
        mxs = (
            "global {name}\n"
            "try(unregisterRedrawViewsCallback {name})catch()\n"
            "fn {name} = (\n"
            "    python.execute \"import sys; m = sys.modules.get('FocusCam.overlay_utils') or sys.modules.get('Focus.overlay_utils') or sys.modules.get('overlay_utils'); m._redraw_callback_entry() if m else None\"\n"
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

        Called automatically by the redraw callback.
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

        # ---- Retrieve render dimensions to compute Safe Frame -----------
        try:
            render_width = int(rt.renderWidth)
            render_height = int(rt.renderHeight)
        except Exception:
            render_width = vp_width
            render_height = vp_height

        x, y, w, h = get_safe_frame_rect(vp_width, vp_height, render_width, render_height)


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
            self._draw_line_segments(calc_thirds(x, y, w, h))

        if OVERLAY_GOLDEN in self.active_overlays:
            self._draw_line_segments(calc_golden_ratio(x, y, w, h))

        if OVERLAY_DIAGONALS in self.active_overlays:
            self._draw_line_segments(calc_diagonals(x, y, w, h))

        if OVERLAY_SPIRAL in self.active_overlays:
            rects, spiral_arcs = _calc_spiral_golden_rects(x, y, w, h)
            
            # 1. Draw sub-rectangles in a dimmer color (clr / 2.5)
            r_dim = int(r / 2.5)
            g_dim = int(g / 2.5)
            b_dim = int(b / 2.5)
            try:
                rt.execute(
                    "gw.setColor #line (color {r} {g} {b})".format(r=r_dim, g=g_dim, b=b_dim)
                )
            except Exception:
                pass
            
            for r_pts in rects:
                self._draw_closed_polyline(r_pts)
                
            # 2. Restore main color for the spiral curve
            try:
                rt.execute(
                    "gw.setColor #line (color {r} {g} {b})".format(r=r, g=g, b=b)
                )
            except Exception:
                pass
                
            for arc in spiral_arcs:
                self._draw_polyline(arc)

        # Flush GW buffer so the lines appear on screen
        try:
            gw.enlargeUpdateRect(rt.Name("whole"))
            gw.updateScreen()
        except Exception:
            pass

    # -- internal helpers ---------------------------------------------------

    def _draw_closed_polyline(self, points: Sequence[Tuple[int, int]]) -> None:
        """Draw a closed polyline through *points* via ``gw.hPolyline``."""
        if rt is None:
            return
        if len(points) < 2:
            return
        pts_str = ", ".join(
            "[{x},{y},0]".format(x=px, y=py) for px, py in points
        )
        mxs = "gw.hPolyline #({pts}) true".format(pts=pts_str)
        try:
            rt.execute(mxs)
        except Exception:
            pass

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

# Author: Roman Matveichuk
# Telegram: https://t.me/refer_manage
# GitHub: https://github.com/rmatveichuk/FocusCam

"""
overlay_utils.py – Viewport composition grid overlays for 3ds Max.

Draws Rule-of-Thirds, Golden-Ratio, Diagonal, and Fibonacci-Spiral guides
on top of the camera viewport using a transparent Qt overlay widget
(``ViewportOverlayWidget``) positioned over the camera viewport window.

The Qt approach replaces the old ``gw.hPolyline`` method which only works
for the active viewport.  The Qt overlay is viewport-independent and works
regardless of which viewport is currently active.

Usage:
    from overlay_utils import OverlayManager, OVERLAY_THIRDS, OVERLAY_GOLDEN

    mgr = OverlayManager()
    mgr.set_target_camera(some_camera_node)
    mgr.toggle_overlay(OVERLAY_THIRDS)
    mgr.register_callback()
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
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
# Qt import guard (PySide6 for 3ds Max 2025+, PySide2 fallback)
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import Qt, QTimer, QPoint, QPointF
    from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
except ImportError:
    try:
        from PySide2.QtWidgets import QWidget  # type: ignore[assignment]
        from PySide2.QtCore import Qt, QTimer, QPoint, QPointF  # type: ignore[assignment]
        from PySide2.QtGui import QPainter, QPen, QColor, QPolygonF  # type: ignore[assignment]
    except ImportError:
        QWidget = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Win32 API for viewport HWND geometry (fast, no MAXScript overhead)
# ---------------------------------------------------------------------------
_user32 = None
try:
    _user32 = ctypes.windll.user32
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowRect.restype = wintypes.BOOL
except Exception:
    pass

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
# Win32 Viewport HWND Helpers
# ---------------------------------------------------------------------------

def _get_screen_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """Return (x, y, width, height) in screen coordinates via Win32 GetWindowRect."""
    if _user32 is None:
        return (0, 0, 0, 0)
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def _find_camera_viewport_hwnd(camera_name: str) -> Tuple[Optional[int], Optional[Tuple[int, int, int, int]]]:
    """Find the HWND and screen rect of the viewport Label showing *camera_name*.

    Returns ``(hwnd, (screen_x, screen_y, width, height))`` or ``(None, None)``.
    """
    if rt is None:
        return None, None

    try:
        max_hwnd = int(rt.windows.getMAXHWND())
    except Exception:
        return None, None

    # 1. Find ViewPanel among Max main window children
    try:
        children = rt.windows.getChildrenHWND(max_hwnd)
    except Exception:
        return None, None

    view_panel_hwnd = None
    for child in children:
        try:
            if str(child[3]) == "ViewPanel":
                view_panel_hwnd = int(child[0])
                break
        except Exception:
            continue
    if view_panel_hwnd is None:
        return None, None

    # 2. Find the Label child whose title contains the camera name
    try:
        vp_children = rt.windows.getChildrenHWND(view_panel_hwnd)
    except Exception:
        return None, None

    for child in vp_children:
        try:
            class_name = str(child[3])
            title = str(child[4])
            if class_name == "Label" and camera_name in title:
                hwnd = int(child[0])
                screen_rect = _get_screen_rect(hwnd)
                if screen_rect[2] > 0 and screen_rect[3] > 0:
                    return hwnd, screen_rect
        except Exception:
            continue

    return None, None


# ---------------------------------------------------------------------------
# Qt Viewport Overlay Widget
# ---------------------------------------------------------------------------

class ViewportOverlayWidget(QWidget):
    """Transparent, click-through widget that draws composition overlays.

    Positioned over the camera viewport window.  Uses QPainter for
    antialiased rendering independent of the Nitrous ``gw`` pipeline.
    """

    def __init__(self, manager: "OverlayManager", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._manager: "OverlayManager" = manager
        self._render_w: int = 1920
        self._render_h: int = 1080

    # -- public helpers -------------------------------------------------

    def set_render_size(self, w: int, h: int) -> None:
        """Update render resolution for safe-frame calculation."""
        if w != self._render_w or h != self._render_h:
            self._render_w = w
            self._render_h = h
            self.update()

    def reposition(self, screen_x: int, screen_y: int, w: int, h: int) -> None:
        """Move/resize the overlay to cover the given screen rectangle."""
        parent = self.parentWidget()
        if parent is not None:
            local = parent.mapFromGlobal(QPoint(screen_x, screen_y))
            self.setGeometry(local.x(), local.y(), w, h)
        else:
            self.setGeometry(screen_x, screen_y, w, h)

    # -- painting -------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        mgr = self._manager
        if mgr is None or not mgr.active_overlays:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        vp_w = self.width()
        vp_h = self.height()

        x, y, sf_w, sf_h = get_safe_frame_rect(
            vp_w, vp_h, self._render_w, self._render_h
        )

        r, g, b = mgr.line_color
        main_color = QColor(r, g, b, 180)
        main_pen = QPen(main_color, 1.5)

        # ── Line segments (Thirds / Golden / Diagonals) ──────────────
        painter.setPen(main_pen)

        if OVERLAY_THIRDS in mgr.active_overlays:
            for seg in calc_thirds(x, y, sf_w, sf_h):
                painter.drawLine(seg[0], seg[1], seg[2], seg[3])

        if OVERLAY_GOLDEN in mgr.active_overlays:
            for seg in calc_golden_ratio(x, y, sf_w, sf_h):
                painter.drawLine(seg[0], seg[1], seg[2], seg[3])

        if OVERLAY_DIAGONALS in mgr.active_overlays:
            for seg in calc_diagonals(x, y, sf_w, sf_h):
                painter.drawLine(seg[0], seg[1], seg[2], seg[3])

        # ── Fibonacci Spiral ─────────────────────────────────────────
        if OVERLAY_SPIRAL in mgr.active_overlays:
            rects, arcs = _calc_spiral_golden_rects(x, y, sf_w, sf_h)

            # Dimmer colour for subdivision rectangles
            dim_color = QColor(r // 2, g // 2, b // 2, 120)
            dim_pen = QPen(dim_color, 1.0)
            painter.setPen(dim_pen)

            for rect_pts in rects:
                if len(rect_pts) >= 2:
                    poly = QPolygonF([QPointF(float(p[0]), float(p[1])) for p in rect_pts])
                    poly.append(poly[0])  # close the polygon
                    painter.drawPolyline(poly)

            # Main colour for spiral arcs
            painter.setPen(main_pen)
            for arc in arcs:
                if len(arc) >= 2:
                    poly = QPolygonF([QPointF(float(p[0]), float(p[1])) for p in arc])
                    painter.drawPolyline(poly)

        painter.end()


# ---------------------------------------------------------------------------
# Overlay Manager
# ---------------------------------------------------------------------------

# Legacy global kept for backward compatibility with old MAXScript callbacks
_global_manager: Optional["OverlayManager"] = None


def _redraw_callback_entry() -> None:
    """Legacy entry point — no longer used (overlay uses Qt widget now).

    Kept so that any residual MAXScript ``focusOverlayRedrawCB`` callback
    does not raise an AttributeError.
    """
    pass


class OverlayManager:
    """Manages viewport composition overlays via a Qt overlay widget.

    Attributes
    ----------
    active_overlays : set[int]
        Currently enabled overlay types (use the ``OVERLAY_*`` constants).
    target_camera_node : object | None
        The 3ds Max camera node for which overlays should be drawn.
        If *None*, the overlay is hidden.
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

        self._overlay_widget: Optional[ViewportOverlayWidget] = None
        self._geometry_timer: Optional[QTimer] = None
        self._last_vp_hwnd: Optional[int] = None
        self._last_vp_rect: Optional[Tuple[int, int, int, int]] = None
        self._callback_registered: bool = False

    # -- public API ---------------------------------------------------------

    def toggle_overlay(self, overlay_type: int) -> None:
        """Add *overlay_type* to the active set if absent, otherwise remove it."""
        if overlay_type in self.active_overlays:
            self.active_overlays.discard(overlay_type)
        else:
            self.active_overlays.add(overlay_type)
        self._update_visibility()

    def is_active(self, overlay_type: int) -> bool:
        """Return *True* if *overlay_type* is currently enabled."""
        return overlay_type in self.active_overlays

    def set_target_camera(self, camera_node: object | None) -> None:
        """Set the camera node whose viewport will receive overlays."""
        self.target_camera_node = camera_node
        # Force a full re-scan on the next sync tick
        self._last_vp_hwnd = None
        self._last_vp_rect = None
        self._rebind_viewport()

    # -- callback registration / removal (public API kept for compat) -------

    def register_callback(self) -> None:
        """Create the Qt overlay widget and start geometry sync.

        Replaces the old ``registerRedrawViewsCallback`` approach.
        """
        if QWidget is None or rt is None:
            return
        if self._callback_registered:
            return

        # Clean up any residual MAXScript gw-based callback from a prior version
        try:
            rt.execute("try(unregisterRedrawViewsCallback focusOverlayRedrawCB)catch()")
        except Exception:
            pass

        # Store ourselves as the global (legacy compat)
        global _global_manager
        _global_manager = self

        # Create the overlay widget (parented to Max main window)
        parent_widget = None
        try:
            max_hwnd = int(rt.windows.getMAXHWND())
            parent_widget = QWidget.find(max_hwnd)
        except Exception:
            pass

        self._overlay_widget = ViewportOverlayWidget(self, parent=parent_widget)

        # Start geometry sync timer
        self._geometry_timer = QTimer()
        self._geometry_timer.timeout.connect(self._sync_geometry)
        self._geometry_timer.start(300)

        self._callback_registered = True

        # Perform initial viewport binding
        self._rebind_viewport()

    def unregister_callback(self) -> None:
        """Destroy the Qt overlay widget and stop geometry sync."""
        if not self._callback_registered:
            return

        # Stop timer
        if self._geometry_timer is not None:
            self._geometry_timer.stop()
            try:
                self._geometry_timer.deleteLater()
            except Exception:
                pass
            self._geometry_timer = None

        # Destroy widget
        if self._overlay_widget is not None:
            try:
                self._overlay_widget.close()
                self._overlay_widget.deleteLater()
            except Exception:
                pass
            self._overlay_widget = None

        self._last_vp_hwnd = None
        self._last_vp_rect = None
        self._callback_registered = False

        global _global_manager
        if _global_manager is self:
            _global_manager = None

    # -- drawing (triggers Qt repaint) --------------------------------------

    def draw_overlays(self) -> None:
        """Trigger a repaint of the overlay widget.

        Called for backward compatibility — the actual drawing happens
        in ``ViewportOverlayWidget.paintEvent()``.
        """
        if self._overlay_widget is not None and self.active_overlays:
            self._overlay_widget.update()

    # -- internal helpers ---------------------------------------------------

    def _update_visibility(self) -> None:
        """Show/hide the overlay widget based on current state."""
        if self._overlay_widget is None:
            return
        if self.active_overlays and self.target_camera_node is not None:
            if not self._overlay_widget.isVisible():
                self._rebind_viewport()
            else:
                self._overlay_widget.update()  # just repaint
        else:
            self._overlay_widget.hide()

    def _rebind_viewport(self) -> None:
        """Find the camera viewport HWND and position the overlay over it."""
        if self._overlay_widget is None:
            return
        if self.target_camera_node is None or not self.active_overlays:
            self._overlay_widget.hide()
            return

        try:
            cam_name = str(self.target_camera_node.name)
        except Exception:
            self._overlay_widget.hide()
            return

        hwnd, rect = _find_camera_viewport_hwnd(cam_name)
        if hwnd is None or rect is None:
            self._overlay_widget.hide()
            return

        self._last_vp_hwnd = hwnd
        self._last_vp_rect = rect

        sx, sy, sw, sh = rect
        self._overlay_widget.reposition(sx, sy, sw, sh)

        # Sync render dimensions for safe-frame
        try:
            rw = int(rt.renderWidth)
            rh = int(rt.renderHeight)
            self._overlay_widget.set_render_size(rw, rh)
        except Exception:
            pass

        self._overlay_widget.show()
        self._overlay_widget.raise_()
        self._overlay_widget.update()

    def _sync_geometry(self) -> None:
        """Timer callback: keep overlay positioned over the camera viewport.

        Uses fast Win32 ``GetWindowRect`` for the cached HWND (no MAXScript
        round-trip) and falls back to a full re-scan only when the HWND is lost.
        """
        if self._overlay_widget is None or not self.active_overlays:
            return
        if self.target_camera_node is None:
            if self._overlay_widget.isVisible():
                self._overlay_widget.hide()
            return

        # Fast path: re-read geometry of the known HWND
        if self._last_vp_hwnd is not None and _user32 is not None:
            rect = _get_screen_rect(self._last_vp_hwnd)
            if rect[2] > 0 and rect[3] > 0:
                if rect != self._last_vp_rect:
                    self._last_vp_rect = rect
                    sx, sy, sw, sh = rect
                    self._overlay_widget.reposition(sx, sy, sw, sh)

                # Sync render dimensions
                try:
                    rw = int(rt.renderWidth)
                    rh = int(rt.renderHeight)
                    self._overlay_widget.set_render_size(rw, rh)
                except Exception:
                    pass

                if not self._overlay_widget.isVisible():
                    self._overlay_widget.show()
                    self._overlay_widget.raise_()
                return

        # Slow path: full re-scan (HWND lost or not yet known)
        self._rebind_viewport()

# Author: Roman Matveichuk
# Telegram: https://t.me/refer_manage
# GitHub: https://github.com/rmatveichuk/FocusCam

"""
overlay_utils.py – Viewport composition grid overlays for 3ds Max.

Draws Rule-of-Thirds, Golden-Ratio, Diagonal, and Fibonacci-Spiral guides
on top of camera viewports using a non-rendering Scripted Helper Plugin.

The Helper Plugin uses Nitrous `on display do` viewport callbacks, which:
1. Align 100% accurately with the 3ds Max Safe Frame.
2. Render natively inside non-active camera viewports without changing `activeViewport`.
3. Do not create external floating Windows or Qt widgets.
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
# Scripted Plugin Helper Definition
# ---------------------------------------------------------------------------

def _ensure_plugin_defined() -> None:
    """Ensure that FocusCamOverlayPlugin is defined in MAXScript."""
    if rt is None:
        return
    mxs = """
    if (FocusCamOverlayPlugin == undefined) then (
        global FocusCamOverlayPlugin = plugin helper FocusCamOverlayPlugin
        name:"FocusCamOverlay"
        classID:#(0x7f3a1b2c, 0x4d5e6f70)
        category:"FocusCam"
        extends:dummy
        (
            local PHI = (1.0 + sqrt 5.0) / 2.0
            local PHI_INV = 1.0 / PHI

            parameters main
            (
                targetCam type:#node
                drawThirds type:#boolean default:false
                drawGolden type:#boolean default:false
                drawDiagonals type:#boolean default:false
                drawSpiral type:#boolean default:false
            )

            fn getSafeFrameRect vpW vpH rw rh =
            (
                local viewAspect = (vpW as float) / (vpH as float)
                local renderAspect = (rw as float) / (rh as float)
                
                local sfW = vpW, sfH = vpH, sfX = 0, sfY = 0
                if renderAspect > viewAspect then (
                    sfW = vpW
                    sfH = (vpW / renderAspect) as integer
                    sfX = 0
                    sfY = ((vpH - sfH) / 2.0) as integer
                ) else (
                    sfH = vpH
                    sfW = (vpH * renderAspect) as integer
                    sfX = ((vpW - sfW) / 2.0) as integer
                    sfY = 0
                )
                
                #(sfX, sfY, sfW, sfH)
            )

            on display do
            (
                local vpCam = viewport.getCamera()
                if vpCam != undefined and targetCam != undefined and vpCam == targetCam then
                (
                    if drawThirds or drawGolden or drawDiagonals or drawSpiral then (
                        local vpW = gw.getWinSizeX()
                        local vpH = gw.getWinSizeY()
                        local rw = renderWidth as float
                        local rh = renderHeight as float
                        
                        if (isProperty vpCam #FocusCam_ResWidth) and vpCam.FocusCam_ResWidth != undefined and vpCam.FocusCam_ResWidth > 0 do (
                            rw = vpCam.FocusCam_ResWidth as float
                            rh = vpCam.FocusCam_ResHeight as float
                        )
                        
                        local sf = getSafeFrameRect vpW vpH rw rh
                        local sfX = sf[1], sfY = sf[2], sfW = sf[3], sfH = sf[4]
                        
                        gw.setTransform (matrix3 1)
                        gw.setColor #line (color 200 200 200)
                        
                        -- 1. Thirds
                        if drawThirds do (
                            local x1 = sfX + ((sfW / 3.0) as integer)
                            local x2 = sfX + ((2.0 * sfW / 3.0) as integer)
                            local y1 = sfY + ((sfH / 3.0) as integer)
                            local y2 = sfY + ((2.0 * sfH / 3.0) as integer)
                            
                            gw.hPolyline #([x1, sfY, 0], [x1, sfY + sfH, 0]) false
                            gw.hPolyline #([x2, sfY, 0], [x2, sfY + sfH, 0]) false
                            gw.hPolyline #([sfX, y1, 0], [sfX + sfW, y1, 0]) false
                            gw.hPolyline #([sfX, y2, 0], [sfX + sfW, y2, 0]) false
                        )
                        
                        -- 2. Golden Ratio
                        if drawGolden do (
                            local gx = (sfW * PHI_INV) as integer
                            local gy = (sfH * PHI_INV) as integer
                            local gx2 = sfW - gx
                            local gy2 = sfH - gy
                            
                            local mx1 = sfX + (amin gx gx2)
                            local mx2 = sfX + (amax gx gx2)
                            local my1 = sfY + (amin gy gy2)
                            local my2 = sfY + (amax gy gy2)
                            
                            gw.hPolyline #([mx1, sfY, 0], [mx1, sfY + sfH, 0]) false
                            gw.hPolyline #([mx2, sfY, 0], [mx2, sfY + sfH, 0]) false
                            gw.hPolyline #([sfX, my1, 0], [sfX + sfW, my1, 0]) false
                            gw.hPolyline #([sfX, my2, 0], [sfX + sfW, my2, 0]) false
                        )
                        
                        -- 3. Diagonals
                        if drawDiagonals do (
                            gw.hPolyline #([sfX, sfY, 0], [sfX + sfW, sfY + sfH, 0]) false
                            gw.hPolyline #([sfX + sfW, sfY, 0], [sfX, sfY + sfH, 0]) false
                        )
                        
                        -- 4. Spiral
                        if drawSpiral do (
                            local x1 = sfX + ((sfW * 0.618034) as integer)
                            local y1 = sfY + ((sfH * 0.618034) as integer)
                            gw.hPolyline #([sfX, y1, 0], [sfX + sfW, y1, 0]) false
                            gw.hPolyline #([x1, sfY, 0], [x1, sfY + sfH, 0]) false
                        )
                        
                        gw.enlargeUpdateRect #whole
                    )
                )
            )
        )
    )
    """
    try:
        rt.execute(mxs)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Grid Calculation Helpers (kept for python utility compatibility)
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
        w = vp_width
        h = int(round(vp_width / render_aspect))
        x = 0
        y = int(round((vp_height - h) / 2.0))
    else:
        w = int(round(vp_height * render_aspect))
        h = vp_height
        x = int(round((vp_width - w) / 2.0))
        y = 0

    return x, y, w, h


def calc_thirds(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    x1 = x + int(round(w / 3.0))
    x2 = x + int(round(2.0 * w / 3.0))
    y1 = y + int(round(h / 3.0))
    y2 = y + int(round(2.0 * h / 3.0))
    return [
        (x1, y, x1, y + h),
        (x2, y, x2, y + h),
        (x, y1, x + w, y1),
        (x, y2, x + w, y2),
    ]


def calc_golden_ratio(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    gx = int(round(w * PHI_INV))
    gy = int(round(h * PHI_INV))
    gx2 = w - gx
    gy2 = h - gy
    mx1 = x + min(gx, gx2)
    mx2 = x + max(gx, gx2)
    my1 = y + min(gy, gy2)
    my2 = y + max(gy, gy2)
    return [
        (mx1, y, mx1, y + h),
        (mx2, y, mx2, y + h),
        (x, my1, x + w, my1),
        (x, my2, x + w, my2),
    ]


def calc_diagonals(x: int, y: int, w: int, h: int) -> List[LineSegment]:
    return [
        (x, y, x + w, y + h),
        (x + w, y, x, y + h),
    ]


# ---------------------------------------------------------------------------
# Overlay Manager
# ---------------------------------------------------------------------------

_global_manager: Optional["OverlayManager"] = None


def _redraw_callback_entry() -> None:
    """Legacy entry point kept for backward compatibility."""
    if _global_manager is not None:
        _global_manager.draw_overlays()


class OverlayManager:
    """Manages viewport composition overlays using a non-rendering Scripted Helper Plugin.

    Attributes
    ----------
    active_overlays : set[int]
        Currently enabled overlay types (use the ``OVERLAY_*`` constants).
    target_camera_node : object | None
        The 3ds Max camera node for which overlays should be drawn.
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
        self._helper_node: object | None = None

    # -- internal helper node accessor --------------------------------------

    def _get_helper_node(self):
        """Retrieve or create the non-rendering FocusCamOverlay helper node."""
        if rt is None:
            return None
        _ensure_plugin_defined()

        if self._helper_node is not None and rt.isValidNode(self._helper_node):
            return self._helper_node

        # Look for an existing helper node in the scene
        try:
            nodes = rt.getNodeByName("_FocusCamOverlayHelper", all=True)
            if nodes and len(nodes) > 0:
                self._helper_node = nodes[0]
                return self._helper_node
        except Exception:
            pass

        # Create new helper node
        try:
            h = rt.FocusCamOverlayPlugin(name="_FocusCamOverlayHelper")
            h.renderable = False
            self._helper_node = h
            return h
        except Exception:
            return None

    # -- public API ---------------------------------------------------------

    def toggle_overlay(self, overlay_type: int) -> None:
        """Add *overlay_type* to the active set if absent, otherwise remove it."""
        if overlay_type in self.active_overlays:
            self.active_overlays.discard(overlay_type)
        else:
            self.active_overlays.add(overlay_type)
        self._sync_helper()

    def is_active(self, overlay_type: int) -> bool:
        """Return *True* if *overlay_type* is currently enabled."""
        return overlay_type in self.active_overlays

    def set_target_camera(self, camera_node: object | None) -> None:
        """Set the camera node whose viewport will receive overlays."""
        self.target_camera_node = camera_node
        self._sync_helper()

    # -- callback registration / removal (public API kept for compat) -------

    def register_callback(self) -> None:
        """Initialize and sync the Scripted Helper plugin."""
        global _global_manager
        _global_manager = self
        self._sync_helper()

    def unregister_callback(self) -> None:
        """Clear overlays and sync helper."""
        self.active_overlays.clear()
        self._sync_helper()
        global _global_manager
        if _global_manager is self:
            _global_manager = None

    def draw_overlays(self) -> None:
        """Trigger a viewport sync."""
        self._sync_helper()

    # -- sync with helper plugin --------------------------------------------

    def _sync_helper(self) -> None:
        """Update properties on the Scripted Helper plugin and redraw viewports."""
        if rt is None:
            return
        h = self._get_helper_node()
        if h is None:
            return

        try:
            h.targetCam = self.target_camera_node
            h.drawThirds = (OVERLAY_THIRDS in self.active_overlays)
            h.drawGolden = (OVERLAY_GOLDEN in self.active_overlays)
            h.drawDiagonals = (OVERLAY_DIAGONALS in self.active_overlays)
            h.drawSpiral = (OVERLAY_SPIRAL in self.active_overlays)
            rt.redrawViews()
        except Exception:
            pass

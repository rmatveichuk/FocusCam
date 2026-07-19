# Author: Roman Matveichuk
# Telegram: https://t.me/refer_manage
# GitHub: https://github.com/rmatveichuk/FocusCam

"""
camera_utils.py — Camera-related operations for the Focus plugin (3ds Max 2025+).

Provides:
    - Custom Attributes management (cameraLightPresets CA block)
    - Camera discovery and sorting
    - Viewport thumbnail grabbing (returns QPixmap)
    - Render resolution save / load / apply / swap
    - Sort order persistence
    - Active viewport camera switching
"""

import os
import tempfile

# ---------------------------------------------------------------------------
# pymxs import — guarded so the module can be imported outside 3ds Max
# (e.g. for linting, testing, type-checking).
# ---------------------------------------------------------------------------
try:
    import pymxs
    rt = pymxs.runtime
except ImportError:
    pymxs = None  # type: ignore[assignment]
    rt = None      # type: ignore[assignment]

# ---------------------------------------------------------------------------
# PySide6 imports (bundled with 3ds Max 2025+)
# ---------------------------------------------------------------------------
try:
    from PySide6.QtGui import QPixmap, QImage
    from PySide6.QtCore import Qt
except ImportError:
    QPixmap = None  # type: ignore[assignment,misc]
    QImage = None   # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# MAXScript source for the cameraLightPresets custom-attribute block.
# Defined once as a Python string so we can feed it to rt.execute().
# ---------------------------------------------------------------------------
_CA_DEFINITION = """
attributes cameraLightPresets (
    parameters main (
        lightHandles type:#intTab tabSizeVariable:true
        lightStates type:#boolTab tabSizeVariable:true
        hasPhysicalPreset type:#boolean default:false
        lmChannels type:#stringTab tabSizeVariable:true
        lmIntensities type:#floatTab tabSizeVariable:true
        lmColors type:#colorTab tabSizeVariable:true
        lmStates type:#boolTab tabSizeVariable:true
        hasMixPreset type:#boolean default:false
        sortOrder type:#integer default:0
    )
)
"""

_RES_CA_DEFINITION = """
attributes focusResolutionPresets (
    parameters main (
        renderWidth type:#integer default:0
        renderHeight type:#integer default:0
        hasResolution type:#boolean default:false
    )
)
"""

# We cache the CA definition object so we don't re-execute every call.
_ca_def_cache = None
_res_ca_def_cache = None


def _get_ca_def():
    """Return the cameraLightPresets attribute definition, creating it once."""
    global _ca_def_cache
    if _ca_def_cache is None:
        _ca_def_cache = rt.execute(_CA_DEFINITION)
    return _ca_def_cache

def _get_res_ca_def():
    """Return the focusResolutionPresets attribute definition, creating it once."""
    global _res_ca_def_cache
    if _res_ca_def_cache is None:
        _res_ca_def_cache = rt.execute(_RES_CA_DEFINITION)
    return _res_ca_def_cache


# ===================================================================
# 1. Custom Attributes
# ===================================================================

def is_node_valid(node) -> bool:
    """Return True if node is not None and is a valid (not deleted) 3ds Max scene object."""
    if rt is None or node is None:
        return False
    try:
        return rt.isValidNode(node)
    except Exception:
        return False


def _get_ca_block(camera_node, ca_name_str: str):
    """Return the custom attribute block of name *ca_name_str* if present on *camera_node*."""
    if not is_node_valid(camera_node):
        return None
    try:
        ca_count = rt.custAttributes.count(camera_node)
        for i in range(1, ca_count + 1):
            ca = rt.custAttributes.get(camera_node, i)
            ca_def = rt.custAttributes.getDef(ca)
            if ca_def is not None:
                if str(getattr(ca_def, "name", "")) == ca_name_str:
                    return ca
    except Exception:
        pass
    return None


def _has_ca(camera_node) -> bool:
    """Return True if *camera_node* already carries the cameraLightPresets CA."""
    return _get_ca_block(camera_node, "cameraLightPresets") is not None


def _has_res_ca(camera_node) -> bool:
    """Return True if *camera_node* already carries the focusResolutionPresets CA."""
    return _get_ca_block(camera_node, "focusResolutionPresets") is not None


def ensure_custom_attributes(camera_node) -> None:
    """
    Attach the *cameraLightPresets* CA block to *camera_node* if it is not
    already present.  Safe to call multiple times on the same node.
    """
    if not is_node_valid(camera_node):
        return
    if _has_ca(camera_node):
        return
    ca_def = _get_ca_def()
    rt.custAttributes.add(camera_node, ca_def)


def ensure_res_custom_attributes(camera_node) -> None:
    """
    Attach the *focusResolutionPresets* CA block to *camera_node* if it is not
    already present.
    """
    if not is_node_valid(camera_node):
        return
    if _has_res_ca(camera_node):
        return
    ca_def = _get_res_ca_def()
    rt.custAttributes.add(camera_node, ca_def)


# ===================================================================
# 2. Camera Discovery
# ===================================================================

# SuperClass / class names we recognise as cameras.
_CAMERA_CLASSES = {
    "Physical",
    "Freecamera",
    "Targetcamera",
    "VRayPhysicalCamera",
    "CoronaCam",
    # Legacy / less common but still valid
    "Free_camera",
    "Target_camera",
}


def _is_camera(node) -> bool:
    """Return True if *node* is any kind of camera we care about."""
    try:
        # The fastest check: superclass should be 'camera'.
        if str(rt.superClassOf(node)) == "camera":
            return True
        # Fallback: check the class name string against our known set.
        class_name = str(rt.classOf(node))
        if class_name in _CAMERA_CLASSES:
            return True
    except Exception:
        pass
    return False


def get_all_cameras() -> list:
    """
    Return a list of all camera nodes in the current scene.

    Cameras that carry the *cameraLightPresets* CA are sorted by their
    ``sortOrder`` value first (ascending).  Cameras without the CA or
    with sortOrder == 0 fall back to alphabetical name sorting.
    """
    cameras = []
    for obj in rt.objects:
        if is_node_valid(obj) and _is_camera(obj):
            cameras.append(obj)

    def _sort_key(cam):
        order = get_sort_order(cam)
        name = str(cam.name).lower()
        # Cameras with a positive sortOrder come first, sorted numerically.
        # Cameras without (order == 0) are appended alphabetically.
        if order > 0:
            return (0, order, name)
        return (1, 0, name)

    cameras.sort(key=_sort_key)
    return cameras


# ===================================================================
# 3. Viewport Thumbnail Grab
# ===================================================================

def grab_viewport_thumbnail(camera_node, width: int = 200, height: int = 112):
    """
    Grab a viewport thumbnail through *camera_node* and return a ``QPixmap``.
    """
    if rt is None or QPixmap is None or not is_node_valid(camera_node):
        return None

    # -- Save current viewport state -----------------------------------------
    active_vp = rt.viewport.activeViewport
    
    try: prev_type = rt.viewport.getType()
    except Exception: prev_type = None

    try: prev_camera = rt.viewport.getCamera()
    except Exception: prev_camera = None

    show_flags = {}
    flag_names = ["ShowHelpers", "ShowCameras", "ShowLights", "ShowGrid"]
    for flag in flag_names:
        getter = "Get" + flag
        try: show_flags[flag] = rt.execute("viewport.{}()".format(getter))
        except Exception: show_flags[flag] = None

    tmp_path = None
    try:
        # -- Configure viewport for a clean grab --------------------------------
        for flag in flag_names:
            setter = "Set" + flag
            try: rt.execute("viewport.{}(false)".format(setter))
            except Exception: pass

        # Switch viewport to the target camera.
        rt.viewport.setCamera(camera_node)
            
        # Force a synchronous complete redraw to ensure viewport updates.
        try: rt.completeRedraw()
        except Exception:
            try: rt.forceCompleteRedraw()
            except Exception: pass

        # -- Grab the viewport DIB -----------------------------------------------
        dib = rt.gw.getViewportDib()
        if dib is None:
            return None

        # Write the bitmap to a temporary BMP so we can load it as QPixmap.
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".bmp")
        os.close(tmp_fd)

        # Save the DIB directly to preserve its exact aspect ratio.
        dib.filename = tmp_path
        rt.save(dib)
        rt.close(dib)

        # Load into QPixmap.
        pixmap = QPixmap(tmp_path)
        if pixmap.isNull():
            return None
        return pixmap

    except Exception:
        return None

    finally:
        # -- Restore viewport state ----------------------------------------------
        log_path = os.path.join(os.path.dirname(__file__), "debug_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- grab_viewport_thumbnail restore start for {getattr(camera_node, 'name', 'N/A')} ---\n")
                f.write(f"  active_vp: {active_vp}, prev_type: {prev_type} ({type(prev_type)}), prev_camera: {getattr(prev_camera, 'name', 'None' if prev_camera is None else str(prev_camera))}\n")
        except:
            pass

        try:
            if str(prev_type) == "view_camera":
                if prev_camera is not None and prev_camera != rt.undefined:
                    rt.viewport.setCamera(prev_camera)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"  Restored camera {prev_camera.name} in viewport {rt.viewport.activeViewport}\n")
            else:
                if prev_type is not None:
                    rt.viewport.setType(prev_type)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"  Restored viewport type {prev_type} in viewport {rt.viewport.activeViewport}\n")
        except Exception as restore_err:
            import traceback
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  === Restore failed ===\n")
                    traceback.print_exc(file=f)
            except:
                pass

        for flag in flag_names:
            if show_flags.get(flag) is not None:
                setter = "Set" + flag
                val = "true" if show_flags[flag] else "false"
                try: rt.execute("viewport.{}({})".format(setter, val))
                except Exception: pass

        try: rt.viewport.activeViewport = active_vp
        except Exception: pass

        # Clean up temp file.
        if tmp_path and os.path.isfile(tmp_path):
            try: os.remove(tmp_path)
            except OSError: pass
            
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("--- grab_viewport_thumbnail restore end ---\n\n")
        except:
            pass


# ===================================================================
# 4. Resolution Management
# ===================================================================

def save_resolution(camera_node, width: int, height: int) -> None:
    """Persist render resolution into the camera's CA."""
    if not is_node_valid(camera_node):
        return
    ensure_res_custom_attributes(camera_node)
    ca = _get_ca_block(camera_node, "focusResolutionPresets")
    if ca is not None:
        try:
            ca.renderWidth = width
            ca.renderHeight = height
            ca.hasResolution = True
        except Exception:
            pass


def load_resolution(camera_node) -> tuple:
    """
    Read stored resolution from the camera's CA.

    Returns:
        (width, height, has_resolution) — *has_resolution* is ``False`` when
        the CA is absent or no resolution has been saved yet.
    """
    if not is_node_valid(camera_node):
        return (0, 0, False)
    ca = _get_ca_block(camera_node, "focusResolutionPresets")
    if ca is not None:
        try:
            has = bool(ca.hasResolution)
            w = int(ca.renderWidth)
            h = int(ca.renderHeight)
            return (w, h, has)
        except Exception:
            pass
    return (0, 0, False)


def get_effective_resolution(camera_node):
    w, h, has = load_resolution(camera_node)
    if has and w > 0 and h > 0:
        return w, h
    try:
        return int(rt.renderWidth), int(rt.renderHeight)
    except Exception:
        return 1920, 1080


def show_safe_frame_only_on_camera_views() -> None:
    """Enable Safe Frames display only on viewports of type #view_camera."""
    if rt is None:
        return
    try:
        num_views = int(rt.viewport.numViews)
        saved_active = int(rt.viewport.activeViewport)
        for i in range(1, num_views + 1):
            try:
                rt.viewport.activeViewport = i
                if str(rt.viewport.getType()) == "view_camera":
                    rt.displaySafeFrames = True
            except Exception:
                pass
        rt.viewport.activeViewport = saved_active
    except Exception:
        pass


def apply_resolution(width: int, height: int) -> None:
    """Set the active 3ds Max render resolution."""
    if rt is None:
        return
    
    try:
        if int(rt.renderWidth) == width and int(rt.renderHeight) == height:
            return
    except Exception:
        pass
    
    # Set the aspect ratio first to prevent padlock auto-scaling distortion
    try:
        if height > 0:
            rt.rendImageAspectRatio = width / float(height)
    except Exception:
        pass

    try:
        rt.renderWidth = width
        rt.renderHeight = height
    except Exception:
        pass

    show_safe_frame_only_on_camera_views()

    # Refresh Render Setup dialog UI if it is open
    try:
        if rt.renderSceneDialog.isOpen():
            rt.renderSceneDialog.update()
    except Exception:
        pass


def swap_resolution(camera_node) -> None:
    """
    Swap width ↔ height in the camera CA and immediately apply the new
    resolution to the renderer.
    """
    w, h, has = load_resolution(camera_node)
    if not has:
        return
    save_resolution(camera_node, h, w)
    apply_resolution(h, w)


# ===================================================================
# 5. Sort Order
# ===================================================================

def save_sort_order(camera_node, order: int) -> None:
    """Write *order* into the camera's ``sortOrder`` CA parameter."""
    if not is_node_valid(camera_node):
        return
    ensure_custom_attributes(camera_node)
    ca = _get_ca_block(camera_node, "cameraLightPresets")
    if ca is not None:
        try:
            ca.sortOrder = order
        except Exception:
            pass


def get_sort_order(camera_node) -> int:
    """
    Read the ``sortOrder`` value from the camera's CA.

    Returns ``0`` when the CA is not present or the attribute cannot be read.
    """
    if not is_node_valid(camera_node):
        return 0
    ca = _get_ca_block(camera_node, "cameraLightPresets")
    if ca is not None:
        try:
            return int(ca.sortOrder)
        except Exception:
            pass
    return 0


# ===================================================================
# 6. Camera Switching
# ===================================================================

def switch_to_camera(camera_node) -> None:
    """
    Set the viewport camera to *camera_node* using smart viewport selection.
    """
    if rt is None or not is_node_valid(camera_node):
        return

    log_path = os.path.join(os.path.dirname(__file__), "debug_log.txt")

    try:
        num_views = int(rt.viewport.numViews)
        saved_active = int(rt.viewport.activeViewport)
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- switch_to_camera start. active: {saved_active}, total views: {num_views} ---\n")
            
        camera_view_indices = []
        for i in range(1, num_views + 1):
            try:
                rt.viewport.activeViewport = i
                vp_type = rt.viewport.getType()
                vp_type_str = str(vp_type)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"  Viewport {i} type: {vp_type_str} (repr: {repr(vp_type)})\n")
                if vp_type_str == "view_camera":
                    camera_view_indices.append(i)
            except Exception as loop_err:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"  Error checking viewport {i}: {loop_err}\n")
                
        # Restore active viewport
        rt.viewport.activeViewport = saved_active
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"  Camera viewports found: {camera_view_indices}\n")
            
        if camera_view_indices:
            if saved_active in camera_view_indices:
                rt.viewport.setCamera(camera_node)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  Changed camera in active camera viewport.\n")
            else:
                target_idx = camera_view_indices[0]
                rt.viewport.activeViewport = target_idx
                rt.viewport.setCamera(camera_node)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"  Switched active viewport to {target_idx} and set camera.\n")
        else:
            rt.viewport.setCamera(camera_node)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("  No camera viewports. Set camera in active viewport.\n")
                
        show_safe_frame_only_on_camera_views()
        rt.forceCompleteRedraw()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- switch_to_camera success ---\n\n")
            
    except Exception as e:
        import traceback
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=== switch_to_camera FAILED ===\n")
                traceback.print_exc(file=f)
                f.write("\n")
        except:
            pass
        # Fallback
        try:
            rt.viewport.setCamera(camera_node)
            rt.forceCompleteRedraw()
        except:
            pass


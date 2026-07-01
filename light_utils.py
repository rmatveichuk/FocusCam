# -*- coding: utf-8 -*-
"""
Focus – Light Utilities
~~~~~~~~~~~~~~~~~~~~~~~~
Light preset saving / restoring and LightMix integration for the Focus plugin.

Provides two layers of light control per camera:
  • Physical Light Preset  – stores on/off state of every scene light.
  • LightMix Preset        – stores renderer-level LightMix channel data
                             (Corona or V-Ray).
"""

# ── pymxs guard ──────────────────────────────────────────────────────────────
try:
    import pymxs
    from pymxs import runtime as rt
except ImportError:
    pymxs = None
    rt = None

# ── Local import (same package) ─────────────────────────────────────────────
from . import camera_utils


# =============================================================================
# 1.  LIGHT DISCOVERY
# =============================================================================

def get_all_lights():
    """Return a list of every light node in the current scene.

    Includes standard, photometric, Corona and V-Ray lights.
    Uses ``rt.lights`` which covers all objects whose superclass is ``light``.
    """
    if rt is None:
        return []
    try:
        return list(rt.lights)
    except Exception:
        return []


# =============================================================================
# 2.  PHYSICAL LIGHT PRESET  ([Light] button)
# =============================================================================

def _get_light_enabled(light_node):
    """Read the enabled / on state of a light, handling different APIs.

    Standard and photometric lights use ``.enabled``; some third-party lights
    (Corona, V-Ray) may use ``.on`` instead.
    """
    if rt is None:
        return True
    try:
        if rt.hasProperty(light_node, "enabled"):
            return bool(rt.getProperty(light_node, "enabled"))
    except Exception:
        pass
    try:
        if rt.hasProperty(light_node, "on"):
            return bool(rt.getProperty(light_node, "on"))
    except Exception:
        pass
    return True


def _set_light_enabled(light_node, state):
    """Set the enabled / on state of a light, handling different APIs."""
    if rt is None:
        return
    state_val = bool(state)
    try:
        if rt.hasProperty(light_node, "enabled"):
            rt.setProperty(light_node, "enabled", state_val)
            return
    except Exception:
        pass
    try:
        if rt.hasProperty(light_node, "on"):
            rt.setProperty(light_node, "on", state_val)
            return
    except Exception:
        pass


# =============================================================================
# Helpers for Persistent Handles
# =============================================================================

def _get_node_handle(node):
    """Get the persistent inode handle of a 3ds Max node."""
    try:
        return int(node.inode.handle)
    except Exception:
        pass
    try:
        return int(node.handle)
    except Exception:
        pass
    try:
        return int(rt.getProperty(node, "handle"))
    except Exception:
        pass
    raise ValueError("Could not get persistent node handle")


def _get_node_by_handle(handle):
    """Retrieve a 3ds Max node by its persistent handle."""
    try:
        return rt.maxOps.getNodeByHandle(handle)
    except Exception:
        return None


# ── save ─────────────────────────────────────────────────────────────────────

def save_light_preset(camera_node):
    """Snapshot the on/off state of every scene light and store it in the
    camera node's Custom Attributes (``lightHandles``, ``lightStates``).
    """
    if rt is None or camera_node is None:
        return

    try:
        camera_utils.ensure_custom_attributes(camera_node)
        lights = get_all_lights()
        
        handles = rt.Array()
        states = rt.Array()
        for lgt in lights:
            try:
                h = _get_node_handle(lgt)
                s = _get_light_enabled(lgt)
                rt.append(handles, h)
                rt.append(states, s)
            except Exception:
                continue

        # Write to CA
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            ca.lightHandles = handles
            ca.lightStates = states
            ca.hasPhysicalPreset = True
    except Exception:
        pass


# ── load ─────────────────────────────────────────────────────────────────────

def load_light_preset(camera_node):
    """Read ``lightHandles`` / ``lightStates`` from the camera's CA."""
    if rt is None or camera_node is None:
        return None

    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None or not ca.hasPhysicalPreset:
            return None

        handles = ca.lightHandles
        states = ca.lightStates
        if handles is None or states is None:
            return None

        py_handles = list(handles)
        py_states = list(states)
        
        result = []
        for h, s in zip(py_handles, py_states):
            result.append((int(h), bool(s)))
            
        return result if result else None
    except Exception:
        return None


# ── apply ────────────────────────────────────────────────────────────────────

def apply_light_preset(camera_node):
    """Apply a previously saved light preset."""
    if rt is None or camera_node is None:
        return
        
    try:
        preset = load_light_preset(camera_node)
        if preset is None:
            return

        for handle, state in preset:
            try:
                node = _get_node_by_handle(handle)
                if node is None or not rt.isValidNode(node):
                    continue
                _set_light_enabled(node, state)
            except Exception:
                continue
    except Exception:
        pass


# ── query / clear ────────────────────────────────────────────────────────────

def has_light_preset(camera_node):
    """Return True if the camera already stores a physical light preset."""
    if rt is None or camera_node is None:
        return False
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        return bool(ca.hasPhysicalPreset) if ca is not None else False
    except Exception:
        return False


def clear_light_preset(camera_node):
    """Remove the physical light preset from the camera's CA."""
    if rt is None or camera_node is None:
        return
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            ca.lightHandles = rt.Array()
            ca.lightStates = rt.Array()
            ca.hasPhysicalPreset = False
    except Exception:
        pass


# =============================================================================
# 3.  LIGHTMIX PRESET  ([LMix] button)
# =============================================================================

def detect_renderer():
    """Detect the current production renderer.

    Returns:
        str – ``'corona'``, ``'vray'``, or ``'unknown'``.
    """
    if rt is None:
        return "unknown"
    try:
        renderer = rt.renderers.current
        cls_name = str(rt.classOf(renderer))
        cls_lower = cls_name.lower()
        if "corona" in cls_lower:
            return "corona"
        if "v_ray" in cls_lower or "vray" in cls_lower:
            return "vray"
    except Exception:
        pass
    return "unknown"


# ── Corona helpers ───────────────────────────────────────────────────────────

def _save_corona_lightmix(camera_node):
    """Read Corona LightMix data via the CoronaFp interface and store it
    in the camera CA arrays.
    """
    try:
        count = int(rt.execute("(CoronaRenderer.CoronaFp).LightMix_GetChannelCount()"))
    except Exception:
        return False

    names = rt.Array()
    intensities = rt.Array()
    colors = rt.Array()
    enabled_states = rt.Array()

    for i in range(count):
        try:
            name = rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_GetChannelName {idx}".format(idx=i)
            )
            intensity = rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_GetChannelIntensity {idx}".format(idx=i)
            )
            color = rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_GetChannelColor {idx}".format(idx=i)
            )
            enabled = rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_GetChannelEnabled {idx}".format(idx=i)
            )

            rt.append(names, str(name) if name else "")
            rt.append(intensities, float(intensity) if intensity is not None else 1.0)
            
            c_val = rt.Color(float(color.r), float(color.g), float(color.b)) if color else rt.Color(255, 255, 255)
            rt.append(colors, c_val)
            rt.append(enabled_states, bool(enabled))
        except Exception:
            continue

    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            ca.lmChannels = names
            ca.lmIntensities = intensities
            ca.lmColors = colors
            ca.lmStates = enabled_states
            ca.hasMixPreset = True
            return True
    except Exception:
        pass
    return False


def _apply_corona_lightmix(camera_node):
    """Restore Corona LightMix channels from the camera's CA."""
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None or not ca.hasMixPreset:
            return False
            
        names = ca.lmChannels
        intensities = ca.lmIntensities
        colors = ca.lmColors
        enabled_states = ca.lmStates
    except Exception:
        return False

    if names is None or intensities is None:
        return False

    count = int(names.count) if hasattr(names, "count") else 0

    for i in range(count):
        idx_mx = i + 1  # MAXScript 1-indexed array
        ch_idx = i       # CoronaFp uses 0-indexed channels
        try:
            intensity_val = float(intensities[idx_mx])
            c = colors[idx_mx]
            cr = float(c.r)
            cg = float(c.g)
            cb = float(c.b)
            en = bool(enabled_states[idx_mx])

            rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_SetChannelIntensity {idx} {val}"
                .format(idx=ch_idx, val=intensity_val)
            )
            rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_SetChannelColor {idx} (color {r} {g} {b})"
                .format(idx=ch_idx, r=cr, g=cg, b=cb)
            )
            rt.execute(
                "(CoronaRenderer.CoronaFp).LightMix_SetChannelEnabled {idx} {val}"
                .format(idx=ch_idx, val="true" if en else "false")
            )
        except Exception:
            continue

    return True


# ── V-Ray helpers ────────────────────────────────────────────────────────────

def _save_vray_lightmix(camera_node):
    """Read V-Ray LightMix data from ``renderers.current`` properties and
    store it in the camera CA.
    """
    try:
        renderer = rt.renderers.current
        intensities_src = renderer.colorMap_lightmixIntensities
        colors_src = renderer.colorMap_lightmixColors
    except Exception:
        return False

    intensities = rt.Array()
    colors = rt.Array()

    if intensities_src is not None:
        count = int(intensities_src.count) if hasattr(intensities_src, "count") else 0
        for i in range(1, count + 1):
            try:
                rt.append(intensities, float(intensities_src[i]))
            except Exception:
                rt.append(intensities, 1.0)

    if colors_src is not None:
        count = int(colors_src.count) if hasattr(colors_src, "count") else 0
        for i in range(1, count + 1):
            try:
                c = colors_src[i]
                c_val = rt.Color(float(c.r), float(c.g), float(c.b))
                rt.append(colors, c_val)
            except Exception:
                rt.append(colors, rt.Color(255, 255, 255))

    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            ca.lmChannels = rt.Array()  # V-Ray has no channel names
            ca.lmIntensities = intensities
            ca.lmColors = colors
            ca.lmStates = rt.Array()  # V-Ray has no per-channel enable
            ca.hasMixPreset = True
            return True
    except Exception:
        pass
    return False


def _apply_vray_lightmix(camera_node):
    """Restore V-Ray LightMix values from the camera's CA back to the renderer."""
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None or not ca.hasMixPreset:
            return False
            
        intensities = ca.lmIntensities
        colors = ca.lmColors
    except Exception:
        return False

    if intensities is None or colors is None:
        return False

    try:
        renderer = rt.renderers.current
    except Exception:
        return False

    int_arr = rt.Array()
    col_arr = rt.Array()
    int_count = int(intensities.count) if hasattr(intensities, "count") else 0
    for i in range(1, int_count + 1):
        try:
            rt.append(int_arr, float(intensities[i]))
        except Exception:
            rt.append(int_arr, 1.0)

    col_count = int(colors.count) if hasattr(colors, "count") else 0
    for i in range(1, col_count + 1):
        try:
            c = colors[i]
            c_val = rt.Color(float(c.r), float(c.g), float(c.b))
            rt.append(col_arr, c_val)
        except Exception:
            rt.append(col_arr, rt.Color(255, 255, 255))

    try:
        renderer.colorMap_lightmixIntensities = int_arr
        renderer.colorMap_lightmixColors = col_arr
        return True
    except Exception:
        return False


# ── Public LightMix API ─────────────────────────────────────────────────────

def save_lightmix_preset(camera_node):
    """Snapshot the current LightMix state and store it in the camera's CA."""
    if rt is None or camera_node is None:
        return

    camera_utils.ensure_custom_attributes(camera_node)

    renderer_type = detect_renderer()
    if renderer_type == "corona":
        _save_corona_lightmix(camera_node)
    elif renderer_type == "vray":
        _save_vray_lightmix(camera_node)


def apply_lightmix_preset(camera_node):
    """Restore a previously saved LightMix preset to the active renderer."""
    if rt is None or camera_node is None:
        return
    if not has_lightmix_preset(camera_node):
        return

    current = detect_renderer()
    
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None:
            return
        is_corona_preset = int(ca.lmChannels.count) > 0
    except Exception:
        is_corona_preset = False

    if is_corona_preset and current == "corona":
        _apply_corona_lightmix(camera_node)
    elif not is_corona_preset and current == "vray":
        _apply_vray_lightmix(camera_node)


def has_lightmix_preset(camera_node):
    """Return True if the camera stores a LightMix preset."""
    if rt is None or camera_node is None:
        return False
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        return bool(ca.hasMixPreset) if ca is not None else False
    except Exception:
        return False


def clear_lightmix_preset(camera_node):
    """Remove the LightMix preset from the camera's CA."""
    if rt is None or camera_node is None:
        return
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            ca.lmChannels = rt.Array()
            ca.lmIntensities = rt.Array()
            ca.lmColors = rt.Array()
            ca.lmStates = rt.Array()
            ca.hasMixPreset = False
    except Exception:
        pass


# ── Render-element setup ────────────────────────────────────────────────────

def setup_lightmix_elements():
    """Ensure that a LightMix render element exists in the scene."""
    if rt is None:
        return False

    renderer_type = detect_renderer()

    if renderer_type == "corona":
        return _ensure_render_element("CShading_LightMix")
    elif renderer_type == "vray":
        return _ensure_render_element("VRayLightMix")
    return False


def _ensure_render_element(class_name):
    """Check whether a render element of *class_name* exists; create it if not."""
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()

        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            elem_class_name = str(rt.classOf(elem))
            if elem_class_name.lower() == class_name.lower():
                return True

        new_elem = rt.execute("{cls}()".format(cls=class_name))
        if new_elem is not None:
            mgr.AddRenderElement(new_elem)
            return True
    except Exception:
        pass
    return False

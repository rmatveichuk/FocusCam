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
        # rt.lights returns a MAXScript collection of all light-superclass nodes
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
    # Fallback – assume the light is on
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


# ── save ─────────────────────────────────────────────────────────────────────

def save_light_preset(camera_node):
    """Snapshot the on/off state of every scene light and store it in the
    camera node's Custom Attributes (``lightHandles``, ``lightStates``).

    Calls ``camera_utils.ensure_custom_attributes`` first so the CA block
    is guaranteed to exist.
    """
    if rt is None or camera_node is None:
        return

    import traceback
    log_path = r"C:\Users\RMatv\AppData\Local\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\Focus\debug_log.txt"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- save_light_preset start for {getattr(camera_node, 'name', 'N/A')} ---\n")
            
        camera_utils.ensure_custom_attributes(camera_node)
        lights = get_all_lights()
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"  Found {len(lights)} lights in scene.\n")

        handles = rt.Array()
        states = rt.Array()
        for lgt in lights:
            try:
                h = rt.GetHandleByAnim(lgt)
                s = _get_light_enabled(lgt)
                rt.append(handles, h)
                rt.append(states, s)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"    Light: {lgt.name}, Handle: {h}, Enabled: {s}\n")
            except Exception as lgt_err:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"    Error reading light {getattr(lgt, 'name', 'N/A')}: {lgt_err}\n")
                continue

        # Write to CA
        try:
            if hasattr(camera_node, "cameraLightPresets"):
                camera_node.cameraLightPresets.lightHandles = handles
                camera_node.cameraLightPresets.lightStates = states
                camera_node.cameraLightPresets.hasPhysicalPreset = True
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  Saved via camera_node.cameraLightPresets block.\n")
            else:
                camera_node.lightHandles = handles
                camera_node.lightStates = states
                camera_node.hasPhysicalPreset = True
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  Saved via direct camera_node properties.\n")
        except Exception as write_err:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"  Error writing to Custom Attributes: {write_err}\n")
                traceback.print_exc(file=f)
            raise write_err
            
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- save_light_preset end success ---\n\n")
            
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"=== save_light_preset failed ===: {e}\n")
                traceback.print_exc(file=f)
        except:
            pass


# ── load ─────────────────────────────────────────────────────────────────────

def load_light_preset(camera_node):
    """Read ``lightHandles`` / ``lightStates`` from the camera's CA.

    Returns:
        list[tuple[int, bool]]  – pairs of (handle, enabled_state), or
        None if no preset is stored.
    """
    if rt is None or camera_node is None:
        return None

    import traceback
    log_path = r"C:\Users\RMatv\AppData\Local\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\Focus\debug_log.txt"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- load_light_preset start for {getattr(camera_node, 'name', 'N/A')} ---\n")
            
        if not has_light_preset(camera_node):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("  has_light_preset returned False.\n")
            return None

        handles = None
        states = None
        
        try:
            if hasattr(camera_node, "cameraLightPresets"):
                handles = camera_node.cameraLightPresets.lightHandles
                states = camera_node.cameraLightPresets.lightStates
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  Read via camera_node.cameraLightPresets block.\n")
            else:
                handles = camera_node.lightHandles
                states = camera_node.lightStates
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("  Read via direct camera_node properties.\n")
        except Exception as read_err:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"  Error reading from Custom Attributes: {read_err}\n")
                traceback.print_exc(file=f)
            return None

        if handles is None or states is None:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("  handles or states is None.\n")
            return None

        # Convert pymxs array to python list to avoid index base issues
        try:
            py_handles = list(handles)
            py_states = list(states)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"  Converted to python lists. Length: {len(py_handles)}\n")
        except Exception as conv_err:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"  Failed to convert to python lists: {conv_err}\n")
                traceback.print_exc(file=f)
            py_handles = None
            py_states = None

        result = []
        if py_handles is not None and py_states is not None:
            for h, s in zip(py_handles, py_states):
                result.append((int(h), bool(s)))
        else:
            try:
                count = int(handles.count)
            except Exception:
                try: count = len(handles)
                except Exception: count = 0
            
            for i in range(1, count + 1):
                try:
                    h = handles[i]
                    s = states[i]
                    result.append((int(h), bool(s)))
                except Exception:
                    try:
                        h = handles[i-1]
                        s = states[i-1]
                        result.append((int(h), bool(s)))
                    except Exception:
                        continue

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"  Loaded preset with {len(result)} lights.\n")
            f.write("--- load_light_preset end success ---\n\n")
            
        return result if result else None
        
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"=== load_light_preset failed ===: {e}\n")
                traceback.print_exc(file=f)
        except:
            pass
        return None


# ── apply ────────────────────────────────────────────────────────────────────

def apply_light_preset(camera_node):
    """Apply a previously saved light preset.

    For each stored handle, find the light via ``rt.GetAnimByHandle`` and
    restore its enabled state.  Handles pointing to deleted nodes are silently
    skipped.  Lights that exist in the scene but are NOT in the preset are left
    untouched (Variant A).
    """
    import traceback
    log_path = r"C:\Users\RMatv\AppData\Local\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\Focus\debug_log.txt"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- apply_light_preset start for {getattr(camera_node, 'name', 'N/A')} ---\n")
            
        preset = load_light_preset(camera_node)
        if preset is None:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("  No preset loaded (preset is None).\n")
            return

        for handle, state in preset:
            try:
                node = rt.GetAnimByHandle(handle)
                if node is None:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"    Handle {handle}: Node is None.\n")
                    continue
                if not rt.isValidNode(node):
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"    Handle {handle} ({node}): Node is invalid/deleted.\n")
                    continue
                
                prev_state = _get_light_enabled(node)
                _set_light_enabled(node, state)
                new_state = _get_light_enabled(node)
                
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"    Light: {node.name}, Handle: {handle}, State change: {prev_state} -> {new_state} (target: {state})\n")
            except Exception as app_err:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"    Error applying light for handle {handle}: {app_err}\n")
                continue
                
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- apply_light_preset end ---\n\n")
            
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"=== apply_light_preset failed ===: {e}\n")
                traceback.print_exc(file=f)
        except:
            pass


# ── query / clear ────────────────────────────────────────────────────────────

def has_light_preset(camera_node):
    """Return True if the camera already stores a physical light preset."""
    if rt is None or camera_node is None:
        return False
    try:
        if hasattr(camera_node, "cameraLightPresets"):
            return bool(camera_node.cameraLightPresets.hasPhysicalPreset)
        return bool(camera_node.hasPhysicalPreset)
    except Exception:
        return False


def clear_light_preset(camera_node):
    """Remove the physical light preset from the camera's CA."""
    if rt is None or camera_node is None:
        return
    try:
        camera_node.lightHandles = rt.Array()
        camera_node.lightStates = rt.Array()
        camera_node.hasPhysicalPreset = False
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

    Corona stores LightMix channels through the ``CoronaRenderer.CoronaFp``
    scripted interface which exposes:
      - ``LightMix_GetChannelCount()``
      - ``LightMix_GetChannelName(i)``
      - ``LightMix_GetChannelIntensity(i)``
      - ``LightMix_GetChannelColor(i)``
      - ``LightMix_GetChannelEnabled(i)``
    Channels are 0-indexed.
    """
    try:
        count = int(rt.execute("(CoronaRenderer.CoronaFp).LightMix_GetChannelCount()"))
    except Exception:
        return False

    names = rt.Array()
    intensities = rt.Array()
    colors_r = rt.Array()
    colors_g = rt.Array()
    colors_b = rt.Array()
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
            # Store colour components separately (MAXScript Point3 or Color)
            rt.append(colors_r, float(color.r) if color else 255.0)
            rt.append(colors_g, float(color.g) if color else 255.0)
            rt.append(colors_b, float(color.b) if color else 255.0)
            rt.append(enabled_states, bool(enabled))
        except Exception:
            continue

    try:
        camera_node.lmixNames = names
        camera_node.lmixIntensities = intensities
        camera_node.lmixColorsR = colors_r
        camera_node.lmixColorsG = colors_g
        camera_node.lmixColorsB = colors_b
        camera_node.lmixEnabled = enabled_states
        camera_node.lmixRenderer = "corona"
        camera_node.hasMixPreset = True
    except Exception:
        return False

    return True


def _apply_corona_lightmix(camera_node):
    """Restore Corona LightMix channels from the camera's CA."""
    try:
        names = camera_node.lmixNames
        intensities = camera_node.lmixIntensities
        colors_r = camera_node.lmixColorsR
        colors_g = camera_node.lmixColorsG
        colors_b = camera_node.lmixColorsB
        enabled_states = camera_node.lmixEnabled
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
            cr = float(colors_r[idx_mx])
            cg = float(colors_g[idx_mx])
            cb = float(colors_b[idx_mx])
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

    V-Ray exposes LightMix through properties on the active V-Ray renderer:
      - ``colorMap_lightmixIntensities``  – array of float intensities
      - ``colorMap_lightmixColors``       – array of Color values
    """
    try:
        renderer = rt.renderers.current
        intensities_src = renderer.colorMap_lightmixIntensities
        colors_src = renderer.colorMap_lightmixColors
    except Exception:
        return False

    # Copy into fresh MAXScript arrays so they are independent of the renderer
    intensities = rt.Array()
    colors_r = rt.Array()
    colors_g = rt.Array()
    colors_b = rt.Array()

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
                rt.append(colors_r, float(c.r))
                rt.append(colors_g, float(c.g))
                rt.append(colors_b, float(c.b))
            except Exception:
                rt.append(colors_r, 255.0)
                rt.append(colors_g, 255.0)
                rt.append(colors_b, 255.0)

    try:
        camera_node.lmixNames = rt.Array()  # V-Ray has no channel names
        camera_node.lmixIntensities = intensities
        camera_node.lmixColorsR = colors_r
        camera_node.lmixColorsG = colors_g
        camera_node.lmixColorsB = colors_b
        camera_node.lmixEnabled = rt.Array()  # V-Ray has no per-channel enable
        camera_node.lmixRenderer = "vray"
        camera_node.hasMixPreset = True
    except Exception:
        return False

    return True


def _apply_vray_lightmix(camera_node):
    """Restore V-Ray LightMix values from the camera's CA back to the renderer."""
    try:
        intensities = camera_node.lmixIntensities
        colors_r = camera_node.lmixColorsR
        colors_g = camera_node.lmixColorsG
        colors_b = camera_node.lmixColorsB
    except Exception:
        return False

    if intensities is None:
        return False

    try:
        renderer = rt.renderers.current
    except Exception:
        return False

    # Rebuild the MAXScript arrays expected by V-Ray
    int_arr = rt.Array()
    col_arr = rt.Array()
    int_count = int(intensities.count) if hasattr(intensities, "count") else 0
    for i in range(1, int_count + 1):
        try:
            rt.append(int_arr, float(intensities[i]))
        except Exception:
            rt.append(int_arr, 1.0)

    cr_count = int(colors_r.count) if hasattr(colors_r, "count") else 0
    for i in range(1, cr_count + 1):
        try:
            c = rt.Color(float(colors_r[i]), float(colors_g[i]), float(colors_b[i]))
            rt.append(col_arr, c)
        except Exception:
            rt.append(col_arr, rt.Color(255, 255, 255))

    try:
        renderer.colorMap_lightmixIntensities = int_arr
        renderer.colorMap_lightmixColors = col_arr
    except Exception:
        return False

    return True


# ── Public LightMix API ─────────────────────────────────────────────────────

def save_lightmix_preset(camera_node):
    """Snapshot the current LightMix state and store it in the camera's CA.

    Automatically detects the active renderer (Corona / V-Ray).
    """
    if rt is None or camera_node is None:
        return

    camera_utils.ensure_custom_attributes(camera_node)

    renderer_type = detect_renderer()
    if renderer_type == "corona":
        _save_corona_lightmix(camera_node)
    elif renderer_type == "vray":
        _save_vray_lightmix(camera_node)


def apply_lightmix_preset(camera_node):
    """Restore a previously saved LightMix preset to the active renderer.

    The preset records which renderer was used when saving; if the current
    renderer differs from the stored one, the operation is skipped.
    """
    if rt is None or camera_node is None:
        return
    if not has_lightmix_preset(camera_node):
        return

    try:
        stored_renderer = str(camera_node.lmixRenderer).lower()
    except Exception:
        stored_renderer = ""

    current = detect_renderer()

    # Only apply if the renderer matches
    if stored_renderer == "corona" and current == "corona":
        _apply_corona_lightmix(camera_node)
    elif stored_renderer == "vray" and current == "vray":
        _apply_vray_lightmix(camera_node)


def has_lightmix_preset(camera_node):
    """Return True if the camera stores a LightMix preset."""
    if rt is None or camera_node is None:
        return False
    try:
        return bool(camera_node.hasMixPreset)
    except Exception:
        return False


def clear_lightmix_preset(camera_node):
    """Remove the LightMix preset from the camera's CA."""
    if rt is None or camera_node is None:
        return
    try:
        camera_node.lmixNames = rt.Array()
        camera_node.lmixIntensities = rt.Array()
        camera_node.lmixColorsR = rt.Array()
        camera_node.lmixColorsG = rt.Array()
        camera_node.lmixColorsB = rt.Array()
        camera_node.lmixEnabled = rt.Array()
        camera_node.lmixRenderer = ""
        camera_node.hasMixPreset = False
    except Exception:
        pass


# ── Render-element setup ────────────────────────────────────────────────────

def setup_lightmix_elements():
    """Ensure that a LightMix render element exists in the scene.

    Creates one if missing.  Supports Corona (``CShading_LightMix``) and
    V-Ray (``VRayLightMix``).

    Returns:
        bool – True if the element already existed or was created successfully.
    """
    if rt is None:
        return False

    renderer_type = detect_renderer()

    if renderer_type == "corona":
        return _ensure_render_element("CShading_LightMix")
    elif renderer_type == "vray":
        return _ensure_render_element("VRayLightMix")
    return False


def _ensure_render_element(class_name):
    """Check whether a render element of *class_name* exists; create it if not.

    Uses ``rt.maxOps.GetCurRenderElementMgr()`` to query and add elements.
    """
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()

        target_class = rt.execute(class_name)
        # target_class is the MAXScript class value; we'll compare class names

        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            elem_class_name = str(rt.classOf(elem))
            if elem_class_name.lower() == class_name.lower():
                return True  # Already exists

        # Create and add the element
        new_elem = rt.execute("{cls}()".format(cls=class_name))
        if new_elem is not None:
            mgr.AddRenderElement(new_elem)
            return True
    except Exception:
        pass
    return False

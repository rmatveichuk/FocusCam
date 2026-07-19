# -*- coding: utf-8 -*-
# Author: Roman Matveichuk
# Telegram: https://t.me/refer_manage
# GitHub: https://github.com/rmatveichuk/FocusCam
"""
Focus – Light Utilities
~~~~~~~~~~~~~~~~~~~~~~~~
Light preset saving / restoring and LightMix integration for the Focus plugin.

Provides two layers of light control per camera:
  • Physical Light Preset  – stores on/off state of every scene light.
  • LightMix Preset        – stores renderer-level LightMix channel data
                             (Corona or V-Ray).
"""

import os

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

def _find_render_element_vfb_channel_index(element_name):
    """Find the VFB channel index (2-based) of a render element, excluding LightSelect elements."""
    if rt is None:
        return 2
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()
        vfb_index = 2  # 0 is Beauty, 1 is Alpha
        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            elem_class = str(rt.classOf(elem)).lower()
            # Exclude LightSelect elements as they are not listed in the VFB channel dropdown
            if "lightselect" in elem_class:
                continue
            if elem.elementName == element_name:
                return vfb_index
            vfb_index += 1
    except Exception:
        pass
    return 2


def _ensure_corona_camera_lightmix_element(camera_node):
    """Ensure a CShading_LightMix element named LMix_<CameraName> exists in the scene."""
    if rt is None or camera_node is None:
        return None
    element_name = "LMix_{}".format(camera_node.name)
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()

        # Check if it already exists
        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            if str(rt.classOf(elem)).lower() == "cshading_lightmix":
                if elem.elementName == element_name:
                    return elem

        # Create new CShading_LightMix element
        new_elem = rt.execute("CShading_LightMix()")
        if new_elem is not None:
            new_elem.elementName = element_name
            mgr.AddRenderElement(new_elem)
            return new_elem
    except Exception:
        pass
    return None


def _remove_corona_camera_lightmix_element(camera_node):
    """Delete the camera's specific CShading_LightMix element from the scene."""
    if rt is None or camera_node is None:
        return
    element_name = "LMix_{}".format(camera_node.name)
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()
        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            if str(rt.classOf(elem)).lower() == "cshading_lightmix":
                if elem.elementName == element_name:
                    mgr.RemoveRenderElement(elem)
                    break
    except Exception:
        pass


def _find_corona_lightmix_channel_index(camera_node):
    """Find the 0-based index of the CShading_LightMix render element for the camera."""
    if rt is None or camera_node is None:
        return 0
    element_name = "LMix_{}".format(camera_node.name)
    try:
        mgr = rt.maxOps.GetCurRenderElementMgr()
        num_elements = mgr.NumRenderElements()
        lm_index = 0
        for i in range(num_elements):
            elem = mgr.GetRenderElement(i)
            if str(rt.classOf(elem)).lower() == "cshading_lightmix":
                if elem.elementName == element_name:
                    return lm_index
                lm_index += 1
    except Exception:
        pass
    return 0


def _get_lightmix_preset_path(camera_node):
    """Get the path to the .conf file for the camera's LightMix preset."""
    if rt is None or camera_node is None:
        return None
    
    safe_name = "".join([c for c in camera_node.name if c.isalnum() or c in ("-", "_")]).strip()
    filename = "LMix_{}.conf".format(safe_name)
    
    # Paths definition
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "Focus_LightMix")
    temp_path = os.path.join(temp_dir, filename)
    
    scene_path = rt.maxFilePath
    if scene_path and os.path.exists(scene_path):
        # 1. Search for existing file in subfolders (up to 2 levels deep)
        found_path = None
        for root, dirs, files in os.walk(scene_path):
            # Limit depth to 2 levels to keep it fast
            depth = root[len(scene_path):].count(os.sep)
            if depth > 2:
                dirs[:] = []  # stop recursion for this branch
                continue
            if "Focus_LightMix" in dirs:
                potential_path = os.path.join(root, "Focus_LightMix", filename)
                if os.path.exists(potential_path):
                    found_path = potential_path
                    break
        
        if found_path:
            return found_path
            
        # 2. If file not found, check if Focus_LightMix directory exists anywhere in subfolders
        found_dir = None
        for root, dirs, files in os.walk(scene_path):
            depth = root[len(scene_path):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            if "Focus_LightMix" in dirs:
                found_dir = os.path.join(root, "Focus_LightMix")
                break
                
        # 3. Use the found directory, or default to maxFilePath/Focus_LightMix
        if found_dir:
            presets_dir = found_dir
        else:
            presets_dir = os.path.join(scene_path, "Focus_LightMix")
            
        try:
            os.makedirs(presets_dir, exist_ok=True)
        except Exception:
            pass
            
        target_path = os.path.join(presets_dir, filename)
        
        # If the file exists in TEMP but not in target_path, copy it over
        if not os.path.exists(target_path) and os.path.exists(temp_path):
            try:
                import shutil
                shutil.copy2(temp_path, target_path)
            except Exception:
                pass
                
        return target_path
    else:
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except Exception:
            pass
        return temp_path


def _save_corona_lightmix(camera_node):
    """Save Corona LightMix data using native saveLightMixSettings to a .conf file."""
    _ensure_corona_camera_lightmix_element(camera_node)
    lm_idx = _find_corona_lightmix_channel_index(camera_node)
    
    # Check how many LightMix channels are currently rendered in the active VFB
    vfb_count = 0
    try:
        vfb_count = int(rt.execute("(CoronaRenderer.CoronaFp).numLightMixChannels()"))
    except Exception:
        pass

    # If the camera's specific LightMix channel is not yet rendered/present in the VFB,
    # read/save from the first available active VFB channel (index 0) where the user is making adjustments.
    read_idx = lm_idx if lm_idx < vfb_count else 0
    
    conf_file = _get_lightmix_preset_path(camera_node)
    if not conf_file:
        return False
        
    try:
        # Convert path separators to forward slashes for MAXScript safety
        conf_file_mxs = conf_file.replace("\\", "/")
        rt.execute(
            "(CoronaRenderer.CoronaFp).saveLightMixSettings {read_idx} \"{filename}\""
            .format(read_idx=read_idx, filename=conf_file_mxs)
        )
    except Exception:
        return False

    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            # Mark hasMixPreset as True and populate lmChannels as a flag indicator
            ca.lmChannels = rt.Array()
            rt.append(ca.lmChannels, "use_external_conf")
            ca.hasMixPreset = True
            return True
    except Exception:
        pass
    return False


def _apply_corona_lightmix(camera_node):
    """Restore Corona LightMix channels from the .conf file using loadLightMixSettings."""
    _ensure_corona_camera_lightmix_element(camera_node)
    lm_idx = _find_corona_lightmix_channel_index(camera_node)
    
    # Check how many LightMix channels are currently rendered in the active VFB
    vfb_count = 0
    try:
        vfb_count = int(rt.execute("(CoronaRenderer.CoronaFp).numLightMixChannels()"))
    except Exception:
        pass

    # If the camera's specific LightMix channel is not yet rendered/present in the VFB,
    # apply to the first available active VFB channel (index 0) so the VFB updates visually.
    apply_idx = lm_idx if lm_idx < vfb_count else 0
    
    conf_file = _get_lightmix_preset_path(camera_node)
    if not conf_file or not os.path.exists(conf_file):
        return False
        
    try:
        conf_file_mxs = conf_file.replace("\\", "/")
        rt.execute(
            "(CoronaRenderer.CoronaFp).loadLightMixSettings {apply_idx} \"{filename}\""
            .format(apply_idx=apply_idx, filename=conf_file_mxs)
        )
    except Exception:
        pass

    # Switch the displayed VFB channel to match the LightMix element
    vfb_chan = 2  # Default fallback
    try:
        vfb_chan = _find_render_element_vfb_channel_index("LMix_{}".format(camera_node.name))
    except Exception:
        pass

    try:
        # Switch the VFB displayed render element/channel (this switches VFB dropdown and display)
        rt.execute(
            "(CoronaRenderer.CoronaFp).setDisplayedChannel {vfb_chan}"
            .format(vfb_chan=vfb_chan)
        )
    except Exception:
        pass

    try:
        # Also switch the active LightMix channel in the VFB tab (backup/sync)
        rt.execute("global focus_lm_error = \"\"")
        rt.execute(
            "try ( (CoronaRenderer.CoronaFp).setDisplayedLightMixChannel {apply_idx} ) catch ( focus_lm_error = getCurrentException() )"
            .format(apply_idx=apply_idx)
        )
        err = rt.execute("focus_lm_error")
        if err:
            with open("C:\\Users\\RMatv\\.gemini\\antigravity\\brain\\925fc049-fb8f-412b-9e5d-60184321c2d6\\scratch\\vfb_error.txt", "a", encoding="utf-8") as f:
                f.write("setDisplayedLightMixChannel Error: {}\n".format(err))
    except Exception:
        pass

    return True


# ── V-Ray helpers ────────────────────────────────────────────────────────────

def _save_vray_lightmix(camera_node):
    """Read V-Ray LightMix data (VFB layers JSON) and store it in the camera CA."""
    if rt is None:
        return False
    try:
        mgr_array = rt.vfbControl(rt.Name("getLayerMgr"))
        if mgr_array is None or int(mgr_array.count) == 0:
            return False
        mgr = mgr_array[0]
        json_str = mgr.saveLayersToJSON()
    except Exception:
        return False

    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is not None:
            channels = rt.Array()
            rt.append(channels, "vray_json")
            rt.append(channels, str(json_str))
            ca.lmChannels = channels
            
            # Clear other properties to not confuse with Corona/other
            ca.lmIntensities = rt.Array()
            ca.lmColors = rt.Array()
            ca.lmStates = rt.Array()
            ca.hasMixPreset = True
            return True
    except Exception:
        pass
    return False


def _apply_vray_lightmix(camera_node):
    """Restore V-Ray LightMix values from the camera's CA back to the VFB."""
    if rt is None:
        return False
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None or not ca.hasMixPreset:
            return False
            
        channels = ca.lmChannels
        if channels is None or int(channels.count) < 2:
            return False
            
        flag = str(channels[0])
        if flag != "vray_json":
            return False
            
        json_str = str(channels[1])
    except Exception:
        return False

    try:
        mgr_array = rt.vfbControl(rt.Name("getLayerMgr"))
        if mgr_array is None or int(mgr_array.count) == 0:
            return False
        mgr = mgr_array[0]
        res = bool(mgr.loadLayersFromJSON(json_str))
        if res and hasattr(rt, "vrayIsRenderingIPR") and int(rt.vrayIsRenderingIPR()) > 0:
            try:
                rt.vrayUpdateIPR()
            except Exception:
                pass
        return res
    except Exception:
        return False


# ── Public LightMix API ─────────────────────────────────────────────────────

def save_lightmix_preset(camera_node):
    """Snapshot the current LightMix state and store it in the camera's CA."""
    if rt is None or camera_node is None:
        return

    setup_lightmix_elements()
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

    setup_lightmix_elements()
    current = detect_renderer()
    
    try:
        ca = camera_utils._get_ca_block(camera_node, "cameraLightPresets")
        if ca is None:
            return
        is_vray_preset = False
        if int(ca.lmChannels.count) > 0:
            is_vray_preset = (str(ca.lmChannels[0]) == "vray_json")
    except Exception:
        is_vray_preset = False

    if not is_vray_preset and current == "corona":
        _apply_corona_lightmix(camera_node)
    elif is_vray_preset and current == "vray":
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

        # Remove the camera-specific CShading_LightMix render element
        renderer_type = detect_renderer()
        if renderer_type == "corona":
            _remove_corona_camera_lightmix_element(camera_node)
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

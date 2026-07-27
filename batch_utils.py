# -*- coding: utf-8 -*-
# Author: Roman Matveichuk
# Telegram: https://t.me/refer_manage
# GitHub: https://github.com/rmatveichuk/FocusCam

"""
batch_utils.py — Batch Render automation utilities for FocusCam.

Provides:
    - Filename sanitization for Windows filesystems
    - Output path construction (defaulting to scene_path/renders/Scene_Camera.png)
    - Scene saved warning check
    - Smart Upsert of cameras into 3ds Max batchRenderMgr
"""

import os
import re

try:
    import pymxs
    rt = pymxs.runtime
except ImportError:
    pymxs = None
    rt = None


def sanitize_filename(name: str) -> str:
    """Remove illegal Windows filesystem characters: \\ / : * ? " < > |"""
    if not name:
        return "Camera"
    return re.sub(r'[\\/*?:"<>|]', '_', name)


def check_scene_saved_warning() -> bool:
    """
    Check if the current 3ds Max scene is saved.
    If not saved, displays a bilingual (RU/EN) warning message box.
    Returns True if saved, False otherwise.
    """
    if rt is None or not getattr(rt, "maxFilePath", ""):
        msg_text = (
            "Пожалуйста, сохраните сцену 3ds Max перед добавлением камер в Batch Render,\n"
            "чтобы скрипт мог автоматически сформировать папку рендера.\n\n"
            "Please save your 3ds Max scene before adding cameras to Batch Render\n"
            "so the script can automatically set up the render folder."
        )
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                None,
                "FocusCam — Scene Not Saved / Сцена не сохранена",
                msg_text
            )
        except Exception:
            if rt and hasattr(rt, "messageBox"):
                rt.messageBox(msg_text, title="FocusCam Warning")
        return False
    return True


def build_output_path(cam_node, ext: str = "png", custom_dir: str = None, subfolder: str = "renders", pattern: str = "{Scene}_{Camera}") -> str:
    """
    Construct render output file path for camera.
    Automatically creates the output directory on disk if it does not exist.
    """
    if rt is None:
        return ""

    max_path = getattr(rt, "maxFilePath", "")
    max_name = getattr(rt, "maxFileName", "")

    if custom_dir:
        render_dir = custom_dir
    elif max_path:
        render_dir = os.path.join(max_path, subfolder)
    else:
        return ""

    scene_name = os.path.splitext(max_name)[0] if max_name else "Untitled"
    cam_name = getattr(cam_node, "name", "Camera") if cam_node else "Camera"

    clean_scene = sanitize_filename(scene_name)
    clean_cam = sanitize_filename(cam_name)

    file_name = pattern.replace("{Scene}", clean_scene).replace("{Camera}", clean_cam)
    file_name_with_ext = f"{file_name}.{ext.lstrip('.')}"

    if not os.path.exists(render_dir):
        try:
            os.makedirs(render_dir, exist_ok=True)
        except Exception as e:
            print(f"[FocusCam] Failed to create directory {render_dir}: {e}")

    return os.path.join(render_dir, file_name_with_ext)


def find_view_by_camera(cam_node):
    """Return existing BatchRenderView object for cam_node if present, else None."""
    if rt is None or not hasattr(rt, "batchRenderMgr"):
        return None

    mgr = rt.batchRenderMgr
    try:
        num_views = int(mgr.numViews)
        for i in range(1, num_views + 1):
            v = mgr.GetView(i)
            if v and getattr(v, "camera", None) == cam_node:
                return v
    except Exception as e:
        print(f"[FocusCam] Error searching BatchRender views: {e}")
    return None


def smart_upsert_camera(cam_node, ext: str = "png", custom_dir: str = None, subfolder: str = "renders", pattern: str = "{Scene}_{Camera}"):
    """
    Smart Upsert a camera into 3ds Max Batch Render:
        - If camera exists: updates properties (enabled=True, outputFilename, width, height, pixelAspect=1.0)
        - If camera does not exist: creates a new BatchRenderView entry
    """
    if rt is None or not hasattr(rt, "batchRenderMgr") or cam_node is None:
        return None

    mgr = rt.batchRenderMgr
    view = find_view_by_camera(cam_node)

    if view is None:
        try:
            view = mgr.CreateView(cam_node)
        except Exception as e:
            print(f"[FocusCam] Error creating BatchRender view for {cam_node.name}: {e}")
            return None

    try:
        view.name = getattr(cam_node, "name", "Camera")
        view.camera = cam_node
        view.enabled = True

        output_path = build_output_path(cam_node, ext=ext, custom_dir=custom_dir, subfolder=subfolder, pattern=pattern)
        if output_path:
            view.outputFilename = output_path

        # Sync custom camera resolution from focusResolutionPresets CA if available
        ca_block = _get_res_ca_block(cam_node)
        if ca_block and getattr(ca_block, "hasResolution", False):
            rw = int(getattr(ca_block, "renderWidth", 0))
            rh = int(getattr(ca_block, "renderHeight", 0))
            if rw > 0 and rh > 0:
                view.overridePreset = True
                view.width = rw
                view.height = rh
                view.pixelAspect = 1.0  # Strictly required to prevent aspect ratio corruption in Corona / V-Ray
            else:
                view.overridePreset = False
        else:
            view.overridePreset = False

    except Exception as e:
        print(f"[FocusCam] Error updating BatchRender view parameters: {e}")

    return view


def smart_upsert_all_cameras(cameras, ext: str = "png", custom_dir: str = None, subfolder: str = "renders", pattern: str = "{Scene}_{Camera}") -> int:
    """
    Smart Upsert all cameras in the list into 3ds Max Batch Render.
    Returns the count of processed views.
    """
    count = 0
    if not cameras:
        return count

    for cam in cameras:
        if cam and smart_upsert_camera(cam, ext=ext, custom_dir=custom_dir, subfolder=subfolder, pattern=pattern) is not None:
            count += 1

    return count


def _get_res_ca_block(camera_node):
    """Retrieve focusResolutionPresets custom attribute block from camera_node."""
    if rt is None or camera_node is None:
        return None
    try:
        if not rt.isValidNode(camera_node):
            return None
        ca_count = rt.custAttributes.count(camera_node)
        for i in range(1, ca_count + 1):
            ca = rt.custAttributes.get(camera_node, i)
            ca_def = rt.custAttributes.getDef(ca)
            if ca_def is not None and str(getattr(ca_def, "name", "")) == "focusResolutionPresets":
                return ca
    except Exception:
        pass
    return None

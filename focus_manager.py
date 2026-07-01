# -*- coding: utf-8 -*-
"""
Focus – Main Manager
~~~~~~~~~~~~~~~~~~~~
Entry point and primary controller for the Focus 3ds Max plugin.
Connects the UI to the underlying camera, light, and overlay utilities.
"""

import os

try:
    import pymxs
    rt = pymxs.runtime
except ImportError:
    rt = None

try:
    from PySide6.QtWidgets import QDockWidget, QWidget, QVBoxLayout
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon
except ImportError:
    pass

from . import camera_utils
from . import light_utils
from . import overlay_utils
from .ui_components import FocusUI


class FocusManagerWindow(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Diagnostic logging at startup
        try:
            log_path = os.path.join(os.path.dirname(__file__), "debug_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=== WINDOW INITIALIZATION START ===\n")
                import sys
                import inspect
                # Log sys.path
                f.write(f"sys.path: {sys.path}\n")
                # Log related modules in sys.modules
                mods = [m for m in sys.modules if 'focus' in m.lower() or 'camera' in m.lower()]
                f.write(f"sys.modules match: {mods}\n")
                
                # Check what camera_utils is imported
                from . import camera_utils
                f.write(f"Imported camera_utils path: {getattr(camera_utils, '__file__', 'N/A')}\n")
                try:
                    f.write("Imported camera_utils.switch_to_camera source:\n")
                    f.write(inspect.getsource(camera_utils.switch_to_camera))
                    f.write("\n")
                except Exception as inspect_err:
                    f.write(f"Failed to inspect switch_to_camera: {inspect_err}\n")
                f.write("=== WINDOW INITIALIZATION END ===\n\n")
        except Exception:
            pass

        self.setObjectName("FocusDockWidget")
        self.setWindowTitle("Focus Camera & Light Manager")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFixedWidth(336)
        self.resize(336, 650)
        
        # Window Icon
        icon_path = os.path.join(os.path.dirname(__file__), "Icon.svg")
        if os.path.isfile(icon_path):
            try:
                self.setWindowIcon(QIcon(icon_path))
            except NameError:
                pass
        
        # Overlay manager
        self.overlay_mgr = overlay_utils.OverlayManager()
        
        # Central widget and layout
        central = QWidget()
        # Main widget container
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setWidget(central)
        
        # Init UI
        self.ui = FocusUI()
        self.ui.setFixedWidth(326)
        layout.addWidget(self.ui, alignment=Qt.AlignHCenter)
        
        self._apply_stylesheet()
        self._connect_signals()
        
        # Thumbnail generation state
        self._thumb_timer = QTimer(self)
        self._thumb_timer.timeout.connect(self._process_next_thumbnail)
        self._thumb_queue = []
        
        self.refresh_cameras()
        self.overlay_mgr.register_callback()
        
        # Resolution synchronization timer (polls 3ds Max Render Setup every 500ms)
        self._res_sync_timer = QTimer(self)
        self._res_sync_timer.timeout.connect(self._sync_renderer_resolution)
        self._res_sync_timer.start(500)

    def _apply_stylesheet(self):
        style_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.isfile(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _connect_signals(self):
        self.ui.camera_selected.connect(self.on_camera_selected)
        self.ui.save_light_req.connect(self.on_save_light)
        self.ui.save_lmix_req.connect(self.on_save_lmix)
        self.ui.overlay_toggled.connect(self.on_overlay_toggled)
        self.ui.res_changed.connect(self.on_res_changed)
        self.ui.res_swapped.connect(self.on_res_swapped)
        self.ui.refresh_thumbnail_req.connect(self.on_refresh_thumbnail)
        self.ui.refresh_clicked.connect(self.refresh_cameras)

    def refresh_cameras(self):
        """Discover all cameras, populate UI, and start thumbnail generation."""
        cameras = camera_utils.get_all_cameras()
        self.ui.populate_cameras(cameras)
        
        # Queue all cameras for deferred thumbnail generation
        self._thumb_queue = list(cameras)
        if self._thumb_queue:
            self._thumb_timer.start(100)  # 100ms per camera tick

    def _process_next_thumbnail(self):
        """Timer callback to generate thumbnails one by one without freezing UI."""
        if not self._thumb_queue:
            self._thumb_timer.stop()
            return
            
        cam = self._thumb_queue.pop(0)
        pixmap = camera_utils.grab_viewport_thumbnail(cam, width=320, height=180)
        if pixmap:
            card = self.ui.get_card(cam)
            if card:
                card.set_thumbnail(pixmap)

    # -- Signal Handlers --

    def on_camera_selected(self, camera_node):
        """Called when a camera is clicked in the list."""
        # Stop background thumbnail generation to prevent race conditions/viewport hijack
        try:
            if self._thumb_timer.isActive():
                self._thumb_timer.stop()
            self._thumb_queue.clear()
        except:
            pass

        # Debug logging to find the root cause
        if rt:
            try:
                log_path = os.path.join(os.path.dirname(__file__), "debug_log.txt")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("=== DEBUG START ===\n")
                    f.write(f"camera_node: {camera_node} (type: {type(camera_node)})\n")
                    f.write(f"camera_node.name: {getattr(camera_node, 'name', 'N/A')}\n")
                    
                    # Test Name and getType() conversions
                    t_name = rt.Name("view_camera")
                    f.write(f"rt.Name('view_camera') str: '{str(t_name)}', repr: '{repr(t_name)}', type: {type(t_name)}\n")
                    
                    curr_type = rt.viewport.getType()
                    f.write(f"rt.viewport.getType() str: '{str(curr_type)}', repr: '{repr(curr_type)}', type: {type(curr_type)}\n")
                    f.write(f"Comparison 1 (str == str): {str(curr_type) == str(t_name)}\n")
                    f.write(f"Comparison 2 (obj == obj): {curr_type == t_name}\n")
                    
                    # Log camera_utils info
                    import inspect
                    f.write(f"camera_utils path: {getattr(camera_utils, '__file__', 'N/A')}\n")
                    try:
                        f.write("camera_utils.switch_to_camera source:\n")
                        f.write(inspect.getsource(camera_utils.switch_to_camera))
                        f.write("\n")
                    except Exception as inspect_err:
                        f.write(f"Failed to inspect switch_to_camera: {inspect_err}\n")
                    
                    # Test Selection
                    f.write("Attempting rt.select(camera_node)...\n")
                    try:
                        rt.select(camera_node)
                        f.write("rt.select(camera_node) succeeded.\n")
                    except Exception as sel_err:
                        f.write(f"rt.select failed: {sel_err}\n")
                        
                    # Test Modify Panel
                    f.write("Attempting setCommandPanelTaskMode...\n")
                    try:
                        rt.setCommandPanelTaskMode(rt.Name("modify"))
                        f.write("setCommandPanelTaskMode succeeded.\n")
                    except Exception as cmd_err:
                        f.write(f"setCommandPanelTaskMode failed: {cmd_err}\n")
                        
                    f.write("=== DEBUG END ===\n\n")
            except Exception as e:
                pass

        # 1. Switch Viewport
        camera_utils.switch_to_camera(camera_node)
        
        # 2. Update overlays targeting
        self.overlay_mgr.set_target_camera(camera_node)
        
        # 3. Apply Physical Light Preset (if any)
        if light_utils.has_light_preset(camera_node):
            light_utils.apply_light_preset(camera_node)
            
        # 4. Apply LightMix Preset (if any)
        if light_utils.has_lightmix_preset(camera_node):
            light_utils.apply_lightmix_preset(camera_node)
            
        # 5. Apply Resolution (if any)
        w, h, has_res = camera_utils.load_resolution(camera_node)
        if has_res:
            camera_utils.apply_resolution(w, h)
        else:
            # If camera has no resolution, save the current global renderer settings to it
            if rt:
                cur_w, cur_h = rt.renderWidth, rt.renderHeight
                camera_utils.save_resolution(camera_node, cur_w, cur_h)
                # Update UI spinboxes to reflect the newly saved resolution
                self.ui.select_camera(camera_node) 
                
        if rt:
            rt.forceCompleteRedraw()
            
        # Trigger a delayed high-quality thumbnail refresh for the selected camera.
        # Delay allows the viewport to completely render light/resolution updates first.
        QTimer.singleShot(250, lambda: self.on_refresh_thumbnail(camera_node.name))

    def on_save_light(self):
        camera_node = self.ui.active_camera_node
        if camera_node and camera_utils.is_node_valid(camera_node):
            light_utils.save_light_preset(camera_node)

    def on_save_lmix(self):
        camera_node = self.ui.active_camera_node
        if camera_node and camera_utils.is_node_valid(camera_node):
            light_utils.save_lightmix_preset(camera_node)
            # Update thumbnail after saving lightmix (which updates viewport display)
            QTimer.singleShot(250, lambda: self.on_refresh_thumbnail(camera_node.name))

    def on_refresh_thumbnail(self, camera_name: str):
        """Manually refresh the thumbnail of a given camera by its name."""
        if not rt:
            return
        camera_node = rt.getNodeByName(camera_name)
        if camera_node and camera_utils.is_node_valid(camera_node):
            pixmap = camera_utils.grab_viewport_thumbnail(camera_node, width=320, height=180)
            if pixmap:
                card = self.ui.get_card(camera_node)
                if card:
                    card.set_thumbnail(pixmap)

    def on_overlay_toggled(self, overlay_type: int, is_active: bool):
        if is_active:
            self.overlay_mgr.active_overlays.add(overlay_type)
        else:
            self.overlay_mgr.active_overlays.discard(overlay_type)
        if rt:
            rt.forceCompleteRedraw()

    def on_res_changed(self, w: int, h: int):
        camera_node = self.ui.active_camera_node
        if camera_node and camera_utils.is_node_valid(camera_node):
            camera_utils.save_resolution(camera_node, w, h)
            camera_utils.apply_resolution(w, h)
            if rt:
                rt.forceCompleteRedraw()

    def on_res_swapped(self):
        camera_node = self.ui.active_camera_node
        if camera_node and camera_utils.is_node_valid(camera_node):
            camera_utils.swap_resolution(camera_node)
            if rt:
                rt.forceCompleteRedraw()

    def _sync_renderer_resolution(self):
        """Poll 3ds Max Render Setup and update spinboxes and camera CA if they differ."""
        if not rt or not self.ui.active_camera_node:
            return
            
        # Do not overwrite if user is actively typing in the spinboxes
        if self.ui.w_spin.hasFocus() or self.ui.h_spin.hasFocus():
            return
            
        try:
            if not camera_utils.is_node_valid(self.ui.active_camera_node):
                self.ui.active_camera_node = None
                self.ui.set_toolbar_enabled(False)
                self.refresh_cameras()
                return

            cur_w = int(rt.renderWidth)
            cur_h = int(rt.renderHeight)
            
            if self.ui.w_spin.value() != cur_w or self.ui.h_spin.value() != cur_h:
                camera_utils.save_resolution(self.ui.active_camera_node, cur_w, cur_h)
                self.ui.w_spin.blockSignals(True)
                self.ui.h_spin.blockSignals(True)
                self.ui.w_spin.setValue(cur_w)
                self.ui.h_spin.setValue(cur_h)
                self.ui.w_spin.blockSignals(False)
                self.ui.h_spin.blockSignals(False)
        except Exception:
            pass

    def closeEvent(self, event):
        """Clean up callbacks when the window is closed."""
        self.overlay_mgr.unregister_callback()
        if self._thumb_timer.isActive():
            self._thumb_timer.stop()
        if self._res_sync_timer.isActive():
            self._res_sync_timer.stop()
        super().closeEvent(event)


# Global reference to keep window alive in 3ds Max
_focus_window = None

def show_focus_window():
    """Launch the Focus UI in 3ds Max."""
    global _focus_window
    
    # Find existing dock widget by object name safely
    from PySide6.QtWidgets import QApplication, QDockWidget
    existing = None
    try:
        for widget in QApplication.topLevelWidgets():
            try:
                if widget.objectName() == "FocusDockWidget":
                    existing = widget
                    break
                found = widget.findChild(QDockWidget, "FocusDockWidget")
                if found:
                    existing = found
                    break
            except (RuntimeError, ReferenceError):
                pass
    except Exception:
        pass

    if existing is not None:
        try:
            existing.close()
            existing.deleteLater()
            QApplication.processEvents()
        except Exception:
            pass

    # Try to get the 3ds Max main window as parent
    max_main_window = None
    try:
        import qtmax
        max_main_window = qtmax.GetQMaxMainWindow()
    except Exception:
        pass

    _focus_window = FocusManagerWindow(parent=max_main_window)
    
    if max_main_window:
        try:
            max_main_window.addDockWidget(Qt.RightDockWidgetArea, _focus_window)
            _focus_window.setFloating(True)  # Starts floating, but is dockable
        except Exception:
            pass
            
    _focus_window.show()

if __name__ == "__main__":
    # For quick testing within MaxScript editor via `python.executeFile`
    show_focus_window()

# -*- coding: utf-8 -*-
"""
Focus – UI Components
~~~~~~~~~~~~~~~~~~~~~
PySide6 interface elements for the Focus 3ds Max plugin.
Includes the custom draggable Camera List, Camera Cards, and the unified Toolbar.
"""

import math

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
        QFrame, QListWidget, QListWidgetItem, QAbstractItemView,
        QSpinBox, QMenu, QSizePolicy
    )
    from PySide6.QtCore import Qt, Signal, QSize, QTimer
    from PySide6.QtGui import QPixmap, QIcon, QCursor
except ImportError:
    pass

from . import camera_utils
from . import light_utils


class ThumbnailLabel(QLabel):
    """
    A custom label that displays a QPixmap scaled to fill the entire label
    proportionally (cropping the center) and rescales dynamically on resize.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setStyleSheet("background-color: #222; border-radius: 2px;")
        self.setAlignment(Qt.AlignCenter)
        
    def setPixmap(self, pixmap, target_w=None, target_h=None):
        self.original_pixmap = pixmap
        self.target_w = target_w
        self.target_h = target_h
        self.setStyleSheet("background-color: #000000; border-radius: 2px;")
        self.update_thumbnail()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_thumbnail()
        
    def update_thumbnail(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        
        try:
            # 1. First, mathematically crop the original DIB to the target camera aspect ratio.
            if hasattr(self, 'target_w') and self.target_w and self.target_h:
                target_ratio = self.target_w / self.target_h
                orig_w = self.original_pixmap.width()
                orig_h = self.original_pixmap.height()
                orig_ratio = orig_w / orig_h

                if target_ratio > orig_ratio:
                    # Target is wider. We must crop the top and bottom of the original DIB.
                    new_h = int(orig_w / target_ratio)
                    crop_y = (orig_h - new_h) // 2
                    cropped = self.original_pixmap.copy(0, crop_y, orig_w, new_h)
                else:
                    # Target is narrower. We must crop the left and right of the original DIB.
                    new_w = int(orig_h * target_ratio)
                    crop_x = (orig_w - new_w) // 2
                    cropped = self.original_pixmap.copy(crop_x, 0, new_w, orig_h)
            else:
                cropped = self.original_pixmap

            # 2. Now scale the cropped image into the label size.
            # Using KeepAspectRatio ensures it will fit perfectly inside 300x168,
            # leaving pure black bars (#000000) where it doesn't cover the label.
            scaled = cropped.scaled(
                w, h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
        except Exception:
            super().setPixmap(self.original_pixmap)


def safe_refresh_style(widget):
    """Safely refresh stylesheet polish state without crashing on deleted styles."""
    try:
        style = widget.style()
        if style:
            style.unpolish(widget)
            style.polish(widget)
    except (RuntimeError, TypeError, ReferenceError):
        try:
            widget.ensurePolished()
        except Exception:
            pass


class CameraCardWidget(QFrame):
    """
    A single camera item card displaying its thumbnail, name, and preset status.
    """
    clicked = Signal(object)        # Emits the camera_node when left-clicked
    right_clicked = Signal(object)  # Emits the camera_node when right-clicked

    def __init__(self, camera_node, parent=None):
        super().__init__(parent)
        self.camera_node = camera_node
        self.setObjectName("cameraCard")
        self.setFixedSize(308, 218)

        # -- Layout --
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)

        # Thumbnail (placeholder initially)
        self.thumbnail_lbl = ThumbnailLabel()
        self.thumbnail_lbl.setFixedSize(304, 171)
        self.layout.addWidget(self.thumbnail_lbl, alignment=Qt.AlignCenter)

        # Info bar (Name + Indicators)
        self.info_layout = QHBoxLayout()
        self.info_layout.setContentsMargins(4, 0, 4, 0)
        
        self.name_lbl = QLabel(getattr(camera_node, "name", "Unknown Camera"))
        self.name_lbl.setObjectName("cameraName")
        self.info_layout.addWidget(self.name_lbl, stretch=1)

        # Preset indicators (small dots or text)
        self.light_ind = QLabel("L")
        self.light_ind.setObjectName("presetIndicator")
        self.light_ind.setToolTip("Physical Light Preset")
        
        self.lmix_ind = QLabel("M")
        self.lmix_ind.setObjectName("presetIndicator")
        self.lmix_ind.setToolTip("LightMix Preset")

        self.info_layout.addWidget(self.light_ind)
        self.info_layout.addWidget(self.lmix_ind)

        self.layout.addLayout(self.info_layout)
        
        self.update_indicators()

    def set_active(self, active: bool):
        if active:
            self.setObjectName("cameraCardActive")
            self.name_lbl.setObjectName("cameraNameActive")
        else:
            self.setObjectName("cameraCard")
            self.name_lbl.setObjectName("cameraName")
        
        # Force stylesheet re-evaluation safely
        safe_refresh_style(self)
        safe_refresh_style(self.name_lbl)

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            w, h, has = camera_utils.load_resolution(self.camera_node)
            if has and w > 0 and h > 0:
                self.thumbnail_lbl.setPixmap(pixmap, target_w=w, target_h=h)
            else:
                # If the camera has no custom resolution saved, we just crop it 
                # mathematically to exactly 16:9 so it completely fills the card 
                # without any black letterboxing.
                self.thumbnail_lbl.setPixmap(pixmap, target_w=304, target_h=171)

    def update_indicators(self):
        """Check CA and update the small L/M preset indicators."""
        has_l = light_utils.has_light_preset(self.camera_node)
        has_m = light_utils.has_lightmix_preset(self.camera_node)
        
        self.light_ind.setObjectName("presetIndicatorActive" if has_l else "presetIndicator")
        self.lmix_ind.setObjectName("presetIndicatorActive" if has_m else "presetIndicator")
        
        safe_refresh_style(self.light_ind)
        safe_refresh_style(self.lmix_ind)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.camera_node)
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self.camera_node)
        super().mousePressEvent(event)


class CameraListWidget(QListWidget):
    """
    A list widget configured for vertical drag-and-drop sorting.
    """
    order_changed = Signal()  # Emitted after drop

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(2)
        # Hide scrollbar handles unless hovered (handled in QSS)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setFocusPolicy(Qt.NoFocus)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()


class FocusUI(QWidget):
    """
    The main UI container holding the camera list and the unified bottom toolbar.
    """
    camera_selected = Signal(object)
    
    # Preset signals
    save_light_req = Signal()
    save_lmix_req = Signal()
    
    # Overlay signals
    overlay_toggled = Signal(int, bool)  # type, is_active
    
    # Resolution signals
    res_changed = Signal(int, int)
    res_swapped = Signal()
    
    # Thumbnail refresh signal (passes camera name string to prevent cross-thread pickle issues)
    refresh_thumbnail_req = Signal(str)
    
    # Refresh scene cameras list signal
    refresh_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_camera_node = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignHCenter)

        # -- Camera List --
        self.cam_list = CameraListWidget()
        self.cam_list.setFixedWidth(326)
        self.cam_list.order_changed.connect(self._on_list_reordered)
        self.layout.addWidget(self.cam_list, stretch=1)
        
        # -- Toolbar --
        self.toolbar = QFrame()
        self.toolbar.setObjectName("toolbarPanel")
        self.toolbar.setFixedWidth(326)
        
        self.tb_main_layout = QVBoxLayout(self.toolbar)
        self.tb_main_layout.setContentsMargins(4, 4, 4, 4)
        self.tb_main_layout.setSpacing(4)
        
        # Row 1 Layout: w_spin -> lock_btn -> h_spin -> swap_btn -> refresh_btn
        self.tb_row1 = QHBoxLayout()
        self.tb_row1.setSpacing(4)
        
        # Resolution controls
        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 99999)
        self.w_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.w_spin.setAlignment(Qt.AlignCenter)
        
        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setObjectName("lockButton")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setToolTip("Lock Aspect Ratio")
        self.lock_btn.toggled.connect(self._on_lock_toggled)
        self._locked_aspect_ratio = None
        self._is_syncing_res = False
        
        self.h_spin = QSpinBox()
        self.h_spin.setRange(1, 99999)
        self.h_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.h_spin.setAlignment(Qt.AlignCenter)
        
        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setObjectName("swapButton")
        self.swap_btn.setFixedSize(32, 28)
        self.swap_btn.clicked.connect(self._on_swap_clicked)
        
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.setFixedSize(32, 28)
        self.refresh_btn.setToolTip("Rescan scene cameras")
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        
        # Connect spinboxes
        self.w_spin.editingFinished.connect(self._on_res_edited)
        self.h_spin.editingFinished.connect(self._on_res_edited)
        self.w_spin.valueChanged.connect(self._on_w_value_changed)
        self.h_spin.valueChanged.connect(self._on_h_value_changed)

        self.tb_row1.addWidget(self.w_spin, stretch=1)
        self.tb_row1.addWidget(self.lock_btn)
        self.tb_row1.addWidget(self.h_spin, stretch=1)
        self.tb_row1.addWidget(self.swap_btn)
        self.tb_row1.addWidget(self.refresh_btn)
        
        # Row 2 Layout: ov1 -> ov2 -> ov3 -> ov4 -> light_btn -> lmix_btn
        self.tb_row2 = QHBoxLayout()
        self.tb_row2.setSpacing(4)
        
        self.ov1 = QPushButton("1")
        self.ov1.setObjectName("overlayButton")
        self.ov1.setFixedHeight(28)
        self.ov1.setCheckable(True)
        self.ov1.setToolTip("Rule of Thirds")
        self.ov1.toggled.connect(lambda state: self.overlay_toggled.emit(1, state))
        
        self.ov2 = QPushButton("2")
        self.ov2.setObjectName("overlayButton")
        self.ov2.setFixedHeight(28)
        self.ov2.setCheckable(True)
        self.ov2.setToolTip("Golden Ratio")
        self.ov2.toggled.connect(lambda state: self.overlay_toggled.emit(2, state))
        
        self.ov3 = QPushButton("3")
        self.ov3.setObjectName("overlayButton")
        self.ov3.setFixedHeight(28)
        self.ov3.setCheckable(True)
        self.ov3.setToolTip("Diagonals")
        self.ov3.toggled.connect(lambda state: self.overlay_toggled.emit(3, state))
        
        self.ov4 = QPushButton("4")
        self.ov4.setObjectName("overlayButton")
        self.ov4.setFixedHeight(28)
        self.ov4.setCheckable(True)
        self.ov4.setToolTip("Fibonacci Spiral")
        self.ov4.toggled.connect(lambda state: self.overlay_toggled.emit(4, state))

        # Preset buttons
        self.light_btn = QPushButton("Light")
        self.light_btn.setObjectName("presetButton")
        self.light_btn.setCheckable(True)
        self.light_btn.setToolTip("Physical Light Preset")
        self.light_btn.clicked.connect(self._on_light_clicked)
        
        self.lmix_btn = QPushButton("LMix")
        self.lmix_btn.setObjectName("presetButton")
        self.lmix_btn.setCheckable(True)
        self.lmix_btn.setToolTip("LightMix Preset")
        self.lmix_btn.clicked.connect(self._on_lmix_clicked)

        self.tb_row2.addWidget(self.ov1)
        self.tb_row2.addWidget(self.ov2)
        self.tb_row2.addWidget(self.ov3)
        self.tb_row2.addWidget(self.ov4)
        self.tb_row2.addWidget(self.light_btn, stretch=1)
        self.tb_row2.addWidget(self.lmix_btn, stretch=1)
        
        self.tb_main_layout.addLayout(self.tb_row1)
        self.tb_main_layout.addLayout(self.tb_row2)
        
        self.layout.addWidget(self.toolbar)
        self.set_toolbar_enabled(False)
        
    def populate_cameras(self, cameras):
        """Populate the list with CameraCardWidgets."""
        self.cam_list.clear()
        for cam in cameras:
            card = CameraCardWidget(cam)
            card.clicked.connect(self._on_card_clicked)
            card.right_clicked.connect(self._on_card_right_clicked)
            
            item = QListWidgetItem(self.cam_list)
            item.setSizeHint(card.sizeHint())
            # Store node reference in user data for reordering
            item.setData(Qt.UserRole, cam)
            
            self.cam_list.addItem(item)
            self.cam_list.setItemWidget(item, card)

    def set_toolbar_enabled(self, state: bool):
        # Disable/enable camera-specific controls while keeping the refresh button enabled
        self.w_spin.setEnabled(state)
        self.h_spin.setEnabled(state)
        self.lock_btn.setEnabled(state)
        self.swap_btn.setEnabled(state)
        
        self.ov1.setEnabled(state)
        self.ov2.setEnabled(state)
        self.ov3.setEnabled(state)
        self.ov4.setEnabled(state)
        
        self.light_btn.setEnabled(state)
        self.lmix_btn.setEnabled(state)

    def select_camera(self, camera_node):
        """Visually select the camera and update toolbar state."""
        self.active_camera_node = camera_node
        self.set_toolbar_enabled(True)
        
        for i in range(self.cam_list.count()):
            item = self.cam_list.item(i)
            card = self.cam_list.itemWidget(item)
            is_active = (card.camera_node == camera_node)
            card.set_active(is_active)
            
            if is_active:
                # Update toolbar values from this camera's CA
                
                # Presets
                self.light_btn.setChecked(light_utils.has_light_preset(camera_node))
                self.lmix_btn.setChecked(light_utils.has_lightmix_preset(camera_node))
                
                # Resolution
                w, h, has_res = camera_utils.load_resolution(camera_node)
                # Temporarily block signals to avoid triggering res_changed
                self.w_spin.blockSignals(True)
                self.h_spin.blockSignals(True)
                if has_res:
                    self.w_spin.setValue(w)
                    self.h_spin.setValue(h)
                    # Update aspect ratio if lock is active
                    if self.lock_btn.isChecked():
                        if h > 0:
                            self._locked_aspect_ratio = w / h
                        else:
                            self._locked_aspect_ratio = 1.0
                else:
                    self.w_spin.setValue(0)
                    self.h_spin.setValue(0)
                self.w_spin.blockSignals(False)
                self.h_spin.blockSignals(False)

    def update_camera_card(self, camera_node):
        """Update indicators for a specific camera."""
        for i in range(self.cam_list.count()):
            item = self.cam_list.item(i)
            card = self.cam_list.itemWidget(item)
            if card.camera_node == camera_node:
                card.update_indicators()
                break

    def get_card(self, camera_node):
        for i in range(self.cam_list.count()):
            item = self.cam_list.item(i)
            card = self.cam_list.itemWidget(item)
            if card.camera_node == camera_node:
                return card
        return None

    # -- Internal Handlers --
    
    def _on_card_clicked(self, camera_node):
        self.select_camera(camera_node)
        self.camera_selected.emit(camera_node)

    def _on_card_right_clicked(self, camera_node):
        # Context menu
        menu = QMenu(self)
        
        action_refresh = menu.addAction("Refresh Thumbnail")
        menu.addSeparator()
        
        has_l = light_utils.has_light_preset(camera_node)
        has_m = light_utils.has_lightmix_preset(camera_node)
        
        action_clear_l = menu.addAction("Clear Light Preset")
        action_clear_l.setEnabled(has_l)
        
        action_clear_m = menu.addAction("Clear LMix Preset")
        action_clear_m.setEnabled(has_m)
        
        res = menu.exec_(QCursor.pos())
        
        if res == action_refresh:
            self.refresh_thumbnail_req.emit(camera_node.name)
        elif res == action_clear_l:
            light_utils.clear_light_preset(camera_node)
            self.update_camera_card(camera_node)
            if self.active_camera_node == camera_node:
                self.light_btn.setChecked(False)
        elif res == action_clear_m:
            light_utils.clear_lightmix_preset(camera_node)
            self.update_camera_card(camera_node)
            if self.active_camera_node == camera_node:
                self.lmix_btn.setChecked(False)
                
    def _on_list_reordered(self):
        """Called when drag-drop finishes. Saves new order to CA."""
        for i in range(self.cam_list.count()):
            item = self.cam_list.item(i)
            cam = item.data(Qt.UserRole)
            if cam:
                # 1-based indexing for sortOrder
                camera_utils.save_sort_order(cam, i + 1)

    def _on_light_clicked(self):
        if not self.active_camera_node:
            return
        self.save_light_req.emit()
        self.light_btn.setChecked(True)
        self.update_camera_card(self.active_camera_node)

    def _on_lmix_clicked(self):
        if not self.active_camera_node:
            return
        self.save_lmix_req.emit()
        self.lmix_btn.setChecked(True)
        self.update_camera_card(self.active_camera_node)

    def _on_lock_toggled(self, checked):
        if checked:
            self.lock_btn.setText("🔒")
            w = self.w_spin.value()
            h = self.h_spin.value()
            if h > 0:
                self._locked_aspect_ratio = w / h
            else:
                self._locked_aspect_ratio = 1.0
        else:
            self.lock_btn.setText("🔓")
            self._locked_aspect_ratio = None

    def _on_w_value_changed(self, val):
        if self._is_syncing_res:
            return
        if self.lock_btn.isChecked() and self._locked_aspect_ratio:
            self._is_syncing_res = True
            new_h = int(round(val / self._locked_aspect_ratio))
            self.h_spin.blockSignals(True)
            self.h_spin.setValue(max(1, new_h))
            self.h_spin.blockSignals(False)
            self._is_syncing_res = False
        self._on_res_edited()

    def _on_h_value_changed(self, val):
        if self._is_syncing_res:
            return
        if self.lock_btn.isChecked() and self._locked_aspect_ratio:
            self._is_syncing_res = True
            new_w = int(round(val * self._locked_aspect_ratio))
            self.w_spin.blockSignals(True)
            self.w_spin.setValue(max(1, new_w))
            self.w_spin.blockSignals(False)
            self._is_syncing_res = False
        self._on_res_edited()

    def _on_res_edited(self, *args):
        if not self.active_camera_node:
            return
        w = self.w_spin.value()
        h = self.h_spin.value()
        if w > 0 and h > 0:
            self.res_changed.emit(w, h)

    def _on_swap_clicked(self, *args):
        if not self.active_camera_node:
            return
        w = self.w_spin.value()
        h = self.h_spin.value()
        if w > 0 and h > 0:
            self.w_spin.blockSignals(True)
            self.h_spin.blockSignals(True)
            self.w_spin.setValue(h)
            self.h_spin.setValue(w)
            self.w_spin.blockSignals(False)
            self.h_spin.blockSignals(False)
            
            # Recalculate aspect ratio if locked
            if self.lock_btn.isChecked():
                if w > 0:
                    self._locked_aspect_ratio = h / w
                else:
                    self._locked_aspect_ratio = 1.0
                    
            self.res_swapped.emit()

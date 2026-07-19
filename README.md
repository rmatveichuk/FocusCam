# FocusCam

**RM Focus** is a modern, dockable camera management and composition tool for Autodesk 3ds Max, built with Python and PySide6. It streamlines the workflow for 3D artists by providing a visual, card-based interface for managing multiple cameras, individual render resolutions, and composition guides.

## ✨ Key Features

* **Visual Camera List**  
  Displays all scene cameras as interactive cards with clean, auto-updating viewport thumbnails. Thumbnails perfectly maintain the camera's aspect ratio (with cinematic letterboxing) without any distortion.
  
* **Instant Camera Switching**  
  Click on any camera card to instantly switch the active viewport to that camera.

* **Per-Camera Render Resolution**  
  Set and save specific render resolutions (Width x Height) for individual cameras. The global render resolution automatically updates when you switch between cameras.

* **Composition Overlays**  
  Enhance your framing with built-in composition guides that overlay directly onto the active viewport:
  * Rule of Thirds
  * Golden Ratio
  * Diagonals
  * Fibonacci Spiral

* **Resolution Swapping**  
  Quickly toggle between landscape and portrait orientations with a single click (e.g., `1920x1080` ↔ `1080x1920`).

* **Persistent Settings (Custom Attributes)**  
  All camera-specific data (resolutions, list sorting order, light presets) are saved directly into the 3ds Max camera nodes using Custom Attributes. Your settings remain intact even if you restart 3ds Max or move the `.max` file to another computer.

* **Drag-and-Drop Sorting**  
  Easily organize your camera list by dragging and dropping the camera cards into your preferred order.

* **Light & LightMix Indicators**  
  Keep track of which cameras have specific lighting setups with visual `L` (Physical Light) and `M` (LightMix) preset indicators.

## 🛠️ Tech Stack
* **Autodesk 3ds Max** (pymxs, MAXScript)
* **Python 3**
* **PySide6** (Qt for Python)

## 👤 Author & Contacts
* **Developer / Channel**: [@refer_manage](https://t.me/refer_manage)
* **GitHub Repository**: [FocusCam](https://github.com/rmatveichuk/FocusCam)

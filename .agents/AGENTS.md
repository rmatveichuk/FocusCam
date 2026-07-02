# 3ds Max Script Installation and Updating Rules

When creating, updating, or packaging scripts for 3ds Max (e.g., as `.mzp` archives), strictly follow these rules to avoid repeating past mistakes seen in `GSplat` and `RM Mat Tools`:

## 1. File Encoding (CRITICAL)
- **MaxScript Files (`.ms`, `.mcr`)**: Must **always** be saved in **UTF-8 with BOM** (Byte Order Mark) or **UTF-16LE**. Standard UTF-8 without BOM will corrupt non-ASCII characters (e.g., Cyrillic text in UI or comments) in older and some newer 3ds Max versions.
- **Python Files (`.py`)**: Save as standard **UTF-8**.

## 2. Architecture & Separation of Concerns
- Separate the interface (MacroScript) from the core logic. 
- Example: `GSplat_UI.mcr` contains only the button definition and UI launch, while `GSplat_Logic.py` contains the actual code.
- This prevents memory clutter and allows logic to be updated without breaking the UI registration.

## 3. Installation Paths (Avoid Admin Rights Issues)
Never use system directories like `$scripts` or `$macroscripts` for installation. Always use user-specific directories:
- `.mcr` files -> copy to `$userMacros\`
- `.ms` and `.py` files -> copy to `$userScripts\`
- Icons (`.svg`, `.png`) -> copy to `$userIcons\Dark\` and `$userIcons\Light\`

## 4. Packaging (`mzp.run`)
Always include an `mzp.run` file that:
1. Copies files to the correct user directories.
2. Drops and runs the installer script (`drop "Install.ms"` and `run "Install.ms"`).
3. Cleans up temporary files with `clear temp on MAX exit`.

## 5. Installer Script (`Install.ms`) Best Practices
The installer script must handle clean updates and user onboarding:
- **Clean Old UI**: Before doing anything, try to close any existing open UI of the tool to prevent file locks or duplicate windows.
  ```maxscript
  try(destroyDialog ::YourToolRollout) catch()
  ```
- **Auto-Register**: Automatically evaluate the `.mcr` and logic files so the user doesn't have to restart 3ds Max.
  ```maxscript
  try (
      filein (getdir #userMacros + "\\YourTool.mcr")
      filein (getdir #userScripts + "\\YourTool_Logic.ms")
  ) catch ()
  ```
- **Success Notification**: Show a clear `rollout` or `messageBox` informing the user that installation succeeded and providing instructions on how to add the button to their UI (e.g., "Go to Customize -> Toolbars -> Category: 'RM scripts'").

## 6. Update and Re-installation Workflow
When a user updates a script by dragging a new `.mzp` package into 3ds Max, the following lifecycle must happen to ensure a clean update without restarting the program:
1. **Extraction**: 3ds Max extracts the `.mzp` to a temporary directory.
2. **Pre-Install Cleanup** (`PreInstall.ms`, runs BEFORE file copy): For Python plugins, the pre-install script MUST:
   - Close any open plugin UI windows (find by class name or objectName and call `.close()` / `.deleteLater()`).
   - Unregister any active callbacks (e.g., `unregisterRedrawViewsCallback`).
   - Unload all Python modules from `sys.modules` (remove entries matching the package name) and call `gc.collect()`.
   - Delete old `.py` files in `$userScripts\<PackageName>\` to prevent stale code.
   - **Delete `__pycache__\`** inside `$userScripts\<PackageName>\` — Python bytecode cache can override new `.py` files with old compiled `.pyc`.
3. **File Replacement**: The `mzp.run` file executes `copy` commands, which physically overwrite the old files stored in `$userMacros`, `$userScripts`, and `$userIcons` with the new versions.
4. **Post-Install Registration** (`Install.ms`): The installer calls `filein` on the `.mcr` file to re-register the macroscript in memory. Shows a success notification to the user.
5. **Cleanup**: Finally, `clear temp on MAX exit` in `mzp.run` ensures no junk is left behind.

## 7. Python Module Deployment (CRITICAL)

3ds Max loads Python packages from `$userScripts` (`C:\Users\<user>\AppData\Local\Autodesk\3dsMax\<version>\ENU\scripts\`), **NOT** from the developer's working directory. When editing `.py` files during development:

1. **Always copy changed `.py` files** from the dev directory to the `$userScripts\<PackageName>\` folder after editing. Without this step, 3ds Max will continue loading the old versions.
2. **Delete `__pycache__`** inside the `$userScripts\<PackageName>\` folder after copying. Python bytecode cache (`.pyc` files) can prevent 3ds Max from picking up the new source code even after the `.py` files are replaced.
3. **Close and reopen the plugin window** (or restart 3ds Max) to trigger `importlib.reload()` on all modules.

### Automated Deployment During Development

When making changes to any `.py` file in a project, **always** perform these steps in order:
```
1. Save the edited .py files in the dev directory
2. Copy the changed files to $userScripts\<PackageName>\
3. Delete $userScripts\<PackageName>\__pycache__\ (if it exists)
4. In 3ds Max: close the plugin window, then relaunch the macro
```

### Example (PowerShell):
```powershell
$src = "c:\Users\RMatv\OneDrive\Рабочий стол\Dev\MaxScripts\Focus"
$dst = "C:\Users\RMatv\AppData\Local\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\Focus"
Copy-Item "$src\*.py" "$dst\" -Force
Remove-Item "$dst\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
```

## 8. Agent Workflow Rule

When the agent edits any `.py` file in a 3ds Max plugin project, it **MUST** immediately after editing:
1. Copy ALL changed `.py` files to the corresponding `$userScripts\<PackageName>\` directory.
2. Delete the `__pycache__` folder in the target directory.
3. Inform the user to close and reopen the plugin in 3ds Max to apply changes.

Failure to do this will result in 3ds Max running stale code, and the user will see no effect from the edits.


## 9. Python Memory Purge & Macro Conflicts (CRITICAL)

### 9a. Complete Python Module Purging
Standard `importlib.reload()` is **unreliable** for nested imports in 3ds Max. If a module isn't cleanly removed from `sys.modules`, Python will keep using the old version cached in memory, even if the `.py` file on disk has changed.
To guarantee that 3ds Max compiles the new code, the MacroScript (`.mcr` file) and install scripts must completely purge all package-related modules from `sys.modules` before importing.
**Purge Snippet:**
```python
my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus'}
to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]
[sys.modules.pop(m, None) for m in to_delete]
import gc; gc.collect()
```

### 9b. Conflicting MacroScripts
3ds Max caches MacroScript code in memory. If duplicate `.mcr` files exist in `$userMacros\` (e.g., `Focus_UI.mcr` and `RM_Focus.mcr` both defining buttons for the same category), 3ds Max can execute the cached old code containing old Python import commands.
- **Rule**: Ensure the `.mzp` installer cleans up old `.mcr` files.
- **Rule**: If multiple macro definitions exist, update **all** of them to run the exact same `sys.modules` purge logic.
- **Rule**: Run `filein` on the updated `.mcr` file during installation to force 3ds Max to recompile it in memory.


## 10. Safe Property Access & Third-Party Renderers

In 3ds Max, calling `rt.getProperty(node, "propertyName")` on a node that doesn't have that property (e.g., calling `"enabled"` on a Corona Light which uses `"on"`) does **not** raise an exception in Python. Instead, it returns `rt.undefined`.
- In Python, `rt.undefined` is evaluated as `False` in boolean operations (`bool(rt.undefined) == False`).
- This causes silent bugs (e.g., the script thinks the light is turned off, when in fact it just has a different property name).

**Rules for Property Access:**
1. **Check Existence First**: Always check if a property exists using `rt.hasProperty(node, "propertyName")` before reading or writing to it.
2. **Implementation Example:**
   ```python
   def _get_light_enabled(light_node):
       if rt.hasProperty(light_node, "enabled"):
           return bool(rt.getProperty(light_node, "enabled"))
       if rt.hasProperty(light_node, "on"):
           return bool(rt.getProperty(light_node, "on"))
       return True
   ```

## 11. Language for Implementation Plans
- Always write implementation plans (`implementation_plan.md`) and walkthroughs (`walkthrough.md`) in Russian (or translate them to Russian if generated in English).


## 12. MCP Server Connection (CRITICAL)
- **MCP Server Path**: `C:\Users\RMatv\OneDrive\Рабочий стол\Dev\MaxScripts\3ds Max MCP`.
- **Instruction**: At the very beginning of the conversation, the agent **MUST** check if the 3ds Max MCP server is active or needs to be connected to. The MCP server provides essential tools like `execute_maxscript` and `capture_screen` which are critical for auto-deploying files, re-running macroscripts, visual validation, and testing. Connect to this MCP server immediately at the start of any task.

macroScript FocusCam
category:"RM scripts"
buttonText:"FocusCam"
tooltip:"FocusCam"
iconName:"Icon"
(
    on execute do (
        python.Execute "
import sys
usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts'))
if usr_scr not in sys.path:
    sys.path.append(usr_scr)
my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus', 'focuscam'}
to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]
for m in to_delete:
    sys.modules.pop(m, None)
import gc
gc.collect()
import FocusCam.focus_manager
FocusCam.focus_manager.show_focus_window()
"
    )
)

macroScript RM_Focus
category:"RM scripts"
buttonText:"RM Focus"
tooltip:"RM Focus Camera & Light Manager"
iconName:"Icon"
(
    on execute do (
        python.Execute "import sys; my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus'}; to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]; [sys.modules.pop(m, None) for m in to_delete]; import gc; gc.collect(); usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts')); sys.path.append(usr_scr) if usr_scr not in sys.path else None; import Focus.focus_manager; Focus.focus_manager.show_focus_window()"
    )
)

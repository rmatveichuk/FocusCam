macroScript FocusCam
category:"RM scripts"
buttonText:"FocusCam"
tooltip:"FocusCam"
iconName:"Icon"
(
    on execute do (
        python.Execute "import sys, gc; usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts')); sys.path.append(usr_scr) if usr_scr not in sys.path else None; to_del = [m for m in list(sys.modules.keys()) if 'focus' in m.lower() or 'batch' in m.lower()]; [sys.modules.pop(m, None) for m in to_del]; gc.collect(); import FocusCam.focus_manager; FocusCam.focus_manager.show_focus_window()"
    )
)

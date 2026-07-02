macroScript FocusCam
category:"RM scripts"
buttonText:"FocusCam"
tooltip:"FocusCam Camera & Light Manager"
iconName:"Icon"
(
    on execute do (
        python.Execute "import sys; usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts')); sys.path.append(usr_scr) if usr_scr not in sys.path else None; import FocusCam.focus_manager; FocusCam.focus_manager.show_focus_window()"
    )
)

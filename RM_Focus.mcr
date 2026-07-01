macroScript RM_Focus
category:"RM scripts"
buttonText:"RM Focus"
tooltip:"RM Focus Camera & Light Manager"
iconName:"Icon"
(
    on execute do (
        python.Execute "import sys; usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts')); sys.path.append(usr_scr) if usr_scr not in sys.path else None; import Focus.focus_manager; Focus.focus_manager.show_focus_window()"
    )
)

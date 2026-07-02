# -*- coding: utf-8 -*-
"""
Helper script to package the Focus plugin into a single .mzp installer file.
It generates necessary installer files (mzp.run, Install.ms, Focus_UI.mcr, __init__.py)
with proper encodings and packages them together.
"""

import os
import zipfile

def build_mzp():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Create empty __init__.py if it doesn't exist
    init_path = os.path.join(current_dir, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w", encoding="utf-8") as f:
            f.write("# Focus package\n")
        print("Created __init__.py")

    # 2. Create RM_Focus.mcr (UTF-8 with BOM / utf-8-sig)
    mcr_content = """macroScript RM_Focus
category:"RM scripts"
buttonText:"RM Focus"
tooltip:"RM Focus Camera & Light Manager"
iconName:"Icon"
(
    on execute do (
        python.Execute "import sys; usr_scr = __import__('pymxs').runtime.getDir(__import__('pymxs').runtime.Name('userScripts')); sys.path.append(usr_scr) if usr_scr not in sys.path else None; import Focus.focus_manager; Focus.focus_manager.show_focus_window()"
    )
)
"""
    mcr_path = os.path.join(current_dir, "RM_Focus.mcr")
    with open(mcr_path, "w", encoding="utf-8-sig") as f:
        f.write(mcr_content)
    print("Created RM_Focus.mcr (UTF-8 with BOM)")


    # 3. Create PreInstall.ms (UTF-8 with BOM / utf-8-sig)
    pre_install_content = """(
    -- Закрываем старое Python-окно и очищаем старый callback, если они активны
    try (
        python.execute "from PySide6.QtWidgets import QApplication; [w.close() or w.deleteLater() for w in QApplication.allWidgets() if w.__class__.__name__ == 'FocusManagerWindow' or w.objectName() == 'FocusDockWidget']; QApplication.processEvents()"
    ) catch ()
    try ( unregisterRedrawViewsCallback focusOverlayRedrawCB ) catch ()
    
    -- Очищаем кэш Python-модулей, чтобы высвободить блокировки файлов
    try (
        python.execute "import sys; import gc; my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus'}; to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]; [sys.modules.pop(m, None) for m in to_delete]; gc.collect()"
    ) catch ()
    
    -- Принудительно удаляем старые файлы, чтобы mzp.run гарантированно скопировал новые
    local destDir = (getdir #userScripts) + "\\\\Focus\\\\"
    local filesToDelete = #("focus_manager.py", "ui_components.py", "camera_utils.py", "light_utils.py", "overlay_utils.py", "__init__.py")
    for f in filesToDelete do (
        try ( deleteFile (destDir + f) ) catch ()
    )
    
    -- Удаляем __pycache__ для гарантии загрузки нового кода Python
    local cacheDir = destDir + "__pycache__\\\\"
    try (
        local cacheFiles = getFiles (cacheDir + "*.*")
        for f in cacheFiles do (
            try ( deleteFile f ) catch ()
        )
        try ( DOSCommand ("rmdir \\"" + cacheDir + "\\" /s /q") ) catch ()
    ) catch ()
)
"""
    pre_install_path = os.path.join(current_dir, "PreInstall.ms")
    with open(pre_install_path, "w", encoding="utf-8-sig") as f:
        f.write(pre_install_content)
    print("Created PreInstall.ms (UTF-8 with BOM)")

    # 4. Create Install.ms (UTF-8 with BOM / utf-8-sig) - Post Install
    install_ms_content = """(
    local mcrName = "RM_Focus.mcr"
    local mcrPath = (getdir #userMacros) + "\\\\" + mcrName
    
    -- Регистрируем макроскрипт в текущей сессии 3ds Max
    if doesFileExist mcrPath then (
        try (
            filein mcrPath
        ) catch ()
    )
    
    -- Создаем простое и понятное окно об успешной установке
    try(destroyDialog ::RMFocus_InstallMsg) catch()
    rollout RMFocus_InstallMsg "Установка завершена" width:350 height:170
    (
        label lbl_title "Скрипт RM Focus успешно установлен!" pos:[15,15]
        
        label lbl_info1 "Как добавить кнопку на панель:" pos:[15,45]
        label lbl_info2 "1. Customize -> Customize User Interface" pos:[15,65]
        label lbl_info3 "2. Вкладка Toolbars" pos:[15,80]
        label lbl_info4 "3. В списке Category выберите: RM scripts" pos:[15,95]
        label lbl_info5 "4. Перетащите RM Focus на любую панель" pos:[15,110]
        
        button btn_close "Закрыть" width:80 height:24 pos:[135,135]
        
        on btn_close pressed do destroyDialog ::RMFocus_InstallMsg
    )
    
    createDialog ::RMFocus_InstallMsg modal:false
    ok
)
"""
    install_ms_path = os.path.join(current_dir, "Install.ms")
    with open(install_ms_path, "w", encoding="utf-8-sig") as f:
        f.write(install_ms_content)
    print("Created Install.ms (UTF-8 with BOM)")

    # 5. Create mzp.run (UTF-8 without BOM)
    mzp_run_content = """name "RM Focus"
version 1.0

run "PreInstall.ms"

copy "RM_Focus.mcr" to "$userMacros\\"
copy "focus_manager.py" to "$userScripts\\Focus\\"
copy "camera_utils.py" to "$userScripts\\Focus\\"
copy "light_utils.py" to "$userScripts\\Focus\\"
copy "overlay_utils.py" to "$userScripts\\Focus\\"
copy "ui_components.py" to "$userScripts\\Focus\\"
copy "__init__.py" to "$userScripts\\Focus\\"
copy "style.qss" to "$userScripts\\Focus\\"
copy "Icon.svg" to "$userScripts\\Focus\\"

copy "Icon.svg" to "$userIcons\\Dark\\"
copy "Icon.svg" to "$userIcons\\Light\\"

run "Install.ms"
drop "Install.ms"

clear temp on MAX exit
"""
    mzp_run_path = os.path.join(current_dir, "mzp.run")
    with open(mzp_run_path, "w", encoding="utf-8") as f:
        f.write(mzp_run_content)
    print("Created mzp.run")

    # 6. Pack everything into RM_Focus_Beta.mzp
    files_to_pack = [
        "mzp.run",
        "PreInstall.ms",
        "Install.ms",
        "RM_Focus.mcr",
        "focus_manager.py",
        "camera_utils.py",
        "light_utils.py",
        "overlay_utils.py",
        "ui_components.py",
        "__init__.py",
        "style.qss",
        "Icon.svg"
    ]
    
    output_filename = "RM_Focus_Beta.mzp"
    output_path = os.path.join(current_dir, output_filename)
    
    print("\nНачало сборки установщика...")
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_name in files_to_pack:
                file_path = os.path.join(current_dir, file_name)
                if os.path.exists(file_path):
                    zip_file.write(file_path, file_name)
                    print(f" -> Добавлен: {file_name}")
                else:
                    print(f" -> Ошибка: Файл {file_name} не найден!")
                    return
        print(f"\nСборка успешно завершена!\nСоздан файл установщика: {output_path}")
    except Exception as e:
        print(f"Ошибка при сборке архива: {e}")

if __name__ == "__main__":
    build_mzp()

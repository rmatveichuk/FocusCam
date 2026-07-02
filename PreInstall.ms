(
    -- Закрываем старое Python-окно и очищаем старый callback, если они активны
    try (
        python.execute "from PySide6.QtWidgets import QApplication; [w.close() or w.deleteLater() for w in QApplication.allWidgets() if w.__class__.__name__ in ['FocusManagerWindow', 'FocusCamWindow'] or w.objectName() in ['FocusDockWidget', 'FocusCamDockWidget']]; QApplication.processEvents()"
    ) catch ()
    try ( unregisterRedrawViewsCallback focusOverlayRedrawCB ) catch ()
    
    -- Очищаем кэш Python-модулей, чтобы высвободить блокировки файлов
    try (
        python.execute "import sys; import gc; my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus', 'focuscam'}; to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]; [sys.modules.pop(m, None) for m in to_delete]; gc.collect()"
    ) catch ()
    
    -- Принудительно удаляем старые файлы, чтобы mzp.run гарантированно скопировал новые
    local destDir = (getdir #userScripts) + "\\FocusCam\\"
    local filesToDelete = #("focus_manager.py", "ui_components.py", "camera_utils.py", "light_utils.py", "overlay_utils.py", "__init__.py")
    for f in filesToDelete do (
        try ( deleteFile (destDir + f) ) catch ()
    )
    
    -- Удаляем __pycache__ для гарантии загрузки нового кода Python
    local cacheDir = destDir + "__pycache__\\"
    try (
        local cacheFiles = getFiles (cacheDir + "*.*")
        for f in cacheFiles do (
            try ( deleteFile f ) catch ()
        )
        try ( DOSCommand ("rmdir \"" + cacheDir + "\" /s /q") ) catch ()
    ) catch ()

    -- Чистим старую папку Focus, если она осталась от предыдущих версий
    local oldDestDir = (getdir #userScripts) + "\\Focus\\"
    try ( DOSCommand ("rmdir \"" + oldDestDir + "\" /s /q") ) catch ()
)

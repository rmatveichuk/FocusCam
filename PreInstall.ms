(
    -- Закрываем старое Python-окно и очищаем старый callback, если они активны
    try (
        python.execute "from PySide6.QtWidgets import QApplication
widgets = QApplication.allWidgets()
for w in widgets:
    try:
        if w.__class__.__name__ == 'FocusManagerWindow' or w.objectName() == 'FocusDockWidget':
            w.close()
            w.deleteLater()
    except:
        pass
QApplication.processEvents()"
    ) catch ()
    try ( unregisterRedrawViewsCallback focusOverlayRedrawCB ) catch ()
    
    -- Очищаем кэш Python-модулей, чтобы высвободить блокировки файлов
    try (
        python.execute "import sys; import gc; my_mods = {'focus_manager', 'ui_components', 'camera_utils', 'light_utils', 'overlay_utils', 'focus'}; to_delete = [m for m in sys.modules if m.split('.')[0].lower() in my_mods or 'focus' in m.lower()]; [sys.modules.pop(m, None) for m in to_delete]; gc.collect()"
    ) catch ()
    
    -- Принудительно удаляем старые файлы, чтобы mzp.run гарантированно скопировал новые
    local destDir = (getdir #userScripts) + "\\Focus\\"
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
)

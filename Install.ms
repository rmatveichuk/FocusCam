(
    local mcrName = "RM_Focus.mcr"
    local mcrPath = (getdir #userMacros) + "\\" + mcrName
    
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

@echo off
setlocal

set "SOURCE=%~dp0"
set "TARGET=C:\Charfinder"

if not exist "%SOURCE%CharFinder.exe" (
    echo ERRO: CharFinder.exe nao foi encontrado na pasta do script:
    echo %SOURCE%
    goto :fail
)

if not exist "%TARGET%\" (
    mkdir "%TARGET%"
    if errorlevel 1 (
        echo ERRO: nao foi possivel criar %TARGET%.
        echo Verifique se voce tem permissao para gravar na raiz do disco C:.
        goto :fail
    )
)

set "INITIAL_SETUP=0"
if not exist "%TARGET%\CharFinder.exe" set "INITIAL_SETUP=1"

if "%INITIAL_SETUP%"=="1" if not exist "%TARGET%\character-exceptions.json" if exist "%SOURCE%character-exceptions.json" (
    copy /Y "%SOURCE%character-exceptions.json" "%TARGET%\character-exceptions.json" >nul
    if errorlevel 1 (
        echo ERRO: nao foi possivel copiar character-exceptions.json.
        goto :fail
    )
)

if "%INITIAL_SETUP%"=="1" if not exist "%TARGET%\LEIAME.html" if exist "%SOURCE%LEIAME.html" (
    copy /Y "%SOURCE%LEIAME.html" "%TARGET%\LEIAME.html" >nul
    if errorlevel 1 (
        echo ERRO: nao foi possivel copiar o manual para LEIAME.html.
        goto :fail
    )
)

copy /Y "%SOURCE%CharFinder.exe" "%TARGET%\CharFinder.exe.update" >nul
if errorlevel 1 (
    del /Q "%TARGET%\CharFinder.exe.update" >nul 2>&1
    echo ERRO: nao foi possivel preparar a nova versao de CharFinder.exe.
    goto :fail
)
move /Y "%TARGET%\CharFinder.exe.update" "%TARGET%\CharFinder.exe" >nul
if errorlevel 1 (
    del /Q "%TARGET%\CharFinder.exe.update" >nul 2>&1
    echo ERRO: nao foi possivel substituir CharFinder.exe.
    echo Feche o CharFinder e tente novamente; o executavel atual foi mantido.
    goto :fail
)

powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; $shell = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $shortcut = $shell.CreateShortcut((Join-Path $desktop 'CharFinder.lnk')); $shortcut.TargetPath = 'C:\Charfinder\CharFinder.exe'; $shortcut.WorkingDirectory = 'C:\Charfinder'; $shortcut.IconLocation = 'C:\Charfinder\CharFinder.exe,0'; $shortcut.Save()"
if errorlevel 1 (
    echo ERRO: nao foi possivel criar o atalho na area de trabalho.
    goto :fail
)

echo.
echo CharFinder atualizado em %TARGET%.
echo Use o atalho CharFinder na area de trabalho.
if exist "%TARGET%\LEIAME.html" echo O manual esta em %TARGET%\LEIAME.html.
echo O executavel foi atualizado; catalogo e manual locais foram preservados.
pause
exit /b 0

:fail
echo.
pause
exit /b 1

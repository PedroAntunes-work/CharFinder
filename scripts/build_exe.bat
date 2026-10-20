@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo Nao foi possivel acessar a pasta do projeto.
    exit /b 1
)

python -m pip install -e ".[build]"
if errorlevel 1 (
    echo Falha ao instalar as dependencias de empacotamento.
    exit /b 1
)

python scripts\prepare_tcl_data.py "build\CharFinder-tcl-data"
if errorlevel 1 (
    echo Falha ao localizar ou preparar os arquivos Tcl/Tk.
    exit /b 1
)

set "TCL_DATA_ARGS="
if exist "build\CharFinder-tcl-data\_tcl_data" (
    set "TCL_DATA_ARGS=--add-data ""build\CharFinder-tcl-data\_tcl_data;_tcl_data"" --add-data ""build\CharFinder-tcl-data\_tk_data;_tk_data"""
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --name CharFinder --distpath "dist" --icon "assets\CharFinder.ico" --version-file "assets\version_info.txt" --add-data "assets\CharFinder.ico;assets" --collect-all tkinterdnd2 %TCL_DATA_ARGS% charfinder.py
if errorlevel 1 (
    echo Falha ao gerar o executavel.
    exit /b 1
)

copy /Y "docs\LEIAME.html" "dist\LEIAME.html" >nul
if errorlevel 1 (
    echo Falha ao copiar o manual para a pasta do executavel.
    exit /b 1
)

copy /Y "character-exceptions.json" "dist\character-exceptions.json" >nul
if errorlevel 1 (
    echo Falha ao copiar o catalogo de caracteres para a pasta do executavel.
    exit /b 1
)

copy /Y "scripts\configurar_charfinder.bat" "dist\configurar_charfinder.bat" >nul
if errorlevel 1 (
    echo Falha ao copiar o script de configuracao para a pasta do executavel.
    exit /b 1
)

copy /Y "scripts\configurar_charfinder_homologa.bat" "dist\configurar_charfinder_homologa.bat" >nul
if errorlevel 1 (
    echo Falha ao copiar o script de homologacao para a pasta do executavel.
    exit /b 1
)

if exist "build\CharFinder-tcl-data" rmdir /s /q "build\CharFinder-tcl-data"

echo.
echo Executavel autonomo gerado em: dist\CharFinder.exe
echo Manual do usuario (opcional): dist\LEIAME.html
echo Catalogo de caracteres: dist\character-exceptions.json
echo Script de configuracao inicial: dist\configurar_charfinder.bat
echo Script de homologacao: dist\configurar_charfinder_homologa.bat
endlocal

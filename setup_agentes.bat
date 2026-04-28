@echo off
REM ============================================================================
REM  setup_agentes.bat
REM  ----------------------------------------------------------------------------
REM  Setup de todos los agentes Python en una sola corrida.
REM  Crea un venv (.venv) en cada carpeta de agente e instala sus dependencias.
REM
REM  Uso (desde cmd):
REM      cd c:\a2a
REM      setup_agentes.bat
REM
REM  Requiere: Python 3.11 o 3.12 instalado y accesible vía 'py'.
REM ============================================================================

setlocal enabledelayedexpansion

REM Verificar que 'py' esté disponible
where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro el lanzador 'py' de Python. Instala Python desde python.org.
    exit /b 1
)

set ROOT=%~dp0

echo.
echo ============================================================
echo  Setup de agentes en: %ROOT%
echo ============================================================
echo.

call :setup_agente "agente_orchestrator"        requirements
if errorlevel 1 goto :error

call :setup_agente "agente_busquedas_internas"  pyproject
if errorlevel 1 goto :error

call :setup_agente "agente_job_description"     pyproject
if errorlevel 1 goto :error

call :setup_agente "agente_entrevistas"         requirements
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  OK - Todos los agentes quedaron listos.
echo ============================================================
echo.
echo Para levantar cada agente, abri una ventana cmd nueva y haceA:
echo   cd %ROOT%agente_orchestrator
echo   .venv\Scripts\activate
echo   python server.py
echo.
exit /b 0


REM ----------------------------------------------------------------------------
REM  :setup_agente <carpeta> <modo>
REM     modo = "requirements" -> usa requirements.txt
REM     modo = "pyproject"    -> usa pip install -e .
REM ----------------------------------------------------------------------------
:setup_agente
set CARPETA=%~1
set MODO=%~2

echo ----------------------------------------------------------
echo  [%CARPETA%]
echo ----------------------------------------------------------

if not exist "%ROOT%%CARPETA%" (
    echo [SKIP] No existe la carpeta %CARPETA%.
    exit /b 0
)

cd /d "%ROOT%%CARPETA%"

REM 1) Crear venv si no existe
if not exist ".venv\Scripts\python.exe" (
    echo Creando venv...
    py -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No pude crear el venv en %CARPETA%.
        exit /b 1
    )
) else (
    echo Venv ya existe, salteando creacion.
)

REM 2) Actualizar pip dentro del venv
echo Actualizando pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet

REM 3) Instalar deps segun el modo
if "%MODO%"=="requirements" (
    if exist "requirements.txt" (
        echo Instalando requirements.txt...
        .venv\Scripts\python.exe -m pip install -r requirements.txt
    ) else (
        echo [WARN] No hay requirements.txt en %CARPETA%.
    )
) else (
    if exist "pyproject.toml" (
        echo Instalando pyproject.toml ^(pip install -e .^)...
        .venv\Scripts\python.exe -m pip install -e .
    ) else (
        echo [WARN] No hay pyproject.toml en %CARPETA%.
    )
)

if errorlevel 1 (
    echo [ERROR] Fallo la instalacion en %CARPETA%.
    exit /b 1
)

REM 4) Instalar dependencias del server HTTP que faltan en los requirements
REM    (los server.py importan fastapi y uvicorn pero los archivos de deps no los listan)
if exist "server.py" (
    echo Instalando fastapi/uvicorn para server.py...
    .venv\Scripts\python.exe -m pip install fastapi uvicorn[standard]
)

cd /d "%ROOT%"
echo OK - %CARPETA% listo.
echo.
exit /b 0


:error
echo.
echo ============================================================
echo  ERROR - El setup fallo. Revisa los mensajes de arriba.
echo ============================================================
exit /b 1

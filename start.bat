@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================================
echo   OpenWuKong — 通用 IDE Agent 督导系统
echo ============================================================
echo.

set VENV_DIR=%~dp0.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    echo [SETUP] Installing dependencies...
    "%VENV_DIR%\Scripts\pip.exe" install -e "%~dp0." -q
    echo [SETUP] Done.
    echo.
)

set PYTHON=%VENV_DIR%\Scripts\python.exe

if "%~1"=="monitor" goto MODE_MONITOR
if "%~1"=="test" goto MODE_TEST
if "%~1"=="agent" goto MODE_AGENT
if "%~1"=="ai" goto MODE_AI
if "%~1"=="supervisor" goto MODE_SUPERVISOR
if "%~1"=="service" goto MODE_SERVICE
if "%~1"=="ui" goto MODE_UI
if "%~1"=="" goto MODE_UI

echo [ERROR] Unknown command: %1
echo Use: start.bat [ui^|test^|monitor^|agent^|ai^|supervisor^|service]
goto :end


:MODE_MONITOR
echo [MODE] IDEMonitor Daemon
echo [TARGET] %2
echo.
if "%~2"=="" (
    "%PYTHON%" -m openwukong.daemon.daemon
) else (
    "%PYTHON%" -m openwukong.daemon.daemon --target %2 %3 %4 %5 %6
)
goto :end


:MODE_TEST
echo [MODE] Integration Test
echo.
"%PYTHON%" "%~dp0tests\test_feasibility.py"
goto :end


:MODE_AGENT
echo [MODE] Ollama Agent [ReAct Planner]
echo.
if "%~2"=="" (
    echo Starting interactive mode...
    "%PYTHON%" -m openwukong.planner.ollama_planner --interactive
) else (
    "%PYTHON%" -m openwukong.planner.ollama_planner %2 %3 %4 %5 %6
)
goto :end


:MODE_AI
echo [MODE] AI Monitor - Multi-Project AI Dashboard
echo.
if "%~2"=="scan" (
    "%PYTHON%" -m openwukong.monitor.ai_monitor --mode scan %3 %4 %5
) else (
    if "%~2"=="json" (
        "%PYTHON%" -m openwukong.monitor.ai_monitor --mode scan --json
    ) else (
        "%PYTHON%" -m openwukong.monitor.ai_monitor --mode watch %2 %3 %4 %5
    )
)
goto :end


:MODE_SUPERVISOR
echo [MODE] Agent Supervisor - IDE Agent 全时督导
echo.
if "%~2"=="--gen-config" (
    "%PYTHON%" -m openwukong.supervisor.agent_supervisor --gen-config %~3
    goto :end
)
if "%~2"=="--demo" (
    "%PYTHON%" -m openwukong.supervisor.agent_supervisor --demo %3 %4 %5 %6 %7 %8
    goto :end
)
if "%~2"=="" (
    "%PYTHON%" -m openwukong.supervisor.agent_supervisor
    goto :end
)
"%PYTHON%" -m openwukong.supervisor.agent_supervisor %2 %3 %4 %5 %6 %7 %8
goto :end


:MODE_SERVICE
echo [MODE] 24/7 Service Wrapper
echo.
if "%~2"=="install" (
    echo Installing auto-start...
    "%PYTHON%" -m openwukong.daemon.service_wrapper install
    goto :end
)
if "%~2"=="uninstall" (
    echo Removing auto-start...
    "%PYTHON%" -m openwukong.daemon.service_wrapper uninstall
    goto :end
)
if "%~2"=="status" (
    "%PYTHON%" -m openwukong.daemon.service_wrapper status
    goto :end
)

echo Starting 24/7 monitoring...
"%PYTHON%" -m openwukong.daemon.service_wrapper %2 %3 %4 %5 %6
goto :end


:MODE_UI
echo [MODE] Supervisior UI - 包工头可视化控制台
echo.
"%PYTHON%" -m openwukong.ui.supervisor_panel
goto :end


:MODE_DEFAULT
echo Usage:
echo   start.bat ui                                - Open GUI Dashboard [Foreman]
echo   start.bat test                              - Run integration tests
echo   start.bat monitor                           - Start IDE monitor [default config]
echo   start.bat monitor Antigravity.exe           - Monitor specific IDE
echo   start.bat monitor Code.exe --duration 120   - Monitor for 120 seconds
echo   start.bat agent                             - Interactive agent [Ollama LLM]
echo   start.bat agent "open terminal and type git status"
echo                                               - Execute a single task
echo   start.bat ai                                - Multi-project AI dashboard [live]
echo   start.bat ai scan                           - Single scan of all projects
echo   start.bat ai json                           - JSON output [for automation]
echo   start.bat supervisor --gen-config goals.json  - Generate example config
echo   start.bat supervisor --config goals.json      - Start auto-supervision
echo   start.bat supervisor --bionic --config goals.json - Bionic mode [neural 4-layer brain]
echo   start.bat supervisor --demo                   - Demo mode [read-only]
echo   start.bat service                           - 24/7 monitoring [auto-restart]
echo   start.bat service install                   - Register auto-start on login
echo   start.bat service uninstall                 - Remove auto-start
echo   start.bat service status                    - Show service status
echo.
echo Opening GUI by default...
echo.
"%PYTHON%" -m openwukong.ui.supervisor_panel
goto :end

:end
endlocal

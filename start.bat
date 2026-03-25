@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================================
echo   UIA Agent - Windows UI Automation Module
echo ============================================================
echo.

set VENV_DIR=%~dp0.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    echo [SETUP] Installing dependencies...
    "%VENV_DIR%\Scripts\pip.exe" install -r "%~dp0requirements.txt" -q
    echo [SETUP] Done.
    echo.
)

set PYTHON=%VENV_DIR%\Scripts\python.exe

if "%1"=="monitor" (
    echo [MODE] IDEMonitor Daemon
    echo [TARGET] %2
    echo.
    if "%2"=="" (
        "%PYTHON%" "%~dp0daemon.py"
    ) else (
        "%PYTHON%" "%~dp0daemon.py" --target %2 %3 %4 %5 %6
    )
    goto :end
)

if "%1"=="test" (
    echo [MODE] Integration Test
    echo.
    "%PYTHON%" "%~dp0test_feasibility.py"
    goto :end
)

if "%1"=="agent" (
    echo [MODE] Ollama Agent (ReAct Planner)
    echo.
    if "%2"=="" (
        echo Starting interactive mode...
        "%PYTHON%" "%~dp0ollama_planner.py" --interactive
    ) else (
        "%PYTHON%" "%~dp0ollama_planner.py" %2 %3 %4 %5 %6
    )
    goto :end
)

if "%1"=="ai" (
    echo [MODE] AI Monitor - Multi-Project AI Dashboard
    echo.
    if "%2"=="scan" (
        "%PYTHON%" "%~dp0ai_monitor.py" --mode scan %3 %4 %5
    ) else if "%2"=="json" (
        "%PYTHON%" "%~dp0ai_monitor.py" --mode scan --json
    ) else (
        "%PYTHON%" "%~dp0ai_monitor.py" --mode watch %2 %3 %4 %5
    )
    goto :end
)

if "%1"=="supervisor" (
    echo [MODE] Agent Supervisor - IDE Agent 全时督导
    echo.
    if "%2"=="--gen-config" (
        "%PYTHON%" "%~dp0agent_supervisor.py" --gen-config %3
    ) else if "%2"=="--demo" (
        "%PYTHON%" "%~dp0agent_supervisor.py" --demo %3 %4 %5 %6 %7 %8
    ) else if "%2"=="" (
        "%PYTHON%" "%~dp0agent_supervisor.py"
    ) else (
        "%PYTHON%" "%~dp0agent_supervisor.py" %2 %3 %4 %5 %6 %7 %8
    )
    goto :end
)

if "%1"=="service" (
    echo [MODE] 24/7 Service Wrapper
    echo.
    if "%2"=="install" (
        echo Installing auto-start...
        "%PYTHON%" "%~dp0service_wrapper.py" install
    ) else if "%2"=="uninstall" (
        echo Removing auto-start...
        "%PYTHON%" "%~dp0service_wrapper.py" uninstall
    ) else if "%2"=="status" (
        "%PYTHON%" "%~dp0service_wrapper.py" status
    ) else (
        echo Starting 24/7 monitoring...
        "%PYTHON%" "%~dp0service_wrapper.py" %2 %3 %4 %5 %6
    )
    goto :end
)

if "%1"=="" (
    echo Usage:
    echo   start.bat test                              - Run integration tests
    echo   start.bat monitor                           - Start IDE monitor (default config)
    echo   start.bat monitor Antigravity.exe           - Monitor specific IDE
    echo   start.bat monitor Code.exe --duration 120   - Monitor for 120 seconds
    echo   start.bat agent                             - Interactive agent (Ollama LLM)
    echo   start.bat agent "open terminal and type git status"
    echo                                               - Execute a single task
    echo   start.bat ai                                - Multi-project AI dashboard (live)
    echo   start.bat ai scan                           - Single scan of all projects
    echo   start.bat ai json                           - JSON output (for automation)
    echo   start.bat supervisor --gen-config goals.json  - Generate example config
    echo   start.bat supervisor --config goals.json      - Start auto-supervision
    echo   start.bat supervisor --demo                   - Demo mode (read-only)
    echo   start.bat service                           - 24/7 monitoring (auto-restart)
    echo   start.bat service install                   - Register auto-start on login
    echo   start.bat service uninstall                 - Remove auto-start
    echo   start.bat service status                    - Show service status
    echo.
    echo Running integration test by default...
    echo.
    "%PYTHON%" "%~dp0test_feasibility.py"
    goto :end
)

echo [ERROR] Unknown command: %1
echo Use: start.bat [test^|monitor^|agent^|ai^|supervisor^|service]

:end
endlocal

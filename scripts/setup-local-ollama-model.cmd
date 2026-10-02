@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-local-ollama-model.ps1" %*
exit /b %ERRORLEVEL%

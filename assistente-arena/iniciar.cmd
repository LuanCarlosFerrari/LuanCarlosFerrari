@echo off
title Assistente Arena
chcp 65001 >nul
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo O uv nao foi encontrado. Instale com: winget install --id=astral-sh.uv -e
  pause
  exit /b 1
)
uv run assistente-arena status
echo.
uv run assistente-arena observar --exportar
echo.
pause

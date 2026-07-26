@echo off
chcp 65001 > nul
REM ============================================
REM VaultAgent 前后端一键启动脚本 (Windows)
REM ============================================

set PYTHON=D:\Miniconda3\envs\myenv1\python.exe
set PROJECT=%~dp0

echo ============================================
echo VaultAgent Demo — 启动前端和后端
echo ============================================

REM 1. 启动 FastAPI 后端
echo [1/2] 启动 FastAPI 后端 (http://localhost:8080)...
start "VaultAgent-API" cmd /c "cd /d %PROJECT% && %PYTHON% -m uvicorn src.api.main:app --host 0.0.0.0 --port 8080"

echo 等待后端启动...
timeout /t 4 /nobreak > nul

REM 2. 启动前端
echo [2/2] 启动前端 (http://localhost:5173)...
cd /d "%PROJECT%frontend"
start "VaultAgent-Frontend" cmd /c "cd /d %PROJECT%frontend && npm run dev"

echo.
echo ============================================
echo 启动完成！
echo API:      http://localhost:8080
echo 前端:     http://localhost:5173
echo API 文档: http://localhost:8080/docs
echo ============================================
echo 按任意键关闭此窗口...
pause > nul

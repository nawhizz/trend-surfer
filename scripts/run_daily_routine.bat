@echo off
REM Trend Surfer Daily Routine - Batch Script for Windows Task Scheduler
REM Created: 2026-01-19

echo ============================================================
echo Trend Surfer Daily Routine Started
echo %date% %time%
echo ============================================================

REM Change to backend directory
cd /d D:\Projects\On\trend-surfer\backend

REM Force UTF-8 Encoding
chcp 65001
set PYTHONIOENCODING=utf-8

REM 로그 파일 경로
set LOG_FILE=D:\Projects\On\trend-surfer\logs\daily_routine_%date:~0,4%%date:~5,2%%date:~8,2%.log
REM 로그 디렉토리 생성
if not exist D:\Projects\On\trend-surfer\logs mkdir D:\Projects\On\trend-surfer\logs

REM Run daily routine script using uv
uv run ..\scripts\daily_routine.py > %LOG_FILE% 2>&1

echo ============================================================
echo Trend Surfer Daily Routine Completed
echo %date% %time%
echo ============================================================

REM Exit with the return code from the Python script
exit /b %ERRORLEVEL%

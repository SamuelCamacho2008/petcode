@echo off
title PetCode - Servidor Web de Identificacion y Rescate
echo ====================================================================
echo  Iniciando PetCode (FastAPI + Uvicorn) en http://127.0.0.1:8000
echo ====================================================================
echo.
echo Presiona Ctrl+C para detener el servidor.
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause


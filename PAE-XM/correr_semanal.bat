@echo off
REM Emisión semanal: actualiza datos de XM, emite y registra el pronóstico,
REM califica los anteriores y regenera el dashboard. Correr cada lunes.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python src\semanal.py || exit /b 1
python dashboard\generar.py

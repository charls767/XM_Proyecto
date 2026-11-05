@echo off
REM Emisión semanal: actualiza datos de XM, emite y registra el pronóstico,
REM califica los anteriores y regenera el dashboard. Correr cada miercoles: antes, la API aun no publica la semana anterior completa.
cd /d "%~dp0"
REM Entorno Python 3.11: .venv-pae si existe (equipo local), si no .venv.
if exist .venv-pae\Scripts\activate.bat (call .venv-pae\Scripts\activate.bat) else (call .venv\Scripts\activate.bat)
python src\semanal.py || exit /b 1
python dashboard\generar.py

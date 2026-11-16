@echo off
REM Emision semanal para la garantia TIE: actualiza datos de XM, emite y registra el pronostico
REM de la semana s+2, califica los anteriores, regenera los resultados de la app, genera el informe PDF
REM (informes\informe_TIE_AAAA-MM-DD.pdf) y ancla el registro en git.
REM Correr cada VIERNES despues de las 20:00 (dia de calculo de la garantia, CREG 004 de 2003): ya estan
REM publicados la semana s-1 completa y los dias de sabado a martes de la semana s.
REM La salida queda en registro\logs\AAAA-MM-DD.log.
cd /d "%~dp0"
REM Entorno Python 3.11: .venv-pae si existe (equipo local), si no .venv.
if exist .venv-pae\Scripts\activate.bat (call .venv-pae\Scripts\activate.bat) else (call .venv\Scripts\activate.bat)
for /f %%i in ('python -c "import datetime; print(datetime.date.today())"') do set HOY=%%i
if not exist registro\logs mkdir registro\logs
set LOG=registro\logs\%HOY%.log

echo === %DATE% %TIME% emision TIE >> "%LOG%"
python src\semanal_tie.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: la emision fallo. Ver %LOG%
    python src\informe_pdf.py >> "%LOG%" 2>&1
    echo Se genero igual el informe PDF con los resultados disponibles.
    exit /b 1
)
python src\resultados_app.py >> "%LOG%" 2>&1
if errorlevel 1 echo AVISO: los resultados de la app no se regeneraron. Ver %LOG%
python src\informe_pdf.py >> "%LOG%" 2>&1
if errorlevel 1 echo AVISO: el informe PDF no se genero. Ver %LOG%

REM Ancla la huella del registro: un commit y un tag por emision. Sin git, solo avisa.
where git >nul 2>&1
if errorlevel 1 (
    echo AVISO: git no esta disponible; el registro no quedo anclado.
    goto :fin
)
git add registro\pronosticos_tie.csv registro\snapshots_tie registro\pronosticos.csv results\app informes >> "%LOG%" 2>&1
git diff --cached --quiet -- registro results\app informes
if errorlevel 1 (
    git commit -m "Emision TIE %HOY%" -- registro\pronosticos_tie.csv registro\snapshots_tie registro\pronosticos.csv results\app informes >> "%LOG%" 2>&1
    git rev-parse -q --verify "refs/tags/registro-tie-%HOY%" >nul || git tag "registro-tie-%HOY%" >> "%LOG%" 2>&1
    echo Registro anclado en git: tag registro-tie-%HOY%
) else (
    echo Sin cambios en el registro; no se hizo commit.
)

:fin
type "%LOG%" | findstr /b /c:"Registrado" /c:"Estado" /c:"Semana" /c:"Calificadas" /c:"Informe generado"
exit /b 0

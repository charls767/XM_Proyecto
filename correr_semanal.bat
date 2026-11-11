@echo off
REM Emision semanal: actualiza datos de XM, emite y registra el pronostico,
REM califica los anteriores, regenera el tablero y ancla el registro en git.
REM Correr cada miercoles: antes, la API aun no publica la semana anterior completa.
REM La salida queda en registro\logs\AAAA-MM-DD.log.
cd /d "%~dp0"
REM Entorno Python 3.11: .venv-pae si existe (equipo local), si no .venv.
if exist .venv-pae\Scripts\activate.bat (call .venv-pae\Scripts\activate.bat) else (call .venv\Scripts\activate.bat)
for /f %%i in ('python -c "import datetime; print(datetime.date.today())"') do set HOY=%%i
if not exist registro\logs mkdir registro\logs
set LOG=registro\logs\%HOY%.log

echo === %DATE% %TIME% emision >> "%LOG%"
python src\semanal.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: la emision fallo. Ver %LOG%
    exit /b 1
)
python dashboard\generar.py >> "%LOG%" 2>&1
if errorlevel 1 echo AVISO: el tablero no se regenero. Ver %LOG%

REM Ancla la huella del registro: un commit y un tag por emision. Sin git, solo avisa.
where git >nul 2>&1
if errorlevel 1 (
    echo AVISO: git no esta disponible; el registro no quedo anclado.
    goto :fin
)
git add registro\pronosticos.csv registro\snapshots dashboard\index.html >> "%LOG%" 2>&1
git diff --cached --quiet -- registro dashboard\index.html
if errorlevel 1 (
    git commit -m "Emision semanal %HOY%" -- registro\pronosticos.csv registro\snapshots dashboard\index.html >> "%LOG%" 2>&1
    git rev-parse -q --verify "refs/tags/registro-%HOY%" >nul || git tag "registro-%HOY%" >> "%LOG%" 2>&1
    echo Registro anclado en git: tag registro-%HOY%
) else (
    echo Sin cambios en el registro; no se hizo commit.
)

:fin
type "%LOG%" | findstr /b /c:"Registrado" /c:"Estado" /c:"Semana" /c:"Candidato" /c:"Calificadas"
exit /b 0

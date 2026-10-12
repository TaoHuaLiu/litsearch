@echo off
chcp 65001 >nul
rem Installe ou met a jour litsearch (recherche bibliographique) et cree le raccourci "Recherche biblio" sur le Bureau.
rem Double-cliquez sur ce fichier. Relancez-le plus tard pour mettre a jour.

rem Adresse de l'archive du depot (a renseigner une fois par le mainteneur) :
set "REPO_ZIP=https://github.com/VOTRE-COMPTE/litsearch/archive/refs/heads/main.zip"

echo.
echo === Installation de litsearch ===
echo.
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
    echo Installation de uv, le gestionnaire Python...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto :fail
)

echo Telechargement et installation de litsearch (premiere fois : quelques minutes)...
uv tool install --python 3.12 --force --reinstall --refresh "litsearch[gui] @ %REPO_ZIP%"
if errorlevel 1 goto :fail
uv tool update-shell >nul 2>nul

echo Creation du raccourci sur le Bureau...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Recherche biblio.lnk'); $s.TargetPath=$env:USERPROFILE+'\.local\bin\litsearch-gui.exe'; $s.WorkingDirectory=$env:USERPROFILE; $s.WindowStyle=7; $s.Description='Recherche bibliographique multi-bases'; $s.Save()"

echo.
echo Termine. Double-cliquez sur "Recherche biblio" sur le Bureau : la page s'ouvre dans votre navigateur.
echo (Une fenetre noire reste ouverte en arriere-plan tant que l'outil tourne ; fermez-la pour l'arreter.)
echo.
pause
exit /b 0

:fail
echo.
echo L'installation a echoue. Envoyez une capture de cette fenetre a la personne qui vous a partage l'outil.
pause
exit /b 1

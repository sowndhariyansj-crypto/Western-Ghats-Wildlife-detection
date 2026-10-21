@echo off
REM ============================================================
REM make.bat — Quick-command helper for the Animal Detection project
REM Run from the project root:  .\make.bat <command>
REM ============================================================

IF "%1"=="" GOTO help
IF "%1"=="help"     GOTO help
IF "%1"=="install"  GOTO install
IF "%1"=="validate" GOTO validate
IF "%1"=="train"    GOTO train
IF "%1"=="eval"     GOTO eval
IF "%1"=="infer"    GOTO infer
IF "%1"=="app"      GOTO app
GOTO help

:help
echo.
echo  Animal Detection — Quick Commands
echo  ==================================
echo  .\make.bat install    Install all dependencies into venv\
echo  .\make.bat validate   Run dataset validation
echo  .\make.bat train      Start training (uses config\settings.yaml)
echo  .\make.bat eval       Evaluate trained model on test split
echo  .\make.bat infer      Run CLI inference  (set SOURCE=path\to\file)
echo  .\make.bat app        Launch the Streamlit web application
echo.
GOTO end

:install
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\pip.exe install -r requirements.txt
echo.
echo  Installation complete. Activate with:  venv\Scripts\activate
GOTO end

:validate
venv\Scripts\python.exe scripts\validate_dataset.py %2 %3 %4
GOTO end

:train
venv\Scripts\python.exe scripts\train.py %2 %3 %4 %5 %6
GOTO end

:eval
venv\Scripts\python.exe scripts\evaluate.py %2 %3 %4
GOTO end

:infer
IF "%SOURCE%"=="" (
    echo  Set the SOURCE variable first:
    echo    set SOURCE=path\to\image_or_video.jpg
    echo    .\make.bat infer
) ELSE (
    venv\Scripts\python.exe scripts\infer.py --source %SOURCE% %2 %3 %4
)
GOTO end

:app
venv\Scripts\streamlit.exe run app\app.py
GOTO end

:end

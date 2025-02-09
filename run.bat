@echo off
REM Ativa o ambiente virtual
call venv\Scripts\activate.bat

REM Define as variáveis de ambiente para o Flask
set FLASK_APP=app.py
set FLASK_ENV=development

REM Inicia o servidor Flask usando o interpretador Python
python -m flask run

pause

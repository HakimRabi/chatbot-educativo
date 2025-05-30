@echo off
echo Instalando dependencias del proyecto...
pip install fastapi
pip install "uvicorn[standard]"
pip install pydantic
pip install python-dotenv
pip install sqlalchemy
pip install passlib[bcrypt]
pip install langchain
pip install langchain-community
pip install ollama
echo Instalación completada.
pause

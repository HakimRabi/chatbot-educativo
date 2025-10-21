#!/usr/bin/env python3
"""
Pre-Check: Verificación rápida del sistema antes del inicio
Verifica que todo esté listo para ejecutar los servicios
"""

import os
import sys
import subprocess
import importlib.util

def check_file_exists(file_path, description):
    """Verifica que un archivo existe"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NO ENCONTRADO")
        return False

def check_python_package(package_name):
    """Verifica que un paquete de Python esté instalado"""
    spec = importlib.util.find_spec(package_name)
    if spec is not None:
        print(f"✅ Python package: {package_name}")
        return True
    else:
        print(f"❌ Python package: {package_name} - NO INSTALADO")
        return False

def check_docker_service():
    """Verifica que Docker esté funcionando"""
    try:
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker: Funcionando")
            return True
        else:
            print("❌ Docker: No funciona correctamente")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Docker: Timeout - puede estar lento")
        return False
    except FileNotFoundError:
        print("❌ Docker: No instalado o no en PATH")
        return False
    except Exception as e:
        print(f"❌ Docker: Error - {e}")
        return False

def main():
    """Función principal de verificación"""
    print("🔍 VERIFICACIÓN PRE-INICIO DEL SISTEMA")
    print("=" * 50)
    
    checks_passed = 0
    total_checks = 0
    
    # Verificar archivos críticos
    critical_files = [
        ("backend/app.py", "FastAPI App"),
        ("backend/celery_worker.py", "Celery Worker"),
        ("start_worker.bat", "Script Worker"),
        ("startAPI.bat", "Script API"),
        ("docker-compose.yml", "Docker Compose"),
        ("requirements.txt", "Dependencias"),
        ("frontend/index.html", "Frontend"),
        ("frontend/assets/js/chat.js", "Frontend JS")
    ]
    
    print("\n📁 ARCHIVOS CRÍTICOS:")
    for file_path, desc in critical_files:
        total_checks += 1
        if check_file_exists(file_path, desc):
            checks_passed += 1
    
    # Verificar paquetes Python críticos
    critical_packages = [
        "fastapi",
        "uvicorn", 
        "celery",
        "redis",
        "sse_starlette",
        "langchain",
        "langchain_ollama"
    ]
    
    print("\n📦 PAQUETES PYTHON:")
    for package in critical_packages:
        total_checks += 1
        if check_python_package(package):
            checks_passed += 1
    
    # Verificar Docker
    print("\n🐳 SERVICIOS EXTERNOS:")
    total_checks += 1
    if check_docker_service():
        checks_passed += 1
    
    # Verificar estructura de directorios
    directories = [
        "backend/data/chroma_db",
        "backend/data/faiss_index", 
        "backend/data/pdfs",
        "scripts"
    ]
    
    print("\n📂 DIRECTORIOS:")
    for directory in directories:
        total_checks += 1
        if os.path.exists(directory):
            print(f"✅ Directorio: {directory}")
            checks_passed += 1
        else:
            print(f"⚠️ Directorio: {directory} - No existe (se creará automáticamente)")
            checks_passed += 1  # No crítico
    
    # Resultados finales
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE VERIFICACIÓN")
    print("=" * 50)
    
    print(f"Total verificaciones: {total_checks}")
    print(f"Verificaciones exitosas: {checks_passed}")
    print(f"Porcentaje de éxito: {(checks_passed/total_checks)*100:.1f}%")
    
    if checks_passed >= total_checks * 0.9:  # 90% o más
        print("\n🎉 SISTEMA LISTO PARA INICIO")
        print("\n📋 PASOS SIGUIENTES:")
        print("1. Terminal 1: docker-compose up -d")
        print("2. Terminal 2: start_worker.bat") 
        print("3. Terminal 3: startAPI.bat")
        print("4. Abrir: http://localhost:8000")
        return True
    else:
        print("\n⚠️ REQUIERE ATENCIÓN")
        print("\n🔧 ACCIONES SUGERIDAS:")
        if checks_passed < total_checks * 0.7:
            print("- Instalar dependencias: pip install -r requirements.txt")
        print("- Verificar Docker Desktop esté ejecutándose")
        print("- Revisar archivos faltantes")
        return False

if __name__ == "__main__":
    success = main()
    input("\nPresiona Enter para continuar...")
    sys.exit(0 if success else 1)

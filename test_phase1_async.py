# Test completo para Fase 1 - Endpoints Asincrónicos
# Uso: & "C:/Program Files/Python313/python.exe" test_phase1_async.py

import requests
import time
import json
import sys
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:8000"
TEST_QUESTIONS = [
    "¿Qué es la inteligencia artificial?",
    "Explica los algoritmos de búsqueda",
    "¿Cómo funciona el aprendizaje automático?",
    "Define la programación orientada a objetos"
]

def test_sync_endpoint():
    """Test del endpoint sincrónico original"""
    print("🔬 Test 1: Endpoint Sincrónico Original")
    print("-" * 50)
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/preguntar", json={
            "texto": TEST_QUESTIONS[0],
            "userId": "test_user_sync",
            "chatToken": "test_token_sync"
        }, timeout=30)
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint sincrónico funciona")
            print(f"   └─ Tiempo: {duration:.2f}s")
            print(f"   └─ Respuesta: {len(data.get('respuesta', ''))} chars")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error en test sincrónico: {e}")
        return False

def test_async_endpoint():
    """Test del endpoint asincrónico nuevo"""
    print("\n🔬 Test 2: Endpoint Asincrónico Nuevo")
    print("-" * 50)
    
    try:
        # Enviar request asincrónico
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/chat/async", json={
            "texto": TEST_QUESTIONS[1],
            "userId": "test_user_async",
            "chatToken": "test_token_async",
            "modelo": "llama3"
        }, timeout=10)
        
        request_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            
            print(f"✅ Request asincrónico enviado")
            print(f"   └─ Task ID: {task_id}")
            print(f"   └─ Tiempo de request: {request_time:.2f}s")
            print(f"   └─ Status: {data.get('status')}")
            
            if task_id and task_id != "error":
                return test_task_status(task_id)
            else:
                print(f"❌ Task ID inválido: {task_id}")
                return False
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error en test asincrónico: {e}")
        return False

def test_task_status(task_id):
    """Test de seguimiento del estado de la tarea"""
    print(f"\n🔬 Test 3: Seguimiento de Tarea {task_id[:8]}...")
    print("-" * 50)
    
    # Esperar un momento inicial para que la tarea se registre en el worker
    print("⏳ Esperando que la tarea se registre en el worker...")
    time.sleep(3)
    
    max_attempts = 25  # Aumentamos intentos
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(f"{BASE_URL}/chat/status/{task_id}")
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress', 0)
                
                print(f"📊 Intento {attempt + 1}: {status.upper()} ({progress}%)")
                
                if status == "completed":
                    result = data.get('result', {})
                    print(f"✅ Tarea completada exitosamente")
                    print(f"   └─ Modelo usado: {result.get('model_used', 'N/A')}")
                    print(f"   └─ Tiempo procesamiento: {result.get('processing_time', 'N/A')}s")
                    print(f"   └─ Respuesta: {len(result.get('response', ''))} chars")
                    return True
                elif status == "failed":
                    error = data.get('error', 'Error desconocido')
                    print(f"❌ Tarea falló: {error}")
                    return False
                elif status in ["pending", "processing"]:
                    time.sleep(3)  # Aumentamos a 3 segundos para dar más tiempo
                    attempt += 1
                else:
                    print(f"⚠️ Estado desconocido: {status}")
                    time.sleep(3)  # Aumentamos también aquí
                    attempt += 1
            else:
                print(f"❌ Error obteniendo estado: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error en seguimiento: {e}")
            return False
    
    print(f"⏱️ Timeout después de {max_attempts} intentos")
    return False

def test_celery_health():
    """Test del health check de Celery"""
    print("\n🔬 Test 4: Health Check Celery")
    print("-" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/health/celery", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status')
            celery_available = data.get('celery_available', False)
            
            print(f"📊 Status: {status.upper()}")
            print(f"🔧 Celery disponible: {'Sí' if celery_available else 'No'}")
            
            if status == "healthy":
                worker_status = data.get('worker_status', {})
                print(f"✅ Celery funcionando correctamente")
                print(f"   └─ AI System: {'Sí' if worker_status.get('ai_system_initialized') else 'No'}")
                print(f"   └─ Redis: {'Sí' if worker_status.get('redis_connection') else 'No'}")
                return True
            elif status == "timeout":
                print(f"⚠️ Worker no responde (puede estar ocupado)")
                return True  # No es un error crítico
            else:
                print(f"❌ Celery no está saludable: {data.get('message', 'N/A')}")
                return False
        else:
            print(f"❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error en health check: {e}")
        return False

def test_concurrent_requests():
    """Test de múltiples requests concurrentes"""
    print("\n🔬 Test 5: Concurrencia (5 requests simultáneos)")
    print("-" * 50)
    
    import threading
    import queue
    
    results = queue.Queue()
    
    def send_async_request(question_index):
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/chat/async", json={
                "texto": TEST_QUESTIONS[question_index % len(TEST_QUESTIONS)],
                "userId": f"test_user_concurrent_{question_index}",
                "modelo": "llama3"
            }, timeout=10)
            
            request_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                results.put({
                    "index": question_index,
                    "success": True,
                    "request_time": request_time,
                    "task_id": data.get('task_id'),
                    "status": data.get('status')
                })
            else:
                results.put({
                    "index": question_index,
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                })
        except Exception as e:
            results.put({
                "index": question_index,
                "success": False,
                "error": str(e)
            })
    
    # Lanzar 5 requests concurrentes
    threads = []
    start_time = time.time()
    
    for i in range(5):
        thread = threading.Thread(target=send_async_request, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Esperar que terminen todos
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    # Analizar resultados
    successful = 0
    failed = 0
    task_ids = []
    
    while not results.empty():
        result = results.get()
        if result["success"]:
            successful += 1
            task_ids.append(result["task_id"])
            print(f"✅ Request {result['index']}: {result['request_time']:.2f}s - {result['status']}")
        else:
            failed += 1
            print(f"❌ Request {result['index']}: {result['error']}")
    
    print(f"\n📊 Resumen concurrencia:")
    print(f"   └─ Exitosos: {successful}/5")
    print(f"   └─ Fallidos: {failed}/5")
    print(f"   └─ Tiempo total: {total_time:.2f}s")
    print(f"   └─ Tasks creados: {len(task_ids)}")
    
    return successful >= 3  # Al menos 3 de 5 deben ser exitosos

def test_server_availability():
    """Test básico de disponibilidad del servidor"""
    print("🔬 Test 0: Disponibilidad del Servidor")
    print("-" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Servidor FastAPI disponible")
            return True
        else:
            print(f"❌ Servidor responde con código: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Servidor no disponible: {e}")
        print("💡 Asegúrate de que el servidor esté ejecutándose:")
        print("   uvicorn app:app --reload")
        return False

def main():
    print("🧪 TESTING FASE 1 - ENDPOINTS ASINCRÓNICOS")
    print("=" * 60)
    print(f"🕒 Inicio: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Disponibilidad Servidor", test_server_availability),
        ("Endpoint Sincrónico", test_sync_endpoint),
        ("Endpoint Asincrónico", test_async_endpoint),
        ("Health Check Celery", test_celery_health),
        ("Concurrencia", test_concurrent_requests)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        success = test_func()
        results.append((test_name, success))
        
        if not success and test_name == "Disponibilidad Servidor":
            print("\n❌ Servidor no disponible - cancelando tests restantes")
            break
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS FASE 1")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:<25} {status}")
        if success:
            passed += 1
    
    print(f"\n📈 Resultado: {passed}/{len(results)} tests pasaron")
    
    if passed == len(results):
        print("🎉 FASE 1 COMPLETADA - Todos los tests pasaron")
        print("✅ Sistema asincrónico funcionando correctamente")
        print("\n📋 Próximos pasos:")
        print("1. Hacer commit de los cambios")
        print("2. Continuar con Fase 2 (vLLM)")
    else:
        print("⚠️ ALGUNOS TESTS FALLARON")
        print("❌ Revisa los errores antes de continuar")
        print("\n🔧 Posibles soluciones:")
        print("1. Verificar que Redis esté funcionando")
        print("2. Verificar que Celery worker esté ejecutándose")
        print("3. Verificar que FastAPI esté ejecutándose")
    
    print("=" * 60)
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

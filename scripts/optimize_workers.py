#!/usr/bin/env python3
"""
T2.2: Optimización Workers Celery para máximo rendimiento
Configurar workers Celery con pool de procesos optimizado
"""

import psutil
import subprocess
import os
import time
import requests
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

def get_system_specs():
    """Obtener specs del sistema para optimización"""
    specs = {
        'cpu_cores': psutil.cpu_count(logical=False),
        'cpu_threads': psutil.cpu_count(logical=True),
        'ram_gb': round(psutil.virtual_memory().total / (1024**3)),
        'cpu_freq': psutil.cpu_freq().max if psutil.cpu_freq() else 0
    }
    
    print("🖥️ ESPECIFICACIONES DEL SISTEMA:")
    print(f"   CPU Cores: {specs['cpu_cores']}")
    print(f"   CPU Threads: {specs['cpu_threads']}")
    print(f"   RAM: {specs['ram_gb']} GB")
    print(f"   CPU Freq: {specs['cpu_freq']:.0f} MHz")
    
    return specs

def calculate_optimal_workers(specs):
    """Calcular número óptimo de workers"""
    # Fórmula optimizada para chatbot:
    # Base: 2 workers por core físico (I/O bound)
    # Max: limitado por RAM y GPU
    
    base_workers = specs['cpu_cores'] * 2
    max_ram_workers = specs['ram_gb'] // 2  # 2GB por worker
    
    # Para RTX 3060: máximo 4 workers concurrentes
    gpu_limit = 4
    
    optimal = min(base_workers, max_ram_workers, gpu_limit)
    
    print(f"\n⚙️ CÁLCULO DE WORKERS:")
    print(f"   Base (2x cores): {base_workers}")
    print(f"   Límite RAM: {max_ram_workers}")
    print(f"   Límite GPU: {gpu_limit}")
    print(f"   🎯 ÓPTIMO: {optimal} workers")
    
    return optimal

def create_optimized_worker_script(num_workers):
    """Crear script optimizado para workers"""
    
    # Configuración avanzada Celery
    script_content = f"""@echo off
echo Iniciando {num_workers} workers Celery optimizados...

REM Configuracion de entorno
set CELERY_WORKER_PREFETCH_MULTIPLIER=1
set CELERY_WORKER_MAX_TASKS_PER_CHILD=100
set CELERY_WORKER_MAX_MEMORY_PER_CHILD=200000
set CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=True
set CELERY_TASK_ACKS_LATE=True
set CELERY_WORKER_DISABLE_RATE_LIMITS=True

REM Pool optimizado para I/O
set CELERY_POOL=threads
set CELERY_WORKER_CONCURRENCY={num_workers * 2}

echo Configuracion aplicada:
echo - Workers: {num_workers}
echo - Pool: threads
echo - Concurrency: {num_workers * 2}
echo - Prefetch: 1
echo - Max tasks per child: 100

REM Iniciar workers
celery -A backend.celery_worker worker --loglevel=info --concurrency={num_workers * 2} --pool=threads --prefetch-multiplier=1 --max-tasks-per-child=100

echo Workers optimizados iniciados
pause
"""
    
    with open('start_optimized_workers.bat', 'w') as f:
        f.write(script_content)
    
    print(f"✅ Script optimizado creado: start_optimized_workers.bat")
    return script_content

def test_worker_performance(num_workers):
    """Test de rendimiento con múltiples workers"""
    print(f"\n🧪 TESTING {num_workers} WORKERS CONCURRENTES")
    print("="*50)
    
    # Preparar requests concurrentes
    test_prompts = [
        "¿Qué es machine learning?",
        "Explica las redes neuronales",
        "¿Cómo funciona deep learning?",
        "Define inteligencia artificial",
        "¿Qué son los algoritmos genéticos?",
        "Explica el procesamiento de lenguaje natural",
        "¿Cómo funciona el aprendizaje supervisado?",
        "Define la visión por computadora"
    ]
    
    # Tomar subset basado en workers
    concurrent_requests = min(len(test_prompts), num_workers * 2)
    selected_prompts = test_prompts[:concurrent_requests]
    
    print(f"📝 Enviando {len(selected_prompts)} requests concurrentes...")
    
    results = []
    start_time = datetime.now()
    
    def send_request(prompt, idx):
        """Enviar request individual"""
        req_start = datetime.now()
        try:
            response = requests.post('http://localhost:8000/chat/async', 
                json={
                    'texto': prompt,
                    'modelo': 'llama3'
                },
                timeout=60
            )
            req_end = datetime.now()
            duration = (req_end - req_start).total_seconds()
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id')
                
                # Esperar resultado con polling
                max_wait = 60  # 60 segundos máximo
                wait_time = 0
                completed = False
                
                while wait_time < max_wait and not completed:
                    time.sleep(2)  # Check cada 2 segundos
                    wait_time += 2
                    
                    result_response = requests.get(f'http://localhost:8000/chat/status/{task_id}', timeout=10)
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        if result_data.get('status') == 'completed':
                            completed = True
                            total_duration = (datetime.now() - req_start).total_seconds()
                            results.append({
                                'idx': idx,
                                'prompt': prompt[:30],
                                'duration': total_duration,
                                'success': True,
                                'response_length': len(str(result_data.get('result', '')))
                            })
                            print(f"   ✅ Request {idx+1}: {total_duration:.2f}s")
                        elif result_data.get('status') == 'failed':
                            results.append({
                                'idx': idx,
                                'prompt': prompt[:30],
                                'duration': wait_time,
                                'success': False,
                                'error': 'Task failed'
                            })
                            print(f"   ❌ Request {idx+1}: Task falló")
                            break
                
                if not completed:
                    results.append({
                        'idx': idx,
                        'prompt': prompt[:30],
                        'duration': max_wait,
                        'success': False,
                        'error': 'Timeout waiting for completion'
                    })
                    print(f"   ⏰ Request {idx+1}: Timeout")
            else:
                results.append({
                    'idx': idx,
                    'prompt': prompt[:30],
                    'duration': duration,
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                })
                print(f"   ❌ Request {idx+1}: HTTP {response.status_code}")
                
        except Exception as e:
            duration = (datetime.now() - req_start).total_seconds()
            results.append({
                'idx': idx,
                'prompt': prompt[:30],
                'duration': duration,
                'success': False,
                'error': str(e)
            })
            print(f"   ❌ Request {idx+1}: {e}")
    
    # Ejecutar requests concurrentes
    with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [executor.submit(send_request, prompt, idx) 
                  for idx, prompt in enumerate(selected_prompts)]
        
        # Esperar todos los resultados
        for future in futures:
            future.result()
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    return results, total_time

def analyze_worker_performance(results, total_time, num_workers):
    """Analizar rendimiento de workers"""
    print(f"\n📊 ANÁLISIS WORKERS ({num_workers} workers)")
    print("="*50)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    if successful:
        durations = [r['duration'] for r in successful]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        # Throughput
        throughput = len(successful) / total_time
        
        print(f"✅ Exitosos: {len(successful)}/{len(results)}")
        print(f"❌ Fallidos: {len(failed)}")
        print(f"⏱️ Tiempo promedio: {avg_duration:.2f}s")
        print(f"🏃 Tiempo mínimo: {min_duration:.2f}s")
        print(f"🐌 Tiempo máximo: {max_duration:.2f}s")
        print(f"⏰ Tiempo total: {total_time:.2f}s")
        print(f"🚀 Throughput: {throughput:.2f} req/s")
        
        return {
            'workers': num_workers,
            'success_rate': len(successful) / len(results) * 100,
            'avg_duration': avg_duration,
            'throughput': throughput,
            'total_time': total_time
        }
    else:
        print("❌ Ningún test exitoso")
        return None

def main():
    print("🚀 OPTIMIZACIÓN WORKERS CELERY")
    print("="*50)
    
    # Obtener specs del sistema
    specs = get_system_specs()
    
    # Calcular workers óptimos
    optimal_workers = calculate_optimal_workers(specs)
    
    # Crear script optimizado
    create_optimized_worker_script(optimal_workers)
    
    print(f"\n⚠️ PASOS PARA TESTING:")
    print("1. Detener workers actuales (Ctrl+C en terminal)")
    print("2. Ejecutar: .\\start_optimized_workers.bat")
    print("3. Esperar que workers se inicien (30 segundos)")
    print("4. Ejecutar este script nuevamente para testing")
    
    # Para demo, simular testing
    print(f"\n¿Workers optimizados ya están ejecutándose? (s/n): ", end="")
    response = "s"  # input().strip().lower()
    
    if response == 's':
        print("\n🧪 Iniciando test de rendimiento...")
        results, total_time = test_worker_performance(optimal_workers)
        performance = analyze_worker_performance(results, total_time, optimal_workers)
        
        if performance:
            # Guardar resultados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = f'worker_optimization_{timestamp}.json'
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': timestamp,
                    'system_specs': specs,
                    'optimization': performance,
                    'results': results
                }, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 Resultados guardados: {report_file}")
            print(f"\n🎯 SIGUIENTE PASO:")
            print("T2.3: Caché Redis avanzado (20min)")
        
    else:
        print(f"\n⏸️ Testing pospuesto. Ejecutar después de optimizar workers.")

if __name__ == "__main__":
    main()

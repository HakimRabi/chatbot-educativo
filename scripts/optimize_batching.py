#!/usr/bin/env python3
"""
T2.4: Batching simulado para Ollama
Simular batching inteligente para optimizar throughput
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor
import requests

class SmartBatchProcessor:
    """Procesador de lotes inteligente para Ollama"""
    
    def __init__(self, batch_size=3, batch_timeout=2.0, max_concurrent=2):
        self.batch_size = batch_size          # Tamaño máximo del lote
        self.batch_timeout = batch_timeout    # Timeout para formar lote (segundos)
        self.max_concurrent = max_concurrent  # Lotes concurrentes máximos
        
        self.pending_requests = deque()       # Cola de requests pendientes
        self.active_batches = 0              # Lotes activos
        self.batch_lock = threading.Lock()   # Lock para thread safety
        self.running = False                 # Estado del procesador
        
        self.stats = {
            'total_requests': 0,
            'total_batches': 0,
            'avg_batch_size': 0,
            'total_processing_time': 0,
            'requests_per_second': 0
        }
    
    def add_request(self, request_data):
        """Agregar request a la cola de batching"""
        with self.batch_lock:
            request_id = f"req_{len(self.pending_requests)}_{int(time.time())}"
            request_item = {
                'id': request_id,
                'data': request_data,
                'timestamp': time.time(),
                'future': None
            }
            
            self.pending_requests.append(request_item)
            self.stats['total_requests'] += 1
            
            # Si alcanzamos el tamaño del lote, procesar inmediatamente
            if len(self.pending_requests) >= self.batch_size:
                self._trigger_batch_processing()
        
        return request_id
    
    def _trigger_batch_processing(self):
        """Disparar procesamiento de lote"""
        if self.active_batches < self.max_concurrent and self.pending_requests:
            # Formar lote
            batch = []
            batch_size = min(self.batch_size, len(self.pending_requests))
            
            for _ in range(batch_size):
                if self.pending_requests:
                    batch.append(self.pending_requests.popleft())
            
            if batch:
                self.active_batches += 1
                # Procesar lote en thread separado
                threading.Thread(
                    target=self._process_batch,
                    args=(batch,),
                    daemon=True
                ).start()
    
    def _process_batch(self, batch):
        """Procesar un lote de requests"""
        batch_start = time.time()
        batch_id = f"batch_{int(batch_start)}"
        
        print(f"🔄 Procesando lote {batch_id} ({len(batch)} requests)")
        
        try:
            # Simular procesamiento optimizado
            # En lugar de procesar 1 a 1, procesamos en paralelo
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = []
                
                for request_item in batch:
                    future = executor.submit(self._process_single_request, request_item)
                    futures.append((request_item, future))
                
                # Recopilar resultados
                results = []
                for request_item, future in futures:
                    try:
                        result = future.result(timeout=60)
                        results.append({
                            'request_id': request_item['id'],
                            'success': True,
                            'result': result,
                            'processing_time': time.time() - request_item['timestamp']
                        })
                    except Exception as e:
                        results.append({
                            'request_id': request_item['id'],
                            'success': False,
                            'error': str(e),
                            'processing_time': time.time() - request_item['timestamp']
                        })
            
            batch_duration = time.time() - batch_start
            
            # Actualizar estadísticas
            with self.batch_lock:
                self.stats['total_batches'] += 1
                self.stats['total_processing_time'] += batch_duration
                self.stats['avg_batch_size'] = (
                    (self.stats['avg_batch_size'] * (self.stats['total_batches'] - 1) + len(batch)) 
                    / self.stats['total_batches']
                )
                
                # Calcular throughput
                if self.stats['total_processing_time'] > 0:
                    self.stats['requests_per_second'] = (
                        self.stats['total_requests'] / self.stats['total_processing_time']
                    )
            
            print(f"✅ Lote {batch_id} completado en {batch_duration:.2f}s")
            
            return results
            
        except Exception as e:
            print(f"❌ Error procesando lote {batch_id}: {e}")
            return []
        
        finally:
            with self.batch_lock:
                self.active_batches -= 1
                # Verificar si hay más requests pendientes
                if self.pending_requests:
                    self._trigger_batch_processing()
    
    def _process_single_request(self, request_item):
        """Procesar un request individual"""
        try:
            prompt = request_item['data']['prompt']
            model = request_item['data'].get('model', 'llama3')
            
            # Hacer request a Ollama
            response = requests.post('http://localhost:8000/chat/async', 
                json={
                    'texto': prompt,
                    'modelo': model
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id')
                
                # Esperar resultado con polling
                max_wait = 60
                wait_time = 0
                
                while wait_time < max_wait:
                    time.sleep(1)
                    wait_time += 1
                    
                    result_response = requests.get(f'http://localhost:8000/chat/status/{task_id}')
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        if result_data.get('status') == 'completed':
                            return {
                                'task_id': task_id,
                                'response': result_data.get('result', {}),
                                'processing_time': wait_time
                            }
                        elif result_data.get('status') == 'failed':
                            return {'error': 'Task failed', 'task_id': task_id}
                
                return {'error': 'Timeout waiting for completion', 'task_id': task_id}
            else:
                return {'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def get_stats(self):
        """Obtener estadísticas del procesador"""
        with self.batch_lock:
            return self.stats.copy()
    
    def start_batch_timer(self):
        """Iniciar timer para procesamiento por timeout"""
        def timer_loop():
            while self.running:
                time.sleep(self.batch_timeout)
                with self.batch_lock:
                    if self.pending_requests and self.active_batches < self.max_concurrent:
                        self._trigger_batch_processing()
        
        self.running = True
        threading.Thread(target=timer_loop, daemon=True).start()
    
    def stop(self):
        """Detener el procesador"""
        self.running = False

def test_batching_performance():
    """Test de rendimiento con batching"""
    print("🧪 TESTING BATCHING SIMULADO")
    print("="*50)
    
    # Configuraciones de test
    test_configs = [
        {'batch_size': 1, 'max_concurrent': 1, 'name': 'Sin Batching (baseline)'},
        {'batch_size': 2, 'max_concurrent': 2, 'name': 'Batching 2x2'},
        {'batch_size': 3, 'max_concurrent': 2, 'name': 'Batching 3x2'},
        {'batch_size': 4, 'max_concurrent': 1, 'name': 'Batching 4x1'}
    ]
    
    test_prompts = [
        "¿Qué es inteligencia artificial?",
        "Explica machine learning",
        "¿Cómo funcionan redes neuronales?",
        "Define deep learning",
        "¿Qué son algoritmos genéticos?",
        "Explica procesamiento de lenguaje natural",
        "¿Cómo funciona aprendizaje supervisado?",
        "Define visión por computadora"
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n📝 Testing: {config['name']}")
        print(f"   Configuración: batch_size={config['batch_size']}, max_concurrent={config['max_concurrent']}")
        
        # Crear procesador
        processor = SmartBatchProcessor(
            batch_size=config['batch_size'],
            batch_timeout=2.0,
            max_concurrent=config['max_concurrent']
        )
        
        processor.start_batch_timer()
        
        # Enviar todas las requests
        start_time = time.time()
        request_ids = []
        
        for i, prompt in enumerate(test_prompts):
            request_data = {
                'prompt': prompt,
                'model': 'llama3'
            }
            req_id = processor.add_request(request_data)
            request_ids.append(req_id)
            print(f"      Request {i+1}: {prompt[:30]}... (ID: {req_id})")
        
        # Esperar que se procesen todos
        print(f"   ⏳ Esperando procesamiento completo...")
        
        # Monitorear progreso
        max_wait = 300  # 5 minutos máximo
        check_interval = 5
        waited = 0
        
        while waited < max_wait:
            time.sleep(check_interval)
            waited += check_interval
            
            stats = processor.get_stats()
            processed = stats['total_requests'] - len(processor.pending_requests)
            
            print(f"      Progreso: {processed}/{len(test_prompts)} requests procesados")
            
            # Verificar si todos están procesados
            if len(processor.pending_requests) == 0 and processor.active_batches == 0:
                break
        
        total_time = time.time() - start_time
        final_stats = processor.get_stats()
        
        processor.stop()
        
        # Calcular métricas
        throughput = len(test_prompts) / total_time
        avg_processing_time = final_stats.get('total_processing_time', 0) / max(final_stats.get('total_batches', 1), 1)
        
        result = {
            'config': config,
            'total_time': total_time,
            'throughput': throughput,
            'avg_batch_size': final_stats.get('avg_batch_size', 0),
            'total_batches': final_stats.get('total_batches', 0),
            'avg_processing_time': avg_processing_time,
            'stats': final_stats
        }
        
        results.append(result)
        
        print(f"   ✅ Completado en {total_time:.2f}s")
        print(f"   📊 Throughput: {throughput:.2f} req/s")
        print(f"   📦 Lotes promedio: {final_stats.get('avg_batch_size', 0):.1f} requests/lote")
        print(f"   🔄 Total lotes: {final_stats.get('total_batches', 0)}")
    
    return results

def analyze_batching_results(results):
    """Analizar resultados de batching"""
    print(f"\n📊 ANÁLISIS COMPARATIVO DE BATCHING")
    print("="*60)
    
    baseline = results[0] if results else None
    
    print(f"{'Configuración':<20} {'Tiempo':<10} {'Throughput':<12} {'Mejora':<10}")
    print("-" * 60)
    
    for result in results:
        config_name = result['config']['name']
        total_time = result['total_time']
        throughput = result['throughput']
        
        if baseline and baseline != result:
            improvement = ((baseline['total_time'] - total_time) / baseline['total_time']) * 100
            improvement_str = f"{improvement:+.1f}%"
        else:
            improvement_str = "baseline"
        
        print(f"{config_name:<20} {total_time:<10.2f} {throughput:<12.2f} {improvement_str:<10}")
    
    # Encontrar mejor configuración
    best_config = max(results, key=lambda x: x['throughput'])
    print(f"\n🏆 MEJOR CONFIGURACIÓN:")
    print(f"   {best_config['config']['name']}")
    print(f"   Throughput: {best_config['throughput']:.2f} req/s")
    print(f"   Tiempo total: {best_config['total_time']:.2f}s")
    print(f"   Batch size promedio: {best_config['avg_batch_size']:.1f}")
    
    return best_config

def main():
    print("🚀 OPTIMIZACIÓN BATCHING SIMULADO")
    print("="*50)
    
    print("📋 CONFIGURACIONES DE PRUEBA:")
    print("1. Sin Batching (1x1) - Baseline")
    print("2. Batching 2x2 - 2 requests por lote, 2 lotes concurrentes")
    print("3. Batching 3x2 - 3 requests por lote, 2 lotes concurrentes")
    print("4. Batching 4x1 - 4 requests por lote, 1 lote a la vez")
    
    print(f"\n⚠️ ADVERTENCIA: Test puede tomar 15-20 minutos")
    print(f"¿Ejecutar test completo de batching? (s/n): ", end="")
    
    response = "s"  # input().strip().lower()
    
    if response == 's':
        print(f"\n🧪 Iniciando test de batching...")
        results = test_batching_performance()
        best_config = analyze_batching_results(results)
        
        # Guardar resultados
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report = {
            'timestamp': timestamp,
            'test_results': results,
            'best_configuration': best_config,
            'recommendations': {
                'optimal_batch_size': best_config['config']['batch_size'],
                'optimal_concurrency': best_config['config']['max_concurrent'],
                'expected_throughput': best_config['throughput']
            }
        }
        
        with open(f'batching_optimization_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 Resultados guardados: batching_optimization_{timestamp}.json")
        print(f"\n🎯 SIGUIENTE PASO:")
        print("T2.5: Monitoring GPU y métricas finales (10min)")
    
    else:
        print(f"\n⏸️ Test pospuesto.")
        print(f"💡 TIP: Para testing rápido, usar configuración 3x2")

if __name__ == "__main__":
    main()

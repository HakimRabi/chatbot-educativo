#!/usr/bin/env python3
"""
T2.5: Monitoring GPU y métricas finales del sistema
Monitoreo completo de rendimiento y recursos
"""

import psutil
import time
import json
import subprocess
import requests
from datetime import datetime
import threading
import GPUtil

class SystemMonitor:
    """Monitor completo del sistema para el chatbot"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = {
            'cpu': [],
            'memory': [],
            'gpu': [],
            'disk': [],
            'network': [],
            'responses': [],
            'errors': []
        }
        self.start_time = None
    
    def get_gpu_stats(self):
        """Obtener estadísticas de GPU"""
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Primera GPU (RTX 3060)
                return {
                    'id': gpu.id,
                    'name': gpu.name,
                    'temperature': gpu.temperature,
                    'load': gpu.load * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'memory_percent': (gpu.memoryUsed / gpu.memoryTotal) * 100
                }
            else:
                return {'error': 'No GPU detected'}
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_stats(self):
        """Obtener estadísticas completas del sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            
            # Memoria
            memory = psutil.virtual_memory()
            
            # Disco
            disk = psutil.disk_usage('/')
            
            # Red (diferencia desde última medición)
            network = psutil.net_io_counters()
            
            # GPU
            gpu_stats = self.get_gpu_stats()
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'frequency': cpu_freq.current if cpu_freq else 0,
                    'cores': psutil.cpu_count()
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'gpu': gpu_stats
            }
            
            return stats
            
        except Exception as e:
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def check_ollama_health(self):
        """Verificar salud de Ollama"""
        try:
            response = requests.get('http://localhost:11434/api/version', timeout=5)
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'version': response.json(),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {'status': 'unhealthy', 'code': response.status_code}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def check_api_health(self):
        """Verificar salud de la API FastAPI"""
        try:
            response = requests.get('http://localhost:8000/', timeout=5)
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {'status': 'unhealthy', 'code': response.status_code}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def check_redis_health(self):
        """Verificar salud de Redis"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            start = time.time()
            r.ping()
            response_time = time.time() - start
            
            info = r.info()
            return {
                'status': 'healthy',
                'response_time': response_time,
                'memory_usage': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0)
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def test_end_to_end_performance(self):
        """Test end-to-end de rendimiento"""
        print("🧪 TEST END-TO-END DE RENDIMIENTO")
        print("="*50)
        
        test_prompts = [
            "¿Qué es inteligencia artificial?",
            "Explica machine learning",
            "¿Cómo funcionan las redes neuronales?"
        ]
        
        results = []
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"📝 Test {i}/3: {prompt[:30]}...")
            
            start_time = time.time()
            
            try:
                # Medir recursos antes
                before_stats = self.get_system_stats()
                
                # Hacer request
                response = requests.post('http://localhost:8000/chat/async',
                    json={
                        'texto': prompt,
                        'modelo': 'llama3'
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    task_id = data.get('task_id')
                    
                    # Esperar resultado
                    max_wait = 60
                    wait_time = 0
                    completed = False
                    
                    while wait_time < max_wait and not completed:
                        time.sleep(2)
                        wait_time += 2
                        
                        result_response = requests.get(f'http://localhost:8000/chat/status/{task_id}')
                        if result_response.status_code == 200:
                            result_data = result_response.json()
                            if result_data.get('status') == 'completed':
                                completed = True
                                break
                    
                    # Medir recursos después
                    after_stats = self.get_system_stats()
                    
                    duration = time.time() - start_time
                    
                    if completed:
                        ai_response = result_data.get('result', {})
                        response_length = len(str(ai_response.get('response', '')))
                        
                        results.append({
                            'prompt': prompt,
                            'duration': duration,
                            'success': True,
                            'response_length': response_length,
                            'task_id': task_id,
                            'before_stats': before_stats,
                            'after_stats': after_stats
                        })
                        
                        print(f"   ✅ Completado en {duration:.2f}s ({response_length} chars)")
                    else:
                        results.append({
                            'prompt': prompt,
                            'duration': duration,
                            'success': False,
                            'error': 'Timeout'
                        })
                        print(f"   ⏰ Timeout después de {duration:.2f}s")
                else:
                    results.append({
                        'prompt': prompt,
                        'duration': time.time() - start_time,
                        'success': False,
                        'error': f'HTTP {response.status_code}'
                    })
                    print(f"   ❌ Error HTTP {response.status_code}")
                    
            except Exception as e:
                results.append({
                    'prompt': prompt,
                    'duration': time.time() - start_time,
                    'success': False,
                    'error': str(e)
                })
                print(f"   ❌ Error: {e}")
        
        return results
    
    def start_monitoring(self, duration_minutes=5):
        """Iniciar monitoreo continuo"""
        print(f"📊 INICIANDO MONITOREO ({duration_minutes} minutos)")
        print("="*50)
        
        self.monitoring = True
        self.start_time = time.time()
        end_time = self.start_time + (duration_minutes * 60)
        
        def monitor_loop():
            while self.monitoring and time.time() < end_time:
                stats = self.get_system_stats()
                self.metrics['cpu'].append(stats.get('cpu', {}))
                self.metrics['memory'].append(stats.get('memory', {}))
                self.metrics['gpu'].append(stats.get('gpu', {}))
                
                # Mostrar stats en tiempo real
                cpu_percent = stats.get('cpu', {}).get('percent', 0)
                memory_percent = stats.get('memory', {}).get('percent', 0)
                gpu_info = stats.get('gpu', {})
                
                if 'error' not in gpu_info:
                    gpu_load = gpu_info.get('load', 0)
                    gpu_memory = gpu_info.get('memory_percent', 0)
                    gpu_temp = gpu_info.get('temperature', 0)
                    
                    print(f"⏱️ {datetime.now().strftime('%H:%M:%S')} | "
                          f"CPU: {cpu_percent:5.1f}% | "
                          f"RAM: {memory_percent:5.1f}% | "
                          f"GPU: {gpu_load:5.1f}% ({gpu_memory:4.1f}% VRAM, {gpu_temp}°C)")
                else:
                    print(f"⏱️ {datetime.now().strftime('%H:%M:%S')} | "
                          f"CPU: {cpu_percent:5.1f}% | "
                          f"RAM: {memory_percent:5.1f}% | "
                          f"GPU: Error")
                
                time.sleep(10)  # Medir cada 10 segundos
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        return monitor_thread
    
    def stop_monitoring(self):
        """Detener monitoreo"""
        self.monitoring = False
    
    def generate_final_report(self):
        """Generar reporte final completo"""
        print(f"\n📄 GENERANDO REPORTE FINAL...")
        
        # Verificar salud de todos los servicios
        ollama_health = self.check_ollama_health()
        api_health = self.check_api_health()
        redis_health = self.check_redis_health()
        
        # Estadísticas actuales
        current_stats = self.get_system_stats()
        
        # Test de rendimiento
        performance_results = self.test_end_to_end_performance()
        
        # Calcular promedios del monitoreo
        avg_stats = {}
        if self.metrics['cpu']:
            avg_stats['cpu'] = sum(m.get('percent', 0) for m in self.metrics['cpu']) / len(self.metrics['cpu'])
        if self.metrics['memory']:
            avg_stats['memory'] = sum(m.get('percent', 0) for m in self.metrics['memory']) / len(self.metrics['memory'])
        if self.metrics['gpu']:
            gpu_loads = [m.get('load', 0) for m in self.metrics['gpu'] if 'error' not in m]
            if gpu_loads:
                avg_stats['gpu_load'] = sum(gpu_loads) / len(gpu_loads)
        
        # Compilar reporte
        report = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_duration': time.time() - self.start_time if self.start_time else 0,
            'service_health': {
                'ollama': ollama_health,
                'api': api_health,
                'redis': redis_health
            },
            'current_stats': current_stats,
            'average_stats': avg_stats,
            'performance_test': performance_results,
            'metrics_history': self.metrics
        }
        
        return report

def main():
    print("🚀 MONITORING GPU Y MÉTRICAS FINALES")
    print("="*50)
    
    monitor = SystemMonitor()
    
    # Verificar estado inicial de servicios
    print("🔍 VERIFICANDO SERVICIOS...")
    ollama_health = monitor.check_ollama_health()
    api_health = monitor.check_api_health()
    redis_health = monitor.check_redis_health()
    
    print(f"   Ollama: {ollama_health.get('status', 'unknown')}")
    print(f"   API: {api_health.get('status', 'unknown')}")
    print(f"   Redis: {redis_health.get('status', 'unknown')}")
    
    # Estadísticas actuales
    print(f"\n💻 ESTADÍSTICAS ACTUALES:")
    current_stats = monitor.get_system_stats()
    
    cpu_info = current_stats.get('cpu', {})
    memory_info = current_stats.get('memory', {})
    gpu_info = current_stats.get('gpu', {})
    
    print(f"   CPU: {cpu_info.get('percent', 0):.1f}% ({cpu_info.get('cores', 0)} cores)")
    print(f"   RAM: {memory_info.get('percent', 0):.1f}% ({memory_info.get('used', 0)/1024/1024/1024:.1f}/{memory_info.get('total', 0)/1024/1024/1024:.1f} GB)")
    
    if 'error' not in gpu_info:
        print(f"   GPU: {gpu_info.get('name', 'Unknown')} - {gpu_info.get('load', 0):.1f}% load, {gpu_info.get('temperature', 0)}°C")
        print(f"        VRAM: {gpu_info.get('memory_percent', 0):.1f}% ({gpu_info.get('memory_used', 0)}/{gpu_info.get('memory_total', 0)} MB)")
    else:
        print(f"   GPU: {gpu_info.get('error', 'Unknown error')}")
    
    print(f"\n¿Ejecutar monitoreo y test final? (s/n): ", end="")
    response = "s"  # input().strip().lower()
    
    if response == 's':
        # Iniciar monitoreo por 2 minutos
        monitor_thread = monitor.start_monitoring(duration_minutes=2)
        
        # Esperar a que termine
        monitor_thread.join()
        monitor.stop_monitoring()
        
        # Generar reporte final
        final_report = monitor.generate_final_report()
        
        # Guardar reporte
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'final_monitoring_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False, default=str)
        
        # Mostrar resumen
        print(f"\n📊 RESUMEN FINAL:")
        print("="*50)
        
        successful_tests = [r for r in final_report['performance_test'] if r.get('success', False)]
        if successful_tests:
            avg_response_time = sum(r['duration'] for r in successful_tests) / len(successful_tests)
            print(f"✅ Tests exitosos: {len(successful_tests)}/{len(final_report['performance_test'])}")
            print(f"⏱️ Tiempo promedio de respuesta: {avg_response_time:.2f}s")
        
        avg_stats = final_report.get('average_stats', {})
        print(f"💻 Uso promedio CPU: {avg_stats.get('cpu', 0):.1f}%")
        print(f"🧠 Uso promedio RAM: {avg_stats.get('memory', 0):.1f}%")
        print(f"🎮 Uso promedio GPU: {avg_stats.get('gpu_load', 0):.1f}%")
        
        print(f"\n📄 Reporte completo guardado: {report_file}")
        print(f"\n🏆 FASE 2 COMPLETADA - SISTEMA OPTIMIZADO")
        
    else:
        print(f"\n⏸️ Monitoreo pospuesto.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script de pruebas de carga SÍNCRONAS para el chatbot educativo con GPU
Evalúa el rendimiento del sistema usando el endpoint /preguntar con GPU habilitada
"""

import asyncio
import aiohttp
import time
import json
import statistics
import psutil
import threading
from datetime import datetime
from typing import List, Dict, Any
import argparse
import sys

class SyncLoadTester:
    def __init__(self, base_url: str = "http://localhost:8000", 
                 email: str = "admin@chatbot.cl", password: str = "1234"):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.results = {}
        self.system_metrics = []
        self.gpu_metrics = []
        self.monitoring = False
        self.auth_token = None
        
    def monitor_system_resources(self):
        """Monitorea recursos del sistema y GPU durante las pruebas"""
        while self.monitoring:
            # CPU y RAM
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Intentar obtener métricas de GPU
            gpu_usage = self.get_gpu_metrics()
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'gpu_usage': gpu_usage.get('utilization', 0),
                'gpu_memory_used': gpu_usage.get('memory_used', 0),
                'gpu_memory_total': gpu_usage.get('memory_total', 0),
                'gpu_temperature': gpu_usage.get('temperature', 0)
            }
            
            self.system_metrics.append(metrics)
            time.sleep(2)
    
    def get_gpu_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de GPU usando nvidia-ml-py o pynvml"""
        try:
            import pynvml
            pynvml.nvmlInit()
            
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # GPU 0
            
            # Utilización
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            # Memoria
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            # Temperatura
            temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            return {
                'utilization': utilization.gpu,
                'memory_used': memory_info.used / (1024**3),  # GB
                'memory_total': memory_info.total / (1024**3),  # GB
                'memory_percent': (memory_info.used / memory_info.total) * 100,
                'temperature': temperature
            }
        except Exception as e:
            # Fallback si no hay pynvml o no hay GPU
            return {
                'utilization': 0,
                'memory_used': 0,
                'memory_total': 0,
                'memory_percent': 0,
                'temperature': 0,
                'error': str(e)
            }
    
    async def authenticate(self, session: aiohttp.ClientSession) -> bool:
        """Autentica con el servidor y obtiene token"""
        try:
            async with session.post(
                f"{self.base_url}/auth/login",
                json={"email": self.email, "password": self.password}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data.get('access_token', '')
                    return True
                else:
                    print(f"❌ Error de autenticación: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error en autenticación: {e}")
            return False

    async def create_session(self, session: aiohttp.ClientSession, user_id: int) -> str:
        """Genera un session_id único para el usuario"""
        import uuid
        return str(uuid.uuid4())
    
    async def send_message_gpu(self, session: aiohttp.ClientSession, user_id: int, 
                              session_id: str, message: str) -> Dict[str, Any]:
        """Envía un mensaje al chatbot usando el endpoint /preguntar con GPU habilitada"""
        start_time = time.time()
        
        # Capturar métricas de GPU antes del request
        gpu_before = self.get_gpu_metrics()
        
        try:
            # Headers de autenticación si es necesario
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            # Asegurar que use GPU (modelo optimizado)
            payload = {
                "texto": message,
                "userId": str(user_id),
                "chatToken": session_id,
                "modelo": "ollama3",  # Modelo que debe usar GPU
                "use_gpu": True,      # Flag explícito para GPU
                "gpu_optimized": True # Optimización GPU
            }
            
            async with session.post(
                f"{self.base_url}/preguntar",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                # Capturar métricas de GPU después del request
                gpu_after = self.get_gpu_metrics()
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Calcular diferencia en uso de GPU
                    gpu_usage_diff = gpu_after.get('utilization', 0) - gpu_before.get('utilization', 0)
                    gpu_memory_diff = gpu_after.get('memory_used', 0) - gpu_before.get('memory_used', 0)
                    
                    return {
                        'success': True,
                        'response_time': response_time,
                        'status_code': response.status,
                        'response_length': len(str(data.get('response', ''))),
                        'user_id': user_id,
                        'gpu_utilized': gpu_usage_diff > 0,
                        'gpu_usage_before': gpu_before.get('utilization', 0),
                        'gpu_usage_after': gpu_after.get('utilization', 0),
                        'gpu_memory_used': gpu_after.get('memory_used', 0),
                        'gpu_temperature': gpu_after.get('temperature', 0),
                        'architecture': 'synchronous_gpu'
                    }
                else:
                    return {
                        'success': False,
                        'response_time': response_time,
                        'status_code': response.status,
                        'error': f"HTTP {response.status}",
                        'user_id': user_id,
                        'architecture': 'synchronous_gpu'
                    }
                    
        except asyncio.TimeoutError:
            return {
                'success': False,
                'response_time': time.time() - start_time,
                'status_code': 408,
                'error': "Timeout",
                'user_id': user_id,
                'architecture': 'synchronous_gpu'
            }
        except Exception as e:
            return {
                'success': False,
                'response_time': time.time() - start_time,
                'status_code': 500,
                'error': str(e),
                'user_id': user_id,
                'architecture': 'synchronous_gpu'
            }

    async def simulate_user(self, session: aiohttp.ClientSession, user_id: int, 
                           messages: List[str]) -> List[Dict[str, Any]]:
        """Simula un usuario enviando múltiples mensajes"""
        results = []
        
        # Crear sesión para el usuario (generar UUID)
        session_id = await self.create_session(session, user_id)
        if not session_id:
            return [{'success': False, 'error': 'No se pudo crear sesión', 'user_id': user_id}]
        
        # Enviar mensajes
        for i, message in enumerate(messages):
            print(f"   👤 Usuario {user_id} - Mensaje {i+1}/{len(messages)}: {message[:30]}...")
            result = await self.send_message_gpu(session, user_id, session_id, message)
            result['message_number'] = i + 1
            result['message_text'] = message[:50] + "..." if len(message) > 50 else message
            results.append(result)
            
            # Pausa pequeña entre mensajes del mismo usuario
            await asyncio.sleep(1)
        
        return results

    async def run_load_test(self, concurrent_users: int, messages_per_user: int = 3) -> Dict[str, Any]:
        """Ejecuta una prueba de carga síncrona con GPU"""
        print(f"\n🔄 Iniciando prueba SÍNCRONA + GPU con {concurrent_users} usuarios simultáneos...")
        
        # Mensajes de prueba optimizados para GPU
        test_messages = [
            "¿Qué es la inteligencia artificial y cómo funciona?",
            "Explícame los algoritmos de búsqueda A* con ejemplos detallados",
            "¿Cuál es la diferencia entre machine learning y deep learning?",
            "Describe las redes neuronales convolucionales y sus aplicaciones",
            "Explícame el algoritmo de backpropagation paso a paso",
            "¿Cómo funcionan los transformers en procesamiento de lenguaje natural?",
            "Analiza las ventajas y desventajas de los algoritmos genéticos"
        ]
        
        start_time = time.time()
        
        # Crear sesión HTTP
        connector = aiohttp.TCPConnector(limit=concurrent_users * 2)
        timeout = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Autenticar si es necesario (comentado por ahora)
            # await self.authenticate(session)
            
            # Crear tareas para todos los usuarios
            tasks = []
            for user_id in range(1, concurrent_users + 1):
                user_messages = test_messages[:messages_per_user]
                task = self.simulate_user(session, user_id, user_messages)
                tasks.append(task)
            
            # Ejecutar todas las tareas concurrentemente
            print(f"🚀 Lanzando {concurrent_users} usuarios concurrentes con GPU...")
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Procesar resultados
        successful_requests = 0
        failed_requests = 0
        response_times = []
        errors = []
        gpu_utilizations = []
        gpu_temperatures = []
        
        for user_results in all_results:
            if isinstance(user_results, Exception):
                failed_requests += 1
                errors.append(str(user_results))
                continue
                
            for result in user_results:
                if result.get('success', False):
                    successful_requests += 1
                    response_times.append(result['response_time'])
                    
                    # Recopilar métricas de GPU
                    if 'gpu_usage_after' in result:
                        gpu_utilizations.append(result['gpu_usage_after'])
                    if 'gpu_temperature' in result:
                        gpu_temperatures.append(result['gpu_temperature'])
                        
                else:
                    failed_requests += 1
                    errors.append(result.get('error', 'Unknown error'))
        
        # Calcular estadísticas
        total_requests = successful_requests + failed_requests
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'concurrent_users': concurrent_users,
            'total_duration': round(total_duration, 2),
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'success_rate': round(success_rate, 2),
            'requests_per_second': round(total_requests / total_duration, 2) if total_duration > 0 else 0,
            'architecture': 'synchronous_gpu'
        }
        
        if response_times:
            stats.update({
                'avg_response_time': round(statistics.mean(response_times), 2),
                'min_response_time': round(min(response_times), 2),
                'max_response_time': round(max(response_times), 2),
                'median_response_time': round(statistics.median(response_times), 2),
                'p95_response_time': round(sorted(response_times)[int(len(response_times) * 0.95)], 2)
            })
        
        # Estadísticas de GPU
        if gpu_utilizations:
            stats.update({
                'avg_gpu_utilization': round(statistics.mean(gpu_utilizations), 2),
                'max_gpu_utilization': round(max(gpu_utilizations), 2),
                'gpu_utilized_requests': len([u for u in gpu_utilizations if u > 0])
            })
            
        if gpu_temperatures:
            stats.update({
                'avg_gpu_temperature': round(statistics.mean(gpu_temperatures), 2),
                'max_gpu_temperature': round(max(gpu_temperatures), 2)
            })
        
        if errors:
            error_summary = {}
            for error in errors:
                error_summary[error] = error_summary.get(error, 0) + 1
            stats['errors'] = error_summary
        
        return stats
    
    def get_system_metrics_summary(self) -> Dict[str, Any]:
        """Calcula estadísticas de los recursos del sistema y GPU"""
        if not self.system_metrics:
            return {}
        
        cpu_values = [m['cpu_percent'] for m in self.system_metrics]
        memory_values = [m['memory_percent'] for m in self.system_metrics]
        gpu_values = [m['gpu_usage'] for m in self.system_metrics if m.get('gpu_usage')]
        gpu_memory_values = [m['gpu_memory_used'] for m in self.system_metrics if m.get('gpu_memory_used')]
        gpu_temp_values = [m['gpu_temperature'] for m in self.system_metrics if m.get('gpu_temperature') and m['gpu_temperature'] > 0]
        
        summary = {
            'avg_cpu_percent': round(statistics.mean(cpu_values), 2),
            'max_cpu_percent': round(max(cpu_values), 2),
            'avg_memory_percent': round(statistics.mean(memory_values), 2),
            'max_memory_percent': round(max(memory_values), 2),
            'samples_collected': len(self.system_metrics)
        }
        
        if gpu_values:
            summary.update({
                'avg_gpu_utilization': round(statistics.mean(gpu_values), 2),
                'max_gpu_utilization': round(max(gpu_values), 2),
                'gpu_monitoring_samples': len(gpu_values)
            })
            
        if gpu_memory_values:
            summary.update({
                'avg_gpu_memory_gb': round(statistics.mean(gpu_memory_values), 2),
                'max_gpu_memory_gb': round(max(gpu_memory_values), 2)
            })
            
        if gpu_temp_values:
            summary.update({
                'avg_gpu_temperature': round(statistics.mean(gpu_temp_values), 2),
                'max_gpu_temperature': round(max(gpu_temp_values), 2)
            })
        
        return summary

    async def run_full_test_suite(self, user_counts: List[int] = None):
        """Ejecuta suite completa de pruebas de carga síncronas con GPU"""
        if user_counts is None:
            user_counts = [1, 5, 10, 20]
        
        print("🚀 Iniciando suite de pruebas de carga SÍNCRONAS + GPU para el chatbot educativo")
        print(f"📊 Usuarios simultáneos a probar: {user_counts}")
        print(f"🎯 Modelo: ollama3 (GPU habilitada)")
        print(f"🔗 URL base: {self.base_url}")
        print(f"👤 Usuario de prueba: {self.email}")
        print(f"🖥️ Arquitectura: Síncrona con aceleración GPU")
        
        # Verificar GPU
        gpu_info = self.get_gpu_metrics()
        if gpu_info.get('memory_total', 0) > 0:
            print(f"✅ GPU detectada: {gpu_info['memory_total']:.1f}GB VRAM total")
        else:
            print(f"⚠️ No se detectó GPU o error: {gpu_info.get('error', 'Unknown')}")
        
        # Verificar conectividad
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/check_connection") as response:
                    if response.status != 200:
                        print("❌ Error: No se puede conectar al servidor")
                        return
                    print("✅ Conexión al servidor verificada")
        except Exception as e:
            print(f"❌ Error de conectividad: {e}")
            return
        
        all_results = []
        
        for user_count in user_counts:
            # Limpiar métricas previas
            self.system_metrics = []
            
            # Iniciar monitoreo del sistema y GPU
            self.monitoring = True
            monitor_thread = threading.Thread(target=self.monitor_system_resources)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            try:
                # Ejecutar prueba
                result = await self.run_load_test(user_count)
                
                # Detener monitoreo
                self.monitoring = False
                monitor_thread.join(timeout=5)
                
                # Agregar métricas del sistema
                result['system_metrics'] = self.get_system_metrics_summary()
                all_results.append(result)
                
                # Mostrar resultados en tiempo real
                self.print_test_results(result)
                
                # Pausa entre pruebas para que el sistema se recupere
                if user_count != user_counts[-1]:
                    print("⏳ Pausa de 10 segundos antes de la siguiente prueba...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                self.monitoring = False
                print(f"❌ Error en prueba con {user_count} usuarios: {e}")
        
        # Generar reporte final
        self.generate_final_report(all_results)
    
    def print_test_results(self, result: Dict[str, Any]):
        """Imprime resultados de una prueba individual con métricas de GPU"""
        print(f"\n📈 Resultados SÍNCRONOS + GPU para {result['concurrent_users']} usuarios:")
        print(f"   ⏱️  Duración total: {result['total_duration']}s")
        print(f"   📝 Total de requests: {result['total_requests']}")
        print(f"   ✅ Exitosos: {result['successful_requests']}")
        print(f"   ❌ Fallidos: {result['failed_requests']}")
        print(f"   📊 Tasa de éxito: {result['success_rate']}%")
        print(f"   🚀 Requests/segundo: {result['requests_per_second']}")
        
        if 'avg_response_time' in result:
            print(f"   ⚡ Tiempo respuesta promedio: {result['avg_response_time']}s")
            print(f"   📉 Tiempo respuesta mínimo: {result['min_response_time']}s")
            print(f"   📈 Tiempo respuesta máximo: {result['max_response_time']}s")
            print(f"   📊 Mediana: {result['median_response_time']}s")
            print(f"   🎯 P95: {result['p95_response_time']}s")
        
        # Métricas de GPU específicas
        if 'avg_gpu_utilization' in result:
            print(f"   🖥️ GPU utilización promedio: {result['avg_gpu_utilization']}%")
            print(f"   🖥️ GPU utilización máxima: {result['max_gpu_utilization']}%")
            print(f"   🔥 Requests que usaron GPU: {result.get('gpu_utilized_requests', 0)}")
        
        if 'avg_gpu_temperature' in result:
            print(f"   🌡️ GPU temperatura promedio: {result['avg_gpu_temperature']}°C")
            print(f"   🌡️ GPU temperatura máxima: {result['max_gpu_temperature']}°C")
        
        if 'system_metrics' in result:
            sm = result['system_metrics']
            print(f"   🖥️  CPU promedio: {sm.get('avg_cpu_percent', 'N/A')}%")
            print(f"   🖥️  CPU máximo: {sm.get('max_cpu_percent', 'N/A')}%")
            print(f"   💾 RAM promedio: {sm.get('avg_memory_percent', 'N/A')}%")
            print(f"   💾 RAM máximo: {sm.get('max_memory_percent', 'N/A')}%")
            
            if 'avg_gpu_memory_gb' in sm:
                print(f"   🎮 VRAM promedio: {sm['avg_gpu_memory_gb']}GB")
                print(f"   🎮 VRAM máximo: {sm['max_gpu_memory_gb']}GB")
        
        if 'errors' in result:
            print(f"   🚨 Errores más frecuentes:")
            for error, count in list(result['errors'].items())[:3]:
                print(f"      - {error}: {count} veces")
    
    def generate_final_report(self, all_results: List[Dict[str, Any]]):
        """Genera reporte final completo con métricas de GPU"""
        print("\n" + "="*70)
        print("📋 REPORTE FINAL DE PRUEBAS DE CARGA SÍNCRONAS + GPU")
        print("="*70)
        
        # Tabla resumen con GPU
        print("\n📊 RESUMEN COMPARATIVO (SÍNCRONO + GPU):")
        print(f"{'Usuarios':<10} {'Éxito%':<8} {'RPS':<8} {'Resp.Prom':<12} {'GPU%':<8} {'CPU%':<8} {'RAM%':<8}")
        print("-" * 70)
        
        for result in all_results:
            users = result['concurrent_users']
            success = f"{result['success_rate']}%"
            rps = f"{result['requests_per_second']}"
            resp_time = f"{result.get('avg_response_time', 'N/A')}s"
            gpu_util = f"{result.get('avg_gpu_utilization', 'N/A')}%"
            cpu = f"{result.get('system_metrics', {}).get('avg_cpu_percent', 'N/A')}%"
            ram = f"{result.get('system_metrics', {}).get('avg_memory_percent', 'N/A')}%"
            
            print(f"{users:<10} {success:<8} {rps:<8} {resp_time:<12} {gpu_util:<8} {cpu:<8} {ram:<8}")
        
        # Análisis de rendimiento con GPU
        print("\n🔍 ANÁLISIS DE RENDIMIENTO CON GPU:")
        
        successful_tests = [r for r in all_results if r['success_rate'] > 90]
        if successful_tests:
            max_users = max(r['concurrent_users'] for r in successful_tests)
            print(f"   ✅ Máximo de usuarios concurrentes con >90% éxito: {max_users}")
        
        if len(all_results) > 1:
            best_rps = max(all_results, key=lambda x: x['requests_per_second'])
            print(f"   🚀 Mejor throughput: {best_rps['requests_per_second']} RPS con {best_rps['concurrent_users']} usuarios")
        
        # Análisis específico de GPU
        gpu_tests = [r for r in all_results if r.get('avg_gpu_utilization', 0) > 0]
        if gpu_tests:
            avg_gpu_usage = statistics.mean([r['avg_gpu_utilization'] for r in gpu_tests])
            max_gpu_usage = max([r['max_gpu_utilization'] for r in gpu_tests])
            print(f"   🖥️ GPU utilización promedio: {avg_gpu_usage:.1f}%")
            print(f"   🖥️ GPU utilización máxima: {max_gpu_usage:.1f}%")
            
            gpu_temps = [r for r in all_results if r.get('max_gpu_temperature', 0) > 0]
            if gpu_temps:
                max_temp = max([r['max_gpu_temperature'] for r in gpu_temps])
                print(f"   🌡️ Temperatura máxima de GPU: {max_temp}°C")
        
        # Recomendaciones específicas para GPU
        print("\n💡 RECOMENDACIONES PARA OPTIMIZACIÓN GPU:")
        
        low_gpu_usage = [r for r in all_results if r.get('avg_gpu_utilization', 0) < 50]
        if low_gpu_usage:
            print(f"   ⚠️  GPU subutilizada (<50% uso) - verifica configuración Ollama")
            print(f"   🔧 Ejecuta 'optimize_ollama_gpu.bat' para optimizar GPU")
        
        high_response_time = [r for r in all_results if r.get('avg_response_time', 0) > 10]
        if high_response_time:
            first_slow = min(high_response_time, key=lambda x: x['concurrent_users'])
            print(f"   🐌 Tiempos de respuesta >10s a partir de {first_slow['concurrent_users']} usuarios")
            print(f"   ⚡ Considera aumentar memoria GPU o reducir tamaño del modelo")
        
        # Guardar resultados en archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sync_gpu_load_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'test_configuration': {
                        'base_url': self.base_url,
                        'model': 'ollama3',
                        'architecture': 'synchronous_gpu'
                    },
                    'results': all_results
                }, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Resultados guardados en: {filename}")
        except Exception as e:
            print(f"\n❌ Error guardando resultados: {e}")

async def main():
    parser = argparse.ArgumentParser(description='Pruebas de carga SÍNCRONAS + GPU para chatbot educativo')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='URL base del servidor (default: http://localhost:8000)')
    parser.add_argument('--users', nargs='+', type=int, default=[1, 5, 10, 20],
                       help='Lista de usuarios concurrentes a probar (default: 1 5 10 20)')
    parser.add_argument('--email', default='admin@chatbot.cl',
                       help='Email para autenticación (default: admin@chatbot.cl)')
    parser.add_argument('--password', default='1234',
                       help='Password para autenticación (default: 1234)')
    
    args = parser.parse_args()
    
    tester = SyncLoadTester(base_url=args.url, email=args.email, password=args.password)
    await tester.run_full_test_suite(user_counts=args.users)

if __name__ == "__main__":
    # Verificar dependencias
    try:
        import aiohttp
        import psutil
    except ImportError as e:
        print(f"❌ Error: Dependencia faltante - {e}")
        print("📦 Instala las dependencias con:")
        print("   pip install aiohttp psutil")
        sys.exit(1)
    
    # Verificar pynvml para GPU (opcional)
    try:
        import pynvml
        print("✅ pynvml disponible para monitoreo de GPU")
    except ImportError:
        print("⚠️ pynvml no disponible - instala con: pip install pynvml")
        print("   (Las pruebas funcionarán sin métricas detalladas de GPU)")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
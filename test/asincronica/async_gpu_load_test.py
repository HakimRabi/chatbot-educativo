#!/usr/bin/env python3
"""
Script de pruebas de carga ASÍNCRONAS para el chatbot educativo con GPU
Evalúa el rendimiento del sistema usando la arquitectura Celery + Worker con GPU habilitada
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

class AsyncGPULoadTester:
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

    async def create_async_task_gpu(self, session: aiohttp.ClientSession, user_id: int, 
                                  conversation_id: str, message: str) -> Dict[str, Any]:
        """Crea una tarea asíncrona con optimización GPU y retorna el task_id"""
        start_time = time.time()
        
        # Capturar métricas de GPU antes del request
        gpu_before = self.get_gpu_metrics()
        
        try:
            # Headers de autenticación si es necesario
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            # Payload optimizado para GPU
            payload = {
                "texto": message,
                "userId": str(user_id),
                "chatToken": conversation_id,
                "modelo": "ollama3",      # Modelo que debe usar GPU
                "conversation_id": conversation_id,
                "use_gpu": True,         # Flag explícito para GPU
                "gpu_optimized": True,   # Optimización GPU
                "worker_priority": "high" # Prioridad alta para worker
            }
            
            async with session.post(
                f"{self.base_url}/chat/async",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()
                submission_time = end_time - start_time
                
                # Capturar métricas de GPU después del request
                gpu_after = self.get_gpu_metrics()
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Calcular diferencia en uso de GPU
                    gpu_usage_diff = gpu_after.get('utilization', 0) - gpu_before.get('utilization', 0)
                    
                    return {
                        'success': True,
                        'submission_time': submission_time,
                        'task_id': data.get('task_id'),
                        'status': data.get('status'),
                        'estimated_time': data.get('estimated_time', 30),
                        'user_id': user_id,
                        'created_at': start_time,
                        'gpu_usage_before': gpu_before.get('utilization', 0),
                        'gpu_usage_after': gpu_after.get('utilization', 0),
                        'gpu_memory_used': gpu_after.get('memory_used', 0),
                        'gpu_temperature': gpu_after.get('temperature', 0),
                        'architecture': 'asynchronous_gpu'
                    }
                else:
                    return {
                        'success': False,
                        'submission_time': submission_time,
                        'status_code': response.status,
                        'error': f"HTTP {response.status}",
                        'user_id': user_id,
                        'architecture': 'asynchronous_gpu'
                    }
                    
        except asyncio.TimeoutError:
            return {
                'success': False,
                'submission_time': time.time() - start_time,
                'status_code': 408,
                'error': "Timeout en submission",
                'user_id': user_id,
                'architecture': 'asynchronous_gpu'
            }
        except Exception as e:
            return {
                'success': False,
                'submission_time': time.time() - start_time,
                'status_code': 500,
                'error': str(e),
                'user_id': user_id,
                'architecture': 'asynchronous_gpu'
            }

    async def poll_task_status_gpu(self, session: aiohttp.ClientSession, task_id: str, 
                                 max_wait_time: int = 180) -> Dict[str, Any]:
        """Hace polling del estado de una tarea hasta que se complete, monitoreando GPU"""
        start_time = time.time()
        poll_count = 0
        
        # Capturar estado inicial de GPU
        gpu_start = self.get_gpu_metrics()
        max_gpu_utilization = gpu_start.get('utilization', 0)
        max_gpu_temperature = gpu_start.get('temperature', 0)
        
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            while True:
                poll_count += 1
                poll_start = time.time()
                
                # Monitorear GPU durante polling
                current_gpu = self.get_gpu_metrics()
                max_gpu_utilization = max(max_gpu_utilization, current_gpu.get('utilization', 0))
                max_gpu_temperature = max(max_gpu_temperature, current_gpu.get('temperature', 0))
                
                async with session.get(
                    f"{self.base_url}/chat/status/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        status = data.get('status', 'unknown')
                        
                        if status == 'completed':
                            total_time = time.time() - start_time
                            result = data.get('result', {})
                            
                            # Capturar estado final de GPU
                            gpu_end = self.get_gpu_metrics()
                            
                            return {
                                'success': True,
                                'total_processing_time': total_time,
                                'poll_count': poll_count,
                                'status': 'completed',
                                'result': result,
                                'response_length': len(str(result.get('response', ''))),
                                'task_id': task_id,
                                'max_gpu_utilization_during_task': max_gpu_utilization,
                                'max_gpu_temperature_during_task': max_gpu_temperature,
                                'final_gpu_memory_used': gpu_end.get('memory_used', 0),
                                'gpu_utilized_during_processing': max_gpu_utilization > gpu_start.get('utilization', 0)
                            }
                        elif status == 'failed':
                            return {
                                'success': False,
                                'total_processing_time': time.time() - start_time,
                                'poll_count': poll_count,
                                'status': 'failed',
                                'error': data.get('error', 'Task failed'),
                                'task_id': task_id,
                                'max_gpu_utilization_during_task': max_gpu_utilization,
                                'max_gpu_temperature_during_task': max_gpu_temperature
                            }
                        elif status in ['pending', 'processing']:
                            # Continuar polling
                            elapsed = time.time() - start_time
                            if elapsed > max_wait_time:
                                return {
                                    'success': False,
                                    'total_processing_time': elapsed,
                                    'poll_count': poll_count,
                                    'status': 'timeout',
                                    'error': f'Timeout después de {max_wait_time}s',
                                    'task_id': task_id,
                                    'max_gpu_utilization_during_task': max_gpu_utilization,
                                    'max_gpu_temperature_during_task': max_gpu_temperature
                                }
                            
                            # Esperar antes del siguiente poll (adaptive polling)
                            if poll_count <= 5:
                                await asyncio.sleep(2)  # Primeros 5 polls cada 2s
                            elif poll_count <= 15:
                                await asyncio.sleep(5)  # Siguientes 10 polls cada 5s
                            else:
                                await asyncio.sleep(10) # Después cada 10s
                        else:
                            return {
                                'success': False,
                                'total_processing_time': time.time() - start_time,
                                'poll_count': poll_count,
                                'status': status,
                                'error': f'Estado desconocido: {status}',
                                'task_id': task_id,
                                'max_gpu_utilization_during_task': max_gpu_utilization,
                                'max_gpu_temperature_during_task': max_gpu_temperature
                            }
                    else:
                        return {
                            'success': False,
                            'total_processing_time': time.time() - start_time,
                            'poll_count': poll_count,
                            'status': 'http_error',
                            'error': f'HTTP {response.status} en polling',
                            'task_id': task_id,
                            'max_gpu_utilization_during_task': max_gpu_utilization,
                            'max_gpu_temperature_during_task': max_gpu_temperature
                        }
                        
        except Exception as e:
            return {
                'success': False,
                'total_processing_time': time.time() - start_time,
                'poll_count': poll_count,
                'status': 'error',
                'error': str(e),
                'task_id': task_id,
                'max_gpu_utilization_during_task': max_gpu_utilization,
                'max_gpu_temperature_during_task': max_gpu_temperature
            }

    async def process_async_message_gpu(self, session: aiohttp.ClientSession, user_id: int, 
                                      conversation_id: str, message: str) -> Dict[str, Any]:
        """Procesa un mensaje completo de forma asíncrona con monitoreo GPU"""
        
        # Paso 1: Submit la tarea
        submit_result = await self.create_async_task_gpu(session, user_id, conversation_id, message)
        
        if not submit_result['success']:
            return submit_result
        
        task_id = submit_result['task_id']
        
        # Paso 2: Poll hasta completion con monitoreo GPU
        poll_result = await self.poll_task_status_gpu(session, task_id)
        
        # Combinar resultados con métricas de GPU
        combined_result = {
            'success': poll_result['success'],
            'user_id': user_id,
            'task_id': task_id,
            'submission_time': submit_result['submission_time'],
            'total_processing_time': poll_result.get('total_processing_time', 0),
            'total_time': submit_result['submission_time'] + poll_result.get('total_processing_time', 0),
            'poll_count': poll_result.get('poll_count', 0),
            'status': poll_result.get('status', 'unknown'),
            'architecture': 'asynchronous_gpu'
        }
        
        # Agregar métricas de GPU
        combined_result.update({
            'gpu_usage_before_submission': submit_result.get('gpu_usage_before', 0),
            'gpu_usage_after_submission': submit_result.get('gpu_usage_after', 0),
            'max_gpu_utilization_during_task': poll_result.get('max_gpu_utilization_during_task', 0),
            'max_gpu_temperature_during_task': poll_result.get('max_gpu_temperature_during_task', 0),
            'gpu_utilized_during_processing': poll_result.get('gpu_utilized_during_processing', False),
            'final_gpu_memory_used': poll_result.get('final_gpu_memory_used', 0)
        })
        
        if poll_result['success']:
            combined_result.update({
                'response_length': poll_result.get('response_length', 0),
                'result': poll_result.get('result', {})
            })
        else:
            combined_result['error'] = poll_result.get('error', 'Unknown error')
        
        return combined_result

    async def simulate_async_user_gpu(self, session: aiohttp.ClientSession, user_id: int, 
                                    messages: List[str]) -> List[Dict[str, Any]]:
        """Simula un usuario enviando múltiples mensajes de forma asíncrona con GPU"""
        results = []
        
        # Generar conversation_id único para este usuario
        import uuid
        conversation_id = str(uuid.uuid4())
        
        # Enviar mensajes
        for i, message in enumerate(messages):
            print(f"   👤 Usuario {user_id} - Mensaje {i+1}/{len(messages)}: {message[:30]}...")
            result = await self.process_async_message_gpu(session, user_id, conversation_id, message)
            result['message_number'] = i + 1
            result['message_text'] = message[:50] + "..." if len(message) > 50 else message
            results.append(result)
            
            # Pausa entre mensajes del mismo usuario
            if i < len(messages) - 1:
                await asyncio.sleep(2)
        
        return results

    async def run_async_gpu_load_test(self, concurrent_users: int, messages_per_user: int = 3) -> Dict[str, Any]:
        """Ejecuta una prueba de carga asíncrona con GPU"""
        print(f"\n🔄 Iniciando prueba ASÍNCRONA + GPU con {concurrent_users} usuarios simultáneos...")
        
        # Mensajes de prueba optimizados para GPU
        test_messages = [
            "¿Qué es la inteligencia artificial y cómo se implementa en sistemas modernos?",
            "Explícame los algoritmos de búsqueda A* con ejemplos prácticos y código",
            "¿Cuál es la diferencia entre machine learning y deep learning en aplicaciones reales?",
            "Describe las redes neuronales convolucionales y sus casos de uso",
            "Explícame el algoritmo de backpropagation con matemáticas detalladas",
            "¿Cómo funcionan los transformers en procesamiento de lenguaje natural?",
            "Analiza las ventajas de los algoritmos genéticos en optimización"
        ]
        
        start_time = time.time()
        
        # Crear sesión HTTP
        connector = aiohttp.TCPConnector(limit=concurrent_users * 2)
        timeout = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Autenticar si es necesario (opcional)
            # await self.authenticate(session)
            
            # Crear tareas para todos los usuarios
            tasks = []
            for user_id in range(1, concurrent_users + 1):
                user_messages = test_messages[:messages_per_user]
                task = self.simulate_async_user_gpu(session, user_id, user_messages)
                tasks.append(task)
            
            # Ejecutar todas las tareas concurrentemente
            print(f"🚀 Lanzando {concurrent_users} usuarios concurrentes con Workers + GPU...")
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Procesar resultados
        successful_requests = 0
        failed_requests = 0
        submission_times = []
        processing_times = []
        total_times = []
        errors = []
        worker_usage_count = 0
        gpu_utilizations = []
        gpu_temperatures = []
        gpu_utilized_count = 0
        
        for user_results in all_results:
            if isinstance(user_results, Exception):
                failed_requests += 1
                errors.append(str(user_results))
                continue
                
            for result in user_results:
                if result.get('success', False):
                    successful_requests += 1
                    submission_times.append(result.get('submission_time', 0))
                    processing_times.append(result.get('total_processing_time', 0))
                    total_times.append(result.get('total_time', 0))
                    worker_usage_count += 1
                    
                    # Recopilar métricas de GPU
                    if 'max_gpu_utilization_during_task' in result:
                        gpu_utilizations.append(result['max_gpu_utilization_during_task'])
                    if 'max_gpu_temperature_during_task' in result:
                        gpu_temperatures.append(result['max_gpu_temperature_during_task'])
                    if result.get('gpu_utilized_during_processing', False):
                        gpu_utilized_count += 1
                        
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
            'worker_tasks_processed': worker_usage_count,
            'architecture': 'asynchronous_gpu'
        }
        
        if submission_times:
            stats.update({
                'avg_submission_time': round(statistics.mean(submission_times), 2),
                'max_submission_time': round(max(submission_times), 2),
            })
        
        if processing_times:
            stats.update({
                'avg_processing_time': round(statistics.mean(processing_times), 2),
                'min_processing_time': round(min(processing_times), 2),
                'max_processing_time': round(max(processing_times), 2),
                'median_processing_time': round(statistics.median(processing_times), 2),
                'p95_processing_time': round(sorted(processing_times)[int(len(processing_times) * 0.95)], 2) if processing_times else 0
            })
            
        if total_times:
            stats.update({
                'avg_total_time': round(statistics.mean(total_times), 2),
                'min_total_time': round(min(total_times), 2),
                'max_total_time': round(max(total_times), 2),
            })
        
        # Estadísticas de GPU específicas
        if gpu_utilizations:
            stats.update({
                'avg_gpu_utilization_during_tasks': round(statistics.mean(gpu_utilizations), 2),
                'max_gpu_utilization_during_tasks': round(max(gpu_utilizations), 2),
                'gpu_utilized_tasks': gpu_utilized_count,
                'gpu_utilization_percentage': round((gpu_utilized_count / successful_requests * 100), 2) if successful_requests > 0 else 0
            })
            
        if gpu_temperatures:
            stats.update({
                'avg_gpu_temperature_during_tasks': round(statistics.mean(gpu_temperatures), 2),
                'max_gpu_temperature_during_tasks': round(max(gpu_temperatures), 2)
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

    async def run_full_async_gpu_test_suite(self, user_counts: List[int] = None):
        """Ejecuta suite completa de pruebas de carga asíncronas con GPU"""
        if user_counts is None:
            user_counts = [1, 5, 10, 20]
        
        print("🚀 Iniciando suite de pruebas de carga ASÍNCRONAS + GPU para el chatbot educativo")
        print(f"📊 Usuarios simultáneos a probar: {user_counts}")
        print(f"🎯 Modelo: ollama3 (GPU habilitada)")
        print(f"🔗 URL base: {self.base_url}")
        print(f"👤 Usuario de prueba: {self.email}")
        print(f"⚡ Arquitectura: Celery Workers + GPU")
        
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
        
        # Verificar que Celery esté disponible
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/async", 
                                      json={"texto": "test GPU", "modelo": "ollama3", "use_gpu": True}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('task_id'):
                            print("✅ Worker asíncrono + GPU disponible")
                        else:
                            print("⚠️ Respuesta inesperada del endpoint async")
                    else:
                        print(f"⚠️ Problema con endpoint async: {response.status}")
        except Exception as e:
            print(f"⚠️ No se pudo verificar el worker: {e}")
        
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
                result = await self.run_async_gpu_load_test(user_count)
                
                # Detener monitoreo
                self.monitoring = False
                monitor_thread.join(timeout=5)
                
                # Agregar métricas del sistema
                result['system_metrics'] = self.get_system_metrics_summary()
                all_results.append(result)
                
                # Mostrar resultados en tiempo real
                self.print_async_gpu_test_results(result)
                
                # Pausa entre pruebas para que el sistema se recupere
                if user_count != user_counts[-1]:
                    print("⏳ Pausa de 15 segundos antes de la siguiente prueba...")
                    await asyncio.sleep(15)
                    
            except Exception as e:
                self.monitoring = False
                print(f"❌ Error en prueba con {user_count} usuarios: {e}")
        
        # Generar reporte final
        self.generate_async_gpu_final_report(all_results)
    
    def print_async_gpu_test_results(self, result: Dict[str, Any]):
        """Imprime resultados de una prueba asíncrona con GPU individual"""
        print(f"\n📈 Resultados ASÍNCRONOS + GPU para {result['concurrent_users']} usuarios:")
        print(f"   ⏱️  Duración total: {result['total_duration']}s")
        print(f"   📝 Total de requests: {result['total_requests']}")
        print(f"   ✅ Exitosos: {result['successful_requests']}")
        print(f"   ❌ Fallidos: {result['failed_requests']}")
        print(f"   📊 Tasa de éxito: {result['success_rate']}%")
        print(f"   🚀 Requests/segundo: {result['requests_per_second']}")
        print(f"   🔧 Tareas procesadas por worker: {result.get('worker_tasks_processed', 0)}")
        
        if 'avg_submission_time' in result:
            print(f"   📤 Tiempo submission promedio: {result['avg_submission_time']}s")
            print(f"   📤 Tiempo submission máximo: {result['max_submission_time']}s")
        
        if 'avg_processing_time' in result:
            print(f"   ⚡ Tiempo procesamiento promedio: {result['avg_processing_time']}s")
            print(f"   📉 Tiempo procesamiento mínimo: {result['min_processing_time']}s")
            print(f"   📈 Tiempo procesamiento máximo: {result['max_processing_time']}s")
            print(f"   📊 Mediana procesamiento: {result['median_processing_time']}s")
            print(f"   🎯 P95 procesamiento: {result['p95_processing_time']}s")
        
        if 'avg_total_time' in result:
            print(f"   🕐 Tiempo total promedio: {result['avg_total_time']}s")
        
        # Métricas específicas de GPU
        if 'avg_gpu_utilization_during_tasks' in result:
            print(f"   🖥️ GPU utilización promedio durante tareas: {result['avg_gpu_utilization_during_tasks']}%")
            print(f"   🖥️ GPU utilización máxima durante tareas: {result['max_gpu_utilization_during_tasks']}%")
            print(f"   🔥 Tareas que utilizaron GPU: {result.get('gpu_utilized_tasks', 0)}/{result['successful_requests']}")
            print(f"   📊 Porcentaje de uso de GPU: {result.get('gpu_utilization_percentage', 0)}%")
        
        if 'avg_gpu_temperature_during_tasks' in result:
            print(f"   🌡️ GPU temperatura promedio: {result['avg_gpu_temperature_during_tasks']}°C")
            print(f"   🌡️ GPU temperatura máxima: {result['max_gpu_temperature_during_tasks']}°C")
        
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
    
    def generate_async_gpu_final_report(self, all_results: List[Dict[str, Any]]):
        """Genera reporte final completo para pruebas asíncronas con GPU"""
        print("\n" + "="*75)
        print("📋 REPORTE FINAL DE PRUEBAS DE CARGA ASÍNCRONAS + GPU")
        print("="*75)
        
        # Tabla resumen con GPU
        print("\n📊 RESUMEN COMPARATIVO (ASÍNCRONO + GPU):")
        print(f"{'Usuarios':<10} {'Éxito%':<8} {'RPS':<8} {'Proc.Prom':<12} {'GPU%':<8} {'CPU%':<8} {'RAM%':<8}")
        print("-" * 75)
        
        for result in all_results:
            users = result['concurrent_users']
            success = f"{result['success_rate']}%"
            rps = f"{result['requests_per_second']}"
            proc_time = f"{result.get('avg_processing_time', 'N/A')}s"
            gpu_util = f"{result.get('avg_gpu_utilization_during_tasks', 'N/A')}%"
            cpu = f"{result.get('system_metrics', {}).get('avg_cpu_percent', 'N/A')}%"
            ram = f"{result.get('system_metrics', {}).get('avg_memory_percent', 'N/A')}%"
            
            print(f"{users:<10} {success:<8} {rps:<8} {proc_time:<12} {gpu_util:<8} {cpu:<8} {ram:<8}")
        
        # Análisis específico para arquitectura asíncrona + GPU
        print("\n🔍 ANÁLISIS DE RENDIMIENTO ASÍNCRONO + GPU:")
        
        successful_tests = [r for r in all_results if r['success_rate'] > 90]
        if successful_tests:
            max_users = max(r['concurrent_users'] for r in successful_tests)
            print(f"   ✅ Máximo de usuarios concurrentes con >90% éxito: {max_users}")
        
        if len(all_results) > 1:
            best_rps = max(all_results, key=lambda x: x['requests_per_second'])
            print(f"   🚀 Mejor throughput: {best_rps['requests_per_second']} RPS con {best_rps['concurrent_users']} usuarios")
            
            total_worker_tasks = sum(r.get('worker_tasks_processed', 0) for r in all_results)
            total_gpu_tasks = sum(r.get('gpu_utilized_tasks', 0) for r in all_results)
            print(f"   🔧 Total de tareas procesadas por workers: {total_worker_tasks}")
            print(f"   🖥️ Total de tareas que utilizaron GPU: {total_gpu_tasks}")
        
        # Análisis específico de GPU
        gpu_tests = [r for r in all_results if r.get('avg_gpu_utilization_during_tasks', 0) > 0]
        if gpu_tests:
            avg_gpu_usage = statistics.mean([r['avg_gpu_utilization_during_tasks'] for r in gpu_tests])
            max_gpu_usage = max([r['max_gpu_utilization_during_tasks'] for r in gpu_tests])
            avg_gpu_percentage = statistics.mean([r.get('gpu_utilization_percentage', 0) for r in gpu_tests])
            
            print(f"   🖥️ GPU utilización promedio durante tareas: {avg_gpu_usage:.1f}%")
            print(f"   🖥️ GPU utilización máxima durante tareas: {max_gpu_usage:.1f}%")
            print(f"   📊 Porcentaje promedio de tareas usando GPU: {avg_gpu_percentage:.1f}%")
            
            gpu_temps = [r for r in all_results if r.get('max_gpu_temperature_during_tasks', 0) > 0]
            if gpu_temps:
                max_temp = max([r['max_gpu_temperature_during_tasks'] for r in gpu_temps])
                print(f"   🌡️ Temperatura máxima de GPU durante tareas: {max_temp}°C")
        
        # Comparación de tiempos asíncronos
        if all_results:
            submission_times = [r.get('avg_submission_time', 0) for r in all_results if r.get('avg_submission_time')]
            processing_times = [r.get('avg_processing_time', 0) for r in all_results if r.get('avg_processing_time')]
            
            if submission_times:
                avg_submission = statistics.mean(submission_times)
                print(f"   📤 Tiempo promedio de submission: {avg_submission:.2f}s")
            if processing_times:
                avg_processing = statistics.mean(processing_times)
                print(f"   ⚡ Tiempo promedio de procesamiento: {avg_processing:.2f}s")
        
        # Recomendaciones específicas para arquitectura asíncrona + GPU
        print("\n💡 RECOMENDACIONES PARA ARQUITECTURA ASÍNCRONA + GPU:")
        
        degraded_tests = [r for r in all_results if r['success_rate'] < 95]
        if degraded_tests:
            first_degraded = min(degraded_tests, key=lambda x: x['concurrent_users'])
            print(f"   ⚠️  Degradación notable a partir de {first_degraded['concurrent_users']} usuarios")
            print(f"   🔧 Considera aumentar el número de workers Celery")
        
        low_gpu_usage = [r for r in all_results if r.get('gpu_utilization_percentage', 0) < 50]
        if low_gpu_usage:
            print(f"   ⚠️  GPU subutilizada (<50% de tareas usan GPU)")
            print(f"   🔧 Verifica configuración Ollama para forzar GPU")
            print(f"   🚀 Ejecuta 'optimize_ollama_gpu.bat' para optimizar")
        
        high_processing_time = [r for r in all_results if r.get('avg_processing_time', 0) > 30]
        if high_processing_time:
            first_slow = min(high_processing_time, key=lambda x: x['concurrent_users'])
            print(f"   🐌 Procesamiento >30s a partir de {first_slow['concurrent_users']} usuarios")
            print(f"   ⚡ Considera aumentar workers o optimizar modelo para GPU")
        
        submission_issues = [r for r in all_results if r.get('avg_submission_time', 0) > 2]
        if submission_issues:
            print(f"   📤 Tiempos de submission elevados - verifica la cola Redis")
        
        # Guardar resultados en archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"async_gpu_load_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'test_configuration': {
                        'base_url': self.base_url,
                        'model': 'ollama3',
                        'architecture': 'asynchronous_gpu'
                    },
                    'results': all_results
                }, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Resultados guardados en: {filename}")
        except Exception as e:
            print(f"\n❌ Error guardando resultados: {e}")

async def main():
    parser = argparse.ArgumentParser(description='Pruebas de carga ASÍNCRONAS + GPU para chatbot educativo')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='URL base del servidor (default: http://localhost:8000)')
    parser.add_argument('--users', nargs='+', type=int, default=[1, 5, 10, 20],
                       help='Lista de usuarios concurrentes a probar (default: 1 5 10 20)')
    parser.add_argument('--email', default='admin@chatbot.cl',
                       help='Email para autenticación (default: admin@chatbot.cl)')
    parser.add_argument('--password', default='1234',
                       help='Password para autenticación (default: 1234)')
    
    args = parser.parse_args()
    
    tester = AsyncGPULoadTester(base_url=args.url, email=args.email, password=args.password)
    await tester.run_full_async_gpu_test_suite(user_counts=args.users)

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
# Stress Test Runner
# Ejecuta tests de estres simulando usuarios concurrentes

import asyncio
import aiohttp
import time
import logging
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import threading

from .metrics_collector import MetricsCollector

logger = logging.getLogger("diagnostics.stress")


# Queries de ejemplo por complejidad
SAMPLE_QUERIES = {
    "simple": [
        "Hola, como estas?",
        "Que es Python?",
        "Explica que es una variable",
        "Que es un bucle for?",
        "Como se define una funcion?"
    ],
    "medium": [
        "Explica la diferencia entre una lista y una tupla en Python",
        "Como funciona la herencia en programacion orientada a objetos?",
        "Que es un decorador en Python y para que sirve?",
        "Explica el patron de diseno MVC",
        "Como se implementa una pila usando listas?"
    ],
    "complex": [
        "Explica en detalle como funciona el garbage collector de Python y como optimizar el uso de memoria",
        "Describe la arquitectura de microservicios, sus ventajas, desventajas y cuando usarla vs monolito",
        "Explica el algoritmo de ordenamiento quicksort, su complejidad temporal y espacial con ejemplos",
        "Como implementarias un sistema de cache distribuido con invalidacion automatica?",
        "Explica las diferencias entre procesos, threads y asyncio en Python con casos de uso"
    ]
}


class StressTestRunner:
    """Ejecutor de tests de estres"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_collector = MetricsCollector()
        self.is_running = False
        self.should_stop = False
        self.query_timeout_seconds = 600  # Default 10 minutos, se actualiza con duration_seconds
        self.current_stats = {
            "active_queries": 0,
            "completed_queries": 0,
            "failed_queries": 0,
            "latencies": []
        }
        self._lock = threading.Lock()
    
    def get_sample_queries(self, complexity: str, count: int) -> List[str]:
        """Obtiene queries de ejemplo segun complejidad"""
        if complexity == "mixed":
            queries = []
            all_queries = SAMPLE_QUERIES["simple"] + SAMPLE_QUERIES["medium"] + SAMPLE_QUERIES["complex"]
            for i in range(count):
                queries.append(all_queries[i % len(all_queries)])
            return queries
        
        base_queries = SAMPLE_QUERIES.get(complexity, SAMPLE_QUERIES["medium"])
        queries = []
        for i in range(count):
            queries.append(base_queries[i % len(base_queries)])
        return queries
    
    async def run_test(
        self,
        config: Dict,
        on_log: Optional[Callable[[str], None]] = None,
        on_snapshot: Optional[Callable[[Dict], None]] = None
    ) -> Dict:
        """
        Ejecuta el test de estres completo
        
        Args:
            config: Configuracion del test
            on_log: Callback para logs en tiempo real
            on_snapshot: Callback para snapshots de metricas
        
        Returns:
            Dict con resultados del test
        """
        self.is_running = True
        self.should_stop = False
        self.current_stats = {
            "active_queries": 0,
            "completed_queries": 0,
            "failed_queries": 0,
            "latencies": []
        }
        
        # Extraer configuracion
        concurrent_users = config.get("concurrent_users", 5)
        queries_per_user = config.get("queries_per_user", 5)
        duration_seconds = config.get("duration_seconds", 120)
        ramp_up_seconds = config.get("ramp_up_seconds", 0)
        complexity = config.get("query_complexity", "medium")
        model = config.get("model_target", "phi4")
        use_rag = config.get("use_rag", True)
        snapshot_interval = config.get("snapshot_interval_seconds", 5)
        custom_queries = config.get("custom_queries", [])
        
        # Timeout por query = duracion maxima del test (para queries lentas en hardware limitado)
        self.query_timeout_seconds = duration_seconds
        
        total_queries = concurrent_users * queries_per_user
        
        # Preparar queries
        if custom_queries:
            queries = custom_queries * (total_queries // len(custom_queries) + 1)
            queries = queries[:total_queries]
        else:
            queries = self.get_sample_queries(complexity, total_queries)
        
        # Log inicio
        self._log(on_log, f"Iniciando test de estres")
        self._log(on_log, f"  Usuarios concurrentes: {concurrent_users}")
        self._log(on_log, f"  Queries por usuario: {queries_per_user}")
        self._log(on_log, f"  Total queries: {total_queries}")
        self._log(on_log, f"  Modelo: {model}")
        self._log(on_log, f"  RAG: {'Si' if use_rag else 'No'}")
        
        # Hardware info
        hardware_info = self.metrics_collector.get_hardware_info()
        self._log(on_log, f"  CPU: {hardware_info['cpu_model']}")
        self._log(on_log, f"  GPU: {hardware_info['gpu_model']}")
        self._log(on_log, f"  RAM: {hardware_info['ram_total_gb']} GB")
        
        # Iniciar recoleccion de metricas en background
        snapshots = []
        start_time = time.time()
        
        snapshot_task = asyncio.create_task(
            self._collect_snapshots_loop(
                start_time, snapshot_interval, duration_seconds, snapshots, on_snapshot
            )
        )
        
        # Ejecutar queries
        try:
            if ramp_up_seconds > 0:
                await self._run_with_ramp_up(
                    queries, concurrent_users, ramp_up_seconds, model, use_rag, on_log
                )
            else:
                await self._run_concurrent(
                    queries, concurrent_users, model, use_rag, on_log
                )
        except Exception as e:
            self._log(on_log, f"ERROR: {str(e)}")
        finally:
            self.should_stop = True
            self.is_running = False
        
        # Esperar a que termine la recoleccion de snapshots
        await snapshot_task
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calcular resumen
        summary = self._calculate_summary(duration, snapshots)
        
        self._log(on_log, f"Test completado en {duration:.2f} segundos")
        self._log(on_log, f"  Queries exitosas: {self.current_stats['completed_queries']}")
        self._log(on_log, f"  Queries fallidas: {self.current_stats['failed_queries']}")
        
        return {
            "hardware_info": hardware_info,
            "snapshots": snapshots,
            "summary": summary,
            "duration_seconds": round(duration, 2)
        }
    
    async def _collect_snapshots_loop(
        self,
        start_time: float,
        interval: int,
        max_duration: int,
        snapshots: List[Dict],
        on_snapshot: Optional[Callable]
    ):
        """Loop para recolectar snapshots periodicamente"""
        while not self.should_stop:
            elapsed = time.time() - start_time
            
            if max_duration and elapsed > max_duration:
                break
            
            snapshot = self.metrics_collector.collect_snapshot(elapsed)
            
            # Agregar stats de queries
            with self._lock:
                snapshot["performance"] = {
                    "active_queries": self.current_stats["active_queries"],
                    "completed_queries": self.current_stats["completed_queries"],
                    "failed_queries": self.current_stats["failed_queries"],
                    "avg_latency_ms": (
                        statistics.mean(self.current_stats["latencies"]) 
                        if self.current_stats["latencies"] else 0
                    ),
                    "throughput_qps": (
                        self.current_stats["completed_queries"] / elapsed 
                        if elapsed > 0 else 0
                    )
                }
            
            snapshots.append(snapshot)
            
            if on_snapshot:
                on_snapshot(snapshot)
            
            await asyncio.sleep(interval)
    
    async def _run_concurrent(
        self,
        queries: List[str],
        concurrent_users: int,
        model: str,
        use_rag: bool,
        on_log: Optional[Callable]
    ):
        """Ejecuta queries concurrentemente"""
        semaphore = asyncio.Semaphore(concurrent_users)
        
        async def run_query(query: str, index: int):
            async with semaphore:
                if self.should_stop:
                    return
                
                with self._lock:
                    self.current_stats["active_queries"] += 1
                
                self._log(on_log, f"[Query {index+1}] Iniciando: {query[:60]}...")
                start = time.time()
                success = False
                error_msg = None
                
                try:
                    result = await self._send_query(query, model, use_rag)
                    success = result.get("success", False)
                    if not success:
                        error_msg = result.get("error", "Unknown error")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error en query {index}: {e}")
                finally:
                    latency = (time.time() - start) * 1000
                    
                    with self._lock:
                        self.current_stats["active_queries"] -= 1
                        if success:
                            self.current_stats["completed_queries"] += 1
                            self._log(on_log, f"[Query {index+1}] OK - {latency:.0f}ms")
                        else:
                            self.current_stats["failed_queries"] += 1
                            self._log(on_log, f"[Query {index+1}] FALLIDA - {error_msg}")
                        self.current_stats["latencies"].append(latency)
                    
                    total = self.current_stats["completed_queries"] + self.current_stats["failed_queries"]
                    completed = self.current_stats["completed_queries"]
                    failed = self.current_stats["failed_queries"]
                    self._log(on_log, f"Progreso: {total}/{len(queries)} (OK: {completed}, FAIL: {failed})")
        
        tasks = [run_query(q, i) for i, q in enumerate(queries)]
        await asyncio.gather(*tasks)
    
    async def _run_with_ramp_up(
        self,
        queries: List[str],
        max_concurrent: int,
        ramp_up_seconds: int,
        model: str,
        use_rag: bool,
        on_log: Optional[Callable]
    ):
        """Ejecuta queries con escalado gradual"""
        self._log(on_log, f"Ramp-up: escalando a {max_concurrent} usuarios en {ramp_up_seconds}s")
        
        queries_per_user = len(queries) // max_concurrent
        user_delay = ramp_up_seconds / max_concurrent
        
        async def user_session(user_id: int, user_queries: List[str]):
            await asyncio.sleep(user_id * user_delay)
            
            if self.should_stop:
                return
            
            self._log(on_log, f"Usuario {user_id + 1} iniciado")
            
            for query in user_queries:
                if self.should_stop:
                    break
                
                with self._lock:
                    self.current_stats["active_queries"] += 1
                
                start = time.time()
                success = False
                
                try:
                    result = await self._send_query(query, model, use_rag)
                    success = result.get("success", False)
                except Exception as e:
                    logger.error(f"Error usuario {user_id}: {e}")
                finally:
                    latency = (time.time() - start) * 1000
                    
                    with self._lock:
                        self.current_stats["active_queries"] -= 1
                        if success:
                            self.current_stats["completed_queries"] += 1
                        else:
                            self.current_stats["failed_queries"] += 1
                        self.current_stats["latencies"].append(latency)
        
        # Dividir queries entre usuarios
        user_tasks = []
        for i in range(max_concurrent):
            start_idx = i * queries_per_user
            end_idx = start_idx + queries_per_user
            user_queries = queries[start_idx:end_idx]
            user_tasks.append(user_session(i, user_queries))
        
        await asyncio.gather(*user_tasks)
    
    async def _send_query(self, query: str, model: str, use_rag: bool) -> Dict:
        """Envia una query al backend"""
        try:
            # Timeout por query = duracion maxima del test configurada
            timeout_secs = self.query_timeout_seconds
            timeout = aiohttp.ClientTimeout(total=timeout_secs, connect=30, sock_read=timeout_secs)
            
            logger.info(f"Conectando a {self.base_url}/preguntar (timeout: {timeout_secs}s)")
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Formato compatible con endpoint /preguntar
                payload = {
                    "texto": query,
                    "userId": "stress-test-user",
                    "chatToken": "stress-test-session",
                    "history": [],
                    "modelo": model
                }
                
                logger.info(f"Enviando query: {query[:50]}...")
                
                async with session.post(
                    f"{self.base_url}/preguntar",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # El endpoint devuelve {"respuesta": "...", "status": "success|error"}
                        api_status = data.get("status", "unknown")
                        if api_status == "success" and data.get("respuesta"):
                            logger.info(f"Query exitosa, respuesta: {str(data.get('respuesta', ''))[:100]}...")
                            return {"success": True, "response": data}
                        else:
                            logger.warning(f"API devolvio status={api_status}")
                            return {"success": False, "error": f"API status: {api_status}"}
                    else:
                        error_text = await response.text()
                        logger.error(f"HTTP {response.status}: {error_text[:200]}")
                        return {"success": False, "error": f"HTTP {response.status}"}
        except asyncio.TimeoutError:
            logger.error(f"Timeout en query ({self.query_timeout_seconds}s) - URL: {self.base_url}")
            return {"success": False, "error": f"Timeout ({self.query_timeout_seconds}s)"}
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexion: {e}")
            return {"success": False, "error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error inesperado en _send_query: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_summary(self, duration: float, snapshots: List[Dict]) -> Dict:
        """Calcula el resumen estadistico del test"""
        completed = self.current_stats["completed_queries"]
        failed = self.current_stats["failed_queries"]
        total = completed + failed
        latencies = self.current_stats["latencies"]
        
        # Estadisticas de latencia
        timing = {
            "total_duration_seconds": round(duration, 2),
            "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
            "min_latency_ms": round(min(latencies), 2) if latencies else 0,
            "max_latency_ms": round(max(latencies), 2) if latencies else 0,
            "p50_latency_ms": round(statistics.median(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(self._percentile(latencies, 95), 2) if latencies else 0,
            "p99_latency_ms": round(self._percentile(latencies, 99), 2) if latencies else 0
        }
        
        # Estadisticas de recursos (picos y promedios)
        resources_peak = {
            "cpu_max_percent": 0,
            "ram_max_percent": 0,
            "ram_max_mb": 0,
            "gpu_max_percent": 0,
            "vram_max_mb": 0,
            "temperature_max_c": 0
        }
        
        cpu_values = []
        ram_values = []
        gpu_values = []
        temp_values = []
        
        for snap in snapshots:
            sys = snap.get("system", {})
            gpu = snap.get("gpu", {})
            
            cpu = sys.get("cpu_percent", 0)
            ram = sys.get("ram_percent", 0)
            ram_mb = sys.get("ram_used_mb", 0)
            gpu_pct = gpu.get("gpu_percent", 0)
            vram = gpu.get("vram_used_mb", 0)
            temp = gpu.get("temperature_c", 0)
            
            cpu_values.append(cpu)
            ram_values.append(ram)
            gpu_values.append(gpu_pct)
            if temp > 0:
                temp_values.append(temp)
            
            resources_peak["cpu_max_percent"] = max(resources_peak["cpu_max_percent"], cpu)
            resources_peak["ram_max_percent"] = max(resources_peak["ram_max_percent"], ram)
            resources_peak["ram_max_mb"] = max(resources_peak["ram_max_mb"], ram_mb)
            resources_peak["gpu_max_percent"] = max(resources_peak["gpu_max_percent"], gpu_pct)
            resources_peak["vram_max_mb"] = max(resources_peak["vram_max_mb"], vram)
            resources_peak["temperature_max_c"] = max(resources_peak["temperature_max_c"], temp)
        
        resources_avg = {
            "cpu_avg_percent": round(statistics.mean(cpu_values), 1) if cpu_values else 0,
            "ram_avg_percent": round(statistics.mean(ram_values), 1) if ram_values else 0,
            "gpu_avg_percent": round(statistics.mean(gpu_values), 1) if gpu_values else 0,
            "temperature_avg_c": round(statistics.mean(temp_values), 1) if temp_values else 0
        }
        
        return {
            "total_queries": total,
            "successful_queries": completed,
            "failed_queries": failed,
            "success_rate": round((completed / total) * 100, 1) if total > 0 else 0,
            "timing": timing,
            "resources_peak": resources_peak,
            "resources_avg": resources_avg,
            "throughput": {
                "queries_per_second": round(completed / duration, 2) if duration > 0 else 0,
                "queries_per_minute": round((completed / duration) * 60, 2) if duration > 0 else 0
            }
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calcula el percentil de una lista de valores"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _log(self, callback: Optional[Callable], message: str):
        """Envia un mensaje de log"""
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        logger.info(message)
        if callback:
            callback(log_entry)
    
    def stop(self):
        """Detiene el test en ejecucion"""
        self.should_stop = True

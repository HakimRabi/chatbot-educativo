"""
Sistema de Métricas para Chatbot Educativo
==========================================

Módulo para monitorear y analizar el rendimiento del sistema:
- Tiempos de respuesta
- Uso de recursos
- Cuellos de botella
- Estadísticas de modelos LLM
- Preparación para sistema de colas

Autor: Sistema de Métricas v1.0
Fecha: Septiembre 2025
"""

import time
import json
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import psutil
import os

logger = logging.getLogger("metrics")

@dataclass
class RequestMetric:
    """Métrica individual de una request"""
    request_id: str
    endpoint: str
    model_used: str
    start_time: float
    end_time: float
    duration: float
    user_id: str
    question_length: int
    response_length: int
    status: str  # success, error, timeout
    error_details: Optional[str] = None
    vector_search_time: Optional[float] = None
    llm_processing_time: Optional[float] = None
    memory_used_mb: Optional[float] = None
    cpu_percent: Optional[float] = None

@dataclass
class SystemMetric:
    """Métrica del sistema en un momento dado"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    active_requests: int
    queue_size: int = 0  # Para futuro sistema de colas
    model_switches: int = 0

class MetricsCollector:
    """Recolector central de métricas del sistema"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.request_metrics: deque = deque(maxlen=max_history)
        self.system_metrics: deque = deque(maxlen=max_history) 
        self.active_requests: Dict[str, RequestMetric] = {}
        self.model_stats = defaultdict(lambda: {"count": 0, "total_time": 0, "errors": 0})
        self.hourly_stats = defaultdict(lambda: {"requests": 0, "avg_time": 0, "errors": 0})
        
        # Contadores
        self.total_requests = 0
        self.total_errors = 0
        self.model_switches = 0
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        # Iniciar recolección de métricas del sistema
        self.system_monitor_task = None
        self.start_system_monitoring()
        
        logger.info("🔍 Sistema de métricas inicializado")
    
    def start_system_monitoring(self):
        """Inicia el monitoreo continuo del sistema"""
        def monitor_system():
            while True:
                try:
                    # Recopilar métricas del sistema
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    
                    with self.lock:
                        metric = SystemMetric(
                            timestamp=time.time(),
                            cpu_percent=cpu_percent,
                            memory_percent=memory.percent,
                            memory_used_mb=memory.used / (1024 * 1024),
                            active_requests=len(self.active_requests),
                            model_switches=self.model_switches
                        )
                        self.system_metrics.append(metric)
                    
                    time.sleep(30)  # Cada 30 segundos
                except Exception as e:
                    logger.error(f"Error en monitoreo del sistema: {e}")
                    time.sleep(30)
        
        # Ejecutar en thread separado
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
        logger.info("🔄 Monitoreo del sistema iniciado")
    
    def start_request(self, request_id: str, endpoint: str, model_used: str, 
                     user_id: str, question_length: int) -> str:
        """Inicia el tracking de una request"""
        with self.lock:
            start_time = time.time()
            metric = RequestMetric(
                request_id=request_id,
                endpoint=endpoint,
                model_used=model_used,
                start_time=start_time,
                end_time=0,
                duration=0,
                user_id=user_id,
                question_length=question_length,
                response_length=0,
                status="processing",
                memory_used_mb=psutil.virtual_memory().used / (1024 * 1024),
                cpu_percent=psutil.cpu_percent()
            )
            
            self.active_requests[request_id] = metric
            self.total_requests += 1
            
            logger.debug(f"📊 Request iniciada: {request_id} | Modelo: {model_used}")
            return request_id
    
    def end_request(self, request_id: str, status: str = "success", 
                   response_length: int = 0, error_details: str = None,
                   vector_search_time: float = None, llm_processing_time: float = None):
        """Finaliza el tracking de una request"""
        with self.lock:
            if request_id not in self.active_requests:
                logger.warning(f"Request {request_id} no encontrada en métricas activas")
                return
            
            metric = self.active_requests[request_id]
            end_time = time.time()
            
            # Completar métrica
            metric.end_time = end_time
            metric.duration = end_time - metric.start_time
            metric.status = status
            metric.response_length = response_length
            metric.error_details = error_details
            metric.vector_search_time = vector_search_time
            metric.llm_processing_time = llm_processing_time
            
            # Mover a historial
            self.request_metrics.append(metric)
            del self.active_requests[request_id]
            
            # Actualizar estadísticas
            self.model_stats[metric.model_used]["count"] += 1
            self.model_stats[metric.model_used]["total_time"] += metric.duration
            
            if status == "error":
                self.total_errors += 1
                self.model_stats[metric.model_used]["errors"] += 1
            
            # Estadísticas por hora
            hour_key = datetime.fromtimestamp(metric.start_time).strftime("%Y-%m-%d %H")
            self.hourly_stats[hour_key]["requests"] += 1
            self.hourly_stats[hour_key]["avg_time"] = (
                (self.hourly_stats[hour_key]["avg_time"] * (self.hourly_stats[hour_key]["requests"] - 1) + metric.duration) 
                / self.hourly_stats[hour_key]["requests"]
            )
            if status == "error":
                self.hourly_stats[hour_key]["errors"] += 1
            
            logger.info(f"✅ Request completada: {request_id} | {metric.duration:.2f}s | {status}")
    
    def record_model_switch(self, from_model: str, to_model: str):
        """Registra un cambio de modelo"""
        with self.lock:
            self.model_switches += 1
            logger.info(f"🔄 Cambio de modelo registrado: {from_model} → {to_model}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas actuales del sistema"""
        with self.lock:
            now = time.time()
            last_hour_requests = [m for m in self.request_metrics 
                                if now - m.start_time <= 3600]
            last_minute_requests = [m for m in self.request_metrics 
                                  if now - m.start_time <= 60]
            
            # Calcular promedios
            avg_response_time = (
                sum(m.duration for m in self.request_metrics) / len(self.request_metrics)
                if self.request_metrics else 0
            )
            
            avg_response_time_hour = (
                sum(m.duration for m in last_hour_requests) / len(last_hour_requests)
                if last_hour_requests else 0
            )
            
            # Métricas del sistema más recientes
            latest_system_metric = self.system_metrics[-1] if self.system_metrics else None
            
            return {
                "general": {
                    "total_requests": self.total_requests,
                    "total_errors": self.total_errors,
                    "error_rate": (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0,
                    "active_requests": len(self.active_requests),
                    "model_switches": self.model_switches
                },
                "performance": {
                    "avg_response_time_all": round(avg_response_time, 3),
                    "avg_response_time_hour": round(avg_response_time_hour, 3),
                    "requests_last_hour": len(last_hour_requests),
                    "requests_last_minute": len(last_minute_requests),
                    "slowest_request": max([m.duration for m in self.request_metrics], default=0),
                    "fastest_request": min([m.duration for m in self.request_metrics], default=0)
                },
                "system": {
                    "cpu_percent": latest_system_metric.cpu_percent if latest_system_metric else 0,
                    "memory_percent": latest_system_metric.memory_percent if latest_system_metric else 0,
                    "memory_used_mb": latest_system_metric.memory_used_mb if latest_system_metric else 0
                },
                "models": dict(self.model_stats),
                "timestamp": now
            }
    
    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """Analiza cuellos de botella en el sistema"""
        with self.lock:
            if not self.request_metrics:
                return {"analysis": "No hay datos suficientes"}
            
            # Analizar tiempos de respuesta
            durations = [m.duration for m in self.request_metrics]
            slow_requests = [m for m in self.request_metrics if m.duration > 5.0]
            
            # Analizar por modelo
            model_performance = {}
            for model, stats in self.model_stats.items():
                if stats["count"] > 0:
                    model_performance[model] = {
                        "avg_time": stats["total_time"] / stats["count"],
                        "requests": stats["count"],
                        "error_rate": (stats["errors"] / stats["count"]) * 100
                    }
            
            # Analizar errores
            error_requests = [m for m in self.request_metrics if m.status == "error"]
            common_errors = defaultdict(int)
            for req in error_requests:
                if req.error_details:
                    common_errors[req.error_details[:100]] += 1
            
            # Recomendaciones
            recommendations = []
            
            if len(slow_requests) > len(durations) * 0.1:  # Más del 10% de requests lentas
                recommendations.append("❗ Alto número de requests lentas detectadas")
            
            if self.total_errors / max(self.total_requests, 1) > 0.05:  # Más del 5% de errores
                recommendations.append("⚠️ Alta tasa de errores en el sistema")
            
            latest_system = self.system_metrics[-1] if self.system_metrics else None
            if latest_system and latest_system.cpu_percent > 80:
                recommendations.append("🔥 Uso alto de CPU detectado")
            
            if latest_system and latest_system.memory_percent > 85:
                recommendations.append("💾 Uso alto de memoria detectado")
            
            return {
                "performance_analysis": {
                    "total_requests_analyzed": len(durations),
                    "slow_requests_count": len(slow_requests),
                    "slow_requests_percentage": round((len(slow_requests) / len(durations)) * 100, 2),
                    "avg_duration": round(sum(durations) / len(durations), 3),
                    "p95_duration": round(sorted(durations)[int(len(durations) * 0.95)], 3) if durations else 0,
                    "p99_duration": round(sorted(durations)[int(len(durations) * 0.99)], 3) if durations else 0
                },
                "model_analysis": model_performance,
                "error_analysis": {
                    "total_errors": len(error_requests),
                    "error_rate": round((len(error_requests) / len(durations)) * 100, 2),
                    "common_errors": dict(common_errors)
                },
                "recommendations": recommendations,
                "queue_readiness": {
                    "needs_queue": len(slow_requests) > 5 or (latest_system and latest_system.cpu_percent > 70),
                    "estimated_benefit": "Alto" if len(slow_requests) > 10 else "Medio",
                    "priority_suggestions": [
                        "Implementar cola para requests lentas",
                        "Separar procesamiento por tipo de tarea",
                        "Optimizar consultas al vector store"
                    ]
                }
            }
    
    def export_metrics(self, filepath: str):
        """Exporta métricas a archivo JSON"""
        with self.lock:
            export_data = {
                "export_timestamp": time.time(),
                "request_metrics": [asdict(m) for m in self.request_metrics],
                "system_metrics": [asdict(m) for m in self.system_metrics],
                "model_stats": dict(self.model_stats),
                "hourly_stats": dict(self.hourly_stats),
                "summary": self.get_current_stats()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📊 Métricas exportadas a: {filepath}")

# Instancia global del recolector de métricas
metrics_collector = MetricsCollector()

# Funciones de conveniencia para usar en toda la aplicación
def start_request_tracking(endpoint: str, model_used: str, user_id: str, question_length: int) -> str:
    """Inicia tracking de una request"""
    import uuid
    request_id = str(uuid.uuid4())
    return metrics_collector.start_request(request_id, endpoint, model_used, user_id, question_length)

def end_request_tracking(request_id: str, status: str = "success", response_length: int = 0, 
                        error_details: str = None, vector_search_time: float = None, 
                        llm_processing_time: float = None):
    """Finaliza tracking de una request"""
    metrics_collector.end_request(request_id, status, response_length, error_details, 
                                 vector_search_time, llm_processing_time)

def record_model_switch(from_model: str, to_model: str):
    """Registra cambio de modelo"""
    metrics_collector.record_model_switch(from_model, to_model)

def get_metrics_summary():
    """Obtiene resumen de métricas"""
    return metrics_collector.get_current_stats()

def get_bottleneck_analysis():
    """Obtiene análisis de cuellos de botella"""
    return metrics_collector.get_bottleneck_analysis()

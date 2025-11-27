# Metrics Collector
# Recolecta metricas del sistema durante tests de estres

import psutil
import platform
import subprocess
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("diagnostics.metrics")

# Intentar importar GPUtil
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("GPUtil no disponible. Metricas GPU limitadas.")


class MetricsCollector:
    """Recolector de metricas del sistema"""
    
    def __init__(self):
        self.gpu_available = GPU_AVAILABLE
        self._hardware_info = None
    
    def get_hardware_info(self) -> Dict:
        """Obtiene informacion del hardware del sistema"""
        if self._hardware_info:
            return self._hardware_info
        
        info = {
            "cpu_model": self._get_cpu_model(),
            "cpu_cores": psutil.cpu_count(logical=False) or 0,
            "cpu_threads": psutil.cpu_count(logical=True) or 0,
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "os": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version()
        }
        
        # GPU info
        gpu_info = self._get_gpu_info()
        if gpu_info:
            info["gpu_model"] = gpu_info.get("name", "N/A")
            info["gpu_vram_gb"] = gpu_info.get("vram_total_gb", 0)
        else:
            info["gpu_model"] = "No detectada"
            info["gpu_vram_gb"] = 0
        
        self._hardware_info = info
        return info
    
    def _get_cpu_model(self) -> str:
        """Obtiene el modelo del CPU"""
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                )
                cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                winreg.CloseKey(key)
                return cpu_name.strip()
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            return platform.processor() or "Desconocido"
        except Exception as e:
            logger.warning(f"Error obteniendo modelo CPU: {e}")
            return platform.processor() or "Desconocido"
    
    def _get_gpu_info(self) -> Optional[Dict]:
        """Obtiene informacion de la GPU"""
        try:
            if self.gpu_available:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    return {
                        "name": gpu.name,
                        "vram_total_gb": round(gpu.memoryTotal / 1024, 2),
                        "driver": gpu.driver
                    }
            
            # Fallback: nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    return {
                        "name": parts[0].strip(),
                        "vram_total_gb": round(float(parts[1].strip()) / 1024, 2)
                    }
        except Exception as e:
            logger.debug(f"No se pudo obtener info GPU: {e}")
        
        return None
    
    def collect_snapshot(self, elapsed_seconds: float = 0) -> Dict:
        """Recolecta un snapshot de metricas del sistema"""
        snapshot = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "elapsed_seconds": round(elapsed_seconds, 2),
            "system": self._collect_system_metrics(),
            "gpu": self._collect_gpu_metrics()
        }
        return snapshot
    
    def _collect_system_metrics(self) -> Dict:
        """Recolecta metricas del sistema (CPU, RAM)"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Frecuencia CPU
        cpu_freq = psutil.cpu_freq()
        freq_mhz = int(cpu_freq.current) if cpu_freq else 0
        
        return {
            "cpu_percent": round(cpu_percent, 1),
            "cpu_freq_mhz": freq_mhz,
            "ram_percent": round(memory.percent, 1),
            "ram_used_mb": round(memory.used / (1024**2), 0),
            "ram_available_mb": round(memory.available / (1024**2), 0)
        }
    
    def _collect_gpu_metrics(self) -> Dict:
        """Recolecta metricas de GPU"""
        gpu_metrics = {
            "gpu_percent": 0,
            "vram_used_mb": 0,
            "vram_total_mb": 0,
            "temperature_c": 0
        }
        
        try:
            if self.gpu_available:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_metrics["gpu_percent"] = round(gpu.load * 100, 1)
                    gpu_metrics["vram_used_mb"] = round(gpu.memoryUsed, 0)
                    gpu_metrics["vram_total_mb"] = round(gpu.memoryTotal, 0)
                    gpu_metrics["temperature_c"] = round(gpu.temperature, 0) if gpu.temperature else 0
                    return gpu_metrics
            
            # Fallback: nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", 
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 4:
                    gpu_metrics["gpu_percent"] = float(parts[0].strip())
                    gpu_metrics["vram_used_mb"] = float(parts[1].strip())
                    gpu_metrics["vram_total_mb"] = float(parts[2].strip())
                    gpu_metrics["temperature_c"] = float(parts[3].strip())
        except Exception as e:
            logger.debug(f"No se pudieron obtener metricas GPU: {e}")
        
        return gpu_metrics
    
    def get_cpu_temperature(self) -> float:
        """Obtiene temperatura del CPU si esta disponible"""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current:
                                return round(entry.current, 1)
        except Exception as e:
            logger.debug(f"No se pudo obtener temperatura CPU: {e}")
        return 0

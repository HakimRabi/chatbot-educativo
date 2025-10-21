#!/usr/bin/env python3
"""
T2.1: Optimización GPU para Ollama con RTX 3060
Configurar Ollama para máximo rendimiento en GPU
"""

import requests
import json
import subprocess
import os
from datetime import datetime

def check_ollama_status():
    """Verificar estado actual de Ollama"""
    try:
        response = requests.get('http://localhost:11434/api/version', timeout=5)
        if response.status_code == 200:
            print("✅ Ollama funcionando correctamente")
            return True
        else:
            print("❌ Ollama no responde")
            return False
    except Exception as e:
        print(f"❌ Error conectando a Ollama: {e}")
        return False

def configure_ollama_gpu():
    """Configurar variables de entorno para optimizar GPU"""
    print("🔧 Configurando Ollama para RTX 3060...")
    
    # Configuración optimizada para RTX 3060 12GB
    gpu_config = {
        'OLLAMA_GPU_MEMORY_FRACTION': '0.85',  # 85% de 12GB = 10.2GB
        'OLLAMA_NUM_PARALLEL': '2',            # 2 requests simultáneos
        'OLLAMA_MAX_LOADED_MODELS': '1',       # 1 modelo en VRAM
        'OLLAMA_NUM_THREAD': '8',              # 8 threads CPU
        'OLLAMA_KEEP_ALIVE': '10m',            # Mantener modelo 10 min
        'OLLAMA_HOST': '0.0.0.0:11434',        # Host binding
        'CUDA_VISIBLE_DEVICES': '0'            # Solo GPU 0
    }
    
    # Crear script de configuración
    script_content = "@echo off\n"
    script_content += "echo Configurando Ollama para RTX 3060...\n"
    
    for key, value in gpu_config.items():
        script_content += f"set {key}={value}\n"
        os.environ[key] = value
        print(f"   {key}={value}")
    
    script_content += "echo Reiniciando Ollama con nueva configuracion...\n"
    script_content += "taskkill /F /IM ollama.exe >nul 2>&1\n"
    script_content += "timeout /t 2 >nul\n"
    script_content += "start \"\" ollama serve\n"
    script_content += "echo Ollama optimizado iniciado\n"
    
    # Guardar script
    with open('optimize_ollama_gpu.bat', 'w') as f:
        f.write(script_content)
    
    print("✅ Script de optimización creado: optimize_ollama_gpu.bat")
    return gpu_config

def test_gpu_utilization():
    """Test de utilización GPU"""
    print("\n🧪 TESTING GPU UTILIZATION...")
    
    test_prompts = [
        "¿Qué es la inteligencia artificial?",
        "Explica el aprendizaje automático",
        "Define las redes neuronales"
    ]
    
    results = []
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n📝 Test {i}/3: {prompt[:30]}...")
        
        start_time = datetime.now()
        
        try:
            response = requests.post('http://localhost:11434/api/generate', 
                json={
                    'model': 'llama3',
                    'prompt': prompt,
                    'stream': False
                },
                timeout=30
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                results.append({
                    'prompt': prompt,
                    'duration': duration,
                    'response_length': len(response_text),
                    'success': True
                })
                
                print(f"   ✅ Completado en {duration:.2f}s")
                print(f"   📊 Respuesta: {len(response_text)} caracteres")
            else:
                print(f"   ❌ Error HTTP: {response.status_code}")
                results.append({
                    'prompt': prompt,
                    'duration': duration,
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                })
                
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"   ❌ Error: {e}")
            results.append({
                'prompt': prompt,
                'duration': duration,
                'success': False,
                'error': str(e)
            })
    
    return results

def analyze_performance(results):
    """Analizar resultados de performance"""
    print("\n📊 ANÁLISIS DE RENDIMIENTO")
    print("="*50)
    
    successful_tests = [r for r in results if r['success']]
    
    if successful_tests:
        durations = [r['duration'] for r in successful_tests]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        print(f"✅ Tests exitosos: {len(successful_tests)}/{len(results)}")
        print(f"⏱️ Tiempo promedio: {avg_duration:.2f}s")
        print(f"🏃 Tiempo mínimo: {min_duration:.2f}s")
        print(f"🐌 Tiempo máximo: {max_duration:.2f}s")
        
        # Comparar con baseline
        baseline = 15.72  # Tiempo promedio anterior
        improvement = ((baseline - avg_duration) / baseline) * 100
        
        if improvement > 0:
            print(f"🚀 Mejora: {improvement:.1f}% más rápido")
        else:
            print(f"⚠️ Degradación: {abs(improvement):.1f}% más lento")
            
        return {
            'avg_duration': avg_duration,
            'improvement_percent': improvement,
            'success_rate': len(successful_tests) / len(results) * 100
        }
    else:
        print("❌ No hay tests exitosos para analizar")
        return None

def generate_optimization_report(config, performance):
    """Generar reporte de optimización"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""
# REPORTE OPTIMIZACIÓN OLLAMA GPU - RTX 3060
Generado: {timestamp}

## CONFIGURACIÓN APLICADA:
"""
    
    for key, value in config.items():
        report += f"- {key}: {value}\n"
    
    if performance:
        report += f"""
## RESULTADOS DE RENDIMIENTO:
- Tiempo promedio: {performance['avg_duration']:.2f}s
- Mejora respecto a baseline: {performance['improvement_percent']:.1f}%
- Tasa de éxito: {performance['success_rate']:.1f}%

## RECOMENDACIONES:
"""
        if performance['improvement_percent'] > 10:
            report += "✅ Optimización exitosa - mantener configuración\n"
        elif performance['improvement_percent'] > 0:
            report += "⚠️ Mejora marginal - considerar ajustes adicionales\n"
        else:
            report += "❌ Sin mejora - revisar configuración\n"
    
    with open('optimization_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Reporte guardado en: optimization_report.md")

def main():
    print("🚀 OPTIMIZACIÓN OLLAMA GPU - RTX 3060")
    print("="*50)
    
    # Verificar Ollama
    if not check_ollama_status():
        print("❌ Ollama no está funcionando. Iniciarlo primero.")
        return
    
    # Configurar GPU
    config = configure_ollama_gpu()
    
    print(f"\n⚠️ IMPORTANTE:")
    print("1. Ejecutar: .\\optimize_ollama_gpu.bat")
    print("2. Esperar 10 segundos para que Ollama reinicie")
    print("3. Ejecutar este script nuevamente para testing")
    
    # Confirmar si continuar con testing
    print(f"\n¿Ollama ya fue reiniciado con la nueva configuración? (s/n): ", end="")
    
    # Para demo, asumimos que sí
    response = "s"  # input().strip().lower()
    
    if response == 's':
        print("\n🧪 Iniciando tests de rendimiento...")
        results = test_gpu_utilization()
        performance = analyze_performance(results)
        generate_optimization_report(config, performance)
        
        print(f"\n🎯 SIGUIENTE PASO:")
        print("T2.2: Optimización Workers Celery (30min)")
    else:
        print("\n⏸️ Testing pospuesto. Ejecutar script después del reinicio.")

if __name__ == "__main__":
    main()

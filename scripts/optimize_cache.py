#!/usr/bin/env python3
"""
T2.3: Caché Redis avanzado para respuestas IA
Implementar caché inteligente con TTL, invalidación y compresión
"""

import redis
import json
import hashlib
import gzip
import base64
from datetime import datetime, timedelta
import requests
import time

class AdvancedRedisCache:
    """Caché Redis avanzado con compresión y TTL inteligente"""
    
    def __init__(self, host='localhost', port=6379, db=0):
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.compression_threshold = 500  # Comprimir si > 500 chars
        
    def _generate_cache_key(self, prompt, model='llama3'):
        """Generar clave única basada en prompt y modelo"""
        # Normalizar prompt (lowercase, trim)
        normalized = prompt.lower().strip()
        
        # Hash del prompt + modelo
        key_data = f"{normalized}|{model}"
        hash_key = hashlib.md5(key_data.encode()).hexdigest()
        
        return f"chat_cache:{model}:{hash_key}"
    
    def _compress_data(self, data):
        """Comprimir datos si exceden threshold"""
        json_str = json.dumps(data, ensure_ascii=False)
        
        if len(json_str) > self.compression_threshold:
            # Comprimir con gzip
            compressed = gzip.compress(json_str.encode('utf-8'))
            encoded = base64.b64encode(compressed).decode('ascii')
            return {
                'compressed': True,
                'data': encoded
            }
        else:
            return {
                'compressed': False,
                'data': data
            }
    
    def _decompress_data(self, cached_data):
        """Descomprimir datos si están comprimidos"""
        if cached_data.get('compressed', False):
            # Descomprimir
            encoded_data = cached_data['data']
            compressed = base64.b64decode(encoded_data.encode('ascii'))
            json_str = gzip.decompress(compressed).decode('utf-8')
            return json.loads(json_str)
        else:
            return cached_data['data']
    
    def get_cached_response(self, prompt, model='llama3'):
        """Obtener respuesta del caché"""
        try:
            cache_key = self._generate_cache_key(prompt, model)
            cached = self.redis_client.get(cache_key)
            
            if cached:
                cached_data = json.loads(cached)
                response = self._decompress_data(cached_data)
                
                # Agregar metadata de caché
                response['cache_hit'] = True
                response['cached_at'] = cached_data.get('cached_at')
                
                return response
                
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo caché: {e}")
            return None
    
    def cache_response(self, prompt, response, model='llama3', ttl_hours=24):
        """Guardar respuesta en caché"""
        try:
            cache_key = self._generate_cache_key(prompt, model)
            
            # Preparar datos para caché
            cache_data = {
                'response': response,
                'model': model,
                'cached_at': datetime.now().isoformat(),
                'prompt_hash': hashlib.md5(prompt.encode()).hexdigest()[:8]
            }
            
            # Comprimir si es necesario
            compressed_data = self._compress_data(cache_data)
            
            # Agregar metadata de compresión
            final_data = {
                **compressed_data,
                'cached_at': cache_data['cached_at']
            }
            
            # Guardar con TTL
            ttl_seconds = ttl_hours * 3600
            self.redis_client.setex(
                cache_key, 
                ttl_seconds, 
                json.dumps(final_data, ensure_ascii=False)
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando caché: {e}")
            return False
    
    def get_cache_stats(self):
        """Obtener estadísticas del caché"""
        try:
            # Contar claves de caché
            cache_keys = self.redis_client.keys('chat_cache:*')
            
            stats = {
                'total_cached_responses': len(cache_keys),
                'memory_usage_mb': 0,
                'oldest_cache': None,
                'newest_cache': None,
                'compression_ratio': 0
            }
            
            if cache_keys:
                # Calcular estadísticas detalladas
                cache_dates = []
                total_original = 0
                total_compressed = 0
                
                for key in cache_keys[:100]:  # Sample de 100 para performance
                    try:
                        cached_str = self.redis_client.get(key)
                        if cached_str:
                            cached_data = json.loads(cached_str)
                            
                            # Fecha de caché
                            cached_at = cached_data.get('cached_at')
                            if cached_at:
                                cache_dates.append(cached_at)
                            
                            # Estadísticas de compresión
                            if cached_data.get('compressed', False):
                                # Estimar tamaño original vs comprimido
                                compressed_size = len(cached_data['data'])
                                estimated_original = compressed_size * 3  # Estimación
                                total_original += estimated_original
                                total_compressed += compressed_size
                            else:
                                size = len(json.dumps(cached_data['data']))
                                total_original += size
                                total_compressed += size
                                
                    except:
                        continue
                
                if cache_dates:
                    cache_dates.sort()
                    stats['oldest_cache'] = cache_dates[0]
                    stats['newest_cache'] = cache_dates[-1]
                
                if total_original > 0:
                    stats['compression_ratio'] = (1 - total_compressed / total_original) * 100
            
            # Memoria utilizada (aproximada)
            info = self.redis_client.info('memory')
            stats['memory_usage_mb'] = round(info.get('used_memory', 0) / 1024 / 1024, 2)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {}
    
    def clear_expired_cache(self):
        """Limpiar caché expirado manualmente"""
        try:
            cleared = 0
            cache_keys = self.redis_client.keys('chat_cache:*')
            
            for key in cache_keys:
                # Redis maneja TTL automáticamente, pero verificamos
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # Clave expirada
                    self.redis_client.delete(key)
                    cleared += 1
            
            return cleared
            
        except Exception as e:
            print(f"❌ Error limpiando caché: {e}")
            return 0

def test_cache_performance():
    """Test de rendimiento del caché"""
    print("🧪 TESTING CACHÉ REDIS AVANZADO")
    print("="*50)
    
    cache = AdvancedRedisCache()
    
    # Test prompts
    test_prompts = [
        "¿Qué es la inteligencia artificial?",
        "Explica el machine learning",
        "¿Cómo funcionan las redes neuronales?",
        "Define deep learning",
        "¿Qué son los algoritmos genéticos?"
    ]
    
    print("📝 Ejecutando requests SIN caché...")
    
    # Primera ronda - sin caché
    no_cache_times = []
    for i, prompt in enumerate(test_prompts, 1):
        print(f"   Request {i}/5: {prompt[:30]}...")
        
        start_time = time.time()
        
        try:
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
                result_data = None
                
                while wait_time < max_wait and not completed:
                    time.sleep(2)
                    wait_time += 2
                    
                    result_response = requests.get(f'http://localhost:8000/chat/status/{task_id}')
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        if result_data.get('status') == 'completed':
                            completed = True
                            break
                
                duration = time.time() - start_time
                no_cache_times.append(duration)
                
                if completed and result_data:
                    # Guardar en caché
                    ai_response = result_data.get('result', {}).get('response', '')
                    cache.cache_response(prompt, ai_response)
                    print(f"      ✅ {duration:.2f}s (guardado en caché)")
                else:
                    print(f"      ⏰ {duration:.2f}s (timeout)")
            else:
                print(f"      ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    print(f"\n📝 Ejecutando mismos requests CON caché...")
    
    # Segunda ronda - con caché
    cache_times = []
    cache_hits = 0
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"   Request {i}/5: {prompt[:30]}...")
        
        start_time = time.time()
        
        # Intentar obtener del caché
        cached_response = cache.get_cached_response(prompt)
        duration = time.time() - start_time
        
        if cached_response:
            cache_hits += 1
            cache_times.append(duration)
            print(f"      🚀 {duration:.4f}s (CACHE HIT)")
        else:
            print(f"      ❌ Cache miss")
    
    return no_cache_times, cache_times, cache_hits

def analyze_cache_performance(no_cache_times, cache_times, cache_hits):
    """Analizar resultados del caché"""
    print(f"\n📊 ANÁLISIS DE RENDIMIENTO CACHÉ")
    print("="*50)
    
    if no_cache_times and cache_times:
        avg_no_cache = sum(no_cache_times) / len(no_cache_times)
        avg_cache = sum(cache_times) / len(cache_times)
        
        speedup = avg_no_cache / avg_cache if avg_cache > 0 else 0
        time_saved = avg_no_cache - avg_cache
        
        print(f"⏱️ Tiempo promedio SIN caché: {avg_no_cache:.2f}s")
        print(f"🚀 Tiempo promedio CON caché: {avg_cache:.4f}s")
        print(f"📈 Speedup: {speedup:.0f}x más rápido")
        print(f"💾 Tiempo ahorrado: {time_saved:.2f}s por request")
        print(f"🎯 Cache hit rate: {cache_hits}/{len(cache_times)} ({cache_hits/len(cache_times)*100:.1f}%)")
        
        return {
            'speedup': speedup,
            'time_saved': time_saved,
            'hit_rate': cache_hits/len(cache_times)*100
        }
    
    return None

def main():
    print("🚀 OPTIMIZACIÓN CACHÉ REDIS AVANZADO")
    print("="*50)
    
    # Verificar conexión Redis
    try:
        cache = AdvancedRedisCache()
        cache.redis_client.ping()
        print("✅ Redis conectado correctamente")
    except Exception as e:
        print(f"❌ Error conectando a Redis: {e}")
        print("   Asegúrate de que Docker esté corriendo:")
        print("   docker-compose up -d redis")
        return
    
    # Estadísticas iniciales
    initial_stats = cache.get_cache_stats()
    print(f"\n📊 ESTADO INICIAL DEL CACHÉ:")
    print(f"   Respuestas cacheadas: {initial_stats.get('total_cached_responses', 0)}")
    print(f"   Memoria usada: {initial_stats.get('memory_usage_mb', 0)} MB")
    print(f"   Ratio compresión: {initial_stats.get('compression_ratio', 0):.1f}%")
    
    # Test de rendimiento
    print(f"\n¿Ejecutar test de rendimiento? (s/n): ", end="")
    response = "s"  # input().strip().lower()
    
    if response == 's':
        no_cache_times, cache_times, cache_hits = test_cache_performance()
        performance = analyze_cache_performance(no_cache_times, cache_times, cache_hits)
        
        # Estadísticas finales
        final_stats = cache.get_cache_stats()
        print(f"\n📊 ESTADO FINAL DEL CACHÉ:")
        print(f"   Respuestas cacheadas: {final_stats.get('total_cached_responses', 0)}")
        print(f"   Memoria usada: {final_stats.get('memory_usage_mb', 0)} MB")
        print(f"   Ratio compresión: {final_stats.get('compression_ratio', 0):.1f}%")
        
        if performance:
            # Guardar resultados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report = {
                'timestamp': timestamp,
                'performance': performance,
                'cache_stats': final_stats,
                'no_cache_times': no_cache_times,
                'cache_times': cache_times
            }
            
            with open(f'cache_optimization_{timestamp}.json', 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 Resultados guardados: cache_optimization_{timestamp}.json")
            print(f"\n🎯 SIGUIENTE PASO:")
            print("T2.4: Batching simulado (15min)")
    
    else:
        print(f"\n⏸️ Test pospuesto.")

if __name__ == "__main__":
    main()

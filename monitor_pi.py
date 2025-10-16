#!/usr/bin/env python3
"""
Monitor do sistema PenAreia para Raspberry Pi
Monitora performance, temperatura e recursos do sistema
"""

import time
import requests
import json
import psutil
import platform
from datetime import datetime

def get_pi_temperature():
    """Obtém temperatura do Raspberry Pi"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read()) / 1000.0
            return temp
    except:
        return None

def get_system_stats():
    """Coleta estatísticas do sistema"""
    stats = {
        'timestamp': datetime.now().isoformat(),
        'cpu_usage': psutil.cpu_percent(interval=1),
        'memory': {
            'total': psutil.virtual_memory().total // (1024*1024),
            'used': psutil.virtual_memory().used // (1024*1024), 
            'percent': psutil.virtual_memory().percent
        },
        'disk': {
            'total': psutil.disk_usage('/').total // (1024*1024),
            'used': psutil.disk_usage('/').used // (1024*1024),
            'percent': psutil.disk_usage('/').percent
        },
        'temperature': get_pi_temperature(),
        'uptime': time.time() - psutil.boot_time(),
        'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
    }
    return stats

def check_penareia_service():
    """Verifica se o serviço PenAreia está rodando"""
    try:
        response = requests.get('http://localhost:5000/status', timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def display_stats():
    """Exibe estatísticas do sistema"""
    while True:
        print("\n" + "="*60)
        print(f"🍓 MONITOR PENAREIA RASPBERRY PI - {datetime.now().strftime('%H:%M:%S')}")
        print("="*60)
        
        # Estatísticas do sistema
        stats = get_system_stats()
        
        print(f"🖥️  CPU: {stats['cpu_usage']:.1f}%")
        print(f"💾 RAM: {stats['memory']['used']:.0f}MB / {stats['memory']['total']:.0f}MB ({stats['memory']['percent']:.1f}%)")
        print(f"💿 Disco: {stats['disk']['used']:.0f}MB / {stats['disk']['total']:.0f}MB ({stats['disk']['percent']:.1f}%)")
        
        if stats['temperature']:
            temp_emoji = "🌡️" if stats['temperature'] < 70 else "🔥"
            print(f"{temp_emoji} Temperatura: {stats['temperature']:.1f}°C")
        
        if stats['load_avg']:
            print(f"⚡ Load Average: {stats['load_avg'][0]:.2f} {stats['load_avg'][1]:.2f} {stats['load_avg'][2]:.2f}")
        
        # Status do serviço PenAreia
        service_running, service_info = check_penareia_service()
        
        if service_running:
            print("✅ Serviço PenAreia: ONLINE")
            if isinstance(service_info, dict):
                print(f"📹 Fonte: {service_info.get('video_source', 'N/A')}")
                print(f"🎬 FPS: {service_info.get('detected_fps', 'N/A')}")
                print(f"📐 Resolução: {service_info.get('frame_dimensions', 'N/A')}")
                print(f"📊 Buffer: {service_info.get('buffer_frames', 0)} frames")
                
                # Avisos de performance
                if stats['cpu_usage'] > 80:
                    print("⚠️  AVISO: CPU alta!")
                
                if stats['memory']['percent'] > 85:
                    print("⚠️  AVISO: Memória alta!")
                
                if stats['temperature'] and stats['temperature'] > 75:
                    print("🔥 AVISO: Temperatura alta!")
        else:
            print(f"❌ Serviço PenAreia: OFFLINE ({service_info})")
        
        # Aguarda próxima atualização
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Monitor encerrado.")
            break

def save_stats_log():
    """Salva estatísticas em arquivo de log"""
    try:
        stats = get_system_stats()
        service_running, service_info = check_penareia_service()
        
        log_entry = {
            **stats,
            'service_status': 'online' if service_running else 'offline',
            'service_info': service_info if service_running else None
        }
        
        with open('/var/log/penareia_stats.log', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        print(f"Erro ao salvar log: {e}")

if __name__ == "__main__":
    print("🍓 Monitor PenAreia para Raspberry Pi")
    print("Pressione Ctrl+C para sair\n")
    
    try:
        display_stats()
    except KeyboardInterrupt:
        print("\nEncerrando monitor...")
    except Exception as e:
        print(f"Erro: {e}")
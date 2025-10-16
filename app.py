from flask import Flask, request
import threading
import time
import cv2
from collections import deque
import os
from b2sdk.v2 import *
from datetime import datetime
import requests
import ffmpeg
import subprocess
import configparser
import socket
import platform
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil não instalado. Monitoramento de recursos desabilitado.")
import json
import shutil
import signal
import sys
import logging
from pathlib import Path
from queue import Queue, Empty
import sqlite3
import hashlib
try:
    from zeroconf import ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    print("⚠️ Zeroconf não instalado. Instale com: pip install zeroconf")

# === CONFIGURAÇÃO DE LOGGING ROBUSTO ===
# Nota: LOG_PATH será definido após detecção de plataforma
# Por enquanto, usa fallback local
temp_log_path = 'penareia.log'
try:
    os.makedirs(os.path.dirname(temp_log_path) if os.path.dirname(temp_log_path) else '.', exist_ok=True)
except:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(temp_log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === CARREGAMENTO DAS CONFIGURAÇÕES ===
config = configparser.ConfigParser()
config.read('config.ini')

# === CONFIGURAÇÕES GLOBAIS ===
# Converte fonte de vídeo: se for número (webcam), converte para int, senão mantém como string (RTSP)
video_source_str = config.get('VIDEO', 'SOURCE')
try:
    VIDEO_SOURCE = int(video_source_str)  # Webcam (0, 1, 2...)
except ValueError:
    VIDEO_SOURCE = video_source_str  # RTSP ou arquivo de vídeo

BUFFER_SECONDS = config.getint('VIDEO', 'BUFFER_SECONDS')
SAVE_SECONDS = config.getint('VIDEO', 'SAVE_SECONDS')

# === CONFIGURAÇÕES ESPECÍFICAS DO RASPBERRY PI ===
FORCE_FPS = config.getint('VIDEO', 'FORCE_FPS', fallback=24)
MAX_WIDTH = config.getint('VIDEO', 'MAX_WIDTH', fallback=1280)
MAX_HEIGHT = config.getint('VIDEO', 'MAX_HEIGHT', fallback=720)

# === CONFIGURAÇÕES DO SERVIDOR ===
ENABLE_MDNS = config.getboolean('SERVER', 'ENABLE_MDNS', fallback=True)
SERVICE_NAME = config.get('SERVER', 'SERVICE_NAME', fallback='PenAreia-Camera')
USE_THREADS = config.getboolean('SERVER', 'THREADS', fallback=True)

# === CONFIGURAÇÕES DE CODIFICAÇÃO OTIMIZADAS ===
ENCODING_TUNE = config.get('VIDEO_ENCODING', 'TUNE', fallback='zerolatency')
ENCODING_THREADS = config.getint('VIDEO_ENCODING', 'THREADS', fallback=4)
USE_GPU = config.getboolean('VIDEO_ENCODING', 'USE_GPU', fallback=False)

# === CONFIGURAÇÃO DO WEBHOOK ===
WEBHOOK_URL = config.get('WEBHOOK', 'URL')

# === CONFIGURAÇÕES DO BACKBLAZE B2 ===
B2_KEY_ID = config.get('BACKBLAZE_B2', 'KEY_ID')
B2_APPLICATION_KEY = config.get('BACKBLAZE_B2', 'APPLICATION_KEY')
B2_BUCKET_NAME = config.get('BACKBLAZE_B2', 'BUCKET_NAME')

# === CONFIGURAÇÕES DO SERVIDOR ===
SERVER_HOST = config.get('SERVER', 'HOST')
SERVER_PORT = config.getint('SERVER', 'PORT')
SERVER_DEBUG = config.getboolean('SERVER', 'DEBUG')

# === CONFIGURAÇÕES DE CODIFICAÇÃO ===
VIDEO_CODEC = config.get('VIDEO_ENCODING', 'CODEC')
AUDIO_CODEC = config.get('VIDEO_ENCODING', 'AUDIO_CODEC')
ENCODING_PRESET = config.get('VIDEO_ENCODING', 'PRESET')
ENCODING_CRF = config.getint('VIDEO_ENCODING', 'CRF')
PIXEL_FORMAT = config.get('VIDEO_ENCODING', 'PIXEL_FORMAT')

# === DETECÇÃO DE PLATAFORMA ===
IS_RASPBERRY_PI = 'arm' in platform.machine().lower() or 'aarch64' in platform.machine().lower()
IS_ARM = 'arm' in platform.processor().lower() or 'aarch64' in platform.processor().lower()

print(f"🔍 Plataforma detectada: {platform.system()} {platform.machine()}")
if IS_RASPBERRY_PI or IS_ARM:
    print("🍓 Raspberry Pi/ARM detectado - aplicando otimizações")

# === PATHS ESPECÍFICOS POR PLATAFORMA ===
if IS_RASPBERRY_PI or IS_ARM:
    DB_PATH = '/var/lib/penareia/queue.db'
    LOG_PATH = '/var/log/penareia.log'
    FFMPEG_CMD = '/usr/bin/ffmpeg'
else:
    # Windows/Desktop - usa pastas locais
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'data', 'queue.db')
    LOG_PATH = os.path.join(BASE_DIR, 'logs', 'penareia.log')
    FFMPEG_CMD = shutil.which('ffmpeg') or 'ffmpeg'
    
    # Cria diretórios locais no Windows
    for directory in [os.path.dirname(DB_PATH), os.path.dirname(LOG_PATH)]:
        if directory:
            os.makedirs(directory, exist_ok=True)

print(f"💾 Banco de dados: {DB_PATH}")
print(f"📝 Log: {LOG_PATH}")
print(f"🎬 FFmpeg: {FFMPEG_CMD}")

# === VARIÁVEIS GLOBAIS PARA PROPRIEDADES DETECTADAS ===
# Força 24 FPS em todas as plataformas para reduzir uso de CPU
detected_fps = FORCE_FPS  # 24 FPS sempre
frame_width = 640
frame_height = 480

# === BUFFER CIRCULAR ===
frame_buffer = None
buffer_lock = threading.Lock()

# === SISTEMA DE FAILOVER E QUEUE ===
upload_queue = Queue(maxsize=100)
failed_uploads = []
upload_thread_running = True
watchdog_enabled = True
last_heartbeat = time.time()
system_healthy = True

# === FUNÇÃO PARA INICIALIZAR BANCO DE DADOS ===
def init_database():
    """Inicializa o banco de dados SQLite para queue persistente"""
    try:
        # Cria diretório se não existir
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"📁 Diretório criado: {db_dir}")
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # 10 segundos de timeout
        cursor = conn.cursor()
        
        # Tabela de queue de uploads
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS upload_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            local_path TEXT NOT NULL,
            remote_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            file_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Tabela de status do sistema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_status (
            id INTEGER PRIMARY KEY,
            last_heartbeat TIMESTAMP,
            uptime_seconds INTEGER DEFAULT 0,
            captures_total INTEGER DEFAULT 0,
            uploads_success INTEGER DEFAULT 0,
            uploads_failed INTEGER DEFAULT 0,
            crashes INTEGER DEFAULT 0,
            total_uploads INTEGER DEFAULT 0
        )
        ''')
        
        # Insere registro inicial se não existir
        cursor.execute('SELECT COUNT(*) FROM system_status WHERE id = 1')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
            INSERT INTO system_status (id, last_heartbeat, uptime_seconds)
            VALUES (1, ?, 0)
            ''', (datetime.now(),))
        
        conn.commit()
        conn.close()
        logger.info("✅ Banco de dados inicializado")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

# === FUNÇÃO PARA ATUALIZAR HEARTBEAT DO SISTEMA ===
def update_heartbeat():
    """Atualiza o heartbeat do sistema para monitoramento"""
    global last_heartbeat, system_healthy
    
    try:
        last_heartbeat = time.time()
        system_healthy = True
        
        # Atualiza no banco de dados
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE system_status 
            SET last_heartbeat = ?, uptime_seconds = uptime_seconds + 1
            WHERE id = 1
            ''', (datetime.now(),))
            conn.commit()
            conn.close()
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar heartbeat: {e}")
        system_healthy = False

# === FUNÇÃO WATCHDOG PARA MONITORAMENTO DO SISTEMA ===
def watchdog_monitor():
    """Monitora a saúde do sistema e reinicia se necessário"""
    global watchdog_enabled, system_healthy, last_heartbeat
    
    logger.info("🐕 Watchdog iniciado")
    
    while watchdog_enabled:
        try:
            # Verifica se heartbeat está atualizado (último minuto)
            time_since_heartbeat = time.time() - last_heartbeat
            
            if time_since_heartbeat > 60:
                logger.error(f"🚨 Heartbeat não atualizado há {time_since_heartbeat:.0f}s!")
                system_healthy = False
                
                # Registra problema no banco
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=10.0)
                    cursor = conn.cursor()
                    cursor.execute('UPDATE system_status SET crashes = crashes + 1 WHERE id = 1')
                    conn.commit()
                    conn.close()
                except:
                    pass
                
                # Se estiver no Raspberry Pi com systemd, deixa o systemd reiniciar
                if IS_RASPBERRY_PI or IS_ARM:
                    logger.error("💀 Sistema com falha crítica - aguardando restart do systemd")
                    os._exit(1)  # Exit para trigger do systemd restart
            else:
                system_healthy = True
            
            # Verifica recursos do sistema (se psutil disponível)
            if PSUTIL_AVAILABLE:
                try:
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    
                    logger.debug(f"📊 CPU: {cpu_percent:.1f}% | RAM: {memory.percent:.1f}% | Heartbeat: {time_since_heartbeat:.0f}s atrás")
                    
                    # Alerta se CPU muito alta
                    if cpu_percent > 90:
                        logger.warning(f"⚠️ CPU alta: {cpu_percent:.1f}%")
                    
                    # Alerta se memória muito alta
                    if memory.percent > 90:
                        logger.warning(f"⚠️ Memória alta: {memory.percent:.1f}%")
                        
                except Exception as e:
                    logger.debug(f"Erro no monitoramento de recursos: {e}")
            else:
                logger.debug(f"📊 Heartbeat: {time_since_heartbeat:.0f}s atrás (psutil não disponível)")
            
            # Limpeza periódica de vídeos antigos (a cada hora)
            current_time = time.time()
            if hasattr(watchdog_monitor, 'last_cleanup'):
                if current_time - watchdog_monitor.last_cleanup > 3600:  # 1 hora
                    cleanup_old_videos(max_age_hours=24)
                    watchdog_monitor.last_cleanup = current_time
            else:
                watchdog_monitor.last_cleanup = current_time
            
            # Aguarda próxima verificação
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"❌ Erro no watchdog: {e}")
            time.sleep(30)
    
    logger.info("🐕 Watchdog encerrado")

# === FUNÇÃO PARA OTIMIZAR CÂMERA NO RASPBERRY PI ===
def optimize_camera_for_pi(cap):
    """Aplica otimizações específicas para Raspberry Pi"""
    if not (IS_RASPBERRY_PI or IS_ARM):
        return cap
        
    print("🍓 Aplicando otimizações para Raspberry Pi...")
    
    # Configurações específicas do Raspberry Pi
    cap.set(cv2.CAP_PROP_FPS, FORCE_FPS)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, min(MAX_WIDTH, 1280))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, min(MAX_HEIGHT, 720))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer mínimo para reduzir latência
    
    # Otimizações de performance
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    
    return cap

# === FUNÇÃO PARA VERIFICAR SE FFMPEG ESTÁ INSTALADO ===
def check_ffmpeg():
    """Verifica se o FFmpeg está instalado no sistema"""
    try:
        # Tenta usar o path global detectado
        cmd = FFMPEG_CMD
        subprocess.run([cmd, '-version'], capture_output=True, check=True)
        print(f"✅ FFmpeg encontrado: {cmd}")
        return True, cmd
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Tenta encontrar no PATH como fallback
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            try:
                subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
                print(f"✅ FFmpeg encontrado: {ffmpeg_path}")
                return True, ffmpeg_path
            except:
                pass
        
        print("❌ FFmpeg não encontrado! Instale o FFmpeg para continuar.")
        if IS_RASPBERRY_PI or IS_ARM:
            print("📝 Para Raspberry Pi: sudo apt update && sudo apt install ffmpeg")
        else:
            print("📝 Para Windows: Baixe em https://ffmpeg.org/download.html")
        return False, None

# === FUNÇÃO PARA CONVERTER VÍDEO COM FFMPEG ===
def convert_video_with_ffmpeg(input_path, output_path):
    """Converte vídeo para formato compatível com navegadores usando FFmpeg"""
    try:
        print(f"Convertendo vídeo com FFmpeg: {input_path} -> {output_path}")
        
        # Configuração do FFmpeg otimizada para Raspberry Pi
        stream = ffmpeg.input(input_path)
        
        # Configurações base
        output_options = {
            'vcodec': VIDEO_CODEC,
            'acodec': AUDIO_CODEC, 
            'preset': ENCODING_PRESET,
            'crf': ENCODING_CRF,
            'pix_fmt': PIXEL_FORMAT,
            'movflags': 'faststart',
            'r': detected_fps,
            's': f'{frame_width}x{frame_height}',
            'f': 'mp4'
        }
        
        # Otimizações específicas para ARM/Raspberry Pi
        if IS_RASPBERRY_PI or IS_ARM:
            output_options.update({
                'tune': ENCODING_TUNE,
                'threads': ENCODING_THREADS,
                'g': detected_fps * 2,  # Keyframe interval
                'sc_threshold': '0',     # Disable scene change detection
                'profile:v': 'baseline', # Perfil mais leve
                'level': '3.1'           # Nível compatível
            })
            
            # Tenta usar hardware acceleration se disponível
            if USE_GPU:
                try:
                    output_options['vcodec'] = 'h264_v4l2m2m'  # Hardware encoder do Pi
                except:
                    pass  # Fallback para software encoder
        
        stream = ffmpeg.output(stream, output_path, **output_options)
        
        # Executa a conversão
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        print(f"✅ Conversão concluída: {output_path}")
        return True, "Conversão bem-sucedida"
        
    except ffmpeg.Error as e:
        error_msg = f"Erro no FFmpeg: {e}"
        print(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado na conversão: {e}"
        print(f"❌ {error_msg}")
        return False, error_msg

# === FUNÇÃO ALTERNATIVA COM SUBPROCESS ===
def convert_video_subprocess(input_path, output_path):
    """Converte vídeo usando subprocess (alternativa se ffmpeg-python falhar)"""
    try:
        print(f"Convertendo vídeo (subprocess): {input_path} -> {output_path}")
        
        # Usa comando FFmpeg global detectado
        ffmpeg_cmd = FFMPEG_CMD
        
        cmd = [
            ffmpeg_cmd,
            '-i', input_path,
            '-c:v', VIDEO_CODEC,
            '-preset', ENCODING_PRESET, 
            '-crf', str(ENCODING_CRF),
            '-c:a', AUDIO_CODEC,
            '-pix_fmt', PIXEL_FORMAT,
            '-movflags', 'faststart',
            '-y'
        ]
        
        # Otimizações para ARM/Raspberry Pi
        if IS_RASPBERRY_PI or IS_ARM:
            cmd.extend([
                '-tune', ENCODING_TUNE,
                '-threads', str(ENCODING_THREADS),
                '-g', str(detected_fps * 2),
                '-sc_threshold', '0',
                '-profile:v', 'baseline',
                '-level', '3.1'
            ])
            
            # Hardware acceleration se disponível
            if USE_GPU:
                try:
                    cmd[cmd.index('-c:v') + 1] = 'h264_v4l2m2m'
                except:
                    pass
        
        cmd.append(output_path)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Conversão subprocess concluída: {output_path}")
            return True, "Conversão bem-sucedida"
        else:
            error_msg = f"Erro subprocess FFmpeg: {result.stderr}"
            print(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Erro no subprocess: {e}"
        print(f"❌ {error_msg}")
        return False, error_msg

# === FUNÇÃO PARA ENVIAR DADOS PARA O WEBHOOK ASSÍNCRONO ===
def send_to_webhook_async(arquivo, url, data_hora):
    """Envia dados para webhook em thread separada"""
    def _send():
        try:
            success, result = send_to_webhook(arquivo, url, data_hora)
            if success:
                logger.info(f"✅ Webhook enviado: {arquivo}")
            else:
                logger.error(f"❌ Falha no webhook: {result}")
        except Exception as e:
            logger.error(f"❌ Erro no webhook assíncrono: {e}")
    
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()

def send_to_webhook(arquivo, url, data_hora):
    """Envia os dados do vídeo para o webhook do site"""
    try:
        # Dados em formato form-data (como esperado pelo webhook PHP)
        data = {
            'arquivo': arquivo,
            'url': url,
            'data_hora': data_hora
        }
        
        # Headers para simular uma requisição de navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
        
        print(f"Enviando dados para webhook: {data}")
        
        # Envia a requisição POST
        response = requests.post(
            WEBHOOK_URL, 
            data=data,  # Usando data= para form-data
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Webhook respondeu com sucesso: {result}")
                return True, result
            except:
                print(f"Webhook respondeu com sucesso: {response.text}")
                return True, response.text
        else:
            print(f"Webhook retornou erro {response.status_code}: {response.text}")
            return False, f"Erro HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        print("Timeout ao enviar para webhook")
        return False, "Timeout na requisição"
    except requests.exceptions.ConnectionError:
        print("Erro de conexão ao enviar para webhook")
        return False, "Erro de conexão"
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar para webhook: {e}")
        return False, str(e)
    except Exception as e:
        print(f"Erro inesperado no webhook: {e}")
        return False, str(e)

# === FUNÇÃO PARA VERIFICAR ESPAÇO EM DISCO ===
def check_disk_space(min_gb=2):
    """Verifica se há espaço suficiente em disco"""
    try:
        # Detecta path correto para verificação
        if IS_RASPBERRY_PI or IS_ARM:
            check_path = '/var/lib/penareia' if os.path.exists('/var/lib/penareia') else '/'
        else:
            check_path = '.'
        
        stat = shutil.disk_usage(check_path)
        free_gb = stat.free / (1024**3)
        
        if free_gb < min_gb:
            logger.error(f"⚠️ Pouco espaço em disco: {free_gb:.2f} GB disponíveis (mínimo: {min_gb} GB)")
            return False
            
        logger.debug(f"💾 Espaço em disco: {free_gb:.2f} GB disponíveis")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível verificar espaço em disco: {e}")
        return True  # Assume OK se não conseguir verificar

# === FUNÇÃO PARA LIMPEZA DE VÍDEOS ANTIGOS ===
def cleanup_old_videos(max_age_hours=24, force=False):
    """Remove vídeos locais com mais de X horas"""
    try:
        removed_count = 0
        freed_space = 0
        
        for folder in ['videos/temp', 'videos/final']:
            if not os.path.exists(folder):
                continue
                
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                
                if not os.path.isfile(filepath):
                    continue
                
                # Verifica idade do arquivo
                age_seconds = time.time() - os.path.getmtime(filepath)
                age_hours = age_seconds / 3600
                
                should_remove = force or (age_hours > max_age_hours)
                
                if should_remove:
                    try:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        removed_count += 1
                        freed_space += file_size
                        logger.info(f"🗑️ Vídeo removido: {filename} (idade: {age_hours:.1f}h)")
                    except Exception as e:
                        logger.warning(f"⚠️ Não foi possível remover {filename}: {e}")
        
        if removed_count > 0:
            freed_mb = freed_space / (1024**2)
            logger.info(f"✅ Limpeza concluída: {removed_count} arquivo(s), {freed_mb:.2f} MB liberados")
        
        return removed_count
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza de vídeos: {e}")
        return 0

# === INICIALIZAÇÃO DO BACKBLAZE B2 ===
def init_b2():
    """Inicializa a conexão com o Backblaze B2"""
    try:
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
        bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
        print("Conectado ao Backblaze B2 com sucesso!")
        return bucket
    except Exception as e:
        print(f"Erro ao conectar no Backblaze B2: {e}")
        return None

# === SISTEMA DE QUEUE PARA UPLOADS ===
def add_to_upload_queue(local_path, remote_name, priority=False):
    """Adiciona arquivo à queue de upload com retry"""
    try:
        # Calcula hash do arquivo para verificação de integridade
        file_hash = hashlib.md5()
        with open(local_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                file_hash.update(chunk)
        
        upload_item = {
            'filename': os.path.basename(local_path),
            'local_path': local_path,
            'remote_path': remote_name,
            'timestamp': datetime.now(),
            'attempts': 0,
            'max_attempts': 5,
            'file_hash': file_hash.hexdigest(),
            'priority': priority
        }
        
        # Adiciona ao banco de dados
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO upload_queue (filename, local_path, remote_path, timestamp, file_hash)
        VALUES (?, ?, ?, ?, ?)
        ''', (upload_item['filename'], upload_item['local_path'], 
              upload_item['remote_path'], upload_item['timestamp'], 
              upload_item['file_hash']))
        conn.commit()
        conn.close()
        
        # Adiciona à queue em memória
        if priority:
            # Para uploads prioritários, adiciona no início
            upload_queue.put(upload_item)
        else:
            upload_queue.put(upload_item)
        
        logger.info(f"📋 Arquivo adicionado à queue: {remote_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar à queue: {e}")
        return False

# === FUNÇÃO PARA MARCAR UPLOAD COMO CONCLUÍDO ===
def mark_upload_completed(upload_item, url):
    """Marca upload como concluído no banco de dados"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE upload_queue 
        SET status = 'completed', updated_at = ?, error_message = ?
        WHERE filename = ? AND local_path = ?
        ''', (datetime.now(), url, upload_item['filename'], upload_item['local_path']))
        
        # Atualiza estatísticas
        cursor.execute('UPDATE system_status SET uploads_success = uploads_success + 1 WHERE id = 1')
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Upload marcado como concluído: {upload_item['filename']}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao marcar upload como concluído: {e}")

# === FUNÇÃO PARA MARCAR UPLOAD COMO FALHADO ===
def mark_upload_failed(upload_item, error_message):
    """Marca upload como falhado no banco de dados"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE upload_queue 
        SET status = 'failed', updated_at = ?, error_message = ?
        WHERE filename = ? AND local_path = ?
        ''', (datetime.now(), error_message, upload_item['filename'], upload_item['local_path']))
        
        # Atualiza estatísticas
        cursor.execute('UPDATE system_status SET uploads_failed = uploads_failed + 1 WHERE id = 1')
        
        conn.commit()
        conn.close()
        logger.warning(f"⚠️ Upload marcado como falhado: {upload_item['filename']} - {error_message}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao marcar upload como falhado: {e}")

# === FUNÇÃO PARA UPLOAD COM RETRY AUTOMÁTICO ===
def upload_to_b2_with_retry(upload_item):
    """Faz upload para B2 com retry automático e exponential backoff"""
    max_retries = 3
    base_delay = 2  # segundos
    
    for attempt in range(max_retries):
        try:
            # Tenta fazer upload
            bucket = init_b2()
            if not bucket:
                raise Exception("Não foi possível conectar ao Backblaze B2")
            
            # Faz upload do arquivo
            uploaded_file = bucket.upload_local_file(
                local_file=upload_item['local_path'],
                file_name=upload_item['remote_path']
            )
            
            # Gera URL pública
            file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{upload_item['remote_path']}"
            
            logger.info(f"✅ Upload B2 concluído (tentativa {attempt + 1}): {file_url}")
            return True, file_url
            
        except Exception as e:
            logger.warning(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
            
            if attempt < max_retries - 1:
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                logger.info(f"🔄 Aguardando {delay}s antes de nova tentativa...")
                time.sleep(delay)
            else:
                # Última tentativa falhou
                error_message = f"Falha após {max_retries} tentativas: {str(e)}"
                logger.error(f"❌ {error_message}")
                return False, error_message
    
    return False, "Número máximo de tentativas excedido"

def process_upload_queue():
    """Thread para processar queue de uploads com retry automático"""
    global upload_thread_running
    
    # Recupera itens pendentes do banco na inicialização
    recover_pending_uploads()
    
    while upload_thread_running:
        try:
            # Pega próximo item da queue (timeout 5s)
            upload_item = upload_queue.get(timeout=5)
            
            logger.info(f"🔄 Processando upload: {upload_item['filename']}")
            
            # Verifica se arquivo ainda existe
            if not os.path.exists(upload_item['local_path']):
                logger.warning(f"⚠️ Arquivo não encontrado: {upload_item['local_path']}")
                mark_upload_failed(upload_item, "Arquivo não encontrado")
                continue
            
            # Verifica integridade do arquivo
            current_hash = hashlib.md5()
            with open(upload_item['local_path'], 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    current_hash.update(chunk)
            
            if current_hash.hexdigest() != upload_item['file_hash']:
                logger.error(f"❌ Integridade comprometida: {upload_item['filename']}")
                mark_upload_failed(upload_item, "Integridade comprometida")
                continue
            
            # Tenta fazer upload
            success, result = upload_to_b2_with_retry(upload_item)
            
            if success:
                logger.info(f"✅ Upload concluído: {upload_item['filename']}")
                # Remove arquivo local após upload bem-sucedido
                try:
                    os.remove(upload_item['local_path'])
                    logger.info(f"🗑️ Arquivo local removido: {upload_item['local_path']}")
                except:
                    pass
                
                # Marca como concluído no banco
                mark_upload_completed(upload_item, result)
                
                # Envia para webhook
                send_to_webhook_async(upload_item['filename'], result, 
                                    upload_item['timestamp'].strftime('%Y-%m-%d %H:%M:%S'))
            else:
                logger.error(f"❌ Falha no upload: {upload_item['filename']} - {result}")
                
                # Incrementa tentativas
                upload_item['attempts'] += 1
                
                if upload_item['attempts'] >= upload_item['max_attempts']:
                    logger.error(f"🚫 Máximo de tentativas excedido: {upload_item['filename']}")
                    mark_upload_failed(upload_item, result)
                else:
                    # Recoloca na queue para nova tentativa (com delay)
                    logger.info(f"🔄 Reagendando upload ({upload_item['attempts']}/{upload_item['max_attempts']}): {upload_item['filename']}")
                    time.sleep(30)  # Aguarda 30s antes de tentar novamente
                    upload_queue.put(upload_item)
            
            update_heartbeat()
            
        except Empty:
            # Timeout normal, continua loop
            continue
        except Exception as e:
            logger.error(f"❌ Erro no processamento da queue: {e}")
            time.sleep(5)

def recover_pending_uploads():
    """Recupera uploads pendentes do banco na inicialização"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM upload_queue WHERE status = 'pending'")
        pending = cursor.fetchall()
        conn.close()
        
        for row in pending:
            upload_item = {
                'id': row[0],
                'filename': row[1],
                'local_path': row[2], 
                'remote_path': row[3],
                'timestamp': datetime.fromisoformat(row[4]),
                'attempts': row[5],
                'max_attempts': row[6],
                'file_hash': row[9]
            }
            
            if os.path.exists(upload_item['local_path']):
                upload_queue.put(upload_item)
                logger.info(f"📋 Recuperado upload pendente: {upload_item['filename']}")
            else:
                mark_upload_failed(upload_item, "Arquivo não encontrado na recuperação")
                
    except Exception as e:
        logger.error(f"❌ Erro ao recuperar uploads pendentes: {e}")

def mark_upload_completed(upload_item, url):
    """Marca upload como concluído no banco"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE upload_queue SET status = 'completed', error_message = ?
        WHERE filename = ? AND local_path = ?
        ''', (url, upload_item['filename'], upload_item['local_path']))
        
        cursor.execute('UPDATE system_status SET total_uploads = total_uploads + 1 WHERE id = 1')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Erro ao marcar upload como concluído: {e}")

def mark_upload_failed(upload_item, error_msg):
    """Marca upload como falhou no banco"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE upload_queue SET status = 'failed', error_message = ?
        WHERE filename = ? AND local_path = ?
        ''', (error_msg, upload_item['filename'], upload_item['local_path']))
        
        cursor.execute('UPDATE system_status SET failed_uploads = failed_uploads + 1 WHERE id = 1')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Erro ao marcar upload como falhado: {e}")

# === FUNÇÃO DE UPLOAD PARA B2 COM RETRY ===
def upload_to_b2_with_retry(upload_item):
    """Faz upload com retry automático"""
    for attempt in range(3):  # 3 tentativas imediatas
        try:
            bucket = init_b2()
            if not bucket:
                if attempt == 2:  # Última tentativa
                    return False, "Falha na conexão com B2 após 3 tentativas"
                time.sleep(5)
                continue
            
            logger.info(f"🔄 Upload tentativa {attempt + 1}: {upload_item['filename']}")
            
            bucket.upload_local_file(
                local_file=upload_item['local_path'],
                file_name=upload_item['remote_path']
            )
            
            # Gera URL público do arquivo
            file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{upload_item['remote_path']}"
            return True, file_url
            
        except Exception as e:
            logger.warning(f"⚠️ Tentativa {attempt + 1} falhou: {e}")
            if attempt == 2:  # Última tentativa
                return False, str(e)
            time.sleep(5)  # Aguarda 5s entre tentativas
    
    return False, "Todas as tentativas falharam"

# === FUNÇÃO LEGADA MANTIDA PARA COMPATIBILIDADE ===
def upload_to_b2(local_file_path, remote_file_name):
    """Função legada - agora usa o sistema de queue"""
    return add_to_upload_queue(local_file_path, remote_file_name, priority=True)

# === FUNÇÃO DE CAPTURA DE FRAMES ===
def capture_frames():
    global frame_buffer, detected_fps, frame_width, frame_height
    
    reconnect_count = 0
    max_reconnects = 10
    
    while reconnect_count < max_reconnects:
        try:
            logger.info(f"🎥 Iniciando captura (tentativa {reconnect_count + 1})")
            
            cap = cv2.VideoCapture(VIDEO_SOURCE)
            if not cap.isOpened():
                logger.error(f"❌ Erro ao conectar na fonte de vídeo: {VIDEO_SOURCE}")
                reconnect_count += 1
                time.sleep(5)
                continue

            # APLICA OTIMIZAÇÕES PARA RASPBERRY PI
            cap = optimize_camera_for_pi(cap)

            # DETECÇÃO AUTOMÁTICA DAS PROPRIEDADES DA CÂMERA
            detected_fps = cap.get(cv2.CAP_PROP_FPS) or FORCE_FPS
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Força 24 FPS em todas as plataformas para economia de CPU
            detected_fps = FORCE_FPS  # 24 FPS sempre
            
            # Limita resolução se especificado
            if IS_RASPBERRY_PI or IS_ARM:
                frame_width = min(frame_width, MAX_WIDTH)
                frame_height = min(frame_height, MAX_HEIGHT)

            if detected_fps == 0 or detected_fps is None:
                logger.warning("⚠️ Câmera não informou FPS. Usando valor forçado.")
                detected_fps = FORCE_FPS

            # INICIALIZAÇÃO DINÂMICA DO BUFFER COM BASE NO FPS REAL
            buffer_size = int(BUFFER_SECONDS * detected_fps)
            frame_buffer = deque(maxlen=buffer_size)

            logger.info(f"✅ Conectado à câmera: {frame_width}x{frame_height} @ {detected_fps:.2f} FPS. Buffer de {BUFFER_SECONDS}s.")
            
            # Reset contador de reconexões
            reconnect_count = 0
            consecutive_failures = 0
            
            while True:
                try:
                    ret, frame = cap.read()
                    if not ret:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Falha na leitura do frame ({consecutive_failures})")
                        
                        if consecutive_failures > 10:
                            logger.error("❌ Muitas falhas consecutivas, reconectando...")
                            break
                        
                        time.sleep(0.1)
                        continue
                    
                    # Reset contador de falhas
                    consecutive_failures = 0
                    
                    with buffer_lock:
                        frame_buffer.append(frame)
                    
                    # Atualiza heartbeat periodicamente
                    if len(frame_buffer) % (detected_fps * 5) == 0:  # A cada 5 segundos
                        update_heartbeat()
                        
                except KeyboardInterrupt:
                    logger.info("🛑 Captura interrompida pelo usuário")
                    cap.release()
                    return
                except Exception as e:
                    logger.error(f"❌ Erro na captura: {e}")
                    break
            
            cap.release()
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização da captura: {e}")
            
        reconnect_count += 1
        logger.info(f"🔄 Tentando reconectar em 5 segundos... ({reconnect_count}/{max_reconnects})")
        time.sleep(5)
    
    logger.error(f"🚫 Máximo de tentativas de reconexão excedido ({max_reconnects})")
    # Em caso de falha total, mantém o sistema rodando sem captura
    while True:
        time.sleep(30)
        update_heartbeat()

# === FUNÇÃO PARA DESCOBERTA AUTOMÁTICA NA REDE (mDNS) ===
def setup_mdns():
    """Configura descoberta automática na rede usando mDNS/Zeroconf"""
    if not ENABLE_MDNS or not ZEROCONF_AVAILABLE:
        return None
        
    try:
        # Obtém IP local
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Configuração do serviço mDNS
        desc = {
            'version': '1.0',
            'type': 'camera',
            'model': 'PenAreia',
            'platform': platform.system(),
            'endpoints': '/trigger,/status'
        }
        
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{SERVICE_NAME}._http._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=SERVER_PORT,
            properties=desc,
            server=f"{hostname}.local."
        )
        
        zeroconf = Zeroconf()
        zeroconf.register_service(info)
        
        print(f"📶 Serviço mDNS registrado: {SERVICE_NAME}.local:{SERVER_PORT}")
        print(f"🌐 Disponível em: http://{local_ip}:{SERVER_PORT}")
        
        return zeroconf
        
    except Exception as e:
        print(f"⚠️ Erro ao configurar mDNS: {e}")
        return None

# === FUNÇÃO PARA OBTER INFORMAÇÕES DO SISTEMA ===
def get_system_info():
    """Retorna informações do sistema para monitoramento"""
    try:
        if PSUTIL_AVAILABLE:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/') if (IS_RASPBERRY_PI or IS_ARM) else psutil.disk_usage('.')
        else:
            cpu_usage = 0
            memory = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})
            disk = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})
        
        return {
            'cpu_usage': f"{cpu_usage:.1f}%",
            'memory_usage': f"{memory.percent:.1f}%",
            'disk_usage': f"{disk.percent:.1f}%",
            'temperature': get_cpu_temperature()
        }
    except:
        return {'cpu_usage': 'N/A', 'memory_usage': 'N/A', 'disk_usage': 'N/A', 'temperature': 'N/A'}

def get_cpu_temperature():
    """Obtém temperatura da CPU (Raspberry Pi)"""
    try:
        if IS_RASPBERRY_PI:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000.0
                return f"{temp:.1f}°C"
    except:
        pass
    return 'N/A'

# === ENDPOINT DE TRIGGER COM UPLOAD E WEBHOOK ===
@app.route('/trigger', methods=['POST'])
def trigger():
    print("🎥 Trigger RECEBIDO! Salvando vídeo...")
    
    # Verifica espaço em disco antes de gravar
    if not check_disk_space(min_gb=1):
        logger.error("🚨 Espaço em disco insuficiente!")
        # Tenta limpeza emergencial
        cleanup_old_videos(max_age_hours=1, force=False)
        if not check_disk_space(min_gb=0.5):
            return {
                "error": "Espaço em disco insuficiente",
                "message": "Limpe arquivos antigos ou aumente o espaço disponível"
            }, 507  # HTTP 507 Insufficient Storage
    
    frames_to_save = []
    
    with buffer_lock:
        if not frame_buffer:
            print("❌ Nenhum frame disponível no buffer!")
            return {"error": "Nenhum frame disponível no buffer!"}, 500
        
        num_frames = int(SAVE_SECONDS * detected_fps)
        frames_to_save = list(frame_buffer)[-num_frames:]

    if not frames_to_save:
        print("❌ Frames para salvar estão vazios!")
        return {"error": "Frames para salvar estão vazios!"}, 500
    
    # Cria as pastas necessárias
    for folder in ['videos', 'videos/temp', 'videos/final']:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Pasta '{folder}' criada.")

    # SALVA O VÍDEO TEMPORÁRIO COM OPENCV
    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec temporário
        now = datetime.now()
        date_time_str = now.strftime("Penareia_%d-%m-%Y_%H-%M-%S")
        
        temp_filename = f'videos/temp/{date_time_str}_temp.mp4'  # Arquivo temporário
        final_filename = f'videos/final/{date_time_str}.mp4'     # Arquivo final
        remote_filename = f'{date_time_str}.mp4'                 # Nome no B2
        
        out = cv2.VideoWriter(temp_filename, fourcc, detected_fps, (frame_width, frame_height))
        
        if not out.isOpened():
            print("❌ Erro ao criar arquivo de vídeo temporário!")
            return {"error": "Erro ao criar arquivo de vídeo temporário!"}, 500
        
        print(f"💾 Salvando {len(frames_to_save)} frames...")
        for frame in frames_to_save:
            out.write(frame)
            
        out.release()
        print(f"✅ Vídeo temporário salvo: {temp_filename}")
        
    except Exception as e:
        print(f"❌ Erro ao salvar vídeo temporário: {e}")
        return {"error": f"Erro ao salvar vídeo temporário: {str(e)}"}, 500
    
    # CONVERTE VÍDEO COM FFMPEG PARA COMPATIBILIDADE COM NAVEGADORES
    print("🔄 Convertendo vídeo com FFmpeg...")
    conversion_success, conversion_result = convert_video_with_ffmpeg(temp_filename, final_filename)
    
    if not conversion_success:
        print("⚠️ Tentando conversão alternativa com subprocess...")
        conversion_success, conversion_result = convert_video_subprocess(temp_filename, final_filename)
    
    if not conversion_success:
        print(f"❌ Falha na conversão: {conversion_result}")
        return {"error": f"Falha na conversão do vídeo: {conversion_result}"}, 500
    
    # Remove arquivo temporário após conversão bem-sucedida
    try:
        os.remove(temp_filename)
        print(f"🗑️ Arquivo temporário removido: {temp_filename}")
    except:
        print(f"⚠️ Não foi possível remover arquivo temporário: {temp_filename}")
    
    # ADICIONA À QUEUE DE UPLOAD
    logger.info("📋 Adicionando vídeo à queue de upload...")
    queue_success = add_to_upload_queue(final_filename, remote_filename, priority=True)
    
    if queue_success:
        logger.info("✅ Vídeo adicionado à queue com sucesso!")
        
        return {
            "success": True,
            "message": "Vídeo salvo e adicionado à queue de upload!",
            "arquivo": remote_filename,
            "conversao": "FFmpeg H.264",
            "status": "Na queue de upload"
        }, 200
    else:
        logger.error("❌ Falha ao adicionar à queue")
        
        return {
            "success": False,
            "message": "Falha ao adicionar vídeo à queue",
            "arquivo": final_filename,
            "conversao": "FFmpeg H.264",
            "error": "Queue system error"
        }, 500

@app.route('/', methods=['GET'])
def home():
    ffmpeg_status = "✅ Instalado" if check_ffmpeg() else "❌ Não encontrado"
    
    return f"""
    <h1>🎥 Servidor Flask Filmaeu Online!</h1>
    <h2>Status do Sistema:</h2>
    <ul>
        <li><strong>FFmpeg:</strong> {ffmpeg_status}</li>
        <li><strong>Resolução:</strong> {frame_width}x{frame_height}</li>
        <li><strong>FPS:</strong> {detected_fps}</li>
        <li><strong>Buffer:</strong> {BUFFER_SECONDS}s</li>
        <li><strong>Gravação:</strong> {SAVE_SECONDS}s</li>
    </ul>
    
    <h2>Endpoints disponíveis:</h2>
    <ul>
        <li><strong>GET /</strong> - Esta página</li>
        <li><strong>POST /trigger</strong> - Salva vídeo, converte com FFmpeg e envia para B2 e banco</li>
        <li><strong>GET /status</strong> - Status detalhado do sistema</li>
    </ul>
    
    <h2>Formato de vídeo:</h2>
    <p>✅ H.264 + AAC (compatível com todos os navegadores)</p>
    """

@app.route('/status', methods=['GET'])
def status():
    """Endpoint para verificar o status do sistema"""
    buffer_size = len(frame_buffer) if frame_buffer else 0
    ffmpeg_available = check_ffmpeg()
    system_info = get_system_info()
    
    return {
        "status": "online",
        "video_source": VIDEO_SOURCE,
        "detected_fps": detected_fps,
        "frame_dimensions": f"{frame_width}x{frame_height}",
        "buffer_seconds": BUFFER_SECONDS,
        "save_seconds": SAVE_SECONDS,
        "buffer_frames": buffer_size,
        "webhook_url": WEBHOOK_URL,
        "b2_bucket": B2_BUCKET_NAME,
        "ffmpeg_available": ffmpeg_available,
        "video_format": "H.264 + AAC (Web Compatible)",
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "is_raspberry_pi": IS_RASPBERRY_PI,
            "hostname": socket.gethostname()
        },
        "system_info": system_info,
        "mdns_enabled": ENABLE_MDNS and ZEROCONF_AVAILABLE,
        "service_name": SERVICE_NAME if ENABLE_MDNS else None
    }

def signal_handler(signum, frame):
    """Handler para sinais do sistema"""
    global upload_thread_running, watchdog_enabled
    
    logger.info(f"🛑 Sinal {signum} recebido, encerrando gracefully...")
    upload_thread_running = False
    watchdog_enabled = False
    sys.exit(0)

if __name__ == '__main__':
    # Registra handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🎬 === INICIANDO SERVIDOR FLASK FILMAEU ===")
    logger.info(f"🖥️ Plataforma: {platform.system()} {platform.machine()}")
    if IS_RASPBERRY_PI or IS_ARM:
        logger.info("🍓 Modo Raspberry Pi ativado com otimizações ARM")
    
    logger.info("📋 Configurações:")
    logger.info(f"   • Vídeo fonte: {VIDEO_SOURCE}")
    logger.info(f"   • Buffer: {BUFFER_SECONDS}s")
    logger.info(f"   • Gravação: {SAVE_SECONDS}s")
    logger.info(f"   • FPS forçado: {FORCE_FPS}")
    logger.info(f"   • Resolução máxima: {MAX_WIDTH}x{MAX_HEIGHT}")
    logger.info(f"   • Webhook: {WEBHOOK_URL}")
    logger.info(f"   • Bucket B2: {B2_BUCKET_NAME}")
    
    # Reconfigura logging com path correto da plataforma
    try:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        
        log_dir = os.path.dirname(LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_PATH, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )
        logger.info(f"📝 Log reconfigurado: {LOG_PATH}")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível reconfigurar logging: {e}")
    
    # Inicializa banco de dados
    init_database()
    
    # Verifica se FFmpeg está disponível e atualiza o path global
    ffmpeg_available, detected_ffmpeg = check_ffmpeg()
    if ffmpeg_available and detected_ffmpeg:
        # Atualiza variável global com path detectado
        globals()['FFMPEG_CMD'] = detected_ffmpeg
        logger.info(f"✅ FFmpeg configurado: {detected_ffmpeg}")
    else:
        logger.warning("⚠️ FFmpeg não encontrado! Instale o FFmpeg para conversão de vídeos.")
        if IS_RASPBERRY_PI or IS_ARM:
            logger.info("📖 Instalar: sudo apt update && sudo apt install ffmpeg")
        else:
            logger.info("📖 Ver instruções no README.md")
    
    # Configura descoberta automática na rede
    zeroconf_service = None
    if ENABLE_MDNS:
        zeroconf_service = setup_mdns()
    
    # Inicia thread de processamento de uploads
    upload_thread = threading.Thread(target=process_upload_queue, daemon=True)
    upload_thread.start()
    logger.info("📤 Thread de upload iniciada")
    
    # Inicia watchdog
    watchdog_thread = threading.Thread(target=watchdog_monitor, daemon=True)
    watchdog_thread.start()
    logger.info("🐕 Watchdog iniciado")
    
    # Inicia thread de captura de vídeo
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    logger.info("🎥 Thread de captura iniciada")
    
    # Aguarda inicialização
    time.sleep(5 if (IS_RASPBERRY_PI or IS_ARM) else 3)
    
    try:
        # Inicia servidor Flask
        logger.info(f"🚀 Servidor Flask: {SERVER_HOST}:{SERVER_PORT}")
        if ENABLE_MDNS and ZEROCONF_AVAILABLE:
            logger.info(f"📱 mDNS: {SERVICE_NAME}.local:{SERVER_PORT}")
        
        # Atualiza heartbeat inicial
        update_heartbeat()
        
        app.run(
            host=SERVER_HOST, 
            port=SERVER_PORT, 
            debug=SERVER_DEBUG,
            threaded=USE_THREADS,
            use_reloader=False  # Importante para evitar problemas com threads
        )
    except Exception as e:
        logger.error(f"🚨 Erro crítico: {e}")
        # Registra crash no banco
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute('UPDATE system_status SET crashes = crashes + 1 WHERE id = 1')
            conn.commit()
            conn.close()
        except:
            pass
        raise
    finally:
        # Limpa recursos
        logger.info("🧹 Limpando recursos...")
        upload_thread_running = False
        watchdog_enabled = False
        
        if zeroconf_service:
            try:
                zeroconf_service.close()
                logger.info("📡 mDNS encerrado")
            except:
                pass

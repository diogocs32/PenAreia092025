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

# === VARIÁVEIS GLOBAIS PARA PROPRIEDADES DETECTADAS ===
detected_fps = 30.0  # Valor padrão
frame_width = 640
frame_height = 480

# === BUFFER CIRCULAR ===
frame_buffer = None
buffer_lock = threading.Lock()

# === FUNÇÃO PARA VERIFICAR SE FFMPEG ESTÁ INSTALADO ===
def check_ffmpeg():
    """Verifica se o FFmpeg está instalado no sistema"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg encontrado e funcionando!")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg não encontrado! Instale o FFmpeg para continuar.")
        return False

# === FUNÇÃO PARA CONVERTER VÍDEO COM FFMPEG ===
def convert_video_with_ffmpeg(input_path, output_path):
    """Converte vídeo para formato compatível com navegadores usando FFmpeg"""
    try:
        print(f"Convertendo vídeo com FFmpeg: {input_path} -> {output_path}")
        
        # Configuração do FFmpeg para navegadores
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            vcodec=VIDEO_CODEC,  # Codec de vídeo do config
            acodec=AUDIO_CODEC,  # Codec de áudio do config
            preset=ENCODING_PRESET,  # Preset do config
            crf=ENCODING_CRF,    # Qualidade do config
            pix_fmt=PIXEL_FORMAT, # Formato de pixel do config
            movflags='faststart',  # Para streaming web
            r=detected_fps,    # Taxa de frames
            s=f'{frame_width}x{frame_height}',  # Resolução
            f='mp4'           # Formato MP4
        )
        
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
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', VIDEO_CODEC,     # Codec de vídeo do config
            '-preset', ENCODING_PRESET,  # Preset do config
            '-crf', str(ENCODING_CRF),   # Qualidade do config
            '-c:a', AUDIO_CODEC,     # Codec de áudio do config
            '-pix_fmt', PIXEL_FORMAT, # Formato de pixel do config
            '-movflags', 'faststart', # Para web streaming
            '-y',                  # Sobrescrever arquivo existente
            output_path
        ]
        
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

# === FUNÇÃO PARA ENVIAR DADOS PARA O WEBHOOK ===
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

# === FUNÇÃO DE UPLOAD PARA B2 ===
def upload_to_b2(local_file_path, remote_file_name):
    """Faz upload de um arquivo para o Backblaze B2"""
    try:
        bucket = init_b2()
        if not bucket:
            return False, "Falha na conexão com B2"
        
        print(f"Iniciando upload de {local_file_path} para B2...")
        bucket.upload_local_file(
            local_file=local_file_path,
            file_name=remote_file_name
        )
        
        # Gera URL público do arquivo
        file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{remote_file_name}"
        print(f"Upload concluído! URL: {file_url}")
        return True, file_url
        
    except Exception as e:
        print(f"Erro no upload: {e}")
        return False, str(e)

# === FUNÇÃO DE CAPTURA DE FRAMES ===
def capture_frames():
    global frame_buffer, detected_fps, frame_width, frame_height

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"Erro ao conectar na fonte de vídeo: {VIDEO_SOURCE}")
        return

    # DETECÇÃO AUTOMÁTICA DAS PROPRIEDADES DA CÂMERA
    detected_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if detected_fps == 0 or detected_fps is None:
        print("Aviso: Câmera não informou FPS. Usando valor padrão de 30.")
        detected_fps = 30.0

    # INICIALIZAÇÃO DINÂMICA DO BUFFER COM BASE NO FPS REAL
    buffer_size = int(BUFFER_SECONDS * detected_fps)
    frame_buffer = deque(maxlen=buffer_size)

    print(f"Conectado à câmera: {frame_width}x{frame_height} @ {detected_fps:.2f} FPS. Buffer de {BUFFER_SECONDS}s.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Falha ao ler frame. Tentando reconectar em 5 segundos...")
            time.sleep(5)
            cap.release()
            cap = cv2.VideoCapture(VIDEO_SOURCE)
            if not cap.isOpened():
                print("Reconexão falhou. Encerrando thread.")
                break
            else:
                print("Reconectado com sucesso.")
                continue

        with buffer_lock:
            frame_buffer.append(frame)
    
    cap.release()
    print("Thread de captura finalizada.")

# === ENDPOINT DE TRIGGER COM UPLOAD E WEBHOOK ===
@app.route('/trigger', methods=['POST'])
def trigger():
    print("🎥 Trigger RECEBIDO! Salvando vídeo...")
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
    
    # FAZ UPLOAD PARA O BACKBLAZE B2
    print("☁️ Iniciando upload para Backblaze B2...")
    success, result = upload_to_b2(final_filename, remote_filename)
    
    if success:
        video_url = result
        print(f"✅ Upload para B2 concluído: {video_url}")
        
        # ENVIA OS DADOS PARA O WEBHOOK DO SITE
        data_hora_formatada = now.strftime("%Y-%m-%d %H:%M:%S")  # Formato MySQL
        
        print("🌐 Enviando dados para o webhook...")
        webhook_success, webhook_result = send_to_webhook(
            arquivo=remote_filename,
            url=video_url,
            data_hora=data_hora_formatada
        )
        
        if webhook_success:
            print("✅ Dados enviados para o banco de dados com sucesso!")
            # Remove arquivo final local após tudo dar certo (opcional)
            try:
                os.remove(final_filename)
                print(f"🗑️ Arquivo final local removido: {final_filename}")
            except:
                print(f"⚠️ Não foi possível remover arquivo final: {final_filename}")
            
            return {
                "success": True,
                "message": "Vídeo salvo, convertido, enviado para B2 e registrado no banco!",
                "url": video_url,
                "arquivo": remote_filename,
                "conversao": "FFmpeg H.264",
                "webhook_response": webhook_result
            }, 200
        else:
            print(f"❌ Falha ao enviar para webhook: {webhook_result}")
            return {
                "success": False,
                "message": "Vídeo convertido e enviado para B2, mas falha no registro do banco",
                "url": video_url,
                "arquivo": remote_filename,
                "conversao": "FFmpeg H.264",
                "webhook_error": webhook_result
            }, 206
    else:
        print(f"❌ Falha no upload para B2: {result}")
        return {
            "success": False,
            "message": "Vídeo convertido mas falha no upload",
            "arquivo": final_filename,
            "conversao": "FFmpeg H.264",
            "error": result
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
        "video_format": "H.264 + AAC (Web Compatible)"
    }

if __name__ == '__main__':
    print("🎬 === INICIANDO SERVIDOR FLASK FILMAEU ===")
    print(f"Configurações:")
    print(f"- Vídeo fonte: {VIDEO_SOURCE}")
    print(f"- Buffer: {BUFFER_SECONDS}s")
    print(f"- Gravação: {SAVE_SECONDS}s")
    print(f"- Webhook: {WEBHOOK_URL}")
    print(f"- Bucket B2: {B2_BUCKET_NAME}")
    
    # Verifica se FFmpeg está disponível
    if not check_ffmpeg():
        print("⚠️ AVISO: FFmpeg não encontrado! Instale o FFmpeg para conversão de vídeos.")
        print("📖 Instruções de instalação:")
        print("   Windows: choco install ffmpeg")
        print("   Ubuntu:  sudo apt install ffmpeg")
        print("   macOS:   brew install ffmpeg")
    
    # Inicia thread de captura de vídeo
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    print("🎥 Thread de captura de vídeo iniciada.")
    
    # Aguarda um pouco para a thread inicializar
    time.sleep(2)
    
    # Inicia servidor Flask
    print(f"🚀 Iniciando servidor Flask em {SERVER_HOST}:{SERVER_PORT}...")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)

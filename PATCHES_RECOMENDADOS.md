# 🔧 Patches Recomendados para Compatibilidade Multi-Plataforma

## Patch 1: Paths Dinâmicos por Plataforma

### Problema
O código atual usa paths hardcoded do Linux:
- `/var/lib/penareia/queue.db` → Falha no Windows
- `/var/log/penareia.log` → Falha no Windows
- `/usr/bin/ffmpeg` → Pode não existir

### Solução
Adicionar logo após a detecção de plataforma (linha ~105):

```python
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
        os.makedirs(directory, exist_ok=True)

print(f"💾 Banco de dados: {DB_PATH}")
print(f"📝 Log: {LOG_PATH}")
print(f"🎬 FFmpeg: {FFMPEG_CMD}")
```

### Onde aplicar
1. Remover linha `DB_PATH = '/var/lib/penareia/queue.db'` (linha ~120)
2. Adicionar código acima logo após `IS_ARM = ...`

---

## Patch 2: Logging Multi-Plataforma

### Problema
Tentativa de escrever em `/var/log/penareia.log` falha no Windows

### Solução
Modificar configuração de logging (linha ~35):

```python
# === CONFIGURAÇÃO DE LOGGING ROBUSTO ===
# Determina path do log baseado na plataforma
if 'IS_RASPBERRY_PI' not in locals():
    # Se ainda não detectou plataforma, usa fallback
    LOG_PATH = 'penareia.log'

# Garante que diretório do log existe
log_dir = os.path.dirname(LOG_PATH)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except:
        # Se falhar (ex: sem permissão), usa diretório atual
        LOG_PATH = 'penareia.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 Log configurado: {LOG_PATH}")
```

---

## Patch 3: FFmpeg Path Dinâmico

### Problema
Código assume `/usr/bin/ffmpeg` no Pi, mas pode estar em outro lugar

### Solução
Modificar funções de conversão (linhas ~160 e ~220):

```python
def check_ffmpeg():
    """Verifica se o FFmpeg está instalado no sistema"""
    try:
        # Tenta encontrar FFmpeg no PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
            print(f"✅ FFmpeg encontrado: {ffmpeg_path}")
            return True, ffmpeg_path
        
        # Fallback para path padrão do Pi
        if IS_RASPBERRY_PI or IS_ARM:
            pi_path = '/usr/bin/ffmpeg'
            subprocess.run([pi_path, '-version'], capture_output=True, check=True)
            print(f"✅ FFmpeg encontrado: {pi_path}")
            return True, pi_path
            
        return False, None
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg não encontrado! Instale o FFmpeg para continuar.")
        if IS_RASPBERRY_PI or IS_ARM:
            print("📝 Para Raspberry Pi: sudo apt update && sudo apt install ffmpeg")
        else:
            print("📝 Para Windows: Baixe em https://ffmpeg.org/download.html")
        return False, None

# No início do main(), após detecção de plataforma:
ffmpeg_available, FFMPEG_CMD = check_ffmpeg()
if not ffmpeg_available:
    logger.warning("⚠️ Sistema iniciará sem conversão de vídeo!")
```

E nas funções de conversão, substituir:
```python
# ANTES:
ffmpeg_cmd = '/usr/bin/ffmpeg' if (IS_RASPBERRY_PI or IS_ARM) else 'ffmpeg'

# DEPOIS:
ffmpeg_cmd = FFMPEG_CMD  # Usa variável global detectada
```

---

## Patch 4: Validação de Espaço em Disco

### Problema
Sistema pode travar se disco encher durante gravação

### Solução
Adicionar função de verificação (inserir após `init_b2()`):

```python
def check_disk_space(min_gb=2):
    """Verifica se há espaço suficiente em disco"""
    try:
        # Detecta path correto para verificação
        check_path = '/var/lib/penareia' if (IS_RASPBERRY_PI or IS_ARM) else '.'
        
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

# No endpoint /trigger, adicionar antes de salvar vídeo:
if not check_disk_space(min_gb=2):
    logger.error("🚨 Espaço em disco insuficiente!")
    return {
        "error": "Espaço em disco insuficiente",
        "message": "Limpe arquivos antigos ou aumente o espaço disponível"
    }, 507  # HTTP 507 Insufficient Storage
```

---

## Patch 5: Limpeza Automática de Vídeos Antigos

### Problema
Vídeos locais podem acumular e encher o disco

### Solução
Adicionar função de limpeza (inserir após `check_disk_space()`):

```python
def cleanup_old_videos(max_age_hours=24, force=False):
    """Remove vídeos locais com mais de X horas
    
    Args:
        max_age_hours: Idade máxima em horas (padrão 24h)
        force: Se True, remove todos os arquivos independente da idade
    """
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
        else:
            logger.debug("✨ Nenhum arquivo antigo para remover")
            
        return removed_count
        
    except Exception as e:
        logger.error(f"❌ Erro na limpeza de vídeos: {e}")
        return 0

# Adicionar no watchdog_monitor(), dentro do loop:
if IS_RASPBERRY_PI or IS_ARM:
    # A cada 1 hora, limpa vídeos com mais de 24h
    if time.time() % 3600 < 30:  # Executa próximo do início de cada hora
        cleanup_old_videos(max_age_hours=24)
        
    # Se disco estiver baixo, força limpeza imediata
    if not check_disk_space(min_gb=1):
        logger.warning("🚨 Disco quase cheio! Forçando limpeza...")
        cleanup_old_videos(max_age_hours=1)  # Remove vídeos com mais de 1h
```

---

## Patch 6: Health Check Endpoint

### Problema
Difícil monitorar saúde do sistema externamente

### Solução
Adicionar endpoint antes do `@app.route('/trigger')`:

```python
@app.route('/health')
def health_check():
    """Endpoint de health check para monitoramento externo"""
    try:
        time_since_heartbeat = time.time() - last_heartbeat
        is_healthy = system_healthy and (time_since_heartbeat < 60)
        
        # Coleta informações do sistema
        health_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "last_heartbeat_seconds_ago": round(time_since_heartbeat, 2),
            "buffer_frames": len(frame_buffer) if frame_buffer else 0,
            "queue_size": upload_queue.qsize(),
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "is_raspberry_pi": IS_RASPBERRY_PI
            }
        }
        
        # Adiciona métricas do sistema se psutil disponível
        try:
            health_data["resources"] = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent if (IS_RASPBERRY_PI or IS_ARM) else psutil.disk_usage('.').percent
            }
        except:
            pass
        
        # Informações do banco de dados
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM system_status WHERE id = 1')
            row = cursor.fetchone()
            conn.close()
            
            if row:
                health_data["statistics"] = {
                    "captures_total": row[3],
                    "uploads_success": row[4],
                    "uploads_failed": row[5],
                    "crashes": row[6],
                    "uptime_seconds": row[2]
                }
        except:
            pass
        
        status_code = 200 if is_healthy else 503
        return health_data, status_code
        
    except Exception as e:
        logger.error(f"❌ Erro no health check: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500
```

---

## Patch 7: Validação de Configuração na Inicialização

### Problema
Sistema pode iniciar com configuração inválida

### Solução
Adicionar função de validação (inserir após leitura do config.ini):

```python
def validate_configuration():
    """Valida configurações obrigatórias do config.ini"""
    errors = []
    warnings = []
    
    # Validações obrigatórias
    required = {
        'VIDEO': ['SOURCE', 'BUFFER_SECONDS', 'SAVE_SECONDS'],
        'BACKBLAZE_B2': ['KEY_ID', 'APPLICATION_KEY', 'BUCKET_NAME'],
        'WEBHOOK': ['URL'],
        'SERVER': ['HOST', 'PORT']
    }
    
    for section, keys in required.items():
        if not config.has_section(section):
            errors.append(f"❌ Seção obrigatória ausente: [{section}]")
            continue
            
        for key in keys:
            if not config.has_option(section, key):
                errors.append(f"❌ Chave obrigatória ausente: [{section}].{key}")
            elif not config.get(section, key).strip():
                errors.append(f"❌ Valor vazio: [{section}].{key}")
    
    # Validações de valores
    try:
        buffer_sec = config.getint('VIDEO', 'BUFFER_SECONDS')
        save_sec = config.getint('VIDEO', 'SAVE_SECONDS')
        
        if buffer_sec < save_sec:
            errors.append(f"❌ BUFFER_SECONDS ({buffer_sec}) deve ser >= SAVE_SECONDS ({save_sec})")
        
        if save_sec < 5:
            warnings.append(f"⚠️ SAVE_SECONDS ({save_sec}) muito baixo, recomendado >= 10")
            
        if buffer_sec > 60:
            warnings.append(f"⚠️ BUFFER_SECONDS ({buffer_sec}) muito alto, pode consumir muita RAM")
    except:
        pass
    
    # Validação de URL do webhook
    try:
        webhook_url = config.get('WEBHOOK', 'URL')
        if not webhook_url.startswith('http'):
            errors.append(f"❌ WEBHOOK.URL inválida: {webhook_url}")
    except:
        pass
    
    # Exibe resultados
    if errors:
        print("\n" + "="*60)
        print("🚨 ERROS CRÍTICOS NA CONFIGURAÇÃO:")
        print("="*60)
        for error in errors:
            print(error)
        print("="*60 + "\n")
        raise ValueError("Configuração inválida! Corrija os erros acima.")
    
    if warnings:
        print("\n" + "="*60)
        print("⚠️ AVISOS DE CONFIGURAÇÃO:")
        print("="*60)
        for warning in warnings:
            print(warning)
        print("="*60 + "\n")
    
    print("✅ Configuração validada com sucesso!")
    return True

# Adicionar no main(), logo após config.read('config.ini'):
validate_configuration()
```

---

## Como Aplicar os Patches

### Ordem Recomendada
1. **Patch 1** (Paths dinâmicos) - CRÍTICO para Windows
2. **Patch 2** (Logging) - CRÍTICO para Windows  
3. **Patch 7** (Validação de config) - ALTA prioridade
4. **Patch 3** (FFmpeg path) - MÉDIA prioridade
5. **Patch 4** (Espaço em disco) - MÉDIA prioridade
6. **Patch 5** (Limpeza automática) - BAIXA prioridade
7. **Patch 6** (Health check) - BAIXA prioridade

### Script de Aplicação
```bash
# No Windows PowerShell:
# 1. Backup do arquivo atual
Copy-Item app.py app.py.backup

# 2. Aplicar patches manualmente ou com ferramenta
# Use o VS Code para aplicar cada patch seguindo as instruções acima

# 3. Testar sintaxe
python -m py_compile app.py

# 4. Testar localmente
python app.py
```

### No Raspberry Pi
```bash
# Se já aplicou patches no Windows, apenas copiar o arquivo:
scp app.py pi@raspberrypi.local:/home/pi/penareia/

# Se for aplicar direto no Pi:
cd /home/pi/penareia
cp app.py app.py.backup
nano app.py  # Aplicar patches manualmente
python3 -m py_compile app.py
sudo systemctl restart penareia
```

---

## Testes Após Aplicação

### Teste Local (Windows)
```powershell
# 1. Verificar se inicia sem erros
python app.py

# 2. Verificar paths
# Deve criar: .\data\queue.db e .\logs\penareia.log

# 3. Testar trigger
Invoke-RestMethod -Uri http://localhost:5000/trigger -Method POST

# 4. Verificar health
Invoke-RestMethod -Uri http://localhost:5000/health
```

### Teste no Raspberry Pi
```bash
# 1. Verificar paths
ls -la /var/lib/penareia/queue.db
ls -la /var/log/penareia.log

# 2. Testar health check
curl http://localhost:5000/health | jq

# 3. Verificar espaço em disco
df -h

# 4. Testar trigger via ESP32
# (Pressionar botão físico)
```

---

## Resultado Esperado

Após aplicar todos os patches:

✅ **Windows:**
- Paths locais (./data/, ./logs/)
- FFmpeg detectado automaticamente
- Sistema roda sem erros
- Fácil para desenvolvimento

✅ **Raspberry Pi:**
- Paths do sistema (/var/lib/, /var/log/)
- FFmpeg otimizado (hardware acceleration)
- Monitoramento de recursos
- Limpeza automática
- Health check funcional
- Validação de configuração

✅ **Ambos:**
- Código compartilhado (DRY)
- Mesma base de código
- Fácil manutenção
- Logs detalhados

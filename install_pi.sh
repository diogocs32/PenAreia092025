#!/bin/bash
# Script de instalação completo para Raspberry Pi 4 - Sistema PenAreia
# Inclui todos os sistemas de segurança e failover

set -e  # Para o script em caso de erro

echo "🍓 === INSTALAÇÃO COMPLETA PENAREIA RASPBERRY PI 4 ==="
echo "🔒 Sistema com anti-falhas e recuperação automática"

# Função para log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Verifica se é root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Este script não deve ser executado como root"
   exit 1
fi

log "📦 Atualizando sistema..."
sudo apt update && sudo apt upgrade -y

log "🔧 Instalando dependências essenciais..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    ffmpeg \
    git \
    v4l-utils \
    libcamera-apps \
    python3-libcamera \
    python3-kms++ \
    python3-pyqt5 \
    python3-prctl \
    libatlas-base-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libjasper-dev \
    sqlite3 \
    htop \
    curl \
    wget \
    rsync \
    logrotate \
    watchdog \
    avahi-daemon \
    avahi-utils

log "📹 Configurando câmera e GPU..."
sudo raspi-config nonint do_camera 0
sudo raspi-config nonint do_memory_split 128

log "⚡ Aplicando overclock seguro..."
if ! grep -q "arm_freq=1750" /boot/config.txt; then
    sudo tee -a /boot/config.txt > /dev/null <<EOF

# PenAreia Optimizations
arm_freq=1750
over_voltage=2
gpu_freq=600
gpu_mem=128

# Hardware watchdog
dtparam=watchdog=on

# Disable swap for SD card longevity
disable_splash=1
EOF
fi

log "💾 Configurando armazenamento..."
# Desabilita swap para prolongar vida do SD card
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo update-rc.d dphys-swapfile remove

# Cria estrutura de diretórios
sudo mkdir -p /var/lib/penareia
sudo mkdir -p /var/log/penareia
sudo chown $USER:$USER /var/lib/penareia
sudo chown $USER:$USER /var/log/penareia

log "🔒 Configurando watchdog hardware..."
echo 'watchdog-device = /dev/watchdog' | sudo tee /etc/watchdog.conf > /dev/null
echo 'watchdog-timeout = 15' | sudo tee -a /etc/watchdog.conf > /dev/null
echo 'realtime = yes' | sudo tee -a /etc/watchdog.conf > /dev/null
echo 'priority = 1' | sudo tee -a /etc/watchdog.conf > /dev/null
sudo systemctl enable watchdog

# Cria ambiente virtual
echo "🐍 Criando ambiente virtual Python..."
python3 -m venv .venv
source .venv/bin/activate

# Atualiza pip
pip install --upgrade pip

# Instala dependências Python básicas
echo "📚 Instalando dependências Python..."
pip install -r requirements.txt

# Instala dependências específicas do Pi
echo "🍓 Instalando dependências do Raspberry Pi..."
pip install -r requirements_pi.txt

# Instala OpenCV otimizado para Pi
echo "🔍 Instalando OpenCV..."
pip install opencv-python==4.8.1.78

log "🚀 Configurando serviço systemd com failover..."
sudo tee /etc/systemd/system/penareia.service > /dev/null <<EOF
[Unit]
Description=PenAreia Camera Service - Sistema Anti-Falhas
After=network-online.target
Wants=network-online.target
StartLimitBurst=3
StartLimitIntervalSec=60

[Service]
Type=simple
User=$USER
Group=video
WorkingDirectory=$PWD
Environment=PATH=$PWD/.venv/bin
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sleep 10
ExecStart=$PWD/.venv/bin/python app.py
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# Anti-falhas e recovery
Restart=always
RestartSec=5
RestartPreventExitStatus=0

# Limites de recursos
MemoryLimit=1G
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=penareia

[Install]
WantedBy=multi-user.target
EOF

log "📋 Configurando logrotate..."
sudo tee /etc/logrotate.d/penareia > /dev/null <<EOF
/var/log/penareia.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}

/var/log/penareia/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF

log "🔄 Configurando script de backup automático..."
sudo tee /usr/local/bin/penareia-backup.sh > /dev/null <<'EOF'
#!/bin/bash
# Backup automático das configurações PenAreia

BACKUP_DIR="/home/$USER/penareia-backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup da configuração
cp config.ini "$BACKUP_DIR/config_$DATE.ini" 2>/dev/null || true

# Backup do banco de dados
sqlite3 /var/lib/penareia/queue.db ".backup '$BACKUP_DIR/queue_$DATE.db'" 2>/dev/null || true

# Remove backups antigos (>7 dias)
find "$BACKUP_DIR" -name "*" -mtime +7 -delete 2>/dev/null || true
EOF

chmod +x /usr/local/bin/penareia-backup.sh

log "⏰ Configurando crontab para backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/penareia-backup.sh") | crontab -

log "🔐 Configurando permissões finais..."
sudo usermod -a -G video,audio,dialout $USER

# Habilita serviços
sudo systemctl daemon-reload
sudo systemctl enable penareia.service
sudo systemctl enable watchdog

log "📱 Criando script de monitoramento..."
tee monitor.sh > /dev/null <<EOF
#!/bin/bash
# Monitor rápido do PenAreia
echo "🍓 === STATUS PENAREIA ==="
echo "Serviço: \$(systemctl is-active penareia)"
echo "Uptime: \$(systemctl show penareia --property=ActiveEnterTimestamp --value)"
echo "CPU: \$(top -bn1 | grep "Cpu(s)" | awk '{print \$2}' | cut -d'%' -f1)%"
echo "Temp: \$(vcgencmd measure_temp)"
echo "Memória: \$(free -h | grep Mem | awk '{print \$3 "/" \$2}')"
echo ""
echo "Últimas 5 linhas do log:"
sudo journalctl -u penareia -n 5 --no-pager
EOF
chmod +x monitor.sh

echo ""
echo "✅ === INSTALAÇÃO COMPLETA CONCLUÍDA ==="
echo ""
echo "� Sistemas de segurança instalados:"
echo "   ✓ Hardware watchdog ativo"
echo "   ✓ Serviço com restart automático"
echo "   ✓ Backup automático diário"
echo "   ✓ Queue persistente para uploads"
echo "   ✓ Logrotate configurado"
echo "   ✓ Monitoramento de recursos"
echo ""
echo "🔄 REINICIE AGORA para ativar todas as configurações:"
echo "   sudo reboot"
echo ""
echo "📱 Após reiniciar:"
echo "   • Serviço inicia automaticamente"
echo "   • Acesse: http://\$(hostname).local:5000"
echo "   • Monitor: ./monitor.sh"
echo ""
echo "🛠️ Comandos essenciais:"
echo "   sudo systemctl status penareia       # Status"
echo "   sudo journalctl -u penareia -f       # Logs"
echo "   python3 monitor_pi.py               # Monitor detalhado"
echo "   ./monitor.sh                         # Status rápido"
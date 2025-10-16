# 🍓 PenAreia - Configuração para Raspberry Pi 4

Guia completo para instalar e configurar o sistema PenAreia no Raspberry Pi 4 com 8GB RAM, otimizado para máxima performance e descoberta automática na rede.

## 🚀 Instalação Rápida

### 1. Preparar o Sistema

```bash
# Clone o repositório
git clone https://github.com/diogocs32/PenAreia092025.git
cd PenAreia092025

# Execute o script de instalação
chmod +x install_pi.sh
./install_pi.sh
```

### 2. Configurar Credenciais

```bash
# Copie o arquivo de configuração para Raspberry Pi
cp config_pi.ini config.ini

# Edite suas credenciais
nano config.ini
```

### 3. Iniciar o Serviço

```bash
# Reinicie o sistema para aplicar todas as configurações
sudo reboot

# O serviço inicia automaticamente após o reboot
# Verifique o status
sudo systemctl status penareia
```

## ⚙️ Otimizações Implementadas

### 🏎️ Performance
- **24 FPS forçado** em todas as plataformas para melhor performance
- **Resolução otimizada** até 1280x720
- **Preset ultrafast** para encoding rápido
- **Buffer de 25 segundos** com gravação de 20 segundos
- **4 threads** para encoding paralelo
- **GPU acceleration** quando disponível (h264_v4l2m2m)

### 🌐 Rede e Descoberta
- **mDNS automático** - descoberto como `PenAreia-Camera.local`
- **Zeroconf** para descoberta automática pelo ESP32
- **IP fixo opcional** configurável
- **Monitoramento de rede** integrado

### 🔧 Sistema
- **Overclock seguro** para Pi 4 (1.75GHz ARM, 600MHz GPU)
- **GPU memory split** otimizado (128MB)
- **Serviço systemd** para inicialização automática
- **Monitoramento de temperatura** integrado
- **Logs estruturados** para troubleshooting

## 📱 ESP32-C6 - Botão Trigger Inteligente

### 🔧 Hardware Necessário
- **ESP32-C6** (suporte WiFi 6)
- **Botão push** no GPIO 9 (único botão)
- **LED de status** no GPIO 8 (indicação visual)

### 🚀 Funcionalidades Avançadas

#### **Portal Captivo para Configuração**
- **Primeira inicialização**: Cria rede WiFi "PenAreia-Setup"
- **Configuração fácil**: Conecta no WiFi e acessa qualquer site
- **Interface web**: Insere credenciais da rede principal
- **Salvamento automático**: Configurações salvas na memória flash

#### **Estados do LED (Sem Buzzer)**
- 🔴 **Piscando rápido**: Sem conexão WiFi / Configurando
- 🟡 **3 piscadas lentas**: Conectou ao WiFi com sucesso  
- 🟢 **Ligado fixo**: Pronto para usar (servidor encontrado)
- ⚫ **Apagado**: Em cooldown (20 segundos)
- 🔴 **Padrão erro**: Problema de conexão

#### **Operação do Botão Único**
- **Pressão rápida**: Envia trigger de gravação
- **10 segundos pressionado**: Reset total das configurações
- **Cooldown**: 20 segundos entre triggers (LED apagado)
- **Debounce**: Proteção contra múltiplos triggers acidentais

### 📋 Configuração Arduino IDE

#### **1. Instalar ESP32 Core:**
```
File → Preferences → Additional Boards Manager URLs
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json

Tools → Board → Boards Manager → "esp32" → Install
```

#### **2. Instalar Bibliotecas:**
```
ArduinoJson (by Benoit Blanchon) - OBRIGATÓRIA
ESPmDNS (incluída no core)
WiFi (incluída no core)  
WebServer (incluída no core)
DNSServer (incluída no core)
Preferences (incluída no core)
```

#### **3. Configuração da Placa:**
```
Board: "ESP32C6 Dev Module"
Upload Speed: 921600
USB CDC On Boot: Enabled
Partition Scheme: Default 4MB
```

### 🔄 Processo de Setup Completo

#### **Primeira Configuração:**

1. **Upload do código** `esp32_trigger_complete.ino`
2. **ESP32 cria rede** "PenAreia-Setup" (senha: 12345678)
3. **Conectar smartphone/PC** na rede PenAreia-Setup
4. **Abrir navegador** (qualquer site redireciona para configuração)
5. **Inserir credenciais** da rede onde está o Raspberry Pi
6. **Aguardar conexão** (LED pisca 3x quando conectar)
7. **Descoberta automática** do servidor PenAreia
8. **Pronto para usar** (LED fica fixo)

#### **Reset de Configurações:**
- Segurar botão por **10 segundos**
- LED pisca rapidamente durante reset
- Volta para modo configuração inicial

### 🔍 Descoberta Automática

#### **Como Funciona:**
1. **Conecta na rede WiFi** configurada
2. **Busca via mDNS** por serviços HTTP na rede
3. **Testa cada servidor** enviando GET /status
4. **Identifica PenAreia** pela resposta JSON específica
5. **Salva configurações** para próximas inicializações
6. **Monitora servidor** periodicamente (30s)

#### **Fallback e Recovery:**
- Se servidor sair do ar → Tenta redescobrir
- Se WiFi desconectar → Tenta reconectar
- Se nada funcionar → Volta para modo AP
- Verificação contínua de conectividade

### 🎯 Operação Normal

#### **Estados do Sistema:**
- **AP_MODE**: Portal captivo ativo
- **CONNECTING**: Conectando ao WiFi
- **DISCOVERING**: Procurando servidor
- **READY**: Pronto para triggers  
- **COOLDOWN**: Aguardando próximo trigger
- **ERROR**: Problema detectado

#### **Envio de Trigger:**
```cpp
POST http://SERVIDOR_IP:5000/trigger
Content-Type: application/json
Body: {}
```

### 📊 Monitoramento

#### **Status via Serial (115200 baud):**
```
📡 Conectando ao WiFi: MinhaRede
✅ WiFi conectado! IP: 192.168.1.100
🔍 Descobrindo servidor PenAreia...
🎯 Servidor encontrado: 192.168.1.50:5000
✅ Sistema pronto!
🔘 Pressione botão para gravar
```

#### **Status via HTTP:**
```
GET http://192.168.1.100/status
```
Retorna JSON com estado atual do sistema.

## 🖥️ Monitoramento

### Monitor em Tempo Real
```bash
# Execute o monitor do sistema
python3 monitor_pi.py
```

### Verificar Status
```bash
# Status do serviço
sudo systemctl status penareia

# Logs em tempo real
sudo journalctl -u penareia -f

# Verificar servidor web
curl http://localhost:5000/status
```

### Endpoints Disponíveis

- `http://RASPBERRY_IP:5000/` - Página principal
- `http://RASPBERRY_IP:5000/status` - Status JSON
- `http://RASPBERRY_IP:5000/trigger` - Disparar gravação
- `http://PenAreia-Camera.local:5000/` - Via mDNS

## 🔧 Configurações Avançadas

### Ajustar Performance

Edite `config.ini` para ajustar conforme necessário:

```ini
[VIDEO]
FORCE_FPS = 24          # Reduza para 20 se CPU alta
MAX_WIDTH = 1280        # Reduza para 640 se necessário
MAX_HEIGHT = 720        # Reduza para 480 se necessário

[VIDEO_ENCODING]
PRESET = ultrafast      # Use "superfast" para melhor qualidade
CRF = 25               # Reduza para 23 para melhor qualidade
THREADS = 4            # Ajuste conforme CPU
```

### Overclock Personalizado

Edite `/boot/config.txt`:

```ini
# Overclock conservador (padrão do script)
arm_freq=1750
over_voltage=2
gpu_freq=600

# Overclock agressivo (apenas se cooling adequado)
#arm_freq=2000
#over_voltage=4
#gpu_freq=650
```

### Câmera Raspberry Pi

Para usar câmera nativa do Pi em vez de USB:

```ini
[VIDEO]
SOURCE = libcamera     # ou /dev/video0
```

## �️ Sistemas Anti-Falhas Implementados

### 🔒 **Hardware Watchdog**
- **Watchdog timer** reinicia sistema se travar
- **Timeout**: 15 segundos para detecção
- **Monitoramento**: CPU, memória, temperatura
- **Ação**: Reboot automático em caso de falha crítica

### 📤 **Queue Persistente de Upload**
- **Banco SQLite** para queue de uploads
- **Retry automático** até 5 tentativas por arquivo
- **Recuperação na inicialização** de uploads pendentes
- **Verificação de integridade** via hash MD5
- **Priorização** de uploads (novos triggers têm prioridade)

### 🔄 **Sistema de Recovery**
- **Captura robusta**: Reconexão automática da câmera
- **Thread separada** para uploads (não bloqueia captura)
- **Webhook assíncrono**: Não interfere no upload
- **Heartbeat monitoring**: Detecta threads travadas
- **Graceful shutdown**: Encerramento limpo com sinais

### 💾 **Backup e Persistência**
- **Backup diário automático** das configurações
- **Logrotate configurado** (7 dias logs, compressão)
- **Banco de dados** para queue e estatísticas  
- **Configurações salvas** em `/var/lib/penareia/`
- **Logs estruturados** em `/var/log/penareia/`

### ⚡ **Otimizações Raspberry Pi**
- **Desabilitado swap** (preserva SD card)
- **Overclock seguro** (1.75GHz, 600MHz GPU)
- **GPU memory split** otimizado (128MB)
- **Encoding hardware** quando disponível
- **Threads limitadas** para evitar sobrecarga

### 📊 **Monitoramento Contínuo**
- **Watchdog thread** monitora sistema
- **CPU/Memória/Temperatura** em tempo real
- **Status de conectividade** (WiFi, servidor, B2)
- **Estatísticas persistentes** (uploads, falhas, crashes)
- **Alertas automáticos** para problemas

### 🔧 **Inicialização Robusta**
- **Serviço systemd** com restart automático
- **Delay de inicialização** (aguarda rede)
- **Limite de restarts** (evita loops infinitos)  
- **Dependências corretas** (rede, câmera)
- **Timeout configurável** para cada componente

## �🚨 Troubleshooting

### Serviço não inicia
```bash
# Verificar logs
sudo journalctl -u penareia -n 50

# Reinstalar dependências
source .venv/bin/activate
pip install -r requirements_pi.txt
```

### ESP32 não encontra servidor
1. Verificar se Raspberry Pi está na mesma rede
2. Testar mDNS: `ping PenAreia-Camera.local`
3. Verificar firewall: `sudo ufw status`

### Performance baixa
1. Verificar temperatura: `vcgencmd measure_temp`
2. Verificar CPU: `htop`
3. Reduzir FPS ou resolução no config.ini

### Problemas de rede
```bash
# Verificar mDNS
sudo systemctl status avahi-daemon

# Reiniciar serviços de rede
sudo systemctl restart networking
sudo systemctl restart avahi-daemon
```

## 📊 Especificações de Performance

### Raspberry Pi 4 8GB - Performance Esperada

| Configuração | FPS | Resolução | CPU Usage | Qualidade |
|--------------|-----|-----------|-----------|-----------|
| **Otimizada** | 24 | 1280x720 | ~60% | Boa |
| **Balanceada** | 24 | 640x480 | ~40% | Média |
| **Econômica** | 20 | 640x480 | ~30% | Básica |

### Limites Recomendados

- **CPU**: Manter abaixo de 80%
- **Temperatura**: Abaixo de 75°C
- **Memória**: Abaixo de 85%
- **FPS máximo**: 30 (recomendado 24)

## 🔗 Links Úteis

- [Raspberry Pi Camera Guide](https://www.raspberrypi.org/documentation/accessories/camera.html)
- [ESP32-C6 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c6_datasheet_en.pdf)
- [FFmpeg ARM Optimization](https://trac.ffmpeg.org/wiki/HWAccelIntro)

## 🤝 Suporte

Para problemas específicos do Raspberry Pi:

1. Verifique os logs: `sudo journalctl -u penareia -f`
2. Execute o monitor: `python3 monitor_pi.py`
3. Teste a rede: `curl http://localhost:5000/status`
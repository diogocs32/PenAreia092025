# 🎥 PenAreia - Sistema de Captura de Vídeo

Sistema automatizado de captura de vídeo com upload para Backblaze B2 e integração com webhook.

## 📁 Estrutura do Projeto

```
PenAreia092025/
├── app.py                 # Aplicação principal Flask
├── config.ini            # Arquivo de configurações
├── config.ini.example    # Exemplo de configurações
├── validate_config.py    # Script para validar configurações
├── requirements.txt      # Dependências Python
├── ffmpeg.exe            # Executável do FFmpeg
├── static/               # Arquivos estáticos
└── videos/              # Diretório de vídeos
    ├── temp/            # Vídeos temporários
    └── final/           # Vídeos finais
```

## ⚙️ Configuração

### 1. Arquivo de Configuração

Copie o arquivo de exemplo e configure suas credenciais:

```bash
copy config.ini.example config.ini
```

Edite o `config.ini` com suas configurações:

```ini
[VIDEO]
SOURCE = rtsp://user:password@camera_ip:554/stream
BUFFER_SECONDS = 25
SAVE_SECONDS = 20

[WEBHOOK]
URL = https://seusite.com/webhook.php

[BACKBLAZE_B2]
KEY_ID = sua_key_id
APPLICATION_KEY = sua_application_key
BUCKET_NAME = seu_bucket

[SERVER]
HOST = 0.0.0.0
PORT = 5000
DEBUG = False

[VIDEO_ENCODING]
CODEC = libx264
AUDIO_CODEC = aac
PRESET = fast
CRF = 23
PIXEL_FORMAT = yuv420p
```

### 2. Validar Configurações

Antes de executar o programa, valide suas configurações:

```bash
python validate_config.py
```

## 🚀 Instalação e Execução

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Executar o Programa

```bash
python app.py
```

O servidor será iniciado na porta configurada (padrão: 5000).

## 📡 Endpoints Disponíveis

### GET /
- **Descrição**: Página inicial com status do sistema
- **Resposta**: HTML com informações do sistema

### GET /status
- **Descrição**: Status detalhado em formato JSON
- **Resposta**: JSON com configurações e status

### POST /trigger
- **Descrição**: Dispara a gravação de vídeo
- **Resposta**: JSON com resultado da operação

## 🔧 Funcionalidades

### ✅ Captura de Vídeo
- Conecta em câmeras IP via RTSP
- Buffer circular configurável
- Reconexão automática em caso de falha

### ✅ Processamento de Vídeo
- Conversão automática para H.264 + AAC
- Compatibilidade com navegadores web
- Configurações de qualidade personalizáveis

### ✅ Upload e Armazenamento
- Upload automático para Backblaze B2
- URLs públicas geradas automaticamente
- Remoção de arquivos temporários

### ✅ Integração Web
- Envio automático para webhook
- Registro em banco de dados
- API RESTful para integração

## 🛠️ Configurações Avançadas

### Qualidade de Vídeo (CRF)
- **18**: Alta qualidade, arquivos maiores
- **23**: Qualidade padrão (recomendado)
- **28**: Qualidade menor, arquivos menores

### Presets de Encoding
- **ultrafast**: Conversão muito rápida, qualidade menor
- **fast**: Conversão rápida (padrão)
- **medium**: Equilíbrio entre velocidade e qualidade
- **slow**: Conversão lenta, melhor qualidade

### Fontes de Vídeo
```ini
# Câmera IP
SOURCE = rtsp://user:pass@192.168.1.100:554/stream

# Câmera USB local
SOURCE = 0

# Arquivo de vídeo para teste
SOURCE = test_video.mp4
```

## 🔍 Troubleshooting

### FFmpeg não encontrado
Certifique-se de que o `ffmpeg.exe` está na pasta do projeto.

### Erro de conexão RTSP
Verifique:
- IP e porta da câmera
- Credenciais de usuário e senha
- Conectividade de rede

### Erro no upload B2
Verifique suas credenciais no `config.ini`:
- KEY_ID
- APPLICATION_KEY  
- BUCKET_NAME

### Validar configurações
Execute sempre antes de usar:
```bash
python validate_config.py
```

## 📝 Logs

O programa exibe logs detalhados no terminal:
- ✅ Operações bem-sucedidas
- ❌ Erros e falhas
- ⚠️ Avisos importantes
- 🔄 Status de operações

## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request
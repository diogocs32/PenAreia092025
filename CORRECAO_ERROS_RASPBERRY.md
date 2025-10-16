# 🔧 Correção de Erros do Raspberry Pi

## ❌ Erros Identificados

### 1. **Erro de Banco de Dados**
```
Erro ao recuperar uploads pendentes: unable to open database file
```

**Causa:** Diretório `/var/lib/penareia/` sem permissões ou inexistente.

**Sintomas:**
- Sistema não consegue criar ou acessar `queue.db`
- Uploads não são enfileirados
- Perda de histórico de gravações

---

### 2. **Erro de Codec FFmpeg**
```
Error initializing output stream 0:0
Error while opening encoder for output file
Codec AVOption preset specified for output file has not been used
```

**Causa:** Codec H.264 hardware (`h264_v4l2m2m`) não disponível ou mal configurado.

**Sintomas:**
- Vídeos .avi criados mas não convertidos para .mp4
- Conversão falha silenciosamente
- Upload só envia arquivo .avi (sem áudio)

---

## ✅ Solução Rápida (Executar no Raspberry Pi)

### **Método 1: Script Automático** ⭐ RECOMENDADO

```bash
# Baixar atualizações do GitHub
cd ~/PenAreia092025
git pull origin main

# Tornar script executável
chmod +x fix_raspberry_errors.sh

# Executar correções
bash fix_raspberry_errors.sh
```

O script fará:
- ✅ Criar diretórios com permissões corretas
- ✅ Instalar codecs FFmpeg necessários
- ✅ Recriar banco de dados limpo
- ✅ Atualizar dependências Python
- ✅ Verificar codecs disponíveis

---

### **Método 2: Comandos Manuais**

Se preferir executar passo a passo:

#### **Passo 1: Corrigir Permissões**
```bash
# Criar diretórios do sistema
sudo mkdir -p /var/lib/penareia
sudo mkdir -p /var/log/penareia

# Ajustar permissões
sudo chown -R pi:pi /var/lib/penareia
sudo chown -R pi:pi /var/log/penareia
sudo chmod 755 /var/lib/penareia
sudo chmod 755 /var/log/penareia

# Criar diretórios locais
cd ~/PenAreia092025
mkdir -p data logs videos/temp videos/final
chmod 755 data logs videos
```

#### **Passo 2: Instalar Codecs FFmpeg**
```bash
sudo apt update
sudo apt install -y ffmpeg libavcodec-extra libavformat-extra

# Verificar codecs disponíveis
ffmpeg -encoders | grep h264
```

Você deve ver algo como:
```
V..... h264_v4l2m2m     V4L2 mem2mem H.264 encoder wrapper (codec h264)
V..... h264_omx         OpenMAX IL H.264 video encoder (codec h264)
V..... libx264          libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
```

#### **Passo 3: Limpar Banco Antigo**
```bash
cd ~/PenAreia092025
rm -f data/queue.db
rm -f /var/lib/penareia/queue.db
```

#### **Passo 4: Atualizar Código**
```bash
cd ~/PenAreia092025
git pull origin main
source .venv/bin/activate
pip install -r requirements_pi.txt --upgrade
```

#### **Passo 5: Testar Manualmente**
```bash
cd ~/PenAreia092025
source .venv/bin/activate
python app.py
```

Pressione `Ctrl+C` após ver:
```
✅ Conectado à câmera: 704x480 @ 24.00 FPS
Running on http://127.0.0.1:5000
Running on http://192.168.86.77:5000
```

---

## 🎯 Sistema de Fallback de Codecs

O código foi atualizado para tentar **múltiplos codecs automaticamente**:

### **Ordem de Tentativa no Raspberry Pi:**
1. **h264_v4l2m2m** - Hardware encoder (mais rápido, menos CPU)
2. **h264_omx** - Hardware encoder alternativo
3. **libx264** - Software encoder (fallback garantido)

### **No Windows/Linux:**
1. **libx264** - Software encoder padrão

**Vantagem:** Se um codec falhar, o sistema tenta automaticamente o próximo até conseguir converter.

---

## 🔍 Verificação Pós-Correção

### **1. Verificar Diretórios**
```bash
ls -la /var/lib/penareia
ls -la /var/log/penareia
ls -la ~/PenAreia092025/data
ls -la ~/PenAreia092025/logs
```

Deve mostrar permissões `drwxr-xr-x` para o usuário `pi`.

### **2. Verificar FFmpeg**
```bash
ffmpeg -version
ffmpeg -encoders | grep h264
```

Deve listar pelo menos `libx264`.

### **3. Testar Conversão**
```bash
cd ~/PenAreia092025
source .venv/bin/activate
python app.py
```

Abra outro terminal e dispare gravação:
```bash
curl -X POST http://localhost:5000/trigger
```

Verifique se aparece:
```
🔄 Tentando codec: h264_v4l2m2m (Hardware encoder)
✅ Conversão subprocess concluída com h264_v4l2m2m
```

### **4. Verificar Logs**
```bash
# Ver logs em tempo real
tail -f ~/PenAreia092025/logs/app.log

# Ou se usando systemd
sudo journalctl -u penareia -f
```

---

## 📊 Comparação de Codecs

| Codec | Tipo | Velocidade | CPU | Qualidade |
|-------|------|------------|-----|-----------|
| **h264_v4l2m2m** | Hardware | ⚡⚡⚡ Muito rápido | ~5-10% | ✅ Boa |
| **h264_omx** | Hardware | ⚡⚡ Rápido | ~10-15% | ✅ Boa |
| **libx264** | Software | ⚡ Médio | ~40-60% | ✅✅ Excelente |

Para **20 segundos @ 24 FPS (1280x720)**:
- Hardware: ~2-3 segundos de conversão
- Software: ~8-12 segundos de conversão

---

## 🚀 Reiniciar Serviço após Correções

```bash
# Se testou manualmente e funcionou:
sudo systemctl daemon-reload
sudo systemctl restart penareia
sudo systemctl status penareia

# Ver logs
sudo journalctl -u penareia -f
```

---

## ⚠️ Problemas Persistentes?

### **Se FFmpeg continuar falhando:**

1. **Verificar instalação completa:**
```bash
sudo apt install --reinstall ffmpeg libavcodec-extra libavformat-extra libavutil-dev
```

2. **Testar comando direto:**
```bash
# Gravar 5s de teste
ffmpeg -f v4l2 -i /dev/video0 -t 5 -c:v libx264 teste.mp4

# Ver se funciona
ffplay teste.mp4  # ou copiar para Windows e testar
```

3. **Usar modo software forçado:**

Edite `config.ini`:
```ini
[ENCODING]
USE_GPU = False
VIDEO_CODEC = libx264
```

---

## 📋 Checklist Final

Após executar as correções:

- [ ] Diretórios `/var/lib/penareia` e `/var/log/penareia` existem
- [ ] Permissões estão corretas (`pi:pi`)
- [ ] FFmpeg instalado e funcionando
- [ ] Pelo menos codec `libx264` disponível
- [ ] Banco de dados `queue.db` recriado
- [ ] Aplicação inicia sem erros
- [ ] Conversão de vídeo funciona
- [ ] Upload para B2 completa com sucesso

---

## 🎓 Comandos de Diagnóstico

```bash
# Status geral
~/PenAreia092025/fix_raspberry_errors.sh

# Ver o que está rodando
ps aux | grep python

# CPU/RAM
htop

# Temperatura
vcgencmd measure_temp

# Disco
df -h

# Câmera
ls -la /dev/video*

# Últimos vídeos
ls -lht ~/PenAreia092025/videos/final/ | head -5
```

---

**Execute o script e teste novamente! 🍓**

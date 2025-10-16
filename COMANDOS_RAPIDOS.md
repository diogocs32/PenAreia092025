# 🚀 Comandos Rápidos - Raspberry Pi

## 📋 Solução Imediata para Seu Erro

Você está vendo este erro:
```
error: externally managed environment
```

### ✅ Solução (Cole estes comandos):

```bash
# 1. Voltar para o diretório correto
cd ~/PenAreia092025

# 2. Sair do ambiente virtual errado (se estiver ativo)
deactivate

# 3. Remover ambiente errado
rm -rf venu

# 4. Criar ambiente virtual correto
python3 -m venv .venv

# 5. Ativar ambiente virtual
source .venv/bin/activate

# 6. Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements_pi.txt

# 7. Configurar
cp config_pi.ini config.ini
nano config.ini
# Edite as credenciais e salve (Ctrl+O, Enter, Ctrl+X)

# 8. Testar
python app.py
```

---

## 🎯 Comandos Essenciais

### Sempre que abrir um novo terminal:
```bash
cd ~/PenAreia092025
source .venv/bin/activate
```

### Para executar a aplicação manualmente:
```bash
cd ~/PenAreia092025
source .venv/bin/activate
python app.py
```

### Para usar o serviço systemd:
```bash
# Iniciar
sudo systemctl start penareia

# Parar
sudo systemctl stop penareia

# Reiniciar
sudo systemctl restart penareia

# Status
sudo systemctl status penareia

# Logs em tempo real
sudo journalctl -u penareia -f

# Últimas 50 linhas de log
sudo journalctl -u penareia -n 50
```

### Para testar o sistema:
```bash
# Health check
curl http://localhost:5000/health | jq

# Status
curl http://localhost:5000/status | jq

# Trigger (gravar vídeo)
curl -X POST http://localhost:5000/trigger
```

### Para verificar recursos:
```bash
# Temperatura
vcgencmd measure_temp

# CPU/RAM
htop
# (Pressione 'q' para sair)

# Espaço em disco
df -h

# Processos Python
ps aux | grep python
```

---

## 🔍 Verificação Rápida

```bash
# Ambiente virtual está ativo?
echo $VIRTUAL_ENV
# Deve retornar: /home/pi/PenAreia092025/.venv

# Python correto?
which python
# Deve retornar: /home/pi/PenAreia092025/.venv/bin/python

# Pacotes instalados?
pip list | grep -E "flask|opencv|b2sdk"

# FFmpeg instalado?
ffmpeg -version

# Câmera disponível?
ls -la /dev/video*
```

---

## ⚡ Comandos de Manutenção

```bash
# Atualizar código do GitHub
cd ~/PenAreia092025
git pull
source .venv/bin/activate
pip install -r requirements_pi.txt --upgrade
sudo systemctl restart penareia

# Limpar vídeos antigos
rm -rf videos/temp/*
rm -rf videos/final/*

# Ver tamanho dos arquivos
du -sh videos/*

# Backup da configuração
cp config.ini config.ini.backup

# Ver logs do sistema
sudo journalctl -xe

# Reiniciar Raspberry Pi
sudo reboot
```

---

## 🆘 Resolução de Problemas

### Problema: "externally managed environment"
```bash
# Sempre use ambiente virtual!
source .venv/bin/activate
```

### Problema: Câmera não detectada
```bash
# Adicionar usuário ao grupo video
sudo usermod -a -G video $USER
# Fazer logout e login novamente

# Verificar câmera
v4l2-ctl --list-devices
ls -la /dev/video*
```

### Problema: Serviço não inicia
```bash
# Ver erro exato
sudo journalctl -u penareia -n 50 --no-pager

# Testar manualmente
cd ~/PenAreia092025
source .venv/bin/activate
python app.py
# Ver o erro e corrigir
```

### Problema: Sem espaço em disco
```bash
# Ver uso
df -h

# Limpar vídeos
rm -rf videos/temp/*
rm -rf videos/final/*

# Limpar logs antigos
sudo journalctl --vacuum-time=7d
```

### Problema: CPU/Temperatura alta
```bash
# Ver temperatura
vcgencmd measure_temp

# Ver CPU
htop

# Reduzir FPS no config.ini
nano config.ini
# FORCE_FPS = 20
# MAX_WIDTH = 640
# MAX_HEIGHT = 480

# Reiniciar serviço
sudo systemctl restart penareia
```

---

## 📊 Monitoramento

### Dashboard em tempo real:
```bash
# Terminal 1: Logs
sudo journalctl -u penareia -f

# Terminal 2: Recursos
watch -n 2 'vcgencmd measure_temp && free -h && df -h | grep root'

# Terminal 3: Rede
watch -n 5 'curl -s http://localhost:5000/health | jq'
```

### Verificar últimos vídeos:
```bash
ls -lht videos/final/ | head -10
```

### Ver estatísticas do banco:
```bash
sqlite3 data/queue.db "SELECT * FROM system_status;"
```

---

## 🔄 Atualização Rápida

```bash
cd ~/PenAreia092025
git pull
source .venv/bin/activate
pip install -r requirements_pi.txt --upgrade
sudo systemctl restart penareia
sudo systemctl status penareia
```

---

## 📤 Comandos Git (Windows - Desenvolvedor)

### Subir atualizações para o GitHub:
```powershell
# 1. Verificar status e arquivos modificados
git status

# 2. Ver diferenças antes de commitar
git diff

# 3. Adicionar todos os arquivos modificados
git add .

# 4. Fazer commit com mensagem descritiva
git commit -m "feat: Adiciona interface web com botão trigger"

# 5. Enviar para o GitHub
git push origin main

# Ver histórico de commits
git log --oneline -5
```

### Primeira configuração Git (uma vez):
```powershell
# Configurar usuário
git config --global user.name "diogocs32"
git config --global user.email "seu-email@exemplo.com"

# Primeiro push
git push -u origin main
```

---

## 🔄 Atualizar Raspberry Pi após push no GitHub

### Opção 1: Com systemd (Recomendado)
```bash
# 1. Ir para o diretório do projeto
cd ~/PenAreia092025

# 2. Parar o serviço
sudo systemctl stop penareia.service

# 3. Baixar atualizações do GitHub
git pull origin main

# 4. Ativar ambiente virtual
source .venv/bin/activate

# 5. Atualizar dependências (se houver mudanças)
pip install -r requirements_pi.txt --upgrade

# 6. Reiniciar o serviço
sudo systemctl start penareia.service

# 7. Verificar se está rodando
sudo systemctl status penareia.service

# 8. Ver logs em tempo real
sudo journalctl -u penareia.service -f
```

### Opção 2: Teste manual (Sem systemd)
```bash
# 1. Parar processo atual (Ctrl+C se estiver rodando)

# 2. Atualizar código
cd ~/PenAreia092025
git pull origin main

# 3. Ativar ambiente e rodar
source .venv/bin/activate
python app.py
```

### Comando único para atualização completa:
```bash
cd ~/PenAreia092025 && \
sudo systemctl stop penareia && \
git pull origin main && \
source .venv/bin/activate && \
pip install -r requirements_pi.txt --upgrade && \
sudo systemctl start penareia && \
sudo systemctl status penareia
```

---

## 🔍 Verificar versão após atualização

```bash
# Ver último commit
cd ~/PenAreia092025
git log -1 --oneline

# Verificar branch
git branch

# Ver mudanças recentes
git log --oneline -5

# Comparar com remoto
git fetch
git status
```

---

## ✅ Checklist de Instalação

```bash
# ✓ Sistema atualizado?
sudo apt update && sudo apt upgrade -y

# ✓ Ambiente virtual criado?
ls -la .venv/

# ✓ Dependências instaladas?
source .venv/bin/activate
pip list | wc -l
# Deve ter 20+ pacotes

# ✓ FFmpeg instalado?
which ffmpeg

# ✓ Configuração editada?
grep "KEY_ID" config.ini
# Não deve estar vazio

# ✓ Serviço configurado?
sudo systemctl status penareia

# ✓ Aplicação funciona?
curl http://localhost:5000/status
```

---

## 🎓 Resumo dos 3 Comandos Mais Importantes

```bash
# 1. Ativar ambiente virtual (SEMPRE fazer isso primeiro)
source .venv/bin/activate

# 2. Ver logs do serviço
sudo journalctl -u penareia -f

# 3. Testar sistema
curl -X POST http://localhost:5000/trigger
```

---

**Cole estes comandos no seu Raspberry Pi agora! 🍓**

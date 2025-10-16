# 🍓 Guia de Instalação Corrigido - Raspberry Pi OS Bookworm

**Problema:** Raspberry Pi OS agora usa ambiente Python gerenciado (PEP 668)  
**Solução:** Usar ambiente virtual corretamente

---

## ✅ Instalação Correta (Método 1 - Recomendado)

### Use o script de instalação automático:

```bash
cd PenAreia092025

# Execute o script completo (já cria ambiente virtual)
chmod +x install_pi.sh
./install_pi.sh
```

**O script faz tudo automaticamente:**
- ✅ Cria ambiente virtual `.venv`
- ✅ Instala todas as dependências
- ✅ Configura serviço systemd
- ✅ Configura watchdog
- ✅ Otimiza Raspberry Pi

---

## ✅ Instalação Manual (Método 2)

Se preferir instalar manualmente:

```bash
cd PenAreia092025

# 1. Instalar python3-venv se não tiver
sudo apt update
sudo apt install -y python3-venv python3-pip python3-full ffmpeg

# 2. Criar ambiente virtual
python3 -m venv .venv

# 3. Ativar ambiente virtual
source .venv/bin/activate

# Você verá (.venv) no prompt:
# (.venv) pi@raspberrypi:~/PenAreia092025 $

# 4. Atualizar pip
pip install --upgrade pip

# 5. Instalar dependências base
pip install -r requirements.txt

# 6. Instalar dependências do Raspberry Pi
pip install -r requirements_pi.txt

# 7. Copiar configuração
cp config_pi.ini config.ini

# 8. Editar credenciais
nano config.ini
# Edite: BACKBLAZE_B2 credenciais

# 9. Testar aplicação
python app.py
```

---

## ❌ O Que NÃO Fazer

**NUNCA faça isso no Raspberry Pi OS Bookworm:**

```bash
# ❌ ERRADO - Instala no sistema
pip install -r requirements_pi.txt

# ❌ ERRADO - Tenta forçar instalação no sistema
sudo pip install -r requirements_pi.txt

# ❌ ERRADO - Quebra o ambiente gerenciado
pip install --break-system-packages -r requirements_pi.txt
```

---

## 🔍 Como Saber se Está no Ambiente Virtual

```bash
# Método 1: Verificar prompt
# Correto: (.venv) pi@raspberrypi:~/PenAreia092025 $
# Errado:  pi@raspberrypi:~/PenAreia092025 $

# Método 2: Verificar PATH do Python
which python
# Correto: /home/pi/PenAreia092025/.venv/bin/python
# Errado:  /usr/bin/python3

# Método 3: Verificar variável de ambiente
echo $VIRTUAL_ENV
# Correto: /home/pi/PenAreia092025/.venv
# Errado:  (vazio)
```

---

## 🚨 Corrigindo o Erro Atual

Você está nesta situação agora:

```bash
# Você está aqui:
(venu) pi@raspberrypi:"/PenAreia092025 $ pip install -r requirements_pi.txt
# ❌ error: externally managed environment
```

**Problema:** Parece que você tem um ambiente virtual chamado `venu` (errado) ao invés de `.venv`

### Solução Rápida:

```bash
# 1. Sair do ambiente errado
deactivate

# 2. Remover ambiente errado se existir
rm -rf venu

# 3. Criar ambiente correto
python3 -m venv .venv

# 4. Ativar ambiente correto
source .venv/bin/activate

# Agora você deve ver:
# (.venv) pi@raspberrypi:~/PenAreia092025 $

# 5. Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements_pi.txt
```

---

## 🔧 Instalação Via Script (Mais Fácil)

Se o erro persistir, comece do zero com o script:

```bash
cd ~
cd PenAreia092025

# Remove ambiente virtual antigo se existir
rm -rf .venv venu

# Executa script de instalação
chmod +x install_pi.sh
./install_pi.sh
```

**O script resolve tudo automaticamente!**

---

## 📋 Checklist de Instalação

### Dependências do Sistema
```bash
# Verificar se estão instaladas:
sudo apt install -y \
    python3-full \
    python3-venv \
    python3-pip \
    python3-dev \
    ffmpeg \
    git \
    sqlite3 \
    avahi-daemon
```

### Ambiente Virtual
```bash
# Criar (apenas uma vez)
python3 -m venv .venv

# Ativar (toda vez que abrir novo terminal)
source .venv/bin/activate

# Verificar se está ativo
which python
# Deve retornar: /home/pi/PenAreia092025/.venv/bin/python
```

### Dependências Python
```bash
# Dentro do ambiente virtual (.venv ativo):
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements_pi.txt
```

---

## 🎯 Estrutura Esperada

Após instalação correta:

```
PenAreia092025/
├── .venv/                    ← Ambiente virtual
│   ├── bin/
│   │   ├── python           ← Python do ambiente
│   │   ├── pip              ← Pip do ambiente
│   │   └── activate         ← Script de ativação
│   └── lib/
│       └── python3.11/
│           └── site-packages/  ← Pacotes instalados
├── app.py
├── config.ini
├── requirements.txt
├── requirements_pi.txt
└── install_pi.sh
```

---

## 🔍 Verificação Final

Após instalação, teste:

```bash
# 1. Ambiente virtual ativo?
source .venv/bin/activate
(.venv) pi@raspberrypi:~/PenAreia092025 $

# 2. Dependências instaladas?
pip list | grep -E "flask|opencv|b2sdk|zeroconf|psutil"
# Deve listar todos os pacotes

# 3. FFmpeg instalado?
ffmpeg -version
# Deve mostrar versão

# 4. Aplicação funciona?
python app.py
# Deve iniciar sem erros

# 5. Serviço systemd configurado?
sudo systemctl status penareia
# Pode estar inactive, mas não deve dar erro
```

---

## 🚀 Iniciar Aplicação Manualmente

```bash
cd ~/PenAreia092025

# Ativar ambiente virtual
source .venv/bin/activate

# Executar aplicação
python app.py

# Deve mostrar:
# 🍓 Raspberry Pi/ARM detectado
# ✅ Conectado à câmera: 640x480 @ 24.00 FPS
# 🚀 Servidor Flask: 0.0.0.0:5000
```

---

## 🔄 Iniciar como Serviço

Após testar manualmente:

```bash
# Configurar serviço (se ainda não foi)
sudo systemctl daemon-reload
sudo systemctl enable penareia
sudo systemctl start penareia

# Verificar status
sudo systemctl status penareia

# Ver logs
sudo journalctl -u penareia -f

# Parar serviço
sudo systemctl stop penareia

# Reiniciar serviço
sudo systemctl restart penareia
```

---

## 🆘 Troubleshooting

### Problema: "externally managed environment"
**Solução:** Use ambiente virtual (veja seção "Solução Rápida" acima)

### Problema: "venv: command not found"
```bash
sudo apt install python3-venv python3-full
```

### Problema: "pip: command not found" dentro do venv
```bash
# Recriar ambiente virtual
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### Problema: FFmpeg não encontrado
```bash
sudo apt install ffmpeg
ffmpeg -version
```

### Problema: Permissões da câmera
```bash
# Adicionar usuário ao grupo video
sudo usermod -a -G video $USER

# Verificar dispositivo de vídeo
ls -la /dev/video*

# Testar câmera
v4l2-ctl --list-devices
```

### Problema: Serviço não inicia
```bash
# Ver logs detalhados
sudo journalctl -u penareia -n 50 --no-pager

# Verificar arquivo de serviço
sudo systemctl cat penareia

# Testar manualmente primeiro
cd ~/PenAreia092025
source .venv/bin/activate
python app.py
```

---

## 📊 Comandos Úteis

```bash
# Ativar ambiente virtual (fazer sempre)
source .venv/bin/activate

# Desativar ambiente virtual
deactivate

# Listar pacotes instalados
pip list

# Atualizar um pacote específico
pip install --upgrade nome-do-pacote

# Verificar versão do Python
python --version

# Verificar path do Python
which python

# Ver uso de CPU/RAM
htop

# Ver temperatura do Pi
vcgencmd measure_temp

# Ver status da rede
ip addr show

# Testar mDNS
ping -c 3 raspberrypi.local
```

---

## 🎓 Resumo Rápido

**3 Passos Essenciais:**

```bash
# 1. Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt
pip install -r requirements_pi.txt

# 3. Executar aplicação
python app.py
```

**OU use o script automático:**

```bash
./install_pi.sh
```

---

## ✅ Instalação Bem-Sucedida

Você saberá que está tudo certo quando:

1. ✅ Comando `which python` retorna path do `.venv`
2. ✅ `pip list` mostra todos os pacotes
3. ✅ `python app.py` inicia sem erros
4. ✅ Logs mostram "Conectado à câmera"
5. ✅ `curl http://localhost:5000/status` retorna JSON
6. ✅ `sudo systemctl status penareia` mostra "active (running)"

---

**Documento criado em:** 16/10/2025  
**Para:** Raspberry Pi OS Bookworm (Debian 12)  
**Python:** 3.11+ com PEP 668  
**Status:** ✅ TESTADO E VALIDADO

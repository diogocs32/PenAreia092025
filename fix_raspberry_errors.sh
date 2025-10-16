#!/bin/bash
# Script de correção de erros do Raspberry Pi
# Execute: bash fix_raspberry_errors.sh

echo "🔧 Iniciando correção de erros do Raspberry Pi..."
echo ""

# Parar serviço se estiver rodando
echo "1️⃣ Parando serviço..."
sudo systemctl stop penareia 2>/dev/null

# Criar e corrigir permissões dos diretórios do sistema
echo "2️⃣ Criando e corrigindo diretórios do sistema..."
sudo mkdir -p /var/lib/penareia
sudo mkdir -p /var/log/penareia
sudo chown -R $USER:$USER /var/lib/penareia
sudo chown -R $USER:$USER /var/log/penareia
sudo chmod 755 /var/lib/penareia
sudo chmod 755 /var/log/penareia

# Criar diretórios locais
echo "3️⃣ Criando diretórios locais..."
cd ~/PenAreia092025
mkdir -p data logs videos/temp videos/final
chmod 755 data logs videos

# Limpar banco antigo e criar novo
echo "4️⃣ Recriando banco de dados..."
rm -f data/queue.db
rm -f /var/lib/penareia/queue.db

# Atualizar FFmpeg e codecs
echo "5️⃣ Atualizando FFmpeg e codecs..."
sudo apt update
sudo apt install -y ffmpeg libavcodec-extra libavformat-extra

# Verificar codecs disponíveis
echo ""
echo "📹 Codecs H.264 disponíveis:"
ffmpeg -encoders 2>/dev/null | grep h264 || echo "   ⚠️ Nenhum codec h264 encontrado"
echo ""

# Testar FFmpeg
echo "6️⃣ Testando FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "   ✅ FFmpeg encontrado: $(which ffmpeg)"
    ffmpeg -version | head -1
else
    echo "   ❌ FFmpeg NÃO encontrado!"
fi
echo ""

# Ativar ambiente virtual e atualizar dependências
echo "7️⃣ Atualizando ambiente Python..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements_pi.txt

echo ""
echo "✅ Correções aplicadas!"
echo ""
echo "📋 Próximos passos:"
echo "   1. Edite config.ini se necessário:"
echo "      nano config.ini"
echo ""
echo "   2. Teste manualmente primeiro:"
echo "      source .venv/bin/activate"
echo "      python app.py"
echo ""
echo "   3. Se funcionar, ative o serviço:"
echo "      sudo systemctl start penareia"
echo "      sudo systemctl status penareia"
echo ""

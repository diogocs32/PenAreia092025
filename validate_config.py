#!/usr/bin/env python3
"""
Script para validar o arquivo config.ini
"""

import configparser
import sys
import os

def validate_config():
    """Valida o arquivo config.ini"""
    
    if not os.path.exists('config.ini'):
        print("❌ Arquivo config.ini não encontrado!")
        print("💡 Copie config.ini.example para config.ini e configure suas credenciais.")
        return False
    
    config = configparser.ConfigParser()
    
    try:
        config.read('config.ini')
    except Exception as e:
        print(f"❌ Erro ao ler config.ini: {e}")
        return False
    
    # Seções obrigatórias
    required_sections = ['VIDEO', 'WEBHOOK', 'BACKBLAZE_B2', 'SERVER', 'VIDEO_ENCODING']
    
    for section in required_sections:
        if not config.has_section(section):
            print(f"❌ Seção [{section}] não encontrada em config.ini")
            return False
    
    # Validações específicas
    errors = []
    
    # VIDEO
    try:
        buffer_seconds = config.getint('VIDEO', 'BUFFER_SECONDS')
        save_seconds = config.getint('VIDEO', 'SAVE_SECONDS')
        
        if buffer_seconds <= 0:
            errors.append("BUFFER_SECONDS deve ser maior que 0")
        
        if save_seconds <= 0:
            errors.append("SAVE_SECONDS deve ser maior que 0")
            
        if save_seconds > buffer_seconds:
            errors.append("SAVE_SECONDS deve ser menor ou igual a BUFFER_SECONDS")
            
    except ValueError as e:
        errors.append(f"Valores inválidos na seção VIDEO: {e}")
    
    # SERVER
    try:
        port = config.getint('SERVER', 'PORT')
        if port < 1 or port > 65535:
            errors.append("PORT deve estar entre 1 e 65535")
    except ValueError:
        errors.append("PORT deve ser um número inteiro")
    
    # VIDEO_ENCODING
    try:
        crf = config.getint('VIDEO_ENCODING', 'CRF')
        if crf < 0 or crf > 51:
            errors.append("CRF deve estar entre 0 e 51")
    except ValueError:
        errors.append("CRF deve ser um número inteiro")
    
    # Verifica se há credenciais padrão (não configuradas)
    if config.get('BACKBLAZE_B2', 'KEY_ID') == 'your_key_id_here':
        errors.append("Configure suas credenciais do Backblaze B2")
    
    if errors:
        print("❌ Erros encontrados na configuração:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    print("✅ Configuração válida!")
    print("\n📋 Configurações atuais:")
    print(f"   • Fonte de vídeo: {config.get('VIDEO', 'SOURCE')}")
    print(f"   • Buffer: {config.get('VIDEO', 'BUFFER_SECONDS')}s")
    print(f"   • Gravação: {config.get('VIDEO', 'SAVE_SECONDS')}s")
    print(f"   • Servidor: {config.get('SERVER', 'HOST')}:{config.get('SERVER', 'PORT')}")
    print(f"   • Debug: {config.get('SERVER', 'DEBUG')}")
    print(f"   • Codec: {config.get('VIDEO_ENCODING', 'CODEC')}")
    print(f"   • Qualidade (CRF): {config.get('VIDEO_ENCODING', 'CRF')}")
    print(f"   • Bucket B2: {config.get('BACKBLAZE_B2', 'BUCKET_NAME')}")
    
    return True

if __name__ == "__main__":
    if validate_config():
        sys.exit(0)
    else:
        sys.exit(1)
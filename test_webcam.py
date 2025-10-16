import cv2

def test_webcam():
    """Testa se a webcam está disponível"""
    
    print("🔍 Testando webcam...")
    
    # Tenta abrir a webcam
    cap = cv2.VideoCapture(0)
    
    if cap.isOpened():
        print("✅ Webcam disponível!")
        
        # Obtém propriedades da webcam
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"📹 Resolução: {width}x{height}")
        print(f"🎬 FPS: {fps}")
        
        # Tenta capturar um frame
        ret, frame = cap.read()
        if ret:
            print("✅ Captura de frame bem-sucedida!")
            print(f"📐 Shape do frame: {frame.shape}")
        else:
            print("❌ Falha ao capturar frame")
        
        cap.release()
        return True
    else:
        print("❌ Webcam não disponível!")
        print("💡 Verifique se:")
        print("   - A webcam está conectada")
        print("   - Não está sendo usada por outro programa")
        print("   - Os drivers estão instalados")
        return False

if __name__ == "__main__":
    test_webcam()
import streamlit as st
from google.cloud import vision
import json

# Cabeçalho da Página
st.title("OCR de Contracheques (Google Vision API)")
st.write("Envie uma imagem ou PDF escaneado")

# Inicializar o cliente da API do Google Vision
# As credenciais são obtidas automaticamente do secrets.toml
client = vision.ImageAnnotatorClient()

# Upload do arquivo
uploaded_file = st.file_uploader("Arraste e solte o arquivo aqui ou clique para navegar (PNG, JPG, JPEG, PDF)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    # Exibir o nome do arquivo carregado
    st.write(f"Arquivo carregado: {uploaded_file.name}")
    
    try:
        # Ler o arquivo em bytes
        content = uploaded_file.read()
        
        # Configurar para imagens ou PDFs
        if uploaded_file.type == "application/pdf":
            st.error("Atualmente, apenas imagens estão sendo processadas neste exemplo")
        else:  # PNG, JPG, etc.
            image = vision.Image(content=content)
            response = client.text_detection(image=image)
            texts = response.text_annotations

            if texts:
                # Exibir o texto extraído
                st.subheader("Texto detectado:")
                st.write(texts[0].description)
            else:
                st.warning("Nenhum texto detectado na imagem.")
                
    except Exception as e:
        st.error(f"Erro ao processar com o Google Vision: {e}")
        st.error("Certifique-se de que suas credenciais estão configuradas corretamente no arquivo .streamlit/secrets.toml")

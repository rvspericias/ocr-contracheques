import streamlit as st
from google.cloud import vision
import os
import io
from PIL import Image
import base64

# Configuração da credencial da conta de serviço
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_service_account.json"

def extract_text_google(bytes_data):
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=bytes_data)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text if response.full_text_annotation.text else ""

st.set_page_config(page_title="OCR de Contracheques (Google Vision API)")
st.title("📄 OCR de Contracheques (Google Vision API)")

uploaded_file = st.file_uploader("Envie uma imagem ou PDF escaneado", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    st.write(f"Arquivo carregado: {uploaded_file.name}")
    try:
        text = extract_text_google(file_bytes)
        if text.strip():
            st.text_area("Texto extraído:", value=text, height=300)
        else:
            st.warning("Nenhum texto foi detectado pelo OCR.")
    except Exception as e:
        st.error(f"Erro ao processar com Google Vision: {e}")
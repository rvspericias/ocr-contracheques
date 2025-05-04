
import streamlit as st
from google.cloud import vision
import io
from PIL import Image
import base64

def extract_text_google(image_bytes):
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

def main():
    st.title("OCR de Contracheques (Google Vision API)")
    uploaded_file = st.file_uploader("Envie uma imagem ou PDF escaneado", type=["png", "jpg", "jpeg", "pdf"])
    if uploaded_file:
        bytes_data = uploaded_file.read()
        try:
            texto = extract_text_google(bytes_data)
            st.success("Texto extraído com sucesso!")
            st.text_area("Texto extraído:", texto, height=300)
        except Exception as e:
            st.error(f"Erro ao processar com Google Vision: {e}")

if __name__ == "__main__":
    main()

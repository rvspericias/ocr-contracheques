import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
import os
import json
from PyPDF2 import PdfReader
from PIL import Image
import io
import tempfile

st.set_page_config(page_title="Extrator de Contracheques (Google Vision)", layout="wide")

st.title("📄 OCR de Contracheques (Google Vision API)")
st.markdown("Envie um ou mais arquivos de contracheques (PDFs ou imagens):")

uploaded_files = st.file_uploader("Envie múltiplos arquivos", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

# Carrega as credenciais do Google pela variável de segredo
creds_info = json.loads(os.environ["google_service_account.json"])
credentials = service_account.Credentials.from_service_account_info(creds_info)
client = vision.ImageAnnotatorClient(credentials=credentials)


# Função para extrair texto usando Google Vision
def extract_text_google(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text if response.full_text_annotation else ""


# Função para converter páginas do PDF em imagens
def extract_images_from_pdf(pdf_file):
    from pdf2image import convert_from_bytes
    return convert_from_bytes(pdf_file.read(), dpi=300)


# Função para processar cada arquivo
def process_uploaded_file(uploaded_file):
    pages_text = []

    if uploaded_file.name.lower().endswith(".pdf"):
        images = extract_images_from_pdf(uploaded_file)
        for i, image in enumerate(images):
            with tempfile.NamedTemporaryFile(suffix=".png") as temp_img:
                image.save(temp_img.name)
                with open(temp_img.name, "rb") as f:
                    text = extract_text_google(f.read())
                    pages_text.append((f"{uploaded_file.name} - página {i+1}", text))

    else:
        image = Image.open(uploaded_file).convert("RGB")
        with io.BytesIO() as output:
            image.save(output, format="PNG")
            text = extract_text_google(output.getvalue())
            pages_text.append((uploaded_file.name, text))

    return pages_text


# Processa todos os arquivos enviados
if uploaded_files:
    with st.spinner("Processando arquivos..."):
        resultados = []
        for file in uploaded_files:
            resultado = process_uploaded_file(file)
            resultados.extend(resultado)

    # Exibe os resultados
    for pagina, texto in resultados:
        st.subheader(f"📎 {pagina}")
        st.code(texto)

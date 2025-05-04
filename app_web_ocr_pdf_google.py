
import streamlit as st
import requests
import base64
import fitz  # PyMuPDF
from PIL import Image
import io

API_KEY = "AIzaSyBiKpiVS-hxxxIoWmbkYYBtGj-g1zmU0rY"

def extrair_texto_ocr(imagem_bytes):
    content = base64.b64encode(imagem_bytes).decode("utf-8")
    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    body = {
        "requests": [
            {
                "image": {"content": content},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
            }
        ]
    }
    response = requests.post(endpoint, json=body)
    result = response.json()
    if "responses" in result and "fullTextAnnotation" in result["responses"][0]:
        return result["responses"][0]["fullTextAnnotation"]["text"]
    return None

st.set_page_config(page_title="OCR Contracheques Web", layout="centered")
st.title("🧾 OCR de Contracheques (Google Vision API)")

uploaded_file = st.file_uploader("Envie uma imagem ou PDF escaneado", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    st.success("Arquivo carregado com sucesso. Processando...")

    textos_extraidos = []

    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            texto = extrair_texto_ocr(buf.getvalue())
            if texto:
                textos_extraidos.append((i + 1, texto))
    else:
        img_bytes = uploaded_file.read()
        texto = extrair_texto_ocr(img_bytes)
        if texto:
            textos_extraidos.append((1, texto))

    if textos_extraidos:
        st.success(f"{len(textos_extraidos)} página(s) processadas com sucesso!")
        for pag, texto in textos_extraidos:
            st.subheader(f"📄 Página {pag}")
            st.text_area(label="", value=texto, height=300)
    else:
        st.error("⚠️ Nenhum texto foi detectado pelo OCR.")

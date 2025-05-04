
import streamlit as st
import requests
import base64
import fitz
from PIL import Image, ImageEnhance, ImageOps
import io

API_KEY = "AIzaSyBiKpiVS-hxxxIoWmbkYYBtGj-g1zmU0rY"

def extrair_texto_ocr(imagem_bytes):
    content = base64.b64encode(imagem_bytes).decode("utf-8")
    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    body = {"requests": [{"image": {"content": content}, "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}]}
    response = requests.post(endpoint, json=body)
    result = response.json()
    return result.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("text", "")

def preprocessar_imagem(imagem):
    imagem = imagem.convert("L")
    imagem = ImageOps.autocontrast(imagem)
    return ImageEnhance.Contrast(imagem).enhance(2.0)

st.set_page_config(page_title="OCR Debug Contracheques", layout="wide")
st.title("🧪 OCR Debug - Visualização de Imagem PDF + OCR")

uploaded_file = st.file_uploader("Envie um PDF escaneado ou imagem de contracheque", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    st.success("Arquivo carregado com sucesso.")
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for i, page in enumerate(doc):
            st.markdown(f"### Página {i+1}")
            pix = page.get_pixmap(dpi=400)
            imagem = Image.open(io.BytesIO(pix.tobytes("png")))
            imagem_proc = preprocessar_imagem(imagem)
            st.image(imagem_proc, caption="Pré-processada", use_container_width=True)
            buf = io.BytesIO()
            imagem_proc.save(buf, format="PNG")
            texto = extrair_texto_ocr(buf.getvalue())
            if texto:
                st.text_area(f"Texto Página {i+1}", texto, height=300)
            else:
                st.warning("⚠️ Nenhum texto detectado.")

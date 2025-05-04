
import streamlit as st
import requests
import base64
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
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

def preprocessar_imagem(imagem: Image.Image) -> Image.Image:
    imagem = imagem.convert("L")  # escala de cinza
    imagem = ImageOps.autocontrast(imagem)
    imagem = ImageEnhance.Contrast(imagem).enhance(2.0)
    return imagem

st.set_page_config(page_title="OCR Debug Contracheques", layout="wide")
st.title("🧪 OCR Debug - Visualização de Imagem PDF + OCR")

uploaded_file = st.file_uploader("Envie um PDF escaneado ou imagem de contracheque", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.success("Arquivo carregado com sucesso. Processando...")
    textos_extraidos = []

    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for i, page in enumerate(doc):
            st.markdown(f"### Página {i+1}")
            pix = page.get_pixmap(dpi=400)
            imagem = Image.open(io.BytesIO(pix.tobytes("png")))
            imagem_proc = preprocessar_imagem(imagem)

            st.image(imagem_proc, caption="Pré-processada para OCR", use_column_width=True)

            buf = io.BytesIO()
            imagem_proc.save(buf, format="PNG")
            texto = extrair_texto_ocr(buf.getvalue())

            if texto:
                textos_extraidos.append((i + 1, texto))
                st.text_area(f"Texto extraído da Página {i+1}", texto, height=300)
            else:
                st.warning(f"Nenhum texto detectado na página {i+1}")
    else:
        img = Image.open(uploaded_file)
        imagem_proc = preprocessar_imagem(img)
        st.image(imagem_proc, caption="Pré-processada", use_column_width=True)
        buf = io.BytesIO()
        imagem_proc.save(buf, format="PNG")
        texto = extrair_texto_ocr(buf.getvalue())
        if texto:
            st.text_area("Texto extraído", texto, height=300)
        else:
            st.error("Nenhum texto foi detectado.")

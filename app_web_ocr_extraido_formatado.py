
import streamlit as st
import requests
import base64
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import io
import re

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

def extrair_campos(texto: str):
    campos = {
        "Nome": "",
        "Competência": "",
        "Total de Vencimentos": "",
        "Total de Descontos": "",
        "Líquido a Receber": "",
        "Base INSS": "",
        "Base FGTS": "",
        "Base IRRF": "",
        "Salário Base": ""
    }

    linhas = texto.split("\n")

    for linha in linhas:
        l = linha.lower()

        if not campos["Nome"] and "nome" in l:
            campos["Nome"] = linha.split("Nome")[-1].strip(": -")
        if not campos["Competência"] and ("referência" in l or "competência" in l):
            campos["Competência"] = linha.split()[-1]
        if "total de vencimentos" in l:
            campos["Total de Vencimentos"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "total de descontos" in l:
            campos["Total de Descontos"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "líquido a receber" in l:
            campos["Líquido a Receber"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "base" in l and "inss" in l:
            campos["Base INSS"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "base" in l and "fgts" in l:
            campos["Base FGTS"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "base" in l and "irrf" in l:
            campos["Base IRRF"] = re.findall(r"[\d\.,]+", linha)[-1]
        if "salário base" in l:
            campos["Salário Base"] = re.findall(r"[\d\.,]+", linha)[-1]

    return campos

st.set_page_config(page_title="OCR Estruturado de Contracheques", layout="wide")
st.title("📄 Extração Inteligente de Contracheques")

uploaded_file = st.file_uploader("Envie um PDF ou imagem escaneada", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.success("Arquivo carregado. Processando...")

    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for i, page in enumerate(doc):
            st.markdown(f"---\n### Página {i+1}")
            pix = page.get_pixmap(dpi=400)
            imagem = Image.open(io.BytesIO(pix.tobytes("png")))
            imagem_proc = preprocessar_imagem(imagem)
            st.image(imagem_proc, caption="Pré-processada para OCR", use_container_width=True)

            buf = io.BytesIO()
            imagem_proc.save(buf, format="PNG")
            texto = extrair_texto_ocr(buf.getvalue())

            if texto:
                campos = extrair_campos(texto)
                for k, v in campos.items():
                    st.write(f"**{k}:** {v}")
                with st.expander("📝 Texto bruto extraído"):
                    st.text_area("Texto OCR", texto, height=300)
            else:
                st.warning("⚠️ Nenhum texto detectado nesta página.")
    else:
        imagem = Image.open(uploaded_file)
        imagem_proc = preprocessar_imagem(imagem)
        st.image(imagem_proc, caption="Pré-processada", use_container_width=True)
        buf = io.BytesIO()
        imagem_proc.save(buf, format="PNG")
        texto = extrair_texto_ocr(buf.getvalue())
        if texto:
            campos = extrair_campos(texto)
            for k, v in campos.items():
                st.write(f"**{k}:** {v}")
            with st.expander("📝 Texto bruto extraído"):
                st.text_area("Texto OCR", texto, height=300)
        else:
            st.error("Nenhum texto foi detectado.")

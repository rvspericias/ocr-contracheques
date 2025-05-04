
import streamlit as st
import fitz
import io
import base64
import re
from PIL import Image, ImageEnhance, ImageOps
import pytesseract
import requests
import pandas as pd

GOOGLE_VISION_KEY = "AIzaSyBiKpiVS-hxxxIoWmbkYYBtGj-g1zmU0rY"

def preprocess_image(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
    return ImageOps.autocontrast(enhanced)

def ocr_google(image_bytes):
    encoded_image = base64.b64encode(image_bytes).decode()
    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
    body = {
        "requests": [{
            "image": {"content": encoded_image},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
        }]
    }
    try:
        response = requests.post(endpoint, json=body)
        result = response.json()
        return result["responses"][0]["fullTextAnnotation"]["text"]
    except:
        return ""

def ocr_tesseract(image: Image.Image):
    return pytesseract.image_to_string(image, lang="por")

def hybrid_ocr(image: Image.Image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    google_text = ocr_google(buf.getvalue())
    if len(google_text.strip()) > 20:
        return google_text
    return ocr_tesseract(image)

def extrair_dados_por_blocos(texto: str):
    dados = {}
    bloco = "proventos"
    linhas = texto.split("\n")

    nome = re.search(r"(?i)nome[:\s]*([A-ZÇÃÕÉÊÁÍÓ\s]+)", texto)
    comp = re.search(r"(?i)(referência|compet[êe]ncia)[\s:]*([A-Za-z]{3,}/?\d{2,4})", texto)
    dados["Nome"] = nome.group(1).strip() if nome else ""
    dados["Competência"] = comp.group(2).strip() if comp else ""

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        l = linha.lower()

        if "total de vencimentos" in l:
            bloco = "descontos"
            continue
        elif "total de descontos" in l:
            bloco = "totais"
            continue

        match = re.match(r"(.{4,60}?)\s{1,5}([\d,.]+)$", linha)
        if match:
            rubrica = match.group(1).strip().title()
            valor = match.group(2).replace(".", "").replace(",", ".")
            try:
                valor_float = float(valor)
                if bloco == "proventos":
                    dados[f"[PRO] {rubrica}"] = valor_float
                elif bloco == "descontos":
                    dados[f"[DES] {rubrica}"] = valor_float
                else:
                    dados[rubrica] = valor_float
            except:
                pass
    return dados

st.set_page_config("OCR Contracheques IA - MVP 2.0", layout="wide")
st.title("📑 MVP 2.0 – OCR Inteligente de Contracheques com IA")

arquivos = st.file_uploader("Envie múltiplos arquivos (PDF ou imagens)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if arquivos:
    resultados = []
    for arquivo in arquivos:
        st.markdown(f"### 📄 {arquivo.name}")
        if arquivo.type == "application/pdf":
            doc = fitz.open(stream=arquivo.read(), filetype="pdf")
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=400)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                proc = preprocess_image(img)
                texto = hybrid_ocr(proc)
                dados = extrair_dados_por_blocos(texto)
                if dados:
                    dados["Arquivo"] = arquivo.name
                    dados["Página"] = i + 1
                    resultados.append(dados)
        else:
            img = Image.open(arquivo)
            proc = preprocess_image(img)
            texto = hybrid_ocr(proc)
            dados = extrair_dados_por_blocos(texto)
            if dados:
                dados["Arquivo"] = arquivo.name
                dados["Página"] = 1
                resultados.append(dados)

    if resultados:
        df = pd.DataFrame(resultados)
        competencias = sorted(df["Competência"].dropna().unique())
        competencia_sel = st.multiselect("Filtrar por competência (opcional)", competencias, default=competencias)

        if competencia_sel:
            df = df[df["Competência"].isin(competencia_sel)]

        colunas_disponiveis = [col for col in df.columns if col not in ["Nome", "Competência", "Arquivo", "Página"]]
        colunas_selecionadas = st.multiselect("Selecione as rubricas que deseja exportar", colunas_disponiveis, default=colunas_disponiveis)

        if colunas_selecionadas:
            df_final = df[["Nome", "Competência"] + colunas_selecionadas]
            st.dataframe(df_final, use_container_width=True)
            buffer = io.BytesIO()
            df_final.to_excel(buffer, index=False)
            st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="contracheques_mvp2.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Nenhum dado extraído dos arquivos enviados.")

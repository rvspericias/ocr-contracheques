
import streamlit as st
import requests
import base64
import fitz
import io
import pandas as pd
import re
from PIL import Image, ImageEnhance, ImageOps

API_KEY = "AIzaSyBiKpiVS-hxxxIoWmbkYYBtGj-g1zmU0rY"

def ocr_google(image_bytes):
    encoded_image = base64.b64encode(image_bytes).decode()
    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    body = {
        "requests": [{
            "image": {"content": encoded_image},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
        }]
    }
    response = requests.post(endpoint, json=body)
    result = response.json()
    try:
        return result["responses"][0]["fullTextAnnotation"]["text"]
    except:
        return ""

def preprocess_image(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    contrast = ImageEnhance.Contrast(gray).enhance(2.0)
    return ImageOps.autocontrast(contrast)

def extrair_dados(texto):
    dados = {}
    nome = re.search(r"(?i)nome[:\s]*([A-Z\s]+)", texto)
    comp = re.search(r"(?i)(referência|compet[êe]ncia)[\s:]*([A-Za-z]{3,}/?\d{2,4})", texto)
    dados["Nome"] = nome.group(1).strip() if nome else ""
    dados["Competência"] = comp.group(2).strip() if comp else ""

    linhas = texto.split("\n")
    for linha in linhas:
        if any(x in linha.lower() for x in ["provento", "desconto", "descrição"]):
            continue
        match = re.match(r"(.{5,60}?)\s{1,3}[\d,.]{1,3}\s{1,3}([\d,.]+)$", linha.strip())
        if match:
            rubrica = match.group(1).strip().title()
            valor = match.group(2).replace(".", "").replace(",", ".")
            try:
                dados[rubrica] = float(valor)
            except:
                pass
    return dados

def filtrar_por_competencia(lista, inicio, fim):
    def mes_ano_valido(comp):
        try:
            partes = comp.replace("-", "/").split("/")
            if len(partes) == 2:
                m, a = partes
                if len(a) == 2:
                    a = "20" + a
                return int(a) * 100 + int(mes_nome_para_numero(m))
        except:
            return 0
        return 0

    ini = mes_ano_valido(inicio)
    fim = mes_ano_valido(fim)
    return [d for d in lista if ini <= mes_ano_valido(d.get("Competência", "")) <= fim]

def mes_nome_para_numero(mes):
    meses = {
        "janeiro":1,"fevereiro":2,"março":3,"abril":4,"maio":5,"junho":6,
        "julho":7,"agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12
    }
    if mes.lower() in meses:
        return meses[mes.lower()]
    if mes.isdigit():
        return int(mes)
    try:
        return int(mes[:2])
    except:
        return 0

st.set_page_config(page_title="Extrator Inteligente de Contracheques", layout="wide")
st.title("📄 OCR Interativo com Exportação para Excel")

uploaded_file = st.file_uploader("Envie o PDF ou imagem com os contracheques", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    st.success("Arquivo carregado. Processando...")
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    dados_extraidos = []
    for page in doc:
        pix = page.get_pixmap(dpi=400)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        proc = preprocess_image(img)
        buf = io.BytesIO()
        proc.save(buf, format="PNG")
        texto = ocr_google(buf.getvalue())
        dados = extrair_dados(texto)
        if dados:
            dados_extraidos.append(dados)

    if dados_extraidos:
        todas_rubricas = set()
        for item in dados_extraidos:
            todas_rubricas.update(set(item.keys()) - {"Nome", "Competência"})
        rubricas_sel = st.multiselect("Selecione as parcelas que deseja incluir", sorted(todas_rubricas))
        col1, col2 = st.columns(2)
        with col1:
            inicio = st.text_input("Competência inicial (MM/AAAA)", "01/2022")
        with col2:
            fim = st.text_input("Competência final (MM/AAAA)", "12/2025")

        if rubricas_sel and st.button("Gerar pré-visualização"):
            dados_filtrados = filtrar_por_competencia(dados_extraidos, inicio, fim)
            tabela = []
            for item in dados_filtrados:
                linha = {
                    "Nome": item.get("Nome", ""),
                    "Competência": item.get("Competência", "")
                }
                for rubrica in rubricas_sel:
                    linha[rubrica] = item.get(rubrica, 0)
                tabela.append(linha)
            df = pd.DataFrame(tabela)
            st.data_editor(df, use_container_width=True, num_rows="dynamic", column_order=df.columns.tolist())
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="contracheques.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

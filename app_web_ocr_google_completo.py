
import streamlit as st
from google.cloud import vision
from PIL import Image
import pandas as pd
import io
import base64
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📄 OCR de Contracheques com Google Vision")

st.markdown("Envie múltiplos arquivos **PDF ou imagens (PNG, JPG)** contendo contracheques para extrair dados estruturados.")

uploaded_files = st.file_uploader("Envie múltiplos arquivos (PDF ou imagens)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

compet_ini = st.text_input("Filtrar por competência inicial (MM/AAAA)", "")
compet_fim = st.text_input("Filtrar por competência final (MM/AAAA)", "")

client = vision.ImageAnnotatorClient()

def extract_text_google(img_bytes):
    image = vision.Image(content=img_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text if response.full_text_annotation.text else ""

def extrair_dados(texto, nome_arquivo):
    import re
    rubricas = {}
    nome = ""
    comp = ""

    linhas = texto.split("\n")
    for linha in linhas:
        m = re.match(r"(.*?)(?:\s{2,}|\t+)([\d.,]+)$", linha.strip())
        if m:
            chave = m.group(1).strip().title()
            valor = m.group(2).replace(".", "").replace(",", ".")
            try:
                rubricas[chave] = float(valor)
            except:
                pass

    m_nome = re.search(r"(?i)nome[:\s]*([A-ZÇÃÕÉÊÁÍÓ\s]+)", texto)
    m_comp = re.search(r"(?i)(refer[êe]ncia|compet[êe]ncia)[:\s]*([A-Za-z]{3,}/?\d{2,4})", texto)

    if m_nome: nome = m_nome.group(1).strip()
    if m_comp: comp = m_comp.group(2).strip()

    dados = {"Arquivo": nome_arquivo, "Nome": nome, "Competência": comp}
    dados.update(rubricas)
    return dados

registros = []

if uploaded_files:
    with st.spinner("🔍 Extraindo texto dos arquivos..."):
        for arquivo in uploaded_files:
            nome = arquivo.name
            bytes_data = arquivo.read()
            texto = extract_text_google(bytes_data)
            dados = extrair_dados(texto, nome)
            registros.append(dados)

    if registros:
        df = pd.DataFrame(registros)
        colunas_disponiveis = list(df.columns[3:])

        st.markdown("### ✅ Rubricas disponíveis")
        rubricas_escolhidas = st.multiselect("Selecione as rubricas que deseja exportar", options=colunas_disponiveis)

        if rubricas_escolhidas:
            df_filtrado = df[["Arquivo", "Nome", "Competência"] + rubricas_escolhidas]

            if compet_ini and compet_fim:
                def parse_comp(c):
                    import re
                    meses = {
                        "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04", "maio": "05", "junho": "06",
                        "julho": "07", "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
                    }
                    c = c.lower()
                    for mes_nome, mes_num in meses.items():
                        if mes_nome in c:
                            ano = re.search(r"\d{4}", c)
                            if ano: return f"{mes_num}/{ano.group(0)}"
                    return c

                df_filtrado["CompetênciaNum"] = df_filtrado["Competência"].apply(parse_comp)
                df_filtrado = df_filtrado[
                    (df_filtrado["CompetênciaNum"] >= compet_ini) &
                    (df_filtrado["CompetênciaNum"] <= compet_fim)
                ]

            st.markdown("### 🧾 Pré-visualização da planilha")
            st.dataframe(df_filtrado.drop(columns=["CompetênciaNum"], errors="ignore"), use_container_width=True)

            buffer = io.BytesIO()
            df_filtrado.drop(columns=["CompetênciaNum"], errors="ignore").to_excel(buffer, index=False)
            b64 = base64.b64encode(buffer.getvalue()).decode()
            st.markdown(f"📥 [Clique aqui para baixar Excel](data:application/octet-stream;base64,{b64})", unsafe_allow_html=True)
        else:
            st.warning("Selecione pelo menos uma rubrica para continuar.")
    else:
        st.warning("Nenhum dado foi extraído dos arquivos enviados.")

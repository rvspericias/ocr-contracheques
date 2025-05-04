import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
import pandas as pd
import tempfile
import os
import json
from PIL import Image

def extract_text_google(file_bytes):
    # Carrega as credenciais do st.secrets
    credentials_info = json.loads(st.secrets["google_service_account.json"])
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    image = vision.Image(content=file_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(f"Erro da API: {response.error.message}")

    return response.full_text_annotation.text

def process_uploaded_file(uploaded_file):
    file_bytes = uploaded_file.read()
    return extract_text_google(file_bytes)

def parse_contracheque_text(texto):
    linhas = texto.splitlines()
    dados = []
    lendo_proventos = False

    for linha in linhas:
        if "Proventos" in linha:
            lendo_proventos = True
            continue
        if lendo_proventos:
            if "TOTAL DE VENCIMENTOS" in linha or "Descontos" in linha:
                break
            if any(c.isdigit() for c in linha):
                dados.append(linha)

    resultado = []
    for linha in dados:
        partes = linha.rsplit(" ", 2)
        if len(partes) == 3:
            descricao, qtde, valor = partes
            resultado.append({"Descrição": descricao.strip(), "Qtde": qtde.strip(), "Valor": valor.strip()})

    return pd.DataFrame(resultado)

def main():
    st.title("OCR de Contracheques (Google Vision API)")
    st.write("Envie uma imagem ou PDF escaneado")

    uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg", "pdf"])

    if uploaded_file is not None:
        try:
            with st.spinner("Processando o arquivo com OCR do Google..."):
                texto_extraido = process_uploaded_file(uploaded_file)
                df = parse_contracheque_text(texto_extraido)

                st.success("Texto extraído com sucesso!")
                st.dataframe(df)

                if not df.empty:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Baixar como CSV",
                        data=csv,
                        file_name='proventos_extraidos.csv',
                        mime='text/csv'
                    )
        except Exception as e:
            st.error(f"Erro ao processar com Google Vision: {e}")

if __name__ == "__main__":
    main()

import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
import pandas as pd
import io
import base64
import json

# Configuração da página
st.set_page_config(page_title="OCR de Contracheques", layout="wide")

def extract_text_google(file_bytes):
    try:
        # Carrega as credenciais do gerenciador de segredos
        credentials_info = st.secrets["google_service_account"]
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        
        # Processo OCR
        image = vision.Image(content=file_bytes)
        response = client.document_text_detection(image=image)
        
        if response.error.message:
            raise Exception(f"Erro da API: {response.error.message}")
            
        return response.full_text_annotation.text
    except Exception as e:
        st.error(f"Erro ao processar com Google Vision: {str(e)}")
        return None

def parse_contracheque_text(texto):
    if not texto:
        return pd.DataFrame()
    
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
    st.write("Envie uma imagem ou PDF escaneado do contracheque")

    uploaded_file = st.file_uploader("Selecione o arquivo", type=["png", "jpg", "jpeg", "pdf"])

    if uploaded_file is not None:
        # Exibir prévia do arquivo
        st.subheader("Arquivo enviado:")
        file_details = {"Nome": uploaded_file.name, "Tipo": uploaded_file.type, "Tamanho": f"{uploaded_file.size / 1024:.2f} KB"}
        st.write(file_details)
        
        try:
            with st.spinner("🔍 Processando o arquivo com OCR do Google..."):
                file_bytes = uploaded_file.read()
                texto_extraido = extract_text_google(file_bytes)
                
                if texto_extraido:
                    # Exibir texto extraído em formato raw
                    with st.expander("Ver texto extraído (raw)"):
                        st.text(texto_extraido)
                    
                    # Processar o texto para estruturar os dados
                    df = parse_contracheque_text(texto_extraido)

                    if not df.empty:
                        st.success("✅ Dados extraídos com sucesso!")
                        st.dataframe(df)
                        
                        # Exportar para CSV
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Baixar como CSV",
                            data=csv,
                            file_name='proventos_extraidos.csv',
                            mime='text/csv'
                        )
                        
                        # Exportar para Excel
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df.to_excel(writer, sheet_name='Proventos', index=False)
                        buffer.seek(0)
                        
                        # Botão de download Excel
                        b64 = base64.b64encode(buffer.getvalue()).decode()
                        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="proventos_extraidos.xlsx">📊 Baixar como Excel</a>'
                        st.markdown(href, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Não foi possível extrair proventos deste documento. Verifique o formato.")
                else:
                    st.error("❌ Falha na extração de texto. Verifique o formato do arquivo.")
        except Exception as e:
            st.error(f"❌ Erro durante o processamento: {str(e)}")

if __name__ == "__main__":
    main()

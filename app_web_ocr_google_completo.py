import streamlit as st
from google.cloud import vision
import io
import pandas as pd
from PIL import Image
import tempfile
import os
from pdf2image import convert_from_bytes

# Configuração da página Streamlit
st.set_page_config(
    page_title="OCR de Contracheques - Google Vision",
    page_icon="📊",
    layout="wide"
)

# Título e descrição da aplicação
st.title("Extrator de Contracheques")
st.subheader("Extraia informações de contracheques usando OCR")
st.write("Faça upload de uma imagem ou PDF de contracheque para extrair informações.")

# Função para processar texto extraído de um contracheque
def processar_texto_contracheque(texto):
    """
    Processa o texto bruto extraído do OCR para organizar os dados do contracheque.
    """
    # Dividir o texto em linhas
    linhas = texto.split('\n')
    
    # Dicionário para armazenar informações relevantes
    dados = {
        "Item": [],
        "Valor": []
    }
    
    # Procurar por padrões comuns em contracheques (exemplo simplificado)
    for linha in linhas:
        # Ignorar linhas vazias
        if not linha.strip():
            continue
            
        # Procurar por padrões de "Item: Valor"
        if ':' in linha:
            partes = linha.split(':', 1)
            item = partes[0].strip()
            valor = partes[1].strip() if len(partes) > 1 else ""
            dados["Item"].append(item)
            dados["Valor"].append(valor)
        # Procurar por padrões onde há valores monetários
        elif 'R$' in linha or ',' in linha and any(c.isdigit() for c in linha):
            # Tentativa de separar descrição e valor
            for i, char in enumerate(reversed(linha)):
                if char.isdigit() or char in ',.':
                    pos = len(linha) - i
                    # Verificar se há um espaço antes para separar descrição e valor
                    while pos > 0 and linha[pos-1] != ' ' and not linha[pos-1].isalpha():
                        pos -= 1
                    if pos > 0:
                        item = linha[:pos].strip()
                        valor = linha[pos:].strip()
                        dados["Item"].append(item)
                        dados["Valor"].append(valor)
                        break
        else:
            # Para outras linhas, considerar como item sem valor específico
            dados["Item"].append(linha.strip())
            dados["Valor"].append("")
    
    # Criar um DataFrame com os dados extraídos
    return pd.DataFrame(dados)

# Função para extrair texto de uma imagem usando o Google Vision API
def extrair_texto_imagem(conteudo_imagem):
    """
    Usa o Google Vision API para extrair texto de uma imagem.
    """
    # Inicializar o cliente Vision API (usa automaticamente o secrets.toml)
    client = vision.ImageAnnotatorClient()
    
    # Preparar a imagem para o Vision API
    image = vision.Image(content=conteudo_imagem)
    
    # Realizar o OCR na imagem
    response = client.text_detection(image=image)
    
    # Verificar se houve erro
    if response.error.message:
        raise Exception(f"Erro na API do Google Vision: {response.error.message}")
    
    # Extrair o texto completo
    if not response.text_annotations:
        return ""
    return response.text_annotations[0].description

# Função para processar arquivos PDF
def processar_pdf(pdf_bytes):
    """
    Converte PDF para imagens e então extrai texto.
    """
    # Criar diretório temporário para armazenar as imagens
    with tempfile.TemporaryDirectory() as path:
        # Converter PDF para imagens
        images = convert_from_bytes(pdf_bytes, dpi=300, output_folder=path)
        
        # Extrair texto de cada página
        texto_completo = ""
        for i, imagem in enumerate(images):
            # Converter imagem PIL para bytes
            img_byte_arr = io.BytesIO()
            imagem.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            # Extrair texto da imagem
            texto_pagina = extrair_texto_imagem(img_byte_arr.getvalue())
            texto_completo += f"\n--- Página {i+1} ---\n" + texto_pagina
        
        return texto_completo

# Função principal da aplicação
def main():
    # Upload de arquivo
    arquivo = st.file_uploader(
        "Faça upload de um contracheque (PDF, PNG, JPG)", 
        type=["pdf", "png", "jpg", "jpeg"]
    )
    
    if arquivo is not None:
        # Exibir informações do arquivo
        st.write(f"**Arquivo carregado:** {arquivo.name}")
        st.write(f"**Tipo:** {arquivo.type}")
        
        # Criar colunas para organização
        col1, col2 = st.columns(2)
        
        try:
            # Ler o conteúdo do arquivo
            conteudo = arquivo.read()
            
            # Processar conforme o tipo de arquivo
            if arquivo.type == "application/pdf":
                with col1:
                    st.subheader("Visualização do PDF")
                    st.warning("Pré-visualização limitada. Processando todas as páginas.")
                    
                # Processar o PDF
                texto_extraido = processar_pdf(conteudo)
            else:  # Processar imagem
                # Exibir a imagem
                with col1:
                    st.subheader("Imagem Carregada")
                    imagem = Image.open(io.BytesIO(conteudo))
                    st.image(imagem, width=400)
                
                # Extrair texto
                texto_extraido = extrair_texto_imagem(conteudo)
            
            # Processar o texto extraído
            with col2:
                st.subheader("Texto Extraído (Bruto)")
                st.text_area("", texto_extraido, height=300)
            
            # Processar e exibir os dados estruturados
            st.subheader("Dados Estruturados")
            df_dados = processar_texto_contracheque(texto_extraido)
            st.dataframe(df_dados)
            
            # Opções para download
            if not df_dados.empty:
                st.subheader("Download dos Dados")
                
                # Download como CSV
                csv = df_dados.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name='contracheque_dados.csv',
                    mime='text/csv',
                )
                
                # Download como Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_dados.to_excel(writer, sheet_name='Contracheque', index=False)
                excel_data = output.getvalue()
                st.download_button(
                    label="Download Excel",
                    data=excel_data,
                    file_name='contracheque_dados.xlsx',
                    mime='application/vnd.ms-excel',
                )
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
            st.error("Verifique se o arquivo .streamlit/secrets.toml está configurado corretamente.")
    
    # Informações adicionais
    with st.expander("Sobre esta aplicação"):
        st.write("""
        ## Como funciona
        1. **Upload do arquivo**: Faça upload de um contracheque como PDF ou imagem.
        2. **Processamento OCR**: O Google Vision API é usado para extrair texto do documento.
        3. **Estruturação de dados**: O texto extraído é analisado para identificar itens e valores.
        4. **Download dos resultados**: Faça download dos dados em formato CSV ou Excel.
        
        ## Limitações
        - A qualidade da extração depende da clareza do documento original.
        - Contracheques com formatos muito diferentes podem exigir ajustes no processamento.
        - O reconhecimento de padrões é baseado em formatos comuns, mas pode não capturar todos os itens.
        """)

# Executar a aplicação
if __name__ == "__main__":
    main()

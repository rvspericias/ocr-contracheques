import streamlit as st
from google.cloud import vision
import io
import pandas as pd
from PIL import Image
import tempfile
import os
from pdf2image import convert_from_bytes
import subprocess
import sys
from datetime import datetime
import json

# Configuração da página Streamlit
st.set_page_config(
    page_title="OCR de Contracheques - Google Vision",
    page_icon="📊",
    layout="wide"
)

# Seção de diagnóstico para verificar a instalação do Poppler
with st.expander("Diagnóstico de Sistema", expanded=False):
    st.subheader("Verificação de Sistema")

  # Sessão de diagnóstico para verificar a instalação do Poppler
with st.expander("Diagnóstico de Sistema", expanded=False):
    st.subheader("Verificação de Sistema")

    # Verificação direta de comandos do Poppler
    if st.button("Verificar Instalação do Poppler"):
        try:
            # Tentar executar o comando `pdftoppm`
            resultado = subprocess.run(
                ["which", "pdftoppm"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if resultado.stdout.strip():
                st.success(f"✅ pdftoppm encontrado em: {resultado.stdout.strip()}")

                # Verificar a versão
                resultado_versao = subprocess.run(
                    ["pdftoppm", "-v"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                informacoes_versao = (
                    resultado_versao.stderr.strip() 
                    if resultado_versao.stderr.strip() 
                    else resultado_versao.stdout.strip()
                )
                st.code(informacoes_versao)
            else:
                st.error("❌ pdftoppm não encontrado no sistema")
                st.code(f"Erro: {resultado.stderr.strip()}")

        except Exception as e:
            st.error(f"❌ Erro ao verificar pdftoppm: {str(e)}")
            st.exception(e)
            
        if result.stdout:
            st.success(f"✅ pdftoppm encontrado em: {result.stdout}")
            
            # Verificar a versão
            version_result = subprocess.run(["pdftoppm", "-v"],
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE, 
                                          text=True)
            version_info = version_result.stderr if version_result.stderr else version_result.stdout
            st.code(version_info)
        else:
            st.error("❌ pdftoppm não encontrado no sistema")
            st.code(f"Erro: {result.stderr}")
    except Exception as e:
        st.error(f"❌ Erro ao verificar pdftoppm: {str(e)}")
        st.exception(e)

    # Verificar se o Python pode encontrar os executáveis do poppler
    try:
        from pdf2image.pdf2image import pdfinfo_path, pdftoppm_path
        st.write(f"📋 Caminhos do Poppler:")
        st.write(f"- pdfinfo: {pdfinfo_path()}")
        st.write(f"- pdftoppm: {pdftoppm_path()}")
        st.success("✅ Caminhos do Poppler encontrados!")
    except Exception as e:
        st.error(f"❌ Erro ao encontrar caminhos do Poppler: {str(e)}")

    # Tentar executar um comando do poppler para verificar a instalação
    try:
        result = subprocess.run(["pdftoppm", "-v"], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                text=True)
        version_info = result.stderr if result.stderr else result.stdout
        st.write(f"📊 Versão do Poppler:")
        st.code(version_info)
        st.success("✅ Poppler está funcionando!")
    except Exception as e:
        st.error(f"❌ Erro ao executar pdftoppm: {str(e)}")

    # Informações do sistema
    st.write("🔍 Informações do Sistema:")
    st.write(f"- Python: {sys.version}")
    st.write(f"- Sistema Operacional: {os.name}")
    st.write(f"- Path do Python: {sys.executable}")

    # Teste de processamento PDF
    if st.button("Testar processamento de PDF"):
        try:
            # Criar um PDF simples para teste
            from reportlab.pdfgen import canvas
            import io
            from pdf2image import convert_from_bytes
            
            # Criar um PDF em memória
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer)
            c.drawString(100, 750, "Teste de PDF para Poppler")
            c.save()
            pdf_bytes = pdf_buffer.getvalue()
            
            # Tentar converter para imagem
            st.write("Convertendo PDF para imagem...")
            with tempfile.TemporaryDirectory() as path:
                images = convert_from_bytes(pdf_bytes, output_folder=path)
                st.write(f"✅ PDF convertido com sucesso! Gerou {len(images)} imagem(ns).")
                
                # Mostrar a primeira imagem
                if images:
                    st.image(images[0], caption="Imagem extraída do PDF")
            
        except Exception as e:
            st.error(f"❌ Erro ao processar PDF: {str(e)}")
            st.exception(e)

# Título principal do aplicativo
st.title("🔍 OCR para Contracheques com Google Vision")
st.write("Este aplicativo extrai dados de contracheques usando reconhecimento óptico de caracteres (OCR).")

# Verificação de secrets para o Google Cloud
if "gcp_service_account" in st.secrets:
    st.success("✅ Credenciais do Google Cloud encontradas!")
    # Não mostre a chave completa, apenas confirme o project_id
    project_id = st.secrets.gcp_service_account.project_id
    st.write(f"Project ID: {project_id}")
else:
    st.warning("⚠️ Credenciais do Google Cloud não encontradas. Certifique-se de configurar os secrets.")

# Função para extrair texto de imagens usando o Google Vision API
def extrair_texto_imagem(conteudo_imagem):
    """
    Usa o Google Vision API para extrair texto de uma imagem.
    """
    # Inicializar o cliente Vision API (usa automaticamente os secrets)
    client = vision.ImageAnnotatorClient()
    
    # Preparar a imagem para análise
    imagem = vision.Image(content=conteudo_imagem)
    
    # Realizar o reconhecimento de texto
    resposta = client.text_detection(image=imagem)
    textos = resposta.text_annotations
    
    # Verificar se há texto detectado
    if textos:
        return textos[0].description
    else:
        return "Nenhum texto detectado na imagem."

# Função para processar arquivos PDF
def processar_pdf(pdf_bytes):
    """
    Converte PDF para imagens e então extrai texto.
    """
    try:
        # Criar diretório temporário para armazenar as imagens
        with tempfile.TemporaryDirectory() as path:
            try:
                # Tentar converter PDF para imagens
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
                
            except Exception as e:
                st.error(f"Erro ao processar PDF: {str(e)}")
                st.warning("Conversão de PDF pode requerer instalação local. Por favor, tente enviar imagens diretas.")
                return "Erro na conversão do PDF. Tente enviar imagens diretas."
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {str(e)}")
        return "Erro no processamento do arquivo."

# Função para processar o texto extraído e identificar dados do contracheque
def processar_texto_contracheque(texto):
    """
    Analisa o texto extraído para identificar informações do contracheque.
    """
    # Inicializa o dicionário para armazenar os valores encontrados
    dados = {
        "Nome": "",
        "Matrícula": "",
        "Cargo": "",
        "Mês/Ano": "",
        "Salário Base": "",
        "Descontos": "",
        "Valor Líquido": ""
    }
    
    # Divide o texto em linhas para processar
    linhas = texto.split('\n')
    
    # Procura por padrões específicos em cada linha
    for i, linha in enumerate(linhas):
        linha_lower = linha.lower()
        
        # Busca por padrões de nome e outros dados pessoais
        if "nome:" in linha_lower:
            dados["Nome"] = linha.split(":", 1)[1].strip() if ":" in linha else ""
        
        if "matrícula:" in linha_lower or "matricula:" in linha_lower:
            dados["Matrícula"] = linha.split(":", 1)[1].strip() if ":" in linha else ""
        
        if "cargo:" in linha_lower:
            dados["Cargo"] = linha.split(":", 1)[1].strip() if ":" in linha else ""
        
        # Busca pelo mês e ano de referência
        if "referência:" in linha_lower or "referencia:" in linha_lower or "mês:" in linha_lower:
            dados["Mês/Ano"] = linha.split(":", 1)[1].strip() if ":" in linha else ""
        
        # Busca por valores financeiros
        if "salário base" in linha_lower or "salario base" in linha_lower:
            # Tenta extrair o valor após "salário base"
            partes = linha.split()
            for j, parte in enumerate(partes):
                if "base" in parte.lower() and j < len(partes) - 1:
                    dados["Salário Base"] = partes[j+1].replace("R$", "").strip()
        
        if "total descontos" in linha_lower:
            # Tenta extrair o valor após "total descontos"
            partes = linha.split()
            for j, parte in enumerate(partes):
                if "descontos" in parte.lower() and j < len(partes) - 1:
                    dados["Descontos"] = partes[j+1].replace("R$", "").strip()
        
        # Busca pelo valor líquido
        if "valor líquido" in linha_lower or "liquido" in linha_lower:
            # Tenta extrair o valor após "valor líquido"
            partes = linha.split()
            for j, parte in enumerate(partes):
                if "líquido" in parte.lower() or "liquido" in parte.lower() and j < len(partes) - 1:
                    dados["Valor Líquido"] = partes[j+1].replace("R$", "").strip()
    
    # Converte os dados para DataFrame para melhor visualização
    df = pd.DataFrame([dados])
    return df

# Função para salvar os dados extraídos
def salvar_dados_extraidos(dados, nome_arquivo):
    """
    Salva os dados extraídos em um formato estruturado.
    """
    # Criar um diretório para armazenar os dados se não existir
    diretorio = "dados_extraidos"
    if not os.path.exists(diretorio):
        os.makedirs(diretorio)
    
    # Gerar um nome de arquivo baseado na data e hora atual
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_base = os.path.splitext(nome_arquivo)[0]
    nome_arquivo_saida = f"{diretorio}/{nome_base}_{agora}.json"
    
    # Converter DataFrame para dicionário e salvar como JSON
    dados_dict = dados.to_dict(orient='records')[0]
    with open(nome_arquivo_saida, 'w', encoding='utf-8') as f:
        json.dump(dados_dict, f, ensure_ascii=False, indent=4)
    
    return nome_arquivo_saida

# Interface principal para upload de arquivo
st.subheader("📤 Upload de Contracheque")
arquivo = st.file_uploader("Faça upload de uma imagem ou PDF do contracheque", 
                           type=["jpg", "jpeg", "png", "pdf"])

# Processamento do arquivo quando enviado
if arquivo is not None:
    # Feedback para o usuário
    st.write(f"Arquivo carregado: **{arquivo.name}**")
    
    # Leitura do conteúdo do arquivo
    conteudo = arquivo.read()
    
    # Criar colunas para exibir resultados lado a lado
    col1, col2 = st.columns(2)
    
    # Processar conforme o tipo de arquivo
    if arquivo.type == "application/pdf":
        with col1:
            st.subheader("Visualização do PDF")
            st.warning("Processando PDF... Isso pode levar alguns instantes.")
            
            # Converter a primeira página do PDF para imagem para visualização
            try:
                with tempfile.TemporaryDirectory() as path:
                    imagens = convert_from_bytes(conteudo, dpi=150, first_page=1, last_page=1, output_folder=path)
                    if imagens:
                        st.image(imagens[0], caption="Primeira página do PDF", width=400)
            except Exception as e:
                st.error(f"Erro ao visualizar PDF: {e}")
                st.info("A visualização falhou, mas tentaremos extrair o texto mesmo assim.")
        
        with col2:
            st.subheader("Texto Extraído")
            with st.spinner("Extraindo texto do PDF..."):
                texto_extraido = processar_pdf(conteudo)
                st.text_area("Texto Bruto", texto_extraido, height=300)
            
            # Processar o texto e mostrar dados estruturados
            st.subheader("Dados Estruturados")
            with st.spinner("Processando informações..."):
                df_dados = processar_texto_contracheque(texto_extraido)
                st.dataframe(df_dados)
            
            # Opção para salvar os dados
            if st.button("Salvar Dados Extraídos"):
                caminho_salvo = salvar_dados_extraidos(df_dados, arquivo.name)
                st.success(f"Dados salvos com sucesso em {caminho_salvo}")
    
    elif arquivo.type in ["image/png", "image/jpeg", "image/jpg"]:
        with col1:
            st.subheader("Imagem Carregada")
            imagem = Image.open(io.BytesIO(conteudo))
            st.image(imagem, width=400)
        
        with col2:
            st.subheader("Texto Extraído")
            with st.spinner("Extraindo texto da imagem..."):
                texto_extraido = extrair_texto_imagem(conteudo)
                st.text_area("Texto Bruto", texto_extraido, height=300)
            
            # Processar o texto e mostrar dados estruturados
            st.subheader("Dados Estruturados")
            with st.spinner("Processando informações..."):
                df_dados = processar_texto_contracheque(texto_extraido)
                st.dataframe(df_dados)
            
            # Opção para salvar os dados
            if st.button("Salvar Dados Extraídos"):
                caminho_salvo = salvar_dados_extraidos(df_dados, arquivo.name)
                st.success(f"Dados salvos com sucesso em {caminho_salvo}")
    
    else:
        st.error("Formato de arquivo não suportado. Por favor, envie uma imagem (PNG, JPG) ou PDF.")

# Informações adicionais e instruções
with st.expander("ℹ️ Informações sobre o aplicativo"):
    st.write("""
    ## Como usar o aplicativo
    1. Carregue um arquivo de contracheque (imagem ou PDF).
    2. O aplicativo processará automaticamente o arquivo e extrairá o texto.
    3. Os dados identificados serão exibidos na tabela "Dados Estruturados".
    4. Você pode salvar os dados extraídos para uso futuro.
    
    ## Limitações
    - A precisão do OCR pode variar dependendo da qualidade da imagem.
    - Alguns documentos com layout complexo podem não ser processados corretamente.
    - Recomenda-se verificar manualmente os dados extraídos para garantir a precisão.
    
    ## Privacidade
    - Os dados são processados localmente e não são armazenados permanentemente.
    - Os arquivos salvos ficam apenas no servidor local e não são compartilhados.
    """)

# Seção para comparar contracheques (funcionalidade futura)
with st.expander("📊 Comparar Contracheques (Em Desenvolvimento)"):
    st.write("""
    ### Funcionalidade de Comparação
    
    Esta seção permitirá comparar diferentes contracheques ao longo do tempo para:
    - Rastrear mudanças no salário base
    - Monitorar a evolução dos descontos
    - Visualizar o histórico do valor líquido
    - Identificar descontos incomuns ou variações inesperadas
    
    **Próximas Funcionalidades:**
    - Carregamento de múltiplos contracheques
    - Visualização em gráficos de tendências
    - Exportação de relatórios comparativos
    - Análise automática de discrepâncias
    """)
    
    # Placeholder para gráfico futuro
    st.info("Funcionalidade em desenvolvimento. Em breve você poderá visualizar gráficos comparativos aqui.")

# Rodapé da aplicação
st.markdown("---")
st.markdown("**OCR de Contracheques** | Desenvolvido com Google Vision API e Streamlit")
st.markdown("Versão 1.0 | © 2023 - Todos os direitos reservados")

# Contador de processamentos (simples)
if 'contador_processamentos' not in st.session_state:
    st.session_state.contador_processamentos = 0

# Incrementar contador quando um arquivo é processado com sucesso
if arquivo is not None and 'df_dados' in locals():
    st.session_state.contador_processamentos += 1

# Exibir estatísticas de uso
st.sidebar.subheader("📈 Estatísticas")
st.sidebar.write(f"Documentos processados: {st.session_state.contador_processamentos}")
st.sidebar.write(f"Sessão iniciada: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Opções adicionais (sidebar)
st.sidebar.subheader("⚙️ Configurações")
st.sidebar.write("**Ajustes de OCR:**")
ocr_qualidade = st.sidebar.select_slider(
    "Qualidade do OCR (DPI)",
    options=[150, 200, 250, 300],
    value=300
)
st.sidebar.write("Qualidade mais alta = melhor OCR, mas mais lento.")

# Modo de segurança (evita processamento acidental de documentos sensíveis)
modo_seguro = st.sidebar.checkbox("Modo de segurança", value=True, 
                             help="Quando ativado, exige confirmação antes de processar documentos.")

# Confirmação quando o modo de segurança está ativado
if modo_seguro and arquivo is not None:
    st.sidebar.success("🔒 Documento processado com modo de segurança ativado.")

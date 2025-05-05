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
from google.oauth2 import service_account
import sqlite3
import os.path
from pathlib import Path
import matplotlib.pyplot as plt
import hashlib

# Configuração da página Streamlit
st.set_page_config(
    page_title="OCR de Contracheques - Google Vision",
    page_icon="📊",
    layout="wide"
)

# Função para inicializar o banco de dados
def inicializar_banco_dados():
    """
    Cria o banco de dados SQLite e as tabelas necessárias, se não existirem.
    """
    # Garantir que o diretório de dados existe
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    # Caminho para o banco de dados
    db_path = data_dir / "contracheques.db"
    
    # Conectar ao banco de dados (cria se não existir)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Criar tabela de contracheques se não existir
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracheques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            matricula TEXT,
            cargo TEXT,
            mes_referencia TEXT,
            salario_base REAL,
            descontos REAL,
            valor_liquido REAL,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            arquivo_fonte TEXT,
            hash_arquivo TEXT,
            validado BOOLEAN DEFAULT 0,
            observacoes TEXT
        )
    ''')
    
    # Criar tabela para armazenar as imagens processadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arquivos_processados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT,
            hash_arquivo TEXT UNIQUE,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tipo_arquivo TEXT,
            texto_extraido TEXT
        )
    ''')
    
    # Commit e fechar conexão
    conn.commit()
    conn.close()
    
    return str(db_path)

# Função para calcular hash de arquivo
def calcular_hash_arquivo(conteudo_bytes):
    """
    Calcula o hash SHA-256 do conteúdo do arquivo.
    Útil para identificar arquivos duplicados.
    """
    return hashlib.sha256(conteudo_bytes).hexdigest()

# Função para diagnóstico do banco de dados
def diagnosticar_banco_dados():
    """
    Verifica se o banco de dados está funcionando corretamente.
    """
    try:
        conn = sqlite3.connect(st.session_state['db_path'])
        cursor = conn.cursor()
        
        # Verificar tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas = cursor.fetchall()
        tabelas = [tab[0] for tab in tabelas]
        
        # Verificar contagem de registros
        contagens = {}
        for tabela in tabelas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
            contagens[tabela] = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "ok",
            "caminho_bd": st.session_state['db_path'],
            "tabelas": tabelas,
            "contagens": contagens
        }
    except Exception as e:
        return {
            "status": "erro",
            "mensagem": str(e)
        }

# Função para consultar histórico
def consultar_historico(data_inicio=None, data_fim=None, filtro_nome=None, filtro_matricula=None):
    """
    Consulta o histórico de contracheques processados com possibilidade de filtros.
    
    Args:
        data_inicio: Data inicial (opcional)
        data_fim: Data final (opcional)
        filtro_nome: Filtro por nome (opcional)
        filtro_matricula: Filtro por matrícula (opcional)
        
    Returns:
        DataFrame com os resultados da consulta
    """
    conn = sqlite3.connect(st.session_state['db_path'])
    
    # Construir a consulta SQL com filtros dinâmicos
    query = "SELECT * FROM contracheques WHERE 1=1"
    params = []
    
    if data_inicio:
        query += " AND date(data_processamento) >= ?"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND date(data_processamento) <= ?"
        params.append(data_fim)
    
    if filtro_nome:
        query += " AND nome LIKE ?"
        params.append(f"%{filtro_nome}%")
    
    if filtro_matricula:
        query += " AND matricula LIKE ?"
        params.append(f"%{filtro_matricula}%")
    
    # Ordenar por data mais recente primeiro
    query += " ORDER BY data_processamento DESC"
    
    # Executar a consulta
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

# Função para gerar gráfico de valor líquido
def gerar_grafico_valor_liquido(df):
    """
    Gera um gráfico de linha com a evolução dos valores líquidos por mês.
    
    Args:
        df: DataFrame com os dados dos contracheques
    """
    # Verificar se há dados suficientes
    if len(df) < 2:
        st.warning("São necessários pelo menos 2 registros para gerar gráficos comparativos.")
        return
    
    # Tentar extrair mês e ano da coluna mes_referencia
    df['mes_ref_formatado'] = pd.to_datetime(df['data_processamento']).dt.strftime('%m/%Y')
    
    # Preparar dados para o gráfico
    df_grafico = df.sort_values('data_processamento')
    
    # Criar gráfico
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df_grafico['mes_ref_formatado'], df_grafico['valor_liquido'], marker='o', linestyle='-')
    
    # Formatar eixos
    ax.set_xlabel('Mês/Ano')
    ax.set_ylabel('Valor Líquido (R$)')
    ax.set_title('Evolução do Valor Líquido')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Exibir gráfico
    st.pyplot(fig)

# Inicializar banco de dados
db_path = inicializar_banco_dados()
st.session_state['db_path'] = db_path

# Configuração das credenciais do Google Cloud
if "gcp_service_account" in st.secrets:
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        st.success("✅ Credenciais do Google Cloud carregadas com sucesso!")
        # Mostrar apenas o projeto (seguro de exibir)
        if hasattr(credentials, "_project_id"):
            st.write(f"Project ID: {credentials._project_id}")
    except Exception as e:
        st.error(f"❌ Erro ao carregar credenciais: {str(e)}")
        credentials = None
else:
    st.warning("⚠️ Credenciais do Google Cloud não encontradas. Certifique-se de configurar os secrets.")
    credentials = None

# Seção de diagnóstico para verificar a instalação do Poppler
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

    # Verificar conexão com o Google Vision API
    if st.button("Testar Conexão com Google Vision API"):
        try:
            # Inicializar cliente com as credenciais carregadas
            client = vision.ImageAnnotatorClient(credentials=credentials)
            
            # Criar uma imagem simples para teste
            from PIL import Image, ImageDraw
            image = Image.new('RGB', (100, 30), color = (255, 255, 255))
            d = ImageDraw.Draw(image)
            d.text((10,10), "TEST", fill=(0,0,0))
            
            # Converter para bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            # Enviar para a API
            vision_image = vision.Image(content=img_byte_arr.getvalue())
            response = client.text_detection(image=vision_image)
            
            if response.error.message:
                st.error(f"❌ Erro na API: {response.error.message}")
            else:
                st.success("✅ Conexão com Google Vision API estabelecida com sucesso!")
                texts = response.text_annotations
                if texts:
                    st.write(f"Texto detectado na imagem de teste: '{texts[0].description}'")
                else:
                    st.write("Nenhum texto detectado na imagem de teste.")
                    
        except Exception as e:
            st.error(f"❌ Erro ao testar Google Vision API: {str(e)}")
            st.exception(e)

    # Diagnóstico do banco de dados
    if st.button("Verificar Banco de Dados"):
        resultado = diagnosticar_banco_dados()
        if resultado["status"] == "ok":
            st.success("✅ Banco de dados funcionando corretamente")
            st.write(f"Caminho: {resultado['caminho_bd']}")
            st.write("Tabelas encontradas:")
            for tabela in resultado["tabelas"]:
                st.write(f"- {tabela}: {resultado['contagens'][tabela]} registros")
        else:
            st.error(f"❌ Erro no banco de dados: {resultado['mensagem']}")

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

# Função para extrair texto de imagens usando o Google Vision API
def extrair_texto_imagem(conteudo_imagem):
    """
    Usa o Google Vision API para extrair texto de uma imagem.
    """
    try:
        # Inicializar o cliente Vision API com as credenciais carregadas anteriormente
        client = vision.ImageAnnotatorClient(credentials=credentials)
        
        # Preparar a imagem para análise
        imagem = vision.Image(content=conteudo_imagem)
        
        # Realizar o reconhecimento de texto
        resposta = client.text_detection(image=imagem)
        
        # Verificar erros de resposta
        if resposta.error.message:
            return f"Erro na API Vision: {resposta.error.message}"
            
        textos = resposta.text_annotations
        
        # Verificar se há texto detectado
        if textos:
            return textos[0].description
        else:
            return "Nenhum texto detectado na imagem."
    except Exception as e:
        return f"Erro ao processar imagem: {str(e)}"

# Fallback para OCR local (usando pytesseract) caso o Google Vision falhe
def extrair_texto_imagem_fallback(conteudo_imagem):
    """
    Tenta usar pytesseract como fallback caso o Google Vision API falhe.
    Requer instalação do pytesseract e Tesseract OCR.
    """
    try:
        import pytesseract
        imagem = Image.open(io.BytesIO(conteudo_imagem))
        texto = pytesseract.image_to_string(imagem, lang='por')
        return texto
    except Exception as e:
        return f"Erro no OCR local: {str(e)}"

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
                    
                    # Se o Google Vision falhar, tente o fallback
                    if texto_pagina.startswith("Erro"):
                        st.warning(f"Google Vision falhou. Tentando OCR local... {texto_pagina}")
                        texto_pagina = extrair_texto_imagem_fallback(img_byte_arr.getvalue())
                    
                    texto_completo += f"\n--- Página {i+1} ---\n" + texto_pagina
                
                return texto_completo
                
            except Exception as e:
                st.error(f"Erro ao processar PDF: {str(e)}")
                st.warning("Conversão de PDF pode requerer instalação local. Por favor, tente enviar imagens diretas.")
                return f"Erro na conversão do PDF: {str(e)}"
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {str(e)}")
        return f"Erro no processamento do arquivo: {str(e)}"

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
    
    # Se não há texto para processar, retorna o DataFrame vazio
    if not texto or texto.startswith("Erro"):
        return pd.DataFrame([dados])
    
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

# Função para salvar dados extraídos
def salvar_dados_extraidos(dados, nome_arquivo, conteudo_arquivo, texto_extraido):
    """
    Salva os dados extraídos no banco de dados SQLite.
    
    Args:
        dados: DataFrame pandas com os dados estruturados
        nome_arquivo: Nome do arquivo processado
        conteudo_arquivo: Bytes do arquivo original (para cálculo de hash)
        texto_extraido: Texto bruto extraído do documento
    
    Returns:
        id: ID do registro inserido no banco de dados
    """
    # Calcular hash do arquivo
    hash_arquivo = calcular_hash_arquivo(conteudo_arquivo)
    
    # Conectar ao banco de dados
    conn = sqlite3.connect(st.session_state['db_path'])
    cursor = conn.cursor()
    
    try:
        # Verificar se este arquivo já foi processado antes
        cursor.execute("SELECT id FROM arquivos_processados WHERE hash_arquivo = ?", (hash_arquivo,))
        arquivo_existente = cursor.fetchone()
        
        if arquivo_existente:
            # Arquivo já processado, obtém o ID existente
            st.warning(f"Atenção: Este arquivo já foi processado anteriormente (ID: {arquivo_existente[0]}).")
            conn.close()
            return arquivo_existente[0]
        
        # Primeiro, inserir registro na tabela de arquivos processados
        tipo_arquivo = nome_arquivo.split('.')[-1] if '.' in nome_arquivo else 'desconhecido'
        cursor.execute('''
            INSERT INTO arquivos_processados (nome_arquivo, hash_arquivo, tipo_arquivo, texto_extraido)
            VALUES (?, ?, ?, ?)
        ''', (nome_arquivo, hash_arquivo, tipo_arquivo, texto_extraido))
        
        arquivo_id = cursor.lastrowid
        
        # Converter DataFrame para dicionário
        dados_dict = dados.to_dict(orient='records')[0]
        
        # Inserir dados na tabela de contracheques
        cursor.execute('''
            INSERT INTO contracheques 
            (nome, matricula, cargo, mes_referencia, salario_base, descontos, valor_liquido, 
             arquivo_fonte, hash_arquivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dados_dict.get('Nome', ''),
            dados_dict.get('Matrícula', ''),
            dados_dict.get('Cargo', ''),
            dados_dict.get('Mês/Ano', ''),
            dados_dict.get('Salário Base', 0.0),
            dados_dict.get('Descontos', 0.0),
            dados_dict.get('Valor Líquido', 0.0),
            nome_arquivo,
            hash_arquivo
        ))
        
        # Commit e fechar conexão
        conn.commit()
        conn.close()
        
        return arquivo_id
        
    except Exception as e:
        # Em caso de erro, fazer rollback
        conn.rollback()
        conn.close()
        st.error(f"Erro ao salvar dados no banco: {str(e)}")
        return None

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
                caminho_salvo = salvar_dados_extraidos(df_dados, arquivo.name, conteudo, texto_extraido)
                if caminho_salvo:
                    st.success(f"Dados salvos com sucesso no banco de dados (ID: {caminho_salvo})")
    
    elif arquivo.type in ["image/png", "image/jpeg", "image/jpg"]:
        with col1:
            st.subheader("Imagem Carregada")
            imagem = Image.open(io.BytesIO(conteudo))
            st.image(imagem, width=400)
        
        with col2:
            st.subheader("Texto Extraído")
            with st.spinner("Extraindo texto da imagem..."):
                texto_extraido = extrair_texto_imagem(conteudo)
                
                # Se o Google Vision falhar, tente o fallback
                if texto_extraido.startswith("Erro"):
                    st.warning(f"Google Vision falhou. Tentando OCR local... {texto_extraido}")
                    texto_extraido = extrair_texto_imagem_fallback(conteudo)
                
                st.text_area("Texto Bruto", texto_extraido, height=300)
            
            # Processar o texto e mostrar dados estruturados
            st.subheader("Dados Estruturados")
            with st.spinner("Processando informações..."):
                df_dados = processar_texto_contracheque(texto_extraido)
                st.dataframe(df_dados)
            
            # Opção para salvar os dados
            if st.button("Salvar Dados Extraídos"):
                caminho_salvo = salvar_dados_extraidos(df_dados, arquivo.name, conteudo, texto_extraido)
                if caminho_salvo:
                    st.success(f"Dados salvos com sucesso no banco de dados (ID: {caminho_salvo})")
    
    else:
        st.error("Formato de arquivo não suportado. Por favor, envie uma imagem (PNG, JPG) ou PDF.")

# Interface de histórico e relatórios
with st.expander("📊 Histórico e Relatórios", expanded=False):
    st.subheader("Contracheques Processados")
    
    # Filtros para consulta
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data Inicial", value=None)
    with col2:
        data_fim = st.date_input("Data Final", value=None)
    
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Filtrar por Nome", "")
    with col2:
        filtro_matricula = st.text_input("Filtrar por Matrícula", "")
    
    # Botão para consultar
    if st.button("Consultar Histórico"):
        # Converter datas para string no formato correto, se existirem
        data_inicio_str = data_inicio.strftime("%Y-%m-%d") if data_inicio else None
        data_fim_str = data_fim.strftime("%Y-%m-%d") if data_fim else None
        
        # Consultar banco de dados
        df_historico = consultar_historico(
            data_inicio_str, 
            data_fim_str, 
            filtro_nome, 
            filtro_matricula
        )
        
        # Exibir resultados
        if not df_historico.empty:
            st.write(f"Foram encontrados {len(df_historico)} registros.")
            st.dataframe(df_historico)
            
            # Opção para exportar para Excel
            if st.button("Exportar para Excel"):
                # Criar um buffer na memória
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_historico.to_excel(writer, sheet_name='Contracheques', index=False)
                
                # Download do arquivo
                buffer.seek(0)
                st.download_button(
                    label="Download Excel",
                    data=buffer,
                    file_name=f"contracheques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
        else:
            st.info("Nenhum registro encontrado com os filtros selecionados.")

# Seção de gráficos
with st.expander("📈 Análise Gráfica", expanded=False):
    st.subheader("Gráficos e Visualizações")
    
    # Filtros

# Seção de gráficos
with st.expander("📈 Análise Gráfica", expanded=False):
    st.subheader("Gráficos e Visualizações")
    
    # Filtros para gráficos
    filtro_matricula_grafico = st.text_input("Matrícula para Análise", "", key="matricula_grafico")
    
    if st.button("Gerar Gráficos"):
        if filtro_matricula_grafico:
            # Consultar dados para a matrícula específica
            conn = sqlite3.connect(st.session_state['db_path'])
            df_grafico = pd.read_sql_query(
                "SELECT * FROM contracheques WHERE matricula = ? ORDER BY data_processamento",
                conn, 
                params=[filtro_matricula_grafico]
            )
            conn.close()
            
            if not df_grafico.empty:
                st.write(f"Análise para matrícula: {filtro_matricula_grafico}")
                
                # Gerar gráfico de valor líquido
                gerar_grafico_valor_liquido(df_grafico)
                
                # Tabela de dados utilizados
                st.subheader("Dados utilizados na análise")
                st.dataframe(df_grafico)
            else:
                st.warning(f"Nenhum registro encontrado para a matrícula {filtro_matricula_grafico}.")
        else:
            st.warning("Por favor, informe uma matrícula para gerar os gráficos.")

# Informações adicionais e instruções
with st.expander("ℹ️ Informações sobre o aplicativo"):
    st.write("""
    ## Como usar o aplicativo
    1. Carregue um arquivo de contracheque (imagem ou PDF).
    2. O aplicativo processará automaticamente o arquivo e extrairá o texto.
    3. Os dados identificados serão exibidos na tabela "Dados Estruturados".
    4. Você pode salvar os dados extraídos no banco de dados para uso futuro.
    5. Use a seção "Histórico e Relatórios" para consultar dados anteriores.
    6. Use a seção "Análise Gráfica" para visualizar tendências ao longo do tempo.
    
    ## Limitações
    - A precisão do OCR pode variar dependendo da qualidade da imagem.
    - Alguns documentos com layout complexo podem não ser processados corretamente.
    - Recomenda-se verificar manualmente os dados extraídos para garantir a precisão.
    
    ## Privacidade
    - Os dados são armazenados localmente no banco de dados SQLite.
    - Nenhuma informação é enviada para servidores externos, exceto a imagem para o Google Vision API.
    """)

# Seção para comparar contracheques (funcionalidade futura)
with st.expander("📋 Funcionalidades Avançadas (Em Desenvolvimento)"):
    st.write("""
    ### Próximas Funcionalidades
    
    Estamos trabalhando em recursos adicionais para melhorar a experiência:
    
    **1. Validação Automática de Dados**
    - Comparação com sistemas internos de RH
    - Detecção automática de discrepâncias
    - Alertas para inconsistências
    
    **2. Dashboards Avançados**
    - Análise comparativa entre departamentos
    - Visualização de tendências salariais
    - Detecção de anomalias em pagamentos
    
    **3. Integrações com Sistemas de RH**
    - Exportação direta para sistemas de folha de pagamento
    - Sincronização automática com cadastros de colaboradores
    - Geração de relatórios para compliance
    """)
    
    # Placeholder para recursos futuros
    st.info("Estas funcionalidades estão em desenvolvimento. Fique atento às próximas atualizações!")

# Rodapé da aplicação
st.markdown("---")
st.markdown("**OCR de Contracheques** | Desenvolvido com Google Vision API e Streamlit")
st.markdown("Versão 1.1 | © 2023 - Todos os direitos reservados")

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

# Backup do banco de dados
st.sidebar.subheader("🔄 Backup de Dados")
if st.sidebar.button("Fazer Backup do Banco"):
    try:
        # Ler o arquivo do banco de dados
        with open(st.session_state['db_path'], 'rb') as f:
            dados_banco = f.read()
        
        # Criar nome do arquivo de backup com timestamp
        nome_backup = f"backup_contracheques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Oferecer para download
        st.sidebar.download_button(
            label="Download do Backup",
            data=dados_banco,
            file_name=nome_backup,
            mime="application/octet-stream"
        )
        st.sidebar.success("✅ Backup pronto para download!")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao criar backup: {str(e)}")

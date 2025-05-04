import streamlit as st
import io
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter
import tempfile
import os
from pdf2image import convert_from_bytes
from google.cloud import vision
import numpy as np
import re
import sqlite3
import json
from datetime import datetime

# Configuração da página Streamlit
st.set_page_config(
    page_title="Extrator Profissional de Contracheques",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do banco de dados
def init_db():
    conn = sqlite3.connect('contracheques.db')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS arquivos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadados TEXT
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS rubricas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arquivo_id INTEGER,
        rubrica TEXT,
        descricao TEXT,
        valor TEXT,
        tipo TEXT,
        FOREIGN KEY (arquivo_id) REFERENCES arquivos(id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Chamar inicialização do banco
init_db()

# Função para melhorar a qualidade da imagem
def melhorar_imagem(imagem_bytes):
    """Pré-processa a imagem para melhorar resultados do OCR"""
    try:
        # Converter bytes para imagem
        imagem = Image.open(io.BytesIO(imagem_bytes))
        
        # Converter para escala de cinza
        imagem = imagem.convert('L')
        
        # Aumentar contraste
        enhancer = ImageEnhance.Contrast(imagem)
        imagem = enhancer.enhance(2.0)
        
        # Reduzir ruído
        imagem = imagem.filter(ImageFilter.MedianFilter(size=3))
        
        # Converter para bytes
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer.getvalue()
    except Exception as e:
        st.warning(f"Erro no pré-processamento da imagem: {str(e)}")
        return imagem_bytes

# Função para extrair texto de uma imagem
def extrair_texto_imagem(conteudo_imagem, pre_processar=True):
    """Usa o Google Vision API para extrair texto de uma imagem."""
    try:
        # Pré-processar imagem se necessário
        if pre_processar:
            conteudo_imagem = melhorar_imagem(conteudo_imagem)
        
        # Inicializar o cliente Vision API
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
    
    except Exception as e:
        st.error(f"Erro ao extrair texto: {str(e)}")
        raise

# Função para processar arquivos PDF
def processar_pdf(pdf_bytes, pre_processar=True):
    """Converte PDF para imagens e então extrai texto."""
    try:
        # Criar diretório temporário para armazenar as imagens
        with tempfile.TemporaryDirectory() as path:
            # Converter PDF para imagens
            images = convert_from_bytes(pdf_bytes, dpi=300, output_folder=path)
            
            # Mostrar progresso
            progress_bar = st.progress(0)
            
            # Extrair texto de cada página
            texto_completo = ""
            for i, imagem in enumerate(images):
                # Atualizar progresso
                progress = (i + 1) / len(images)
                progress_bar.progress(progress)
                
                # Converter imagem PIL para bytes
                img_byte_arr = io.BytesIO()
                imagem.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                # Extrair texto da imagem
                texto_pagina = extrair_texto_imagem(img_byte_arr.getvalue(), pre_processar)
                texto_completo += f"\n--- Página {i+1} ---\n" + texto_pagina
            
            # Limpar barra de progresso
            progress_bar.empty()
            
            return texto_completo
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        raise

# Função para processar texto extraído de um contracheque
def processar_texto_contracheque(texto):
    """Processa o texto bruto extraído do OCR para organizar os dados do contracheque."""
    # Estrutura de dados
    dados = {
        "Rubrica": [],
        "Descrição": [],
        "Valor": [],
        "Tipo": []  # Crédito ou Débito
    }
    
    # Identificar padrões específicos de contracheques
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", 
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    
    metadados = {
        "data_referencia": None,
        "funcionario": None,
        "empresa": None,
        "tipo_folha": None
    }
    
    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if not linha.strip():
            continue
            
        linha_lower = linha.lower()
        
        # Extrair mês/ano
        for mes in meses:
            if mes in linha_lower and any(str(ano) in linha for ano in range(2018, 2030)):
                metadados["data_referencia"] = linha
                continue
                
        # Detectar nome do funcionário
        if ("nome:" in linha_lower or "funcionário:" in linha_lower) and i < 15:
            metadados["funcionario"] = linha.split(":", 1)[1].strip() if ":" in linha else linha
            continue
            
        # Detectar empresa
        if "empresa:" in linha_lower or "empregador:" in linha_lower:
            metadados["empresa"] = linha.split(":", 1)[1].strip() if ":" in linha else linha
            continue
            
        # Detectar tipo de folha
        if "folha" in linha_lower and ("pagamento" in linha_lower or "adiantamento" in linha_lower):
            metadados["tipo_folha"] = linha
            continue
            
        # Processamento de rubricas/valores
        # Expressões regulares para identificar valores monetários
        valor_pattern = r'R?\$?\s?([\d.,]+)(?:\s*(?:CR|DB|C|D))?'
        
        # Verificar se a linha contém um valor monetário
        valor_match = re.search(valor_pattern, linha)
        if valor_match:
            valor_str = valor_match.group(0)
            valor_num = valor_match.group(1)
            
            # Extrair a descrição (tudo antes do valor)
            descricao = linha[:valor_match.start()].strip()
            
            # Remover números e pontuações do início da descrição (códigos de rubrica)
            rubrica = re.sub(r'^[\d\s.]+', '', descricao).strip()
            
            # Determinar se é crédito ou débito
            tipo = "Crédito"
            if "DB" in linha or "D" in linha or "desconto" in linha_lower or "inss" in linha_lower or "imposto" in linha_lower:
                tipo = "Débito"
                
            # Adicionar aos dados apenas se tiver um valor válido
            if valor_num and len(valor_num) > 0:
                dados["Rubrica"].append(rubrica[:30])  # Limitar tamanho
                dados["Descrição"].append(descricao)
                dados["Valor"].append(valor_str.replace("R$", "").strip())
                dados["Tipo"].append(tipo)
    
    df = pd.DataFrame(dados)
    
    # Limpar valores duplicados ou inválidos
    if not df.empty:
        # Remover linhas com valores idênticos
        df = df.drop_duplicates()
        
        # Tentar converter valores para numéricos
        df["Valor_Num"] = pd.to_numeric(
            df["Valor"].str.replace(".", "").str.replace(",", ".").str.replace("R$", ""),
            errors="coerce"
        )
        
        # Remover linhas com valores nulos
        df = df.dropna(subset=["Valor_Num"])
        
        # Ajustar sinal para débitos
        df.loc[df["Tipo"] == "Débito", "Valor_Num"] = -df.loc[df["Tipo"] == "Débito", "Valor_Num"]
        
        # Formatar valor para exibição
        df["Valor"] = df["Valor_Num"].apply(lambda x: f"R$ {abs(x):.2f}".replace(".", ","))
        
        # Remover coluna auxiliar
        df = df.drop(columns=["Valor_Num"])
    
    return df, metadados

# Função para salvar dados no banco
def salvar_dados(df, metadados, arquivo_nome):
    """Salva os dados extraídos no banco SQLite."""
    try:
        conn = sqlite3.connect('contracheques.db')
        
        # Salvar metadados
        metadados_json = json.dumps(metadados)
        
        # Inserir registro do arquivo
        cursor = conn.execute(
            "INSERT INTO arquivos (nome, metadados) VALUES (?, ?)",
            (arquivo_nome, metadados_json)
        )
        arquivo_id = cursor.lastrowid
        
        # Salvar dados do DataFrame
        for _, row in df.iterrows():
            conn.execute(
                "INSERT INTO rubricas (arquivo_id, rubrica, descricao, valor, tipo) VALUES (?, ?, ?, ?, ?)",
                (arquivo_id, row["Rubrica"], row["Descrição"], row["Valor"], row["Tipo"])
            )
        
        conn.commit()
        conn.close()
        
        return arquivo_id
    except Exception as e:
        st.error(f"Erro ao salvar dados: {str(e)}")
        raise

# Função para buscar histórico de processamentos
def buscar_historico():
    """Busca histórico de arquivos processados."""
    try:
        conn = sqlite3.connect('contracheques.db')
        query = """
        SELECT a.id, a.nome, a.data_processamento, a.metadados,
               COUNT(r.id) as total_rubricas,
               SUM(CASE WHEN r.tipo = 'Crédito' THEN 1 ELSE 0 END) as total_creditos,
               SUM(CASE WHEN r.tipo = 'Débito' THEN 1 ELSE 0 END) as total_debitos
        FROM arquivos a
        LEFT JOIN rubricas r ON a.id = r.arquivo_id
        GROUP BY a.id
        ORDER BY a.data_processamento DESC
        LIMIT 50
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {str(e)}")
        return pd.DataFrame()

# Função para buscar detalhes de um arquivo
def buscar_detalhes_arquivo(arquivo_id):
    """Busca detalhes de um arquivo específico."""
    try:
        conn = sqlite3.connect('contracheques.db')
        query = f"""
        SELECT r.rubrica, r.descricao, r.valor, r.tipo
        FROM rubricas r
        WHERE r.arquivo_id = {arquivo_id}
        ORDER BY r.id
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao buscar detalhes: {str(e)}")
        return pd.DataFrame()

# Função para gerar relatório de período
def gerar_relatorio_periodo(inicio_mes, inicio_ano, fim_mes, fim_ano, rubricas=None):
    """Gera relatório comparativo para um período."""
    try:
        conn = sqlite3.connect('contracheques.db')
        
        # Construir condição para rubricas
        rubrica_condition = ""
        if rubricas and len(rubricas) > 0:
            rubricas_str = "', '".join(rubricas)
            rubrica_condition = f"AND r.rubrica IN ('{rubricas_str}')"
        
        # Query para extrair dados de período
        query = f"""
        SELECT 
            json_extract(a.metadados, '$.data_referencia') as referencia,
            r.rubrica,
            r.tipo,
            r.valor
        FROM arquivos a
        JOIN rubricas r ON a.id = r.arquivo_id
        WHERE 
            json_extract(a.metadados, '$.data_referencia') IS NOT NULL
            {rubrica_condition}
        ORDER BY 
            referencia, r.rubrica
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Processar dataframe para formato de relatório
        # Extrair mês e ano da referência
        df['mes_ano'] = df['referencia'].str.extract(r'(\w+\s+\d{4})')
        
        # Preparar para pivot
        df['valor_num'] = pd.to_numeric(
            df['valor'].str.replace('R$', '').str.replace('.', '').str.replace(',', '.'),
            errors='coerce'
        )
        
        # Aplicar sinal de acordo com o tipo
        df.loc[df['tipo'] == 'Débito', 'valor_num'] = -df.loc[df['tipo'] == 'Débito', 'valor_num']
        
        # Pivot table
        pivot_df = df.pivot_table(
            index='mes_ano',
            columns='rubrica',
            values='valor_num',
            aggfunc='sum'
        ).reset_index()
        
        # Ordenar por data
        pivot_df = pivot_df.sort_values('mes_ano')
        
        return pivot_df
    
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")
        return pd.DataFrame()

# Função para processar arquivo
def process_file(arquivo, pre_processar=True, usar_ml=False):
    try:
        # Exibir informações do arquivo
        st.write(f"**Arquivo carregado:** {arquivo.name}")
        st.write(f"**Tipo:** {arquivo.type}")
        
        # Criar colunas para organização
        col1, col2 = st.columns(2)
        
        # Ler o conteúdo do arquivo
        conteudo = arquivo.read()
        
        # Processar conforme o tipo de arquivo
        if arquivo.type == "application/pdf":
            with col1:

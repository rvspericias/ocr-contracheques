
# MVP 2.0 – OCR Inteligente de Contracheques

Este app utiliza OCR híbrido (Google Vision + Tesseract) e lógica por blocos para extrair dados estruturados de contracheques em PDF e imagem. Ideal para uso por peritos contábeis trabalhistas.

## Funcionalidades

- Upload múltiplo de PDFs e imagens
- Extração separada por blocos: Proventos, Descontos, Totais
- OCR com fallback: Google Vision → Tesseract
- Filtro por competência (MM/AAAA)
- Seleção de rubricas a exportar
- Exportação para Excel com nome, competência e rubricas

## Como publicar no Streamlit Cloud

1. Crie um repositório no GitHub
2. Envie os arquivos deste zip
3. Vá para https://streamlit.io/cloud
4. Conecte sua conta GitHub e selecione o script `app_ocr_mvp2_contracheques.py`


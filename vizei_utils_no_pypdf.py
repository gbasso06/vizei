# import pypdf
import re
import unicodedata

def normalize(text):
    if not text:
        return ""
    text = text.upper().strip()

    # Remove acentos
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

    # Normaliza espaços múltiplos
    return " ".join(text.split())

# Função auxiliar para conversão
def str_br_to_float(valor_str: str) -> float:
    """Converte string no formato brasileiro (1.000,00 ou -1.000,00) para float."""
    if not valor_str:
        return 0.0
        
    # Remove pontos de milhar e substitui vírgula decimal por ponto.
    valor_limpo = valor_str.strip().replace('.', '').replace(',', '.')
    
    # Remove qualquer espaço extra no número, especialmente antes do sinal negativo
    valor_limpo = re.sub(r'-\s*', '-', valor_limpo)
    
    try:
        return float(valor_limpo)
    except ValueError:
        # Retorna 0.0 ou levanta erro, dependendo da necessidade.
        return 0.0

# utils: extrai texto de pdf
# def extrair_texto_pdf(caminho_pdf):
#     """Extrai o texto de todas as páginas do PDF."""
#     texto_completo = []
#     try:
#         with open(caminho_pdf, 'rb') as arquivo:
#             reader = pypdf.PdfReader(arquivo)
#             for pagina in reader.pages:
#                 texto_pagina = pagina.extract_text()
#                 if texto_pagina:
#                     texto_completo.append(texto_pagina)
#         return "\n".join(texto_completo)
#     except FileNotFoundError:
#         print(f"Erro: Arquivo '{caminho_pdf}' não encontrado.")
#         return None
#     except Exception as e:
#         print(f"Ocorreu um erro durante a extração: {e}")
#         return None
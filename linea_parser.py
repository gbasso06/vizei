import re
import vizei_utils
from typing import Tuple, Dict, Any, List

def parsear_identificacao_condominio(texto_bruto: str) -> dict:    
    # 1. Definir a Expressão Regular (Regex)
    # ^.* (Início da linha e qualquer coisa antes)
    # Condomínio:\s*(\d+) (Grupo 1: Captura o código, que é composto por números (\d+))
    # \s*-\s*CONDOMINIO\s* (Separador literal)
    # (.*) (Grupo 2: Captura o restante da string como o nome do condomínio)
    regex_condominio = r'^(.*Condomínio:\s*(\d+)\s*-\s*CONDOMINIO\s*(.*))$'
    
    # 2. Buscar o padrão no texto
    # Usamos re.MULTILINE (re.M) para que o ^ e $ funcionem para cada linha
    match = re.search(regex_condominio, texto_bruto, re.MULTILINE)
    
    if match:
        # Grupo 1 (match.group(1)): A string completa de identificação
        string_identificadora = match.group(1).strip() 
        
        # Grupo 2 (match.group(2)): O código do condomínio
        codigo_condominio = match.group(2).strip()
        
        # Grupo 3 (match.group(3)): O nome do condomínio
        nome_condominio = match.group(3).strip()
        
        return {
            'nome_condominio': nome_condominio,
            'codigo_condominio': codigo_condominio,
            # Retorna a string completa limpa, conforme solicitado
            'string_identificadora': string_identificadora
        }
    else:
        # Retorna um objeto vazio ou None se o padrão não for encontrado
        return {
            'nome_condominio': None,
            'codigo_condominio': None,
            'string_identificadora': None
        }
    
def remover_headers(texto_bruto: str, string_identificadora:str) -> str:
    """
    Remove blocos de cabeçalho que se repetem no início de cada 'página' 
    do texto extraído.
    """
    linhas = texto_bruto.split('\n')
    texto_filtrado = []
    
    # Marcador de início do bloco de cabeçalho
    MARCADOR_INICIO = "RelatDemonCroAntes" 
    # Marcador de fim do bloco de cabeçalho
    MARCADOR_FIM = string_identificadora 
    
    dentro_header = False
    
    for linha in linhas:
        linha_limpa = linha.strip()
        
        # 1. Detecta o início de um bloco de cabeçalho
        if MARCADOR_INICIO in linha_limpa:
            dentro_header = True
            continue # Não adiciona a linha de início
            
        # 2. Se estiver dentro, verifica se é o final
        if dentro_header and MARCADOR_FIM in linha_limpa:
            dentro_header = False
            continue # Não adiciona a linha de fim
            
        # 3. Adiciona a linha APENAS se não for um cabeçalho
        if not dentro_header and linha_limpa:
            texto_filtrado.append(linha)
            
    return "\n".join(texto_filtrado)


# extrai saldos
def parsear_bloco_saldos(texto_bruto: str) -> list[dict]:
    """
    Extrai o Resumo Financeiro Contábil e estrutura os saldos das contas.
    """
    linhas = texto_bruto.split('\n')
    dados_saldos = {}
    texto_filtrado = []
    contas = [] 

    MARCADOR_INICIO = "Resumo Financeiro Contábil"
    MARCADOR_FIM = "TOTAL"
    
    # Regex para capturar os 4 valores no formato BR (opcionalmente negativo) no final da linha
    # Ex: -1.822,42 282.666,22 286.671,27 -5.827,47
    # Padrão: 4 grupos de números com formatação BR e opcionalmente sinal de menos (com espaços ao redor) no final da string ($)
    REGEX_VALORES = r'([\-]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s+([\-]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s+([\-]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s+([\-]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*$'

    dentro_bloco = False
    
    for linha in linhas:
        linha_limpa = linha.strip()
        
        if MARCADOR_INICIO in linha_limpa:
            dentro_bloco = True
            continue # Ignora a linha do cabeçalho da tabela
                    
        if dentro_bloco and linha_limpa:
            match = re.search(REGEX_VALORES, linha_limpa)
            
            if match:
                # Os 4 valores são capturados pelos grupos do regex
                valores_str = match.groups()
                
                # A chave (nome da conta) é o restante da linha
                nome_conta = vizei_utils.normalize(linha_limpa[:match.start()].strip())
                
                # Converte os 4 valores para float
                valores_float = [vizei_utils.str_br_to_float(v) for v in valores_str]

                # Adiciona ao resultado no formato solicitado
                dados_saldos[nome_conta]= {
                        'anterior': valores_float[0],
                        'credito': valores_float[1],
                        'debito': valores_float[2],
                        'atual': valores_float[3]
                    }
                
                contas.append(nome_conta)

        # 3. Adiciona a linha APENAS se não for um cabeçalho
        if not dentro_bloco and linha_limpa:
            texto_filtrado.append(linha)

        if MARCADOR_FIM in linha_limpa:
            # Encerra o parsing quando encontra o Total (conforme solicitado)
            if "TOTAL" in contas: contas.remove("TOTAL")
            dentro_bloco = False
            dados_saldos['contas'] = contas
            continue 
        
                
    return (dados_saldos, "\n".join(texto_filtrado))


#
# parser dos blocos de cada uma das contas
#

def parse_blocos_contas(texto, contas):
    CONTAS = contas

    linhas = texto.splitlines()

    blocos_inicio = []

    # Encontrar inícios de blocos
    for i, linha in enumerate(linhas):
        normalized = vizei_utils.normalize(linha.strip().upper())
        for conta in CONTAS:
            if normalized == conta.upper():
                blocos_inicio.append((conta, i))
                break

    if not blocos_inicio:
        raise ValueError("Nenhum bloco encontrado.")

    # Encontrar linha da seção de cotas em aberto
    idx_cotas_aberto = None
    for i, linha in enumerate(linhas):
        if "RELAÇÃO DE COTAS EM ABERTO" in linha.upper():
            idx_cotas_aberto = i
            break

    if idx_cotas_aberto is None:
        raise ValueError("Linha 'RELAÇÃO DE COTAS EM ABERTO' não encontrada.")

    blocos = []

    # Processar cada bloco
    for idx, (conta, start_idx) in enumerate(blocos_inicio):
        if idx < len(blocos_inicio) - 1:
            limite_busca = blocos_inicio[idx + 1][1]
        else:
            limite_busca = idx_cotas_aberto

        end_idx = None
        for j in range(start_idx + 1, limite_busca):
            linha_up = linhas[j].strip().upper()
        
            # 1) Se achar linha SALDO ATUAL → encerra aqui
            if "SALDO ATUAL" in linha_up:
                end_idx = j
                break
        
            # 2) Se achar outra conta → encerra imediatamente antes dessa linha
            for outra_conta, _ in blocos_inicio:
                if linha_up == outra_conta.upper():
                    end_idx = j - 1
                    break
            if end_idx is not None:
                break
        
        # 3) Se não encontrou nada, encerra no limite - 1
        if end_idx is None:
            end_idx = limite_busca - 1

        bloco_texto = "\n".join(linhas[start_idx:end_idx + 1])

        blocos.append({
            "nome": conta,
            "start": start_idx,
            "end": end_idx,
            "texto": bloco_texto
        })

    # Agora remover os blocos do texto original
    manter = [True] * len(linhas)

    for bloco in blocos:
        for i in range(bloco["start"], bloco["end"] + 1):
            manter[i] = False

    texto_sem_blocos = "\n".join([linhas[i] for i in range(len(linhas)) if manter[i]])

    blocos_unificados = {}
    for bloco in blocos:
        nome = bloco["nome"]
    
        if nome not in blocos_unificados:
            # cria o primeiro bloco base
            blocos_unificados[nome] = {
                "nome": nome,
                "start": bloco["start"],
                "end": bloco["end"],
                "texto": bloco["texto"]
            }
        else:
            # já existe: atualiza start, end e concatena texto
            existente = blocos_unificados[nome]
            existente["start"] = min(existente["start"], bloco["start"])
            existente["end"] = max(existente["end"], bloco["end"])
            existente["texto"] += "\n" + bloco["texto"]
    
    # substitui a lista original pela lista unificada
    #resultado["blocos"] = list(blocos_unificados.values())


    
    return {
        "blocos": blocos_unificados,
        "texto_sem_blocos": texto_sem_blocos
    }





#
# Parser de despesas ordinarias da conta ordinaria
#

def parsear_despesas_ordinarias(texto_bruto: str) -> dict:
    """
    Extrai as despesas da seção ORDINÁRIA (CONTA CORRENTE), incluindo o total das despesas.
    """
    linhas = texto_bruto.split('\n')
    despesas_estruturadas = {}
    total_despesas = None
    texto_filtrado = []
    categorias = []
    
    # Marcadores de Início e Fim (para delimitar a seção)
    MARCADOR_INICIO = "ORDINÁRIA (CONTA CORRENTE)"
    MARCADOR_FIM_SECAO = "TOTAL DAS DESPESAS"
    
    # 1. Regex para identificar um valor colado ao início do texto (Linha Normal)
    REGEX_VALOR_COLADO = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})(.*)$'

    # 2. Regex para identificar a linha de Subtotal (3 valores colados) - ÚLTIMA LINHA
    REGEX_SUBTOTAL = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+([\d,.]+%)(.*)$'
    
    # 3. Novo Regex para capturar o Total das Despesas
    # Ex: "TOTAL DAS DESPESAS 277.442,27"
    REGEX_TOTAL_FINAL = r'^\s*TOTAL DAS DESPESAS\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    
    dentro_bloco = False
    categoria_atual = None
    
    for i,linha in enumerate(linhas):
        linha_limpa = linha.strip()
        
        # A. Início do bloco de despesas
        if MARCADOR_INICIO in linha_limpa:
            # Verifica se a próxima linha contém o "Demonstrativo de Despesas"
            if linhas.index(linha) + 1 < len(linhas) and "Demonstrativo de Despesas" in linhas[linhas.index(linha) + 1]:
                dentro_bloco = True
                continue
        
        if not dentro_bloco:
            # Se não estamos no bloco de despesas, passamos para a próxima linha
            texto_filtrado.append(linha)
            continue
        
        # B. Fim do bloco de despesas e captura do Total
        if MARCADOR_FIM_SECAO in linha_limpa:
            match_total = re.search(REGEX_TOTAL_FINAL, linha_limpa)
            if match_total:
                total_despesas = vizei_utils.str_br_to_float(match_total.group(1))
            texto_filtrado.extend(linhas[i + 1:])
            dentro_bloco = False
            break # Interrompe o loop após encontrar o total final
            
        # C. Identificação da Categoria
        if linha_limpa.isupper() and not any(char.isdigit() for char in linha_limpa):
            if linha_limpa not in ("HISTÓRICO TOTALVALOR", "ORDINÁRIA (CONTA CORRENTE)", "DEMONSTRATIVO DE DESPESAS"):
                categoria_atual = linha_limpa
                despesas_estruturadas[categoria_atual] = {
                    'subtotal': 0.0,
                    'despesas': []
                }
                continue
        
        # D. Parsing das Linhas de Despesa
        if categoria_atual:
            
            # adiciona categoria na lista de categorias
            if categoria_atual not in categorias:
                categorias.append(categoria_atual)

            # Tenta o Regex de Subtotal (3 valores)
            match_subtotal = re.search(REGEX_SUBTOTAL, linha_limpa)
            if match_subtotal:
                subtotal_valor = vizei_utils.str_br_to_float(match_subtotal.group(2))
                despesas_estruturadas[categoria_atual]['subtotal'] = subtotal_valor
                
                valor_despesa = vizei_utils.str_br_to_float(match_subtotal.group(1))
                historico_despesa = match_subtotal.group(4).strip()
                
                if valor_despesa > 0:
                    despesas_estruturadas[categoria_atual]['despesas'].append({
                        'historico': historico_despesa,
                        'valor': valor_despesa
                    })
                
                categoria_atual = None # Encerra a categoria
                continue

            # Tenta o Regex de Valor Colado (Linha Normal)
            match_normal = re.search(REGEX_VALOR_COLADO, linha_limpa)
            if match_normal:
                valor = vizei_utils.str_br_to_float(match_normal.group(1))
                historico = match_normal.group(2).strip()
                
                if valor > 0:
                    despesas_estruturadas[categoria_atual]['despesas'].append({
                        'historico': historico,
                        'valor': valor
                    })
                continue

    # Monta e retorna o objeto final
    output = despesas_estruturadas
    if total_despesas is not None:
        # Adiciona o total na primeira posição (por convenção, embora JSON não garanta ordem)
        output = {"TOTAL_DESPESAS": total_despesas, 
                  "CATEGORIAS": categorias,
                  **despesas_estruturadas}
        
    return (output, "\n".join(texto_filtrado))

def parsear_resumo_emissoes_colunado(texto_bruto: str) -> Tuple[Dict[str, Any], str]:
    """
    Extrai o bloco "Resumo de Emissões Colunado RealizadoPrevisto" de acordo com as regras.

    Args:
        texto_bruto: O texto completo a ser analisado.
        
    Returns:
        Uma tupla contendo o objeto de resumo parseado e o texto restante.
    """
    
    linhas = texto_bruto.split('\n')
    
    # --- Marcadores e Regex ---
    
    MARCADOR_INICIO = "Resumo de Emissões Colunado RealizadoPrevisto"
    MARCADOR_FIM_KEY = "COTAS REC. DE COBRANÇA"
    
    # Regex para a linha Total (dois valores colados) - Ex: 274.733,71418.878,75
    REGEX_LINHA_TOTAL = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    
    # Regex para a linha de Fim (COTAS REC. DE COBRANÇA com um único valor)
    # A linha que define o FIM deve ser "COTAS REC. DE COBRANÇA         EM 31/12/2024 144.145,04"
    REGEX_LINHA_FIM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    
    # Regex para linhas de item normal (descrição + 2 valores colados)
    # Ex: COTAS REC. DE COBRANÇA EM 30/11/2024 19.870,83141.032,88
    REGEX_ITEM_COLUNADO = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'

    # --- Estrutura de Retorno (Baseada no Output Desejado) ---
    resumo_emissao: Dict[str, Any] = {
        'total': {'previsto': None, 'realizado': None}
    }
    
    dentro_bloco = False
    bloco_encontrado = False
    start_index = -1
    end_index = -1
    
    for i, linha in enumerate(linhas):
        linha_limpa = linha.strip()

        # A. Início do bloco
        if linha_limpa.startswith(MARCADOR_INICIO):
            dentro_bloco = True
            bloco_encontrado = True
            start_index = i
            continue

        if not dentro_bloco:
            continue
        
        # B. Linha de Fim (COTAS REC. DE COBRANÇA com um único valor)
        if linha_limpa.startswith(MARCADOR_FIM_KEY):
            
            # Checa se é a linha de FIM (Regra: linha que possui APENAS um valor, logo após o total)
            match_fim = re.search(REGEX_LINHA_FIM_SIMPLES, linha_limpa)
            
            # Se a linha de total já foi processada (ver C) E se é uma linha com apenas um valor
            if resumo_emissao['total']['previsto'] is not None and match_fim:
                
                # Captura dados da linha de FIM
                descricao_completa = match_fim.group(1).strip()
                valor_realizado = vizei_utils.str_br_to_float(match_fim.group(2))
                
                # Extrai a data da descrição
                match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                data_fim = match_data.group(1) if match_data else None

                # Adiciona o item de Fim ao resumo
                resumo_emissao[MARCADOR_FIM_KEY + f" {i}"] = {
                    'date': data_fim,
                    'realizado': valor_realizado,
                }
                
                end_index = i + 1 # Próxima linha é o fim do bloco de extração
                dentro_bloco = False
                break
        
        # C. Linha de Total (dois valores colados)
        match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
        if match_total:
            # Captura os valores totais
            realizado_str = match_total.group(1)
            previsto_str = match_total.group(2)
            
            resumo_emissao["total"]["realizado"] = vizei_utils.str_br_to_float(realizado_str)
            resumo_emissao["total"]["previsto"] = vizei_utils.str_br_to_float(previsto_str)
            continue # Não adiciona a linha total como item, apenas atualiza o objeto total
            
        # D. Linhas de Itens (Descrições)
        match_item = re.search(REGEX_ITEM_COLUNADO, linha_limpa)
        if match_item:
            descricao_completa = match_item.group(1).strip()
            realizado = vizei_utils.str_br_to_float(match_item.group(2))
            previsto = vizei_utils.str_br_to_float(match_item.group(3))
            
            # Tenta extrair a data se o item for 'COTAS REC. DE COBRANÇA'
            data_item = None
            chave_resumo = descricao_completa
            if descricao_completa.startswith(MARCADOR_FIM_KEY):
                chave_resumo = MARCADOR_FIM_KEY + f" {i}" # Chave única para o dicionário de saída
                match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                data_item = match_data.group(1) if match_data else None
            
            resumo_emissao[chave_resumo] = {
                "realizado": realizado,
                "previsto": previsto,
                **({'date': data_item} if data_item else {})
            }
            continue

    if not bloco_encontrado:
        return ({"erro": "Bloco de Resumo de Emissões Colunado não encontrado."}, texto_bruto)
    
    if end_index == -1:
        return ({"erro": "Linha de FIM (COTAS REC. DE COBRANÇA com 1 valor) não foi localizada após o Total."}, texto_bruto)

    # 4. Montar o texto restante (linhas antes do início + linhas depois do fim)
    
    # O bloco extraído vai de start_index até end_index - 1
    linhas_antes = "\n".join(linhas[:start_index])
    linhas_depois = "\n".join(linhas[end_index:])
    
    texto_restante = (linhas_antes + "\n" + linhas_depois).strip()

    return (resumo_emissao, texto_restante)

def parsear_posicao_financeira(texto_bruto: str) -> Tuple[Dict[str, Any], str]:
    import re
    
    linhas = texto_bruto.split('\n')
    
    MARCADOR_INICIO = "Posição Financeira CréditoDébito"
    REGEX_LINHA_TOTAL = r'^\s*TOTAIS\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    REGEX_LINHA_SALDO_ATUAL = r'^\s*SALDO ATUAL\s*(CREDOR|DEVEDOR|)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    REGEX_ITEM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'

    posicao_financeira: Dict[str, Any] = {
        'total': {'credito': None, 'debito': None},
        'itens': {}
    }
    
    dentro_bloco = False
    bloco_encontrado = False
    start_index = -1
    end_index = -1
    
    for i, linha in enumerate(linhas):
        linha_limpa = linha.strip()

        # A. Início
        if linha_limpa.startswith(MARCADOR_INICIO):
            dentro_bloco = True
            bloco_encontrado = True
            start_index = i
            continue

        if not dentro_bloco:
            continue
        
        # B. Saldo Atual
        match_saldo_atual = re.search(REGEX_LINHA_SALDO_ATUAL, linha_limpa)
        if match_saldo_atual:
            tipo_saldo = match_saldo_atual.group(1).strip()
            valor_saldo_str = match_saldo_atual.group(2)
            valor_float = vizei_utils.str_br_to_float(valor_saldo_str)
            chave = f"SALDO ATUAL {tipo_saldo}".strip()

            # SUPORTE A DUPLICIDADES
            posicao_financeira['itens'].setdefault(chave, [])
            posicao_financeira['itens'][chave].append({"valor": valor_float})

            end_index = i + 1
            dentro_bloco = False
            break
            
        # C. Totais
        match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
        if match_total:
            posicao_financeira["total"]["credito"] = vizei_utils.str_br_to_float(match_total.group(1))
            posicao_financeira["total"]["debito"]  = vizei_utils.str_br_to_float(match_total.group(2))
            continue
            
        # D. Itens normais
        match_item = re.search(REGEX_ITEM_SIMPLES, linha_limpa)
        if match_item:
            descricao = match_item.group(1).strip()
            valor = vizei_utils.str_br_to_float(match_item.group(2))
            item = {"valor": valor}

            # Extrair data se existir
            match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao)
            if match_data:
                item["date"] = match_data.group(1)
                descricao = descricao.replace(match_data.group(1), "").strip()

            # SUPORTE A LINHAS DUPLICADAS
            if descricao not in posicao_financeira["itens"]:
                posicao_financeira["itens"][descricao] = item
            else:
                # Se já existe e não for lista → transforma em lista
                if not isinstance(posicao_financeira["itens"][descricao], list):
                    posicao_financeira["itens"][descricao] = [posicao_financeira["itens"][descricao]]
                posicao_financeira["itens"][descricao].append(item)

            continue

    if not bloco_encontrado:
        return ({"erro": "Bloco de Posição Financeira não encontrado."}, texto_bruto)
    
    if end_index == -1:
        return ({"erro": "Linha de FIM (SALDO ATUAL) não foi localizada."}, texto_bruto)

    # Texto restante
    linhas_antes = "\n".join(linhas[:start_index])
    linhas_depois = "\n".join(linhas[end_index:])
    texto_restante = (linhas_antes + "\n" + linhas_depois).strip()

    # Se só existir 1 item por chave → manter formato original
    itens_normalizados = {}
    for k, v in posicao_financeira["itens"].items():
        if isinstance(v, list) and len(v) == 1:
            itens_normalizados[k] = v[0]
        else:
            itens_normalizados[k] = v

    final_output = {
        "posicao_financeira": {
            "total": posicao_financeira["total"],
            **itens_normalizados
        }
    }

    return (final_output, texto_restante)


def parsear_fundo_de_reserva(texto_bruto: str) -> Tuple[Dict[str, Any], str]:
    """
    Extrai o bloco "FUNDO DE RESERVA" e sua Posição Financeira.

    Args:
        texto_bruto: O texto completo a ser analisado.
        
    Returns:
        Uma tupla contendo o objeto de fundo de reserva parseado e o texto restante.
    """
    
    linhas = texto_bruto.split('\n')
    
    # --- Marcadores e Regex ---
    
    MARCADOR_INICIO_1 = "FUNDO DE RESERVA"
    MARCADOR_INICIO_2 = "Posição Financeira CréditoDébito" # Segunda linha do início
    
    # Regex para a linha Total (dois valores colados: Crédito e Débito)
    # Ex: TOTAIS 168.280,3730.077,83
    REGEX_LINHA_TOTAL = r'^\s*TOTAIS\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    
    # Regex para a linha de Fim (Saldo Atual)
    # Ex: SALDO ATUAL CREDOR 138.202,54
    REGEX_LINHA_SALDO_ATUAL = r'^\s*SALDO ATUAL\s*(CREDOR|DEVEDOR|)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
    
    # Regex para linhas de item normal (descrição + 1 valor no final)
    # Ex: APLICAÇÃO 9.229,00
    REGEX_ITEM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'


    # --- Estrutura de Retorno ---
    fundo_reserva: Dict[str, Any] = {
        'total': {'credito': None, 'debito': None},
    }
    
    dentro_bloco = False
    bloco_encontrado = False
    start_index = -1
    end_index = -1
    
    for i, linha in enumerate(linhas):
        linha_limpa = linha.strip()

        # A. Início do bloco (Duplo Marcador)
        if linha_limpa.startswith(MARCADOR_INICIO_1) and (i + 1 < len(linhas) and linhas[i+1].strip().startswith(MARCADOR_INICIO_2)):
            if start_index == -1: start_index = i 
            dentro_bloco = True
            bloco_encontrado = True
            continue # Pula a linha "FUNDO DE RESERVA"
        
        # Pula a segunda linha do marcador
        if dentro_bloco and linha_limpa.startswith(MARCADOR_INICIO_2):
            continue

        if not dentro_bloco:
            continue
        
        # B. Linha de Fim (Saldo Atual)
        match_saldo_atual = re.search(REGEX_LINHA_SALDO_ATUAL, linha_limpa)
        if match_saldo_atual:
            # Captura o saldo atual e termina
            tipo_saldo = match_saldo_atual.group(1).strip() if match_saldo_atual.group(1) else ""
            valor_saldo_str = match_saldo_atual.group(2)
            
            chave_saldo = f"SALDO ATUAL {tipo_saldo}".strip()
            
            # Adiciona ao objeto principal (nível 1, como os demais itens)
            fundo_reserva[chave_saldo] = {
                'valor': vizei_utils.str_br_to_float(valor_saldo_str)
            }
            
            end_index = i + 1 # Próxima linha é o fim do bloco de extração
            dentro_bloco = False
            break
            
        # C. Linha de Total (Crédito e Débito)
        match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
        if match_total:
            # Captura os valores totais
            credito_str = match_total.group(1)
            debito_str = match_total.group(2)
            
            fundo_reserva["total"]["credito"] = vizei_utils.str_br_to_float(credito_str)
            fundo_reserva["total"]["debito"] = vizei_utils.str_br_to_float(debito_str)
            continue 
            
        # D. Linhas de Itens (Descrições e valores)
        match_item = re.search(REGEX_ITEM_SIMPLES, linha_limpa)
        if match_item:
            descricao_completa = match_item.group(1).strip()
            valor = vizei_utils.str_br_to_float(match_item.group(2))
            
            item_data: Dict[str, Any] = {"valor": valor}
            
            # Tenta extrair a data se for uma linha de SALDO ANTERIOR
            if descricao_completa.startswith("SALDO ANTERIOR"):
                match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                if match_data:
                    item_data['date'] = match_data.group(1)
            
            # Adiciona o item
            fundo_reserva[descricao_completa] = item_data
            continue

    if not bloco_encontrado:
        return ({"erro": "Bloco de Fundo de Reserva não encontrado."}, texto_bruto)
    
    if end_index == -1:
        return ({"erro": "Linha de FIM (SALDO ATUAL) não foi localizada."}, texto_bruto)

    # 4. Montar o texto restante (linhas antes do início + linhas depois do fim)
    
    # O bloco extraído vai de start_index até end_index - 1
    linhas_antes = "\n".join(linhas[:start_index])
    linhas_depois = "\n".join(linhas[end_index:])
    
    texto_restante = (linhas_antes + "\n" + linhas_depois).strip()

    # Formata a saída para o padrão solicitado (envolvido por "fundo_de_reserva")
    final_output = {
        "fundo_de_reserva": fundo_reserva
    }

    return (final_output, texto_restante)

def parsear_sabesp_comgas(texto_bruto: str) -> Tuple[Dict[str, Any], str]:
    """
    Extrai o bloco completo SABESP/COMGAS, composto por Resumo de Emissões e Posição Financeira.

    Args:
        texto_bruto: O texto completo a ser analisado.
        
    Returns:
        Uma tupla contendo o objeto parseado e o texto restante.
    """
    
    linhas = texto_bruto.split('\n')
    
    # --- Funções Auxiliares (Lógica herdada dos parsers anteriores) ---

    def _parsear_resumo_emissoes(sub_linhas: List[str]) -> Tuple[Dict[str, Any], int]:
        """
        Extrai o bloco de Resumo de Emissões Colunado (sub-bloco 1).
        Retorna o objeto e o índice da última linha consumida.
        """
        resumo_emissao: Dict[str, Any] = {
            'total': {'previsto': None, 'realizado': None},
            'itens': {}
        }
        
        REGEX_LINHA_TOTAL = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_ITEM_COLUNADO = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        MARCADOR_FIM_KEY = "COTAS REC. DE COBRANÇA"
        
        # O parse começa após "Resumo de Emissões Colunado RealizadoPrevisto" (índice 0)
        i = 1 
        ultima_linha_consumida = -1

        while i < len(sub_linhas):
            linha_limpa = sub_linhas[i].strip()

            # 1. Linha de Total (dois valores colados)
            match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
            if match_total:
                resumo_emissao["total"]["realizado"] = vizei_utils.str_br_to_float(match_total.group(1))
                resumo_emissao["total"]["previsto"] = vizei_utils.str_br_to_float(match_total.group(2))
                i += 1
                ultima_linha_consumida = i - 1
                continue
            
            # 2. Linha de Fim (COTAS REC. DE COBRANÇA com 1 valor, logo após o total)
            if linha_limpa.startswith(MARCADOR_FIM_KEY) and resumo_emissao["total"]["realizado"] is not None:
                REGEX_LINHA_FIM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
                match_fim = re.search(REGEX_LINHA_FIM_SIMPLES, linha_limpa)
                if match_fim:
                    descricao_completa = match_fim.group(1).strip()
                    valor_realizado = vizei_utils.str_br_to_float(match_fim.group(2))
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                    data_fim = match_data.group(1) if match_data else None

                    resumo_emissao[MARCADOR_FIM_KEY] = {
                        'date': data_fim,
                        'realizado': valor_realizado,
                    }
                    ultima_linha_consumida = i
                    return (resumo_emissao, ultima_linha_consumida) # FIM do sub-bloco
                
            # 3. Linhas de Itens
            match_item = re.search(REGEX_ITEM_COLUNADO, linha_limpa)
            if match_item:
                descricao_completa = match_item.group(1).strip()
                realizado = vizei_utils.str_br_to_float(match_item.group(2))
                previsto = vizei_utils.str_br_to_float(match_item.group(3))
                
                item_data: Dict[str, Any] = {"realizado": realizado, "previsto": previsto}
                
                if descricao_completa.startswith(MARCADOR_FIM_KEY):
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                    item_data['date'] = match_data.group(1) if match_data else None
                
                # Usa a descrição limpa como chave, ignorando a data
                chave = re.sub(r'\s+EM\s+\d{2}/\d{2}/\d{4}$', '', descricao_completa).strip()
                resumo_emissao['itens'][chave] = item_data
                
            i += 1
        return (resumo_emissao, ultima_linha_consumida) # Se o loop terminar sem o FIM

    def _parsear_posicao_financeira(sub_linhas: List[str]) -> Tuple[Dict[str, Any], int]:
        """
        Extrai o bloco de Posição Financeira (sub-bloco 2).
        Retorna o objeto e o índice da última linha consumida.
        """
        posicao_financeira: Dict[str, Any] = {
            'total': {'credito': None, 'debito': None},
        }
        
        REGEX_LINHA_TOTAL = r'^\s*TOTAIS\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_LINHA_SALDO_ATUAL = r'^\s*SALDO ATUAL\s*(CREDOR|DEVEDOR|)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_ITEM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'

        # O parse começa após "Posição Financeira CréditoDébito" (índice 0)
        i = 1 
        ultima_linha_consumida = -1

        while i < len(sub_linhas):
            linha_limpa = sub_linhas[i].strip()

            # 1. Linha de Fim (Saldo Atual)
            match_saldo_atual = re.search(REGEX_LINHA_SALDO_ATUAL, linha_limpa)
            if match_saldo_atual:
                tipo_saldo = match_saldo_atual.group(1).strip() if match_saldo_atual.group(1) else ""
                valor_saldo_str = match_saldo_atual.group(2)
                chave_saldo = f"SALDO ATUAL {tipo_saldo}".strip()
                
                posicao_financeira[chave_saldo] = {'valor': vizei_utils.str_br_to_float(valor_saldo_str)}
                
                ultima_linha_consumida = i
                return (posicao_financeira, ultima_linha_consumida) # FIM do sub-bloco
            
            # 2. Linha de Total
            match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
            if match_total:
                posicao_financeira["total"]["credito"] = vizei_utils.str_br_to_float(match_total.group(1))
                posicao_financeira["total"]["debito"] = vizei_utils.str_br_to_float(match_total.group(2))
                i += 1
                ultima_linha_consumida = i - 1
                continue 
                
            # 3. Linhas de Itens
            match_item = re.search(REGEX_ITEM_SIMPLES, linha_limpa)
            if match_item:
                descricao_completa = match_item.group(1).strip()
                valor = vizei_utils.str_br_to_float(match_item.group(2))
                
                item_data: Dict[str, Any] = {"valor": valor}
                
                if descricao_completa.startswith("SALDO ANTERIOR"):
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                    if match_data:
                        item_data['date'] = match_data.group(1)
                
                posicao_financeira[descricao_completa] = item_data
            
            i += 1
        return (posicao_financeira, ultima_linha_consumida) # Se o loop terminar sem o FIM

    # --- Lógica Principal (Coordenador) ---

    MARCADOR_BLOCO_PRINCIPAL = "SABESP/COMGAS (CONTA CORRENTE)"
    MARCADOR_RESUMO_INICIO = "Resumo de Emissões Colunado"
    MARCADOR_POSICAO_INICIO = "Posição Financeira"

    start_index = -1
    
    # 1. Encontrar o início do bloco principal (SABESP/COMGAS)
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(MARCADOR_BLOCO_PRINCIPAL):
            # E a próxima linha deve ser o resumo de emissões
            if i + 1 < len(linhas) and linhas[i+1].strip().startswith(MARCADOR_RESUMO_INICIO):
                start_index = i
                break
            
    if start_index == -1:
        return ({"erro": "Bloco SABESP/COMGAS não encontrado."}, texto_bruto)

    # 2. Preparar sub-linhas para o Resumo de Emissões (começa no Resumo de Emissões Colunado)
    start_resumo_index = start_index + 1
    
    # Encontrar o índice onde começa a Posição Financeira (ou o fim do texto)
    end_resumo_index = -1
    for i in range(start_resumo_index, len(linhas)):
        if linhas[i].strip().startswith(MARCADOR_POSICAO_INICIO):
            end_resumo_index = i - 1 # O resumo termina na linha anterior
            break
        # Lidar com o caso de haver outro marcador "SABESP/COMGAS" (divisão de página)
        if linhas[i].strip().startswith(MARCADOR_BLOCO_PRINCIPAL):
             end_resumo_index = i - 1
             break
    
    if end_resumo_index == -1: end_resumo_index = len(linhas) - 1

    sub_linhas_resumo = linhas[start_resumo_index + 1 : end_resumo_index + 1]
    
    # O Resumo de Emissões precisa da linha de título para funcionar como nos parsers anteriores
    sub_linhas_resumo.insert(0, linhas[start_resumo_index].strip())
    
    resumo_emissao, ultima_linha_resumo = _parsear_resumo_emissoes(sub_linhas_resumo)
    
    # 3. Preparar sub-linhas para a Posição Financeira (começa na Posição Financeira CréditoDébito)
    # Procurar o título da Posição Financeira após o Resumo
    start_posicao_index = -1
    for i in range(start_index + ultima_linha_resumo + 2, len(linhas)):
        if linhas[i].strip().startswith(MARCADOR_POSICAO_INICIO):
            start_posicao_index = i
            break
            
    if start_posicao_index == -1:
         return ({"erro": "Bloco de Posição Financeira (SABESP/COMGAS) não encontrado."}, texto_bruto)
         
    # O bloco de Posição Financeira vai até o fim do texto ou até o próximo bloco (SALÃO DE FESTAS)
    end_posicao_index = len(linhas) 
    for i in range(start_posicao_index + 1, len(linhas)):
        if linhas[i].strip().startswith("SALÃO DE FESTAS"):
            end_posicao_index = i
            break

    sub_linhas_posicao = linhas[start_posicao_index : end_posicao_index]
    
    posicao_financeira, ultima_linha_posicao = _parsear_posicao_financeira(sub_linhas_posicao)
    
    # 4. Combinar Resultados
    
    # Remove as chaves de itens e total e as promove para o nível "resumo" e "posicao_financeira"
    resumo_output = {
        'total': resumo_emissao.pop('total'),
        **resumo_emissao.pop('itens')
    }
    
    posicao_output = {
        'total': posicao_financeira.pop('total'),
        **posicao_financeira
    }
    
    final_output = {
        "sabesp_comgas": {
            "resumo": resumo_output,
            "posicao_financeira": posicao_output
        }
    }
    
    # 5. Montar o texto restante (tudo que vem antes do início + tudo que vem após o fim da Posição Financeira)
    
    # O bloco extraído vai de start_index até start_posicao_index + ultima_linha_posicao
    linhas_antes = "\n".join(linhas[:start_index])
    linhas_depois = "\n".join(linhas[start_posicao_index + ultima_linha_posicao + 1:])
    
    texto_restante = (linhas_antes + "\n" + linhas_depois).strip()

    return (final_output, texto_restante)



def parsear_salao_de_festas(texto_bruto: str) -> Tuple[Dict[str, Any], str]:
    """
    Extrai o bloco completo SALÃO DE FESTAS, composto por Resumo de Emissões e Posição Financeira.

    Args:
        texto_bruto: O texto completo a ser analisado.
        
    Returns:
        Uma tupla contendo o objeto parseado e o texto restante.
    """
    
    linhas = texto_bruto.split('\n')

    # --- Funções Auxiliares (Lógicas adaptadas) ---

    def _parsear_resumo_emissoes_salao(sub_linhas: List[str]) -> Tuple[Dict[str, Any], int]:
        resumo_emissao: Dict[str, Any] = {
            'total': {'previsto': None, 'realizado': None},
            'itens': {}
        }
        
        REGEX_LINHA_TOTAL = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_ITEM_COLUNADO = (
            r'^(.*?)\s*'
            r'(-?\d{1,3}(?:\.\d{3})*,\d{2})'
            r'(?:\s*(-?\d{1,3}(?:\.\d{3})*,\d{2}))?\s*$'
        )
        REGEX_ITEM_UNICO = r'^(.*?)\s*(\d{2}/\d{2}/\d{4})\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'

        MARCADOR_DEVEDORES = "DEVEDORES"
        MARCADOR_INICIO_KEY = "DEVEDORES_INICIAL"
        MARCADOR_FIM_KEY = "DEVEDORES_FINAL"

        i = 1
        ultima_linha_consumida = -1
        apos_total = False
        aguardando_dev_final = None  # guarda {"descricao": str, "date": str}

        while i < len(sub_linhas):
            linha_limpa = sub_linhas[i].strip()

            # ---------------------------------------------------------
            # 1) Caso especial: DEVEDORES_FINAL quebrado em 2 linhas
            # ---------------------------------------------------------
            if aguardando_dev_final:
                if re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$', linha_limpa):
                    valor_realizado = vizei_utils.str_br_to_float(linha_limpa)
                    resumo_emissao[MARCADOR_FIM_KEY] = {
                        "date": aguardando_dev_final["date"],
                        "realizado": valor_realizado,
                        "previsto": 0
                    }
                    ultima_linha_consumida = i
                    return resumo_emissao, ultima_linha_consumida
                else:
                    aguardando_dev_final = None  # abandono
            

            # ---------------------------------------------------------
            # 2) Linha TOTAL → ativa lógica "após o total"
            # ---------------------------------------------------------
            match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
            if match_total:
                resumo_emissao["total"]["realizado"] = vizei_utils.str_br_to_float(match_total.group(1))
                resumo_emissao["total"]["previsto"] = vizei_utils.str_br_to_float(match_total.group(2))
                apos_total = True
                ultima_linha_consumida = i
                i += 1
                continue

            # ---------------------------------------------------------
            # 3) DEVEDORES_INICIAL (primeira ocorrência)
            # ---------------------------------------------------------
            match_unico = re.search(REGEX_ITEM_UNICO, linha_limpa)
            if linha_limpa.startswith(MARCADOR_DEVEDORES) and resumo_emissao["total"]["previsto"] is None and match_unico:
                data = match_unico.group(2)
                valor_previsto = vizei_utils.str_br_to_float(match_unico.group(3))
                resumo_emissao[MARCADOR_INICIO_KEY] = {
                    "date": data,
                    "previsto": valor_previsto
                }
                i += 1
                continue

            # ---------------------------------------------------------
            # 4) DEVEDORES_FINAL – pode vir inteiro ou quebrado em 2 linhas
            # ---------------------------------------------------------
            if linha_limpa.startswith(MARCADOR_DEVEDORES) and apos_total:

                # Caso 1: tudo na mesma linha → descricao + data + valor
                match_unico_fim = re.search(REGEX_ITEM_UNICO, linha_limpa)
                if match_unico_fim:
                    descricao = match_unico_fim.group(1).strip()
                    data_fim = match_unico_fim.group(2)
                    valor_realizado = vizei_utils.str_br_to_float(match_unico_fim.group(3))

                    resumo_emissao[MARCADOR_FIM_KEY] = {
                        "date": data_fim,
                        "realizado": valor_realizado,
                        "previsto": 0
                    }

                    ultima_linha_consumida = i
                    i += 1
                    continue

                # Caso 2: linha contém descrição + data, e valor aparece na linha seguinte
                match_data = re.search(r'(.*?)(\d{2}/\d{2}/\d{4})$', linha_limpa)
                if match_data:
                    aguardando_dev_final = {
                        "descricao": match_data.group(1).strip(),
                        "date": match_data.group(2)
                    }
                    i += 1
                    continue

            # ---------------------------------------------------------
            # 5) Itens gerais
            # ---------------------------------------------------------
            match_item = re.search(REGEX_ITEM_COLUNADO, linha_limpa)
            if match_item:
                descricao = match_item.group(1).strip()
                valor1 = vizei_utils.str_br_to_float(match_item.group(2))
                valor2_raw = match_item.group(3)

                if valor2_raw:
                    realizado = valor1
                    previsto = vizei_utils.str_br_to_float(valor2_raw)
                else:
                    # LÓGICA CORRIGIDA:
                    # antes do total → PREVISTO
                    # depois do total → REALIZADO
                    if apos_total:
                        realizado = valor1
                        previsto = 0
                    else:
                        realizado = 0
                        previsto = valor1

                resumo_emissao['itens'][descricao] = {
                    "realizado": realizado,
                    "previsto": previsto
                }
                i += 1
                continue

            i += 1

        return resumo_emissao, ultima_linha_consumida


    def _parsear_posicao_financeira_salao(sub_linhas: List[str]) -> Tuple[Dict[str, Any], int]:
        """
        Extrai o bloco de Posição Financeira (sub-bloco 2).
        Retorna o objeto e o índice da última linha consumida.
        """
        posicao_financeira: Dict[str, Any] = {
            'total': {'credito': None, 'debito': None},
        }
        
        REGEX_LINHA_TOTAL = r'^\s*TOTAIS\s*(\d{1,3}(?:\.\d{3})*,\d{2})(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_LINHA_SALDO_ATUAL = r'^\s*SALDO ATUAL\s*(CREDOR|DEVEDOR|)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        REGEX_ITEM_SIMPLES = r'^(.*?)\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'

        i = 1 
        ultima_linha_consumida = -1

        while i < len(sub_linhas):
            linha_limpa = sub_linhas[i].strip()

            # 1. Linha de Fim (Saldo Atual)
            match_saldo_atual = re.search(REGEX_LINHA_SALDO_ATUAL, linha_limpa)
            if match_saldo_atual:
                tipo_saldo = match_saldo_atual.group(1).strip() if match_saldo_atual.group(1) else ""
                valor_saldo_str = match_saldo_atual.group(2)
                chave_saldo = f"SALDO ATUAL {tipo_saldo}".strip()
                
                posicao_financeira[chave_saldo] = {'valor': vizei_utils.str_br_to_float(valor_saldo_str)}
                
                ultima_linha_consumida = i
                return (posicao_financeira, ultima_linha_consumida) # FIM do sub-bloco
            
            # 2. Linha de Total
            match_total = re.search(REGEX_LINHA_TOTAL, linha_limpa)
            if match_total:
                posicao_financeira["total"]["credito"] = vizei_utils.str_br_to_float(match_total.group(1))
                posicao_financeira["total"]["debito"] = vizei_utils.str_br_to_float(match_total.group(2))
                i += 1
                ultima_linha_consumida = i - 1
                continue 
                
            # 3. Linhas de Itens
            match_item = re.search(REGEX_ITEM_SIMPLES, linha_limpa)
            if match_item:
                descricao_completa = match_item.group(1).strip()
                valor = vizei_utils.str_br_to_float(match_item.group(2))
                
                item_data: Dict[str, Any] = {"valor": valor}
                
                if descricao_completa.startswith("SALDO ANTERIOR"):
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})$', descricao_completa)
                    if match_data:
                        item_data['date'] = match_data.group(1)
                
                posicao_financeira[descricao_completa] = item_data
            
            i += 1
        return (posicao_financeira, ultima_linha_consumida) 

    # --- Lógica Principal (Coordenador) ---

    MARCADOR_BLOCO_PRINCIPAL = "SALÃO DE FESTAS"
    MARCADOR_RESUMO_INICIO = "Resumo de Emissões Colunado"
    MARCADOR_POSICAO_INICIO = "Posição Financeira"

    start_index = -1
    
    # 1. Encontrar o início do bloco principal (SALÃO DE FESTAS)
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(MARCADOR_BLOCO_PRINCIPAL) and (i + 1 < len(linhas) and linhas[i+1].strip().startswith(MARCADOR_RESUMO_INICIO)):
            start_index = i
            break
            
    if start_index == -1:
        return ({"erro": "Bloco SALÃO DE FESTAS não encontrado."}, texto_bruto)

    # 2. Resumo de Emissões
    start_resumo_index = start_index + 1
    
    # Encontrar o índice onde começa a Posição Financeira (ou o próximo bloco)
    end_resumo_index = -1
    for i in range(start_resumo_index, len(linhas)):
        if linhas[i].strip().startswith(MARCADOR_POSICAO_INICIO):
            end_resumo_index = i - 1 # O resumo termina na linha anterior
            break
        
    if end_resumo_index == -1: end_resumo_index = len(linhas) - 1

    # As sub_linhas_resumo incluem o título do resumo, necessário para a função auxiliar
    sub_linhas_resumo = linhas[start_resumo_index : end_resumo_index + 1]
    
    resumo_emissao, ultima_linha_resumo = _parsear_resumo_emissoes_salao(sub_linhas_resumo)
    
    # 3. Posição Financeira
    # O início da Posição Financeira é na linha após o DEVEDORES final do resumo
    start_posicao_index = -1
    for i in range(start_resumo_index + ultima_linha_resumo + 1, len(linhas)):
        if linhas[i].strip().startswith(MARCADOR_POSICAO_INICIO):
            start_posicao_index = i
            break
            
    if start_posicao_index == -1:
         return ({"erro": "Bloco de Posição Financeira (SALÃO DE FESTAS) não encontrado."}, texto_bruto)
         
    # O bloco de Posição Financeira vai até o próximo bloco (RELAÇÃO DE COTAS EM ABERTO)
    end_posicao_index = len(linhas) 
    for i in range(start_posicao_index + 1, len(linhas)):
        if linhas[i].strip().startswith("RELAÇÃO DE COTAS EM ABERTO"):
            end_posicao_index = i
            break

    sub_linhas_posicao = linhas[start_posicao_index : end_posicao_index]
    
    posicao_financeira, ultima_linha_posicao = _parsear_posicao_financeira_salao(sub_linhas_posicao)
    
    # 4. Combinar Resultados
    
    # Ajustar a estrutura do Resumo: mover itens do dicionário 'itens' para o nível principal, junto com o total
    resumo_output = {
        'total': resumo_emissao.pop('total')
    }
    # Os itens "DEVEDORES" (início e fim) estão no nível superior do resumo_emissao. 
    # Mover também os itens normais (dentro de 'itens')
    resumo_output.update(resumo_emissao.pop('itens'))
    # Mover o DEVEDORES final que é o marcador de fim
    resumo_output.update({k: v for k, v in resumo_emissao.items() if k not in ['total', 'itens']})
    
    # Ajustar a estrutura da Posição Financeira
    posicao_output = {
        'total': posicao_financeira.pop('total'),
        **posicao_financeira
    }
    
    final_output = {
        "salao_de_festas": {
            "resumo": resumo_output,
            "posicao_financeira": posicao_output
        }
    }
    
    # 5. Montar o texto restante 
    
    # O bloco extraído vai de start_index até start_posicao_index + ultima_linha_posicao
    linhas_antes = "\n".join(linhas[:start_index])
    linhas_depois = "\n".join(linhas[start_posicao_index + ultima_linha_posicao + 1:])
    
    texto_restante = (linhas_antes + "\n" + linhas_depois).strip()

    return (final_output, texto_restante)

def parsear_cotas_em_aberto(texto_bruto: str) -> Dict[str, Any]:
    """
    Extrai o bloco "RELAÇÃO DE COTAS EM ABERTO", separando por bloco (BLANC, GRIS).
    """
    
    linhas = texto_bruto.split('\n')
    
    texto_filtrado = []
    # Regex para linha de Unidade: 1. Total (float BR), 2. Unidade (01 023), 3. Período, 4. Status (Opcional, AJP)
    # Regex para linha de Total do Bloco 1. Total do Bloco (float BR), 2. Nome do Bloco (BLANC/GRIS)
    # Regex para linha de Total Geral 1. Total Geral (float BR)
    REGEX_LINHA_UNIDADE = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*(\d{2}\s*\d{3})\s*(\d{2}/\d{2}/\d{4}\s*a\s*\d{2}/\d{2}/\d{4})([AJP])?\s*$'
    REGEX_LINHA_TOTAL_BLOCO = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*Total do Bloco:\s*(\w+)\s*$'    
    REGEX_LINHA_TOTAL_GERAL = r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*Total geral:\s*$'

    cotas_em_aberto: Dict[str, Any] = {'total': None}
    dentro_bloco = False
    #bloco_atual_nome: Optional[str] = None
    lista_blocos = []
    for linha in linhas:
        
        linha_limpa = linha.strip()
        
        if linha_limpa.startswith("RELAÇÃO DE COTAS EM ABERTO"):
            dentro_bloco = True
            bloco_atual = {}
            continue  

        if not dentro_bloco:
            texto_filtrado.append(linha)
            continue
        elif linha_limpa.startswith("Unidade Período Total"):
            continue
        

        # 1. Linha de Unidade (Item devedor)
        match_unidade = re.search(REGEX_LINHA_UNIDADE, linha_limpa)        
        if match_unidade:
            valor_total = vizei_utils.str_br_to_float(match_unidade.group(1))
            unidade = match_unidade.group(2).replace(' ', '')
            periodo = match_unidade.group(3).strip()
            status = match_unidade.group(4)
            if unidade not in bloco_atual.keys():
                bloco_atual[unidade] = {
                'valor_total': valor_total,
                'periodo': periodo,
                'status_cobranca': status if status else None
            }
            
        # 2. Linha de Total do Bloco (Define o bloco atual)
        match_total_bloco = re.search(REGEX_LINHA_TOTAL_BLOCO, linha_limpa)
        if match_total_bloco:
            valor_total = vizei_utils.str_br_to_float(match_total_bloco.group(1))
            nome_bloco = match_total_bloco.group(2)

            bloco_atual['valor_total'] = valor_total
            bloco_atual['nome'] = nome_bloco
            lista_blocos.append(bloco_atual)
            bloco_atual = {}
            continue
            
        # 1. Linha de Total Geral
        match_total_geral = re.search(REGEX_LINHA_TOTAL_GERAL, linha_limpa)
        if match_total_geral:
            cotas_em_aberto['total'] = vizei_utils.str_br_to_float(match_total_geral.group(1))

            # arruma bloco:
            for bloco in lista_blocos:
                cotas_em_aberto[bloco['nome']] = bloco
            
            dentro_bloco = False
            continue        

    return (cotas_em_aberto, texto_filtrado)









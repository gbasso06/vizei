import vizei_utils

def validar_saldos(saldos, tolerancia=1e-6):
    for item in saldos['contas']:
        # Cada item é um dict com apenas 1 chave (nome da conta)
        nome_conta = vizei_utils.normalize(item)
        valores = saldos[nome_conta]

        anterior = valores.get("anterior", 0)
        credito  = valores.get("credito", 0)
        debito   = valores.get("debito", 0)
        atual    = valores.get("atual", 0)

        calculado = anterior + credito - debito

        # Verificação com tolerância
        if abs(calculado - atual) > tolerancia:
            print(f"❌ Divergência na conta '{nome_conta}': calculado={calculado}, atual={atual}")
            return False

    return True


def validar_posicao_financeira(data, categorias):

    pf = data.get("posicao_financeira", {})
    total_oficial = pf.get("total", {})
    total_credito_oficial = total_oficial.get("credito", 0)
    total_debito_oficial = total_oficial.get("debito", 0)

    # Palavras que indicam débito (ajustada — removido FUNDO DE RESERVA)
    palavras_debito = [
        "APLICAÇÃO",
        "APLICACAO",
        "DESPESA",
        "PESSOAL",
        "CONSUMO",
        "CONSUMOS",
        "MANUTENÇÃO",
        "MANUTENCAO",
        "BLOQUEIO JUDICIAL",
        "ADMINISTRATIVA"
    ]
    palavras_debito.extend(categorias)

    total_credito_calc = 0
    total_debito_calc = 0

    classificacao = {}
    logs = []

    for nome, info in pf.items():
        if nome == "total":
            continue

        nome_up = vizei_utils.normalize(nome.upper())

        # normaliza 
        if isinstance(info, list):
            itens = info
        else:
            itens = [info]
            
        # 1. REGRAS FIXAS PARA SALDOS --------------------------------
        if "SALDO ANTERIOR" in nome_up:
            categoria = "credito" if "CREDOR" in nome_up else "debito"
            logs.append(f"[SALDO] {nome} ⇒ {categoria}")

        elif "SALDO ATUAL" in nome_up:
            categoria = "saldo_final"
            logs.append(f"[SALDO] {nome} ⇒ saldo_final")

        # 2. REGRAS ESPECÍFICAS PARA: FUNDO DE RESERVA, CONSUMO DE AGUA E GAS, FUNDO DE MANUTENCAO ----------------
        elif nome_up.startswith("APLICAÇÃO FUNDO DE RESERVA"):
            categoria = "debito"
            logs.append(f"[REGRA ESPECÍFICA] {nome} ⇒ DÉBITO")

        elif nome_up == "FUNDO DE RESERVA":
            categoria = "credito"
            logs.append(f"[REGRA ESPECÍFICA] {nome} ⇒ CRÉDITO")

        elif nome_up.startswith("CONSUMO DE"):
            categoria = "credito"
            logs.append(f"[REGRA ESPECÍFICA] {nome} ⇒ CRÉDITO")

        # elif nome_up.startswith("DIVERSOS/EVENTUAIS/TERCEIROS"):
            # categoria = "debito"
            # logs.append(f"[REGRA ESPECÍFICA] {nome} ⇒ DÉBITO")


        elif nome_up.startswith("FUNDO MANUTENÇÃO") or nome_up.startswith("FUNDO MANUTENCAO"):
            categoria = "credito"
            logs.append(f"[REGRA ESPECÍFICA] {nome} ⇒ CRÉDITO")
        
        # 3. HEURÍSTICA DE DÉBITO POR PALAVRA-CHAVE -----------------
        elif any(p in nome_up for p in palavras_debito):
            categoria = "debito"
            logs.append(f"[HEURÍSTICA] {nome} ⇒ DÉBITO")

        # 4. REGRA GERAL --------------------------------------------
        else:
            categoria = "credito"
            logs.append(f"[REGRA GERAL] {nome} ⇒ CRÉDITO")

        classificacao[nome] = categoria

        # Soma final
        for item in itens:
            valor = item.get("valor", 0)
            logs.append(f"    - item '{nome}': valor={valor}")
            
            if categoria == "credito":
                total_credito_calc += valor
            elif categoria == "debito":
                total_debito_calc += valor

    # 5. Comparações finais -----------------------------------------
    divergencias = []
    if abs(total_credito_calc - total_credito_oficial) > 1e-6:
        divergencias.append(
            f"Crédito divergente: calculado {total_credito_calc}, oficial {total_credito_oficial}"
        )

    if abs(total_debito_calc - total_debito_oficial) > 1e-6:
        divergencias.append(
            f"Débito divergente: calculado {total_debito_calc}, oficial {total_debito_oficial}"
        )

    return {
        "valido": len(divergencias) == 0,
        "creditos_calculados": total_credito_calc,
        "debitos_calculados": total_debito_calc,
        "creditos_oficial": total_credito_oficial,
        "debitos_oficial": total_debito_oficial,
        "classificacao": classificacao,
        "logs": logs,
        "divergencias": divergencias,
    }


def validar_despesas_ordinarias(data):
    logs = []
    valido = True

    # 1 — Total oficial
    total_oficial = data.get("TOTAL_DESPESAS", 0)

    soma_categorias = 0

    # Percorre todas as chaves (categorias)
    for categoria, conteudo in data.items():
        if categoria in ["TOTAL_DESPESAS", "CATEGORIAS"]:
            continue
        
        subtotal_oficial = conteudo.get("subtotal", 0)
        despesas = conteudo.get("despesas", [])

        # Soma real das despesas da categoria
        subtotal_calculado = sum(item.get("valor", 0) for item in despesas)

        # Adiciona ao total geral calculado
        soma_categorias += subtotal_calculado

        # Valida subtotal
        if abs(subtotal_calculado - subtotal_oficial) > 1e-6:
            valido = False
            logs.append(
                f"[ERRO SUBTOTAL] Categoria '{categoria}': subtotal oficial {subtotal_oficial} "
                f"≠ calculado {subtotal_calculado}"
            )
        else:
            logs.append(
                f"[OK SUBTOTAL] Categoria '{categoria}' confere: {subtotal_calculado}"
            )

    # 2 — Valida soma dos subtotais vs total geral
    if abs(soma_categorias - total_oficial) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL] Soma dos subtotais {soma_categorias} "
            f"≠ TOTAL_DESPESAS oficial {total_oficial}"
        )
    else:
        logs.append(
            f"[OK TOTAL] Soma dos subtotais confere com TOTAL_DESPESAS: {total_oficial}"
        )

    return {
        "valido": valido,
        "total_oficial": total_oficial,
        "total_calculado": soma_categorias,
        "logs": logs
    }

def validar_fundo_de_reserva(data):
    logs = []
    valido = True

    fr = data.get("fundo_de_reserva", {})

    # Extrai valores principais
    total_oficial_credito = fr.get("total", {}).get("credito", 0)
    total_oficial_debito = fr.get("total", {}).get("debito", 0)

    # 1) Localiza o SALDO ANTERIOR de forma genérica
    # ---------------------------
    saldo_anterior = 0
    chave_saldo_anterior = None

    # for chave, bloco in fr.items():
    #     if "SALDO ANTERIOR" in chave.upper():
    #         chave_saldo_anterior = chave
    #         saldo_anterior = bloco.get("valor", 0)
    #         logs.append(f"[INFO] Detectado saldo anterior na chave: '{chave}' -> {saldo_anterior}")
    #         break

    
    saldo_atual_oficial = fr.get("SALDO ATUAL CREDOR", {}).get("valor", 0)

    # Regras de classificação
    CREDITOS = {"APLICAÇÃO", "RENDIMENTOS"}
    DEBITOS = {"RESGATE", "I.R.R.F."}

    credito_calc = 0
    debito_calc = 0
    classificacao = {}


    # Percorre todos os campos do fundo de reserva
    for chave, bloco in fr.items():

        nome_up = chave.upper()

        if chave in ["total"]:
            continue

        valor = bloco.get("valor", 0)
        
        if "SALDO ANTERIOR" in nome_up:
            if "CREDOR" in nome_up:
                natureza = "credito" 
                credito_calc += valor
            else:
                natureza ="debito"
                debito_calc += valor
            logs.append(f"[SALDO] {chave} ⇒ {natureza}")

        elif "SALDO ATUAL" in nome_up:
            natureza = "saldo_final"
            logs.append(f"[SALDO] {chave} ⇒ {natureza}")

        elif chave in CREDITOS:
            natureza = 'credito'
            credito_calc += valor
            logs.append(f"[CREDITO] {chave}: +{valor}")

        elif chave in DEBITOS:
            natureza = 'debito'
            debito_calc += valor
            logs.append(f"[DEBITO] {chave}: -{valor}")

        else:
            natureza = None
            logs.append(f"[IGNORADO] {chave}: não classificado")

        classificacao[chave] = natureza

    # Validação dos totais de créditos e débitos
    if abs(credito_calc - total_oficial_credito) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL CREDITO] Calculado {credito_calc} "
            f"≠ Oficial {total_oficial_credito}"
        )
    else:
        logs.append(f"[OK TOTAL CREDITO] {credito_calc}")

    if abs(debito_calc - total_oficial_debito) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL DEBITO] Calculado {debito_calc} "
            f"≠ Oficial {total_oficial_debito}"
        )
    else:
        logs.append(f"[OK TOTAL DEBITO] {debito_calc}")

    # Valida saldo final
    saldo_calculado = saldo_anterior + credito_calc - debito_calc

    if abs(saldo_calculado - saldo_atual_oficial) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO SALDO] Saldo final calculado {saldo_calculado} "
            f"≠ Saldo oficial {saldo_atual_oficial}"
        )
    else:
        logs.append(
            f"[OK SALDO] Saldo final confere: {saldo_calculado}"
        )

    return {
        "valido": valido,
        "classificacao": classificacao,
        "creditos_calculados": credito_calc,
        "debitos_calculados": debito_calc,
        "saldo_calculado": saldo_calculado,
        "saldo_oficial": saldo_atual_oficial,
        "logs": logs
    }



def validar_sabesp_comgas(data):
    logs = []
    valido = True

    bloco = data.get("sabesp_comgas", {})

    # ============================================
    # 1) Validação do RESUMO
    # ============================================

    resumo = bloco.get("resumo", {})
    total_previsto = resumo.get("total", {}).get("previsto", 0)
    total_realizado = resumo.get("total", {}).get("realizado", 0)

    # Encontrar chave de resumo detalhado (ex: "COTAS REC. DE COBRANÇA")
    detalhe_previsto = 0
    detalhe_realizado = 0

    for chave, item in resumo.items():

        if chave == "total":
            continue
        if isinstance(item, dict) and "previsto" in item and "realizado" in item:
            detalhe_previsto = item.get("previsto", 0)
            detalhe_realizado = item.get("realizado", 0)
            chave_detalhada = chave
            break

    # Valida previsto
    if abs(detalhe_previsto - total_previsto) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO RESUMO PREVISTO] '{chave_detalhada}': {detalhe_previsto} ≠ total {total_previsto}"
        )
    else:
        logs.append(f"[OK RESUMO PREVISTO] {detalhe_previsto}")

    # Valida realizado
    if abs(detalhe_realizado - total_realizado) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO RESUMO REALIZADO] '{chave_detalhada}': {detalhe_realizado} ≠ total {total_realizado}"
        )
    else:
        logs.append(f"[OK RESUMO REALIZADO] {detalhe_realizado}")

    # ============================================
    # 2) Validação da POSIÇÃO FINANCEIRA
    # ============================================

    pf = bloco.get("posicao_financeira", {})

    total_credito = pf.get("total", {}).get("credito", 0)
    total_debito = pf.get("total", {}).get("debito", 0)

    # -------------------------
    # Saldo anterior (detectado automaticamente)
    # -------------------------
    saldo_anterior = 0
    chave_saldo_anterior = None

    for chave, item in pf.items():
        if "SALDO ANTERIOR" in chave.upper():
            chave_saldo_anterior = chave
            saldo_anterior = item.get("valor", 0)
            logs.append(f"[INFO] Saldo anterior detectado: {chave} = {saldo_anterior}")
            break

    # -------------------------
    # Saldo atual (detectado automaticamente)
    # -------------------------
    saldo_atual = 0
    chave_saldo_atual = None

    for chave, item in pf.items():
        if "SALDO ATUAL" in chave.upper():
            chave_saldo_atual = chave
            saldo_atual = item.get("valor", 0)
            logs.append(f"[INFO] Saldo atual detectado: {chave} = {saldo_atual}")
            break

    # -------------------------
    # CLASSIFICAÇÃO AUTOMÁTICA
    # -------------------------

    CREDITOS = {
        "COTAS REC. DE COBRANCA",
        "ATUALIZACAO MONETARIA",
        "JUROS",
        "MULTAS REC. DE COBRANCA"
    }

    DEBITOS = {"TRANSFERENCIA ENTRE CONTAS"}

    credito_calc = 0
    debito_calc = 0
    categorias = {}

    for chave, item in pf.items():

        if chave in ["total", chave_saldo_anterior, chave_saldo_atual]:
            continue

        valor = item.get("valor", 0)

        normalized_chave = vizei_utils.normalize(chave)
        if normalized_chave in CREDITOS:
            categorias[chave] = 'credito'
            credito_calc += valor
            logs.append(f"[CREDITO] {chave}: +{valor}")

        elif normalized_chave in DEBITOS:
            categorias[chave] = 'debito'
            debito_calc += valor
            logs.append(f"[DEBITO] {chave}: -{valor}")

        else:
            logs.append(f"[IGNORADO] {chave}: não classificado")

    # -------------------------
    # Validação dos totais
    # -------------------------

    if abs(credito_calc - total_credito) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL CREDITO] {credito_calc} ≠ oficial {total_credito}"
        )
    else:
        logs.append(f"[OK TOTAL CREDITO] {credito_calc}")

    if abs(debito_calc - total_debito) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL DEBITO] {debito_calc} ≠ oficial {total_debito}"
        )
    else:
        logs.append(f"[OK TOTAL DEBITO] {debito_calc}")

    # -------------------------
    # Validação do saldo final
    # -------------------------
    saldo_calculado = saldo_anterior + credito_calc - debito_calc

    if abs(saldo_calculado - saldo_atual) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO SALDO FINAL] calculado {saldo_calculado} ≠ oficial {saldo_atual}"
        )
    else:
        logs.append(f"[OK SALDO FINAL] {saldo_calculado}")

    return {
        "valido": valido,
        "classificacao": categorias,
        "creditos_calculados": credito_calc,
        "debitos_calculados": debito_calc,
        "saldo_calculado": saldo_calculado,
        "saldo_oficial": saldo_atual,
        "logs": logs
    }


def validar_salao_de_festas(data):
    logs = []
    valido = True
    classificacao_resumo = {}

    bloco = data.get("salao_de_festas", {})

    # =====================================================
    # 1) VALIDAR RESUMO
    # =====================================================

    resumo = bloco.get("resumo", {})
    total_previsto = resumo.get("total", {}).get("previsto", 0)
    total_realizado = resumo.get("total", {}).get("realizado", 0)

    soma_previsto = 0
    soma_realizado = 0

    for chave, item in resumo.items():
        
        if chave == "total":
            continue
        
        normalized_key = vizei_utils.normalize(chave)
        if normalized_key in ["DEVEDORES_FINAL", "COTAS EM PROCESSO DE COBRANCA"]:
            continue


        if isinstance(item, dict):
            previsto = item.get("previsto", 0)
            realizado = item.get("realizado", 0)

            soma_previsto += previsto
            soma_realizado += realizado

            # Classificação igual ao da posição financeira
            classificacao_resumo[chave] = "credito"  # tudo aqui é crédito

    # Validação previsto
    if abs(soma_previsto - total_previsto) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO RESUMO PREVISTO] somado {soma_previsto} ≠ total {total_previsto}"
        )
    else:
        logs.append(f"[OK RESUMO PREVISTO] {soma_previsto}")

    # Validação realizado
    if abs(soma_realizado - total_realizado) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO RESUMO REALIZADO] somado {soma_realizado} ≠ total {total_realizado}"
        )
    else:
        logs.append(f"[OK RESUMO REALIZADO] {soma_realizado}")

    # =====================================================
    # 2) VALIDAR POSIÇÃO FINANCEIRA
    # =====================================================

    pf = bloco.get("posicao_financeira", {})

    total_credito_oficial = pf.get("total", {}).get("credito", 0)
    total_debito_oficial = pf.get("total", {}).get("debito", 0)

    # -----------------------------------------
    # Detectar saldo anterior e saldo atual
    # -----------------------------------------

    saldo_anterior = 0
    chave_saldo_anterior = None

    for chave, item in pf.items():
        if "SALDO ANTERIOR" in chave.upper():
            saldo_anterior = item.get("valor", 0)
            chave_saldo_anterior = vizei_utils.normalize(chave)
            logs.append(f"[INFO] Saldo anterior detectado: {chave} = {saldo_anterior}")
            break

    saldo_atual = 0
    chave_saldo_atual = None

    for chave, item in pf.items():
        if "SALDO ATUAL" in chave.upper():
            saldo_atual = item.get("valor", 0)
            chave_saldo_atual = chave
            logs.append(f"[INFO] Saldo atual detectado: {chave} = {saldo_atual}")
            break

    # -----------------------------------------
    # Classificação automática
    # -----------------------------------------

    CREDITOS = {
        chave_saldo_anterior,
        "TAXA SALAO DE FESTAS",
        "TAXA SALAO GOURMET",
        "TAXA CHURRASQUEIRA",
        "ATUALIZACAO MONETARIA",
        "JUROS",
        "MULTAS",
        # a partir de jan/25
        "DEVEDORES",
        # a partir de jun/25
        "ANTECIPACOES"
    }

    DEBITOS = set()  # nenhum identificado no exemplo

    credito_calc = 0
    debito_calc = 0

    for chave, item in pf.items():

        if chave in ["total"]:
            continue

        valor = item.get("valor", 0)
        nome_up = chave.upper()
        normalized_name = vizei_utils.normalize(chave)
        
        if normalized_name in CREDITOS:
            credito_calc += valor
            logs.append(f"[CREDITO] {chave}: +{valor}")

        elif normalized_name in DEBITOS:
            debito_calc += valor
            logs.append(f"[DEBITO] {chave}: -{valor}")

        else:
            logs.append(f"[IGNORADO] {chave}: não classificado")

    # -----------------------------------------
    # Validar totais oficiais
    # -----------------------------------------

    if abs(credito_calc - total_credito_oficial) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL CREDITO] calculado {credito_calc} ≠ oficial {total_credito_oficial}"
        )
    else:
        logs.append(f"[OK TOTAL CREDITO] {credito_calc}")

    if abs(debito_calc - total_debito_oficial) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO TOTAL DEBITO] calculado {debito_calc} ≠ oficial {total_debito_oficial}"
        )
    else:
        logs.append(f"[OK TOTAL DEBITO] {debito_calc}")

    # -----------------------------------------
    # Validar saldo final
    # -----------------------------------------

    saldo_final_calc = credito_calc - debito_calc

    if abs(saldo_final_calc - saldo_atual) > 1e-6:
        valido = False
        logs.append(
            f"[ERRO SALDO FINAL] calculado {saldo_final_calc} ≠ oficial {saldo_atual}"
        )
    else:
        logs.append(f"[OK SALDO FINAL] {saldo_final_calc}")

    # =====================================================
    # SAÍDA FINAL
    # =====================================================

    return {
        "valido": valido,
        "creditos_calculados": credito_calc,
        "debitos_calculados": debito_calc,
        "saldo_calculado": saldo_final_calc,
        "saldo_oficial": saldo_atual,
        "classificacao": classificacao_resumo,
        "logs": logs
    }

def validar_cotas_em_aberto(data):
    erros = {}
    totais_torres = {}
    total_geral_calculado = 0

    # total informado no payload raiz
    total_informado = data.get("total", 0)

    # percorre torres
    for torre, conteudo in data.items():
        if torre == "total":
            continue

        soma_torre = 0
        total_informado_torre = conteudo.get("valor_total", 0)

        for unidade, dados_unidade in conteudo.items():
            if unidade in ("valor_total", "nome"):
                continue

            valor = dados_unidade.get("valor_total", 0)
            soma_torre += valor

        totais_torres[torre] = soma_torre
        total_geral_calculado += soma_torre

        # valida soma da torre
        if abs(soma_torre - total_informado_torre) > 0.01:
            erros.setdefault(torre, []).append(
                f"Somatório das unidades ({soma_torre}) diferente do valor_total informado ({total_informado_torre})"
            )

    # valida total geral
    if abs(total_geral_calculado - total_informado) > 0.01:
        erros.setdefault("GERAL", []).append(
            f"Total geral calculado ({total_geral_calculado}) diferente do total informado ({total_informado})"
        )

    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "totais": {
            **totais_torres,
            "geral_calculado": total_geral_calculado,
            "geral_informado": total_informado
        }
    }



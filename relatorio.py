"""Relatório por sessão: quantas pessoas passaram por cada palestra.

Cada entrada e saída registrada é atribuída a uma sessão da programação:
- Entrada: a sessão que está acontecendo naquela sala; se nenhuma, a próxima,
  se começar em até 30 minutos (as pessoas chegam antes).
- Saída: a sessão que está acontecendo; se nenhuma, a que terminou há até
  30 minutos (as pessoas saem depois).
O que não se encaixa em nenhuma sessão fica como "fora da programação".
"""

from datetime import datetime, timedelta

MARGEM = timedelta(minutes=30)


def _horario(texto: str) -> datetime:
    # "2026-10-20T09:15:02-04:00" ou "2026-10-20T09:15" -> só até os minutos, sem fuso
    return datetime.fromisoformat(texto[:16])


def _sessao_da_entrada(sessoes, momento):
    for sessao in sessoes:
        if sessao["_inicio"] <= momento < sessao["_fim"]:
            return sessao
    for sessao in sessoes:  # estão em ordem de início: a primeira que serve é a próxima
        if momento < sessao["_inicio"] <= momento + MARGEM:
            return sessao
    return None


def _sessao_da_saida(sessoes, momento):
    for sessao in sessoes:
        if sessao["_inicio"] <= momento < sessao["_fim"]:
            return sessao
    for sessao in reversed(sessoes):  # a que terminou por último
        if sessao["_fim"] <= momento <= sessao["_fim"] + MARGEM:
            return sessao
    return None


def gerar(conn, agora: datetime) -> dict:
    """agora: horário atual de Cuiabá (para saber quais sessões já começaram)."""
    agora = agora.replace(tzinfo=None)
    ambientes = {
        linha["codigo"]: dict(linha)
        for linha in conn.execute("SELECT codigo, nome, capacidade FROM ambientes ORDER BY codigo")
    }

    # Sessões de cada ambiente, em ordem de horário
    sessoes_por_ambiente = {codigo: [] for codigo in ambientes}
    for linha in conn.execute(
        "SELECT ambiente_codigo, titulo, palestrante, inicio, fim FROM sessoes ORDER BY inicio"
    ):
        sessao = dict(linha)
        sessao.update(_inicio=_horario(sessao["inicio"]), _fim=_horario(sessao["fim"]),
                      entradas=0, saidas=0, pico=None)
        sessoes_por_ambiente[sessao["ambiente_codigo"]].append(sessao)

    fora = {codigo: {"entradas": 0, "saidas": 0} for codigo in ambientes}
    ocupacao = {codigo: 0 for codigo in ambientes}

    # Percorre os registros em ordem, acompanhando quantas pessoas há em cada sala.
    for evento in conn.execute(
        "SELECT ambiente_codigo, tipo, quantidade, horario FROM eventos WHERE desfeito = 0 ORDER BY id"
    ):
        codigo = evento["ambiente_codigo"]
        momento = _horario(evento["horario"])
        sessoes = sessoes_por_ambiente[codigo]

        # Antes de contar este registro: quem estava na sala quando a sessão começou
        # também faz parte do público dela.
        for sessao in sessoes:
            if sessao["pico"] is None and momento >= sessao["_inicio"]:
                sessao["pico"] = ocupacao[codigo]

        if evento["tipo"] == "entrada":
            ocupacao[codigo] += evento["quantidade"]
            alvo = _sessao_da_entrada(sessoes, momento)
            (alvo or fora[codigo])["entradas"] += evento["quantidade"]
        else:
            ocupacao[codigo] -= evento["quantidade"]
            alvo = _sessao_da_saida(sessoes, momento)
            (alvo or fora[codigo])["saidas"] += evento["quantidade"]

        # Maior número de pessoas na sala durante a sessão
        for sessao in sessoes:
            if sessao["_inicio"] <= momento < sessao["_fim"]:
                sessao["pico"] = max(sessao["pico"] or 0, ocupacao[codigo])

    linhas = []
    for codigo, sessoes in sessoes_por_ambiente.items():
        for sessao in sessoes:
            if sessao["pico"] is None:
                # Nenhum registro depois do início: se a sessão já começou,
                # o público é quem estava na sala; se ainda não, não há o que medir.
                sessao["pico"] = ocupacao[codigo] if sessao["_inicio"] <= agora else None
            linhas.append({
                "ambiente": ambientes[codigo]["nome"],
                "capacidade": ambientes[codigo]["capacidade"],
                "titulo": sessao["titulo"],
                "palestrante": sessao["palestrante"],
                "inicio": sessao["inicio"],
                "fim": sessao["fim"],
                "entradas": sessao["entradas"],
                "saidas": sessao["saidas"],
                "pico": sessao["pico"],
            })
    linhas.sort(key=lambda linha: (linha["inicio"], linha["ambiente"]))

    fora_da_programacao = [
        {"ambiente": ambientes[codigo]["nome"], **totais}
        for codigo, totais in fora.items()
        if totais["entradas"] or totais["saidas"]
    ]
    return {"sessoes": linhas, "fora_da_programacao": fora_da_programacao}

"""Estimativas de lotação: o voluntário olha a sala e informa "uns 60% cheia".

Regra de validade ("zera a cada sessão"): uma estimativa vale até a próxima mudança de sessão
naquela sala. Mudança de sessão = uma sessão começa ou termina. Assim, quando começa uma sessão
nova e ninguém informou nada ainda, o totem mostra "No estimate yet" em vez de um número velho.

O início de cada sessão conta 15 minutos antes (ANTECEDENCIA): as pessoas chegam antes, e o
voluntário que informa às 08:20 já está falando da sessão das 08:30.
"""

from datetime import datetime, timedelta

ANTECEDENCIA = timedelta(minutes=15)

# 0, 10, 20 ... 100, e 110 = "lotada, com gente em pé"
PORCENTAGENS = list(range(0, 101, 10)) + [110]
GENTE_EM_PE = 110


def _minutos(texto: str) -> datetime:
    """ "2026-10-20T09:15:02-04:00" ou "2026-10-20T09:15" -> datetime até os minutos, sem fuso."""
    return datetime.fromisoformat(texto[:16])


def _texto(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M")


def limites_das_sessoes(sessoes: list[dict]) -> list[str]:
    """Os momentos em que a estimativa de uma sala "zera": início (com antecedência) e fim de cada sessão."""
    limites = []
    for sessao in sessoes:
        limites.append(_texto(_minutos(sessao["inicio"]) - ANTECEDENCIA))
        limites.append(sessao["fim"][:16])
    return limites


def valida_desde(sessoes: list[dict], agora: datetime) -> str:
    """A partir de quando uma estimativa desta sala vale agora: o último limite que já passou.

    Sem nenhum limite hoje (ex.: dia sem sessões nesta sala), vale desde a meia-noite.
    """
    agora_texto = _texto(agora)
    passados = [limite for limite in limites_das_sessoes(sessoes) if limite <= agora_texto]
    meia_noite = agora_texto[:10] + "T00:00"
    return max(passados + [meia_noite])


def estimativas_atuais(conn, agora: datetime) -> dict:
    """Para cada sala, a estimativa que vale agora (ou nada, se ela "zerou").

    Devolve {"S1": {"porcentagem": 60, "horario": "...", "voluntario": "Maria"}, ...};
    salas sem estimativa válida ficam de fora.
    """
    agora = agora.replace(tzinfo=None)
    hoje = _texto(agora)[:10]
    sessoes_de = {}
    for sessao in conn.execute(
        "SELECT ambiente_codigo, inicio, fim FROM sessoes WHERE inicio LIKE ?", (hoje + "%",)
    ):
        sessoes_de.setdefault(sessao["ambiente_codigo"], []).append(dict(sessao))

    # A última estimativa de cada sala (o maior id é a mais recente).
    ultimas = conn.execute("""
        SELECT e.ambiente_codigo, e.porcentagem, e.horario, v.nome AS voluntario
        FROM estimativas e JOIN voluntarios v ON v.id = e.voluntario_id
        WHERE e.id IN (SELECT MAX(id) FROM estimativas GROUP BY ambiente_codigo)
    """).fetchall()

    atuais = {}
    for ultima in ultimas:
        codigo = ultima["ambiente_codigo"]
        if ultima["horario"][:16] >= valida_desde(sessoes_de.get(codigo, []), agora):
            atuais[codigo] = {
                "porcentagem": ultima["porcentagem"],
                "horario": ultima["horario"],
                "voluntario": ultima["voluntario"],
            }
    return atuais


def relatorio(conn) -> list[dict]:
    """Uma linha por sessão: quantas estimativas, a maior e a média.

    Contam para uma sessão as estimativas feitas desde 15 min antes do início até o fim.
    "Gente em pé" (110) entra nas contas como 110%.
    """
    sessoes = conn.execute("""
        SELECT s.ambiente_codigo, a.nome AS ambiente, s.titulo, s.palestrante, s.inicio, s.fim
        FROM sessoes s JOIN ambientes a ON a.codigo = s.ambiente_codigo
        ORDER BY s.inicio, a.nome
    """).fetchall()
    linhas = []
    for sessao in sessoes:
        desde = _texto(_minutos(sessao["inicio"]) - ANTECEDENCIA)
        valores = [
            linha["porcentagem"]
            for linha in conn.execute(
                """SELECT porcentagem FROM estimativas
                   WHERE ambiente_codigo = ? AND substr(horario, 1, 16) >= ? AND substr(horario, 1, 16) < ?""",
                (sessao["ambiente_codigo"], desde, sessao["fim"][:16]),
            )
        ]
        linhas.append({
            "ambiente": sessao["ambiente"],
            "titulo": sessao["titulo"],
            "palestrante": sessao["palestrante"],
            "inicio": sessao["inicio"],
            "fim": sessao["fim"],
            "estimativas": len(valores),
            "maior": max(valores) if valores else None,
            "media": round(sum(valores) / len(valores)) if valores else None,
        })
    return linhas

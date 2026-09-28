"""Programação do evento: lê a planilha (CSV) e guarda na tabela sessoes.

A planilha tem uma linha por sessão, com as colunas:
    sala, data, inicio, fim, titulo, palestrante
Exemplo:
    A1, 20/10/2026, 09:00, 10:30, Abertura, Fulano de Tal
"""

import csv
import io
import os
import unicodedata
import urllib.request
from datetime import datetime

ARQUIVO_EXEMPLO = "programacao_exemplo.csv"
COLUNAS = ["sala", "data", "inicio", "fim", "titulo", "palestrante"]

# Resultado da última leitura, mostrado no painel da coordenação.
# Fica na memória: quando o site reinicia, a planilha é lida de novo logo no começo.
ultima_leitura = {"horario": None, "origem": None, "erros": [], "falha": None}


def simplificar(texto: str) -> str:
    """"  Auditório 1 " vira "auditorio 1": sem acento, minúsculo e sem espaços nas pontas."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def baixar_planilha() -> tuple[str, str]:
    """Devolve (texto do CSV, de onde veio). Sem URL_PROGRAMACAO no .env, usa o arquivo de exemplo."""
    url = os.getenv("URL_PROGRAMACAO")
    if not url:
        with open(ARQUIVO_EXEMPLO, encoding="utf-8-sig") as arquivo:
            return arquivo.read(), "arquivo de exemplo"
    with urllib.request.urlopen(url, timeout=20) as resposta:
        texto = resposta.read().decode("utf-8-sig")
    # Se o link for o da planilha "normal" (e não o CSV publicado), o Google devolve uma página HTML.
    if texto.lstrip().startswith("<"):
        raise ValueError("o link não é de um CSV. Use Arquivo > Compartilhar > Publicar na Web > CSV")
    return texto, "planilha do Google"


def ler_horario(data: str, hora: str) -> str:
    """"20/10/2026" + "9:00" vira "2026-10-20T09:00" (horário de Cuiabá).

    Nesse formato, comparar os textos já compara as datas: "…T09:00" < "…T10:30".
    """
    dia = datetime.strptime(data.strip(), "%d/%m/%Y")
    hora = hora.strip()
    # O Google às vezes exporta a hora com segundos (09:00:00).
    formato = "%H:%M:%S" if hora.count(":") == 2 else "%H:%M"
    horario = datetime.strptime(hora, formato)
    return dia.replace(hour=horario.hour, minute=horario.minute).strftime("%Y-%m-%dT%H:%M")


def interpretar(texto: str, ambientes: list[dict]) -> tuple[list[tuple], list[dict]]:
    """Confere cada linha da planilha. Devolve (sessões válidas, erros encontrados)."""
    # A sala pode vir pelo código (A1) ou pelo nome (Auditório 1).
    codigo_por_nome = {}
    for ambiente in ambientes:
        codigo_por_nome[simplificar(ambiente["codigo"])] = ambiente["codigo"]
        codigo_por_nome[simplificar(ambiente["nome"])] = ambiente["codigo"]

    # Planilhas salvas pelo Excel em português costumam separar com ";".
    primeira_linha = texto.split("\n", 1)[0]
    separador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=separador)

    cabecalho = [simplificar(coluna) for coluna in next(leitor, [])]
    faltando = [coluna for coluna in COLUNAS[:5] if coluna not in cabecalho]
    if faltando:
        return [], [{"linha": 1, "motivo": f"faltam as colunas: {', '.join(faltando)}"}]

    sessoes, erros = [], []
    # start=2: a linha 1 é o cabeçalho, então os números batem com os da planilha.
    for numero, valores in enumerate(leitor, start=2):
        if not any(valor.strip() for valor in valores):
            continue  # linha em branco
        linha = dict(zip(cabecalho, valores))
        try:
            codigo = codigo_por_nome.get(simplificar(linha.get("sala", "")))
            if codigo is None:
                raise ValueError(f'sala "{linha.get("sala", "")}" não existe')
            titulo = linha.get("titulo", "").strip()
            if not titulo:
                raise ValueError("falta o título")
            try:
                inicio = ler_horario(linha.get("data", ""), linha.get("inicio", ""))
                fim = ler_horario(linha.get("data", ""), linha.get("fim", ""))
            except ValueError:
                raise ValueError("data ou hora em formato errado (use 20/10/2026 e 09:00)")
            if fim <= inicio:
                raise ValueError("o fim está antes do início")
            palestrante = linha.get("palestrante", "").strip() or None
            sessoes.append((codigo, titulo, palestrante, inicio, fim))
        except ValueError as erro:
            erros.append({"linha": numero, "motivo": str(erro)})
    return sessoes, erros


def atualizar(conn) -> dict:
    """Baixa a planilha e troca a programação guardada no banco pela nova."""
    # astimezone(): inclui o fuso no texto, para o navegador converter a hora certa.
    ultima_leitura["horario"] = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        texto, origem = baixar_planilha()
    except Exception as erro:  # sem internet, link errado, arquivo sumiu...
        ultima_leitura["falha"] = f"Não foi possível ler a planilha: {erro}"
        return ultima_leitura

    ambientes = conn.execute("SELECT codigo, nome FROM ambientes").fetchall()
    sessoes, erros = interpretar(texto, [dict(a) for a in ambientes])
    ultima_leitura.update(origem=origem, erros=erros, falha=None)

    # Planilha vazia ou toda errada: melhor manter a programação antiga do que apagar tudo.
    if not sessoes:
        ultima_leitura["falha"] = "Nenhuma linha válida na planilha. A programação anterior foi mantida."
        return ultima_leitura

    # Apaga e grava na mesma transação: quem consulta o site vê a programação
    # antiga ou a nova, nunca uma mistura das duas.
    conn.execute("DELETE FROM sessoes")
    conn.executemany(
        "INSERT INTO sessoes (ambiente_codigo, titulo, palestrante, inicio, fim) VALUES (?, ?, ?, ?, ?)",
        sessoes,
    )
    return ultima_leitura


def sessoes_do_ambiente(conn, codigo: str) -> list[dict]:
    """Toda a programação de um ambiente, em ordem de horário."""
    linhas = conn.execute(
        "SELECT titulo, palestrante, inicio, fim FROM sessoes WHERE ambiente_codigo = ? ORDER BY inicio",
        (codigo,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


def todas_as_sessoes(conn) -> list[dict]:
    """Programação de todas as salas (para a tela "Programação"), com o nome e o tipo de cada sala."""
    linhas = conn.execute(
        """SELECT s.ambiente_codigo, a.nome AS ambiente_nome, a.tipo, s.titulo, s.palestrante, s.inicio, s.fim
           FROM sessoes s JOIN ambientes a ON a.codigo = s.ambiente_codigo
           ORDER BY s.inicio, a.codigo"""
    ).fetchall()
    return [dict(linha) for linha in linhas]


def agora_e_depois(conn, agora: datetime) -> dict:
    """Para cada ambiente: a sessão que está acontecendo e a próxima.

    Devolve {"A1": {"agora": {...} ou None, "depois": {...} ou None}, ...}
    """
    agora_texto = agora.strftime("%Y-%m-%dT%H:%M")
    resultado = {}

    acontecendo = conn.execute(
        """SELECT ambiente_codigo, titulo, palestrante, inicio, fim FROM sessoes
           WHERE inicio <= ? AND fim > ? ORDER BY inicio""",
        (agora_texto, agora_texto),
    ).fetchall()
    for sessao in acontecendo:  # se duas se sobrepõem, fica a que começou por último
        resultado.setdefault(sessao["ambiente_codigo"], {})["agora"] = dict(sessao)

    # No SQLite, junto com MIN(inicio) as outras colunas vêm da mesma linha do mínimo:
    # ou seja, a próxima sessão de cada ambiente.
    proximas = conn.execute(
        """SELECT ambiente_codigo, titulo, palestrante, MIN(inicio) AS inicio, fim FROM sessoes
           WHERE inicio > ? GROUP BY ambiente_codigo""",
        (agora_texto,),
    ).fetchall()
    for sessao in proximas:
        proxima = dict(sessao)
        proxima["hoje"] = proxima["inicio"][:10] == agora_texto[:10]
        resultado.setdefault(sessao["ambiente_codigo"], {})["depois"] = proxima

    return resultado

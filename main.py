import asyncio
import csv
import hmac
import io
import os
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

import database
import estimativas
import programacao

load_dotenv()  # lê as configurações do arquivo .env, se existir

# Cuiabá fica em UTC−4 o ano todo (não tem horário de verão).
FUSO_CUIABA = timezone(timedelta(hours=-4))

# Usuário e senha do painel da coordenação. Sem eles no .env, o painel fica desligado.
USUARIO_COORDENACAO = os.getenv("USUARIO_COORDENACAO")
SENHA_COORDENACAO = os.getenv("SENHA_COORDENACAO")

# De quanto em quanto tempo o site relê a planilha da programação.
INTERVALO_PROGRAMACAO = timedelta(minutes=10)


def atualizar_programacao() -> dict:
    with database.conectar() as conn:
        return programacao.atualizar(conn)


async def reler_programacao_sempre():
    while True:
        # to_thread: baixar a planilha pode demorar alguns segundos; rodando à parte,
        # o site continua respondendo aos outros pedidos enquanto isso.
        await asyncio.to_thread(atualizar_programacao)
        await asyncio.sleep(INTERVALO_PROGRAMACAO.total_seconds())


@asynccontextmanager
async def ciclo_de_vida(app):
    """O que roda quando o site liga (antes do yield) e quando desliga (depois)."""
    tarefa = asyncio.create_task(reler_programacao_sempre())
    yield
    tarefa.cancel()


app = FastAPI(title="BRACIS 2026 - Salas", lifespan=ciclo_de_vida)

# Guarda quem está logado num cookie assinado com uma chave secreta:
# se alguém alterar o cookie, a assinatura não bate e o site recusa.
# Sem CHAVE_SESSAO no .env, uma chave aleatória é criada a cada vez que o site liga
# (aí todos precisam logar de novo quando o site reinicia).
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("CHAVE_SESSAO") or secrets.token_hex(32),
    max_age=12 * 60 * 60,  # o login vale 12 horas
    # Com HTTPS no ar, o cookie só viaja criptografado (ninguém no Wi-Fi consegue copiá-lo).
    https_only=os.getenv("COOKIE_SO_HTTPS") == "sim",
)

# O site inteiro fica debaixo deste prefixo: bracis.ic.ufmt.br/live (combinado com o IC).
# Se mudar, troque aqui, no <base href> dos HTML e no nginx-bracis.conf.
PREFIXO = "/live"

# Todas as rotas abaixo são registradas neste roteador; no fim do arquivo ele é
# encaixado no site com o PREFIXO na frente (ex.: "/ambientes" vira "/live/ambientes").
rotas = APIRouter()

# Arquivos da pasta static/ (HTML, CSS, JS) ficam disponíveis em /live/static/...
app.mount(PREFIXO + "/static", StaticFiles(directory="static"), name="static")

# Cria as tabelas e os dados de exemplo na primeira vez que o site liga.
database.criar_banco(os.getenv("CRIAR_VOLUNTARIOS_EXEMPLO") == "sim")


# Formatos esperados nos pedidos. O FastAPI recusa sozinho o que vier fora disso.
class DadosLogin(BaseModel):
    usuario: str
    pin: str


class NovaEstimativa(BaseModel):
    ambiente_codigo: str
    # 0, 10, 20 ... 100, ou 110 = lotada, com gente em pé (os botões da tela do voluntário)
    porcentagem: int = Field(ge=0, le=estimativas.GENTE_EM_PE, multiple_of=10)


class LoginCoordenacao(BaseModel):
    usuario: str
    senha: str


class NovoVoluntario(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    usuario: str = Field(min_length=2, max_length=50)
    # Opcional: a coordenação escolhe a senha (ex.: uma senha única para uma conta de todos).
    # Vazio = o site sorteia uma de 6 dígitos.
    pin: str = Field(default="", max_length=20)


class ImportarVoluntarios(BaseModel):
    texto: str = Field(max_length=100_000)


class MudarAtivo(BaseModel):
    ativo: bool


# ---------- Bloqueio depois de muitas tentativas erradas (login dos voluntários) ----------
# Guardado na memória do servidor (some quando ele reinicia, e tudo bem).
# Funciona porque o site roda com 1 processo só; com vários, cada um teria sua lista.
#
# O bloqueio vale para o par (usuário, IP): a ideia é bloquear só quem errou.
# Hoje o proxy do IC não informa o IP do visitante (todos chegam como 10.4.0.74), então,
# na prática, vale para o usuário. Numa conta usada por vários voluntários (ex.: "contagem"),
# 5 erros seguidos travam todos por 5 minutos; a coordenação gera uma "Nova senha", que destrava na hora.
# (A coordenação não usa este bloqueio: veja login_coordenacao.)

TENTATIVAS_MAXIMAS = 5
TEMPO_BLOQUEIO = timedelta(minutes=5)
falhas_login = {}  # (usuário, IP) -> (quantidade de erros, bloqueado até)


def ip_de(request: Request) -> str:
    """IP de quem fez o pedido. Atrás do Nginx e do proxy do IC, o uvicorn só enxerga
    o IP real se confiar neles (--forwarded-allow-ips no deploy/bracis.service)."""
    return request.client.host if request.client else "desconhecido"


def conferir_bloqueio(chave: tuple):
    _, bloqueado_ate = falhas_login.get(chave, (0, None))
    if bloqueado_ate and datetime.now() < bloqueado_ate:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas erradas. Espere 5 minutos e tente de novo.",
        )


def registrar_falha(chave: tuple):
    quantidade, bloqueado_ate = falhas_login.get(chave, (0, None))
    if bloqueado_ate:  # o bloqueio anterior já acabou: recomeça a contar
        quantidade = 0
    quantidade += 1
    bloqueio = datetime.now() + TEMPO_BLOQUEIO if quantidade >= TENTATIVAS_MAXIMAS else None
    falhas_login[chave] = (quantidade, bloqueio)


def limpar_falhas(chave: tuple):
    falhas_login.pop(chave, None)


def liberar_todos_os_ips(quem: str):
    """Tira o bloqueio de um usuário em qualquer IP (usado quando a coordenação gera um PIN novo)."""
    for chave in [c for c in falhas_login if c[0] == quem]:
        del falhas_login[chave]


# ---------- Quem está logado ----------

def exigir_login(request: Request) -> int:
    """Devolve o id do voluntário logado, ou recusa o pedido se ninguém estiver logado."""
    voluntario_id = request.session.get("voluntario_id")
    if voluntario_id is None:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    # Confere se a coordenação não desativou a conta depois do login.
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT ativo FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    if voluntario is None or not voluntario["ativo"]:
        request.session.pop("voluntario_id", None)
        raise HTTPException(status_code=401, detail="Sua conta foi desativada.")
    return voluntario_id


def exigir_coordenacao(request: Request):
    if not request.session.get("coordenacao"):
        raise HTTPException(status_code=401, detail="Faça login para continuar.")


# ---------- Páginas ----------
# include_in_schema=False: páginas não aparecem no /docs, que é só para a API.

@rotas.get("/", include_in_schema=False)
def pagina_participante():
    return FileResponse("static/index.html")


@rotas.get("/voluntario", include_in_schema=False)
def pagina_voluntario():
    return FileResponse("static/voluntario.html")


@rotas.get("/coordenacao", include_in_schema=False)
def pagina_coordenacao():
    return FileResponse("static/coordenacao.html")


# ---------- Login dos voluntários ----------

@rotas.post("/login")
def login(dados: DadosLogin, request: Request):
    usuario = dados.usuario.strip().lower()
    chave = (usuario, ip_de(request))
    conferir_bloqueio(chave)
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT * FROM voluntarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    # Mesma mensagem para usuário ou senha errados, para não revelar quais usuários existem.
    if voluntario is None or not database.verificar_pin(dados.pin, voluntario["pin_hash"]):
        registrar_falha(chave)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")
    limpar_falhas(chave)
    if not voluntario["ativo"]:
        raise HTTPException(status_code=403, detail="Sua conta foi desativada.")
    request.session["voluntario_id"] = voluntario["id"]
    return {"id": voluntario["id"], "nome": voluntario["nome"]}


@rotas.post("/logout")
def logout(request: Request):
    request.session.pop("voluntario_id", None)
    return {"mensagem": "Até logo!"}


@rotas.get("/eu")
def voluntario_atual(request: Request):
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT id, nome, usuario FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    return dict(voluntario)


# ---------- Ambientes e lotação (público) ----------

# Memória curta das respostas públicas. Com centenas de telas pedindo a lista a cada 10 s,
# cada resposta é calculada no máximo uma vez a cada 2 segundos e entregue igual para todos.
# A tela do voluntário (/ambientes/{codigo}) NÃO usa a memória: ele vê a estimativa na hora.
MEMORIA_SEGUNDOS = 2
_memoria = {}  # chave -> (quando foi calculada, resposta)


def da_memoria(chave, calcular):
    """Devolve a resposta guardada se ela tiver menos de 2 s; senão calcula de novo e guarda."""
    agora = time.monotonic()
    guardada = _memoria.get(chave)
    if guardada and agora - guardada[0] < MEMORIA_SEGUNDOS:
        return guardada[1]
    resposta = calcular()
    _memoria[chave] = (agora, resposta)
    return resposta


@rotas.get("/ambientes")
def listar_ambientes():
    return da_memoria("ambientes", calcular_ambientes)


def calcular_ambientes(codigo: str | None = None) -> list[dict]:
    """Cada sala com a sessão de agora, a próxima e a estimativa que vale agora (ou None)."""
    agora = datetime.now(FUSO_CUIABA)
    with database.conectar() as conn:
        ambientes = database.listar_ambientes(conn)
        sessoes = programacao.agora_e_depois(conn, agora)
        atuais = estimativas.estimativas_atuais(conn, agora)
    if codigo is not None:
        ambientes = [a for a in ambientes if a["codigo"] == codigo]
    for ambiente in ambientes:
        da_sala = sessoes.get(ambiente["codigo"], {})
        ambiente["agora"] = da_sala.get("agora")
        ambiente["depois"] = da_sala.get("depois")
        ambiente["estimativa"] = atuais.get(ambiente["codigo"])
    return ambientes


@rotas.get("/ambientes/{codigo}")
def obter_ambiente(codigo: str):
    encontrados = calcular_ambientes(codigo)
    if not encontrados:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")
    return encontrados[0]


# ---------- Estimativa (voluntários) ----------

@rotas.post("/estimativas")
def registrar_estimativa(dados: NovaEstimativa, request: Request):
    """O voluntário toca num botão (ex.: 60%): guarda e devolve a sala já com a estimativa nova."""
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        if database.obter_ambiente(conn, dados.ambiente_codigo) is None:
            raise HTTPException(status_code=404, detail="Sala não encontrada.")
        conn.execute(
            """INSERT INTO estimativas (ambiente_codigo, porcentagem, horario, voluntario_id)
               VALUES (?, ?, ?, ?)""",
            (
                dados.ambiente_codigo,
                dados.porcentagem,
                datetime.now(FUSO_CUIABA).isoformat(timespec="seconds"),
                voluntario_id,
            ),
        )
    _memoria.clear()  # o totem vê a estimativa nova no próximo pedido, sem esperar os 2 s
    return obter_ambiente(dados.ambiente_codigo)


# ---------- Painel da coordenação ----------

# Sem bloqueio depois de erros: o proxy do IC não informa o IP de quem acessa, então um
# bloqueio valeria para todo mundo, e qualquer pessoa poderia travar o painel errando de propósito.
# Em vez disso, cada tentativa errada espera 1 segundo. Quanto mais longa a senha do .env,
# mais tempo levaria para adivinhar.
ESPERA_SENHA_ERRADA = 1  # segundos

@rotas.post("/coordenacao/login")
async def login_coordenacao(dados: LoginCoordenacao, request: Request):
    if not USUARIO_COORDENACAO or not SENHA_COORDENACAO:
        raise HTTPException(
            status_code=503,
            detail="Painel desligado: defina USUARIO_COORDENACAO e SENHA_COORDENACAO no arquivo .env.",
        )
    # compare_digest compara sem "vazar" pelo tempo de resposta quantas letras acertou.
    # Confere os dois sempre (e não para no primeiro errado), pelo mesmo motivo.
    usuario_certo = hmac.compare_digest(dados.usuario.strip().lower().encode(), USUARIO_COORDENACAO.lower().encode())
    senha_certa = hmac.compare_digest(dados.senha.encode(), SENHA_COORDENACAO.encode())
    if not (usuario_certo and senha_certa):
        # asyncio.sleep espera sem travar o site: os outros pedidos continuam sendo atendidos.
        await asyncio.sleep(ESPERA_SENHA_ERRADA)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")
    request.session["coordenacao"] = True
    return {"mensagem": "Bem-vindo(a) ao painel."}


@rotas.post("/coordenacao/logout")
def logout_coordenacao(request: Request):
    request.session.pop("coordenacao", None)
    return {"mensagem": "Até logo!"}


@rotas.get("/coordenacao/eu")
def coordenacao_logada(request: Request):
    exigir_coordenacao(request)
    return {"coordenacao": True}


@rotas.get("/coordenacao/situacao")
def situacao(request: Request):
    """Cada sala com a estimativa que vale agora e a última informada (mesmo que já tenha "zerado")."""
    exigir_coordenacao(request)
    ambientes = calcular_ambientes()
    with database.conectar() as conn:
        ultimas = {
            linha["ambiente_codigo"]: dict(linha)
            for linha in conn.execute("""
                SELECT e.ambiente_codigo, e.porcentagem, e.horario, v.nome AS voluntario
                FROM estimativas e JOIN voluntarios v ON v.id = e.voluntario_id
                WHERE e.id IN (SELECT MAX(id) FROM estimativas GROUP BY ambiente_codigo)
            """)
        }
    for ambiente in ambientes:
        ambiente["ultima"] = ultimas.get(ambiente["codigo"])
    return ambientes


@rotas.get("/coordenacao/voluntarios")
def listar_voluntarios(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        linhas = conn.execute(
            "SELECT id, nome, usuario, ativo FROM voluntarios ORDER BY nome"
        ).fetchall()
    return [dict(linha) for linha in linhas]


# Usuário: letras minúsculas sem acento, números, ponto, hífen, sublinhado e @ (e-mails antigos valem)
USUARIO_VALIDO = re.compile(r"[a-z0-9._@-]{2,50}")


def cadastrar_voluntario(conn, nome: str, usuario: str, pin: str = "") -> dict:
    """Cria o voluntário. Sem PIN escolhido, sorteia um. O PIN só é devolvido aqui, uma única vez."""
    nome = nome.strip()
    usuario = usuario.strip().lower()
    pin = pin.strip()
    if not nome:
        raise ValueError("falta o nome")
    if not USUARIO_VALIDO.fullmatch(usuario):
        raise ValueError("usuário inválido (use letras sem acento e números, sem espaço)")
    if pin and len(pin) < 4:
        raise ValueError("a senha precisa ter pelo menos 4 caracteres")
    pin = pin or database.gerar_pin()
    try:
        conn.execute(
            "INSERT INTO voluntarios (nome, usuario, pin_hash) VALUES (?, ?, ?)",
            (nome, usuario, database.gerar_hash_pin(pin)),
        )
    except sqlite3.IntegrityError:  # o usuário é UNIQUE no banco
        raise ValueError("usuário já cadastrado")
    return {"nome": nome, "usuario": usuario, "pin": pin}


@rotas.post("/coordenacao/voluntarios")
def criar_voluntario(dados: NovoVoluntario, request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        try:
            return cadastrar_voluntario(conn, dados.nome, dados.usuario, dados.pin)
        except ValueError as erro:
            raise HTTPException(status_code=400, detail=f"Não foi possível: {erro}.")


@rotas.post("/coordenacao/voluntarios/importar")
def importar_voluntarios(dados: ImportarVoluntarios, request: Request):
    """Recebe várias linhas "nome, usuário" ou "nome, usuário, senha" (também aceita ; ou tab)."""
    exigir_coordenacao(request)
    criados, erros = [], []
    with database.conectar() as conn:
        for numero, linha in enumerate(dados.texto.splitlines(), start=1):
            if not linha.strip():
                continue
            partes = linha.replace(";", ",").replace("\t", ",").split(",")
            if len(partes) < 2:
                erros.append({"linha": numero, "texto": linha, "motivo": "faltou o usuário"})
                continue
            nome, usuario = partes[0], partes[1]
            pin = partes[2] if len(partes) > 2 else ""
            if usuario.strip().lower() in ("usuario", "usuário"):
                continue  # linha de cabeçalho copiada da planilha
            try:
                criados.append(cadastrar_voluntario(conn, nome, usuario, pin))
            except ValueError as erro:
                erros.append({"linha": numero, "texto": linha, "motivo": str(erro)})
    return {"criados": criados, "erros": erros}


@rotas.post("/coordenacao/voluntarios/{voluntario_id}/novo-pin")
def trocar_pin(voluntario_id: int, request: Request):
    exigir_coordenacao(request)
    pin = database.gerar_pin()
    with database.conectar() as conn:
        cursor = conn.execute(
            "UPDATE voluntarios SET pin_hash = ? WHERE id = ?",
            (database.gerar_hash_pin(pin), voluntario_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Voluntário não encontrado.")
        voluntario = conn.execute(
            "SELECT nome, usuario FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    liberar_todos_os_ips(voluntario["usuario"])  # PIN novo: libera se estava bloqueado
    return {**dict(voluntario), "pin": pin}


@rotas.post("/coordenacao/voluntarios/{voluntario_id}/ativo")
def mudar_ativo(voluntario_id: int, dados: MudarAtivo, request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        cursor = conn.execute(
            "UPDATE voluntarios SET ativo = ? WHERE id = ?", (int(dados.ativo), voluntario_id)
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Voluntário não encontrado.")
    return {"id": voluntario_id, "ativo": dados.ativo}


@rotas.get("/coordenacao/programacao")
def ver_programacao(request: Request):
    """Situação da última leitura da planilha e todas as sessões guardadas."""
    exigir_coordenacao(request)
    with database.conectar() as conn:
        sessoes = conn.execute("""
            SELECT a.nome AS ambiente, s.titulo, s.palestrante, s.inicio, s.fim
            FROM sessoes s JOIN ambientes a ON a.codigo = s.ambiente_codigo
            ORDER BY s.inicio, a.codigo
        """).fetchall()
    return {**programacao.ultima_leitura, "sessoes": [dict(s) for s in sessoes]}


@rotas.post("/coordenacao/programacao/atualizar")
def atualizar_programacao_agora(request: Request):
    exigir_coordenacao(request)
    atualizar_programacao()
    return ver_programacao(request)


def resposta_csv(nome_arquivo: str, cabecalho: list, linhas: list) -> Response:
    """Monta um arquivo CSV para baixar e abrir no Excel."""
    saida = io.StringIO()
    # O Excel em português espera ";" como separador.
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    # "﻿" no começo avisa o Excel que o arquivo é UTF-8 (senão os acentos quebram).
    return Response(
        content="﻿" + saida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


def texto_porcentagem(porcentagem: int | None) -> str:
    """60 -> "60%"; 110 -> "100%+ (gente em pé)"; None -> "" """
    if porcentagem is None:
        return ""
    return "100%+ (gente em pé)" if porcentagem == estimativas.GENTE_EM_PE else f"{porcentagem}%"


@rotas.get("/coordenacao/estimativas.csv")
def exportar_estimativas(request: Request):
    """Todas as estimativas informadas, para abrir no Excel."""
    exigir_coordenacao(request)
    with database.conectar() as conn:
        linhas = conn.execute("""
            SELECT e.id, a.nome AS ambiente, e.porcentagem, e.horario, v.nome AS voluntario
            FROM estimativas e
            JOIN ambientes a ON a.codigo = e.ambiente_codigo
            JOIN voluntarios v ON v.id = e.voluntario_id
            ORDER BY e.id
        """).fetchall()
    return resposta_csv(
        "estimativas-bracis.csv",
        ["id", "ambiente", "estimativa", "horario", "voluntario"],
        [[linha["id"], linha["ambiente"], texto_porcentagem(linha["porcentagem"]), linha["horario"], linha["voluntario"]]
         for linha in linhas],
    )


# ---------- Relatório por sessão ----------

@rotas.get("/coordenacao/relatorio")
def ver_relatorio(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        return estimativas.relatorio(conn)


@rotas.get("/coordenacao/relatorio.csv")
def exportar_relatorio(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        sessoes = estimativas.relatorio(conn)
    linhas = [
        [s["inicio"][:10], s["inicio"][11:16], s["fim"][11:16], s["ambiente"], s["titulo"],
         s["palestrante"] or "", s["estimativas"], texto_porcentagem(s["maior"]), texto_porcentagem(s["media"])]
        for s in sessoes
    ]
    return resposta_csv(
        "relatorio-sessoes-bracis.csv",
        ["dia", "inicio", "fim", "ambiente", "sessao", "palestrante",
         "estimativas_informadas", "maior_estimativa", "media_das_estimativas"],
        linhas,
    )


# ---------- Encaixe no endereço /live ----------

app.include_router(rotas, prefix=PREFIXO)


# Quem digitar o endereço sem o /live (ou sem a barra final) cai na página inicial.
@app.get("/", include_in_schema=False)
@app.get(PREFIXO, include_in_schema=False)
def ir_para_inicio():
    return RedirectResponse(PREFIXO + "/")

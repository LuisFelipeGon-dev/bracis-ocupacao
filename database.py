import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager

ARQUIVO_BANCO = "bracis.db"

# Os 7 ambientes do evento: 2 auditórios e 5 salas (nomes de exemplo até a organização mandar os reais).
# A capacidade daqui só vale quando a sala é criada; depois, quem muda é a coordenação no painel
# (a capacidade muda conforme o momento do congresso).
AMBIENTES_EXEMPLO = [
    ("A1", "Auditório 1", "auditorio", 200),
    ("A2", "Auditório 2", "auditorio", 150),
    ("S1", "Sala 1", "sala", 50),
    ("S2", "Sala 2", "sala", 50),
    ("S3", "Sala 3", "sala", 40),
    ("S4", "Sala 4", "sala", 40),
    ("S5", "Sala 5", "sala", 30),
]

VOLUNTARIOS_EXEMPLO = [
    ("Voluntário Exemplo 1", "voluntario1@exemplo.com", "1111"),
    ("Voluntário Exemplo 2", "voluntario2@exemplo.com", "2222"),
    ("Voluntário Exemplo 3", "voluntario3@exemplo.com", "3333"),
]


@contextmanager
def conectar():
    """Abre o banco, salva as alterações no final e sempre fecha a conexão."""
    conn = sqlite3.connect(ARQUIVO_BANCO)
    conn.row_factory = sqlite3.Row  # permite acessar colunas pelo nome: linha["nome"]
    conn.execute("PRAGMA foreign_keys = ON")  # faz o SQLite checar as ligações entre tabelas
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def gerar_hash_pin(pin: str) -> str:
    """Embaralha o PIN para guardar no banco. O PIN original não pode ser recuperado."""
    sal = secrets.token_hex(16)  # valor aleatório para dois PINs iguais não gerarem o mesmo hash
    hash_pin = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000)
    return f"{sal}${hash_pin.hex()}"


def verificar_pin(pin: str, pin_hash: str) -> bool:
    """Confere se o PIN digitado gera o mesmo hash que está guardado."""
    sal, hash_guardado = pin_hash.split("$")
    hash_pin = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000)
    return hmac.compare_digest(hash_pin.hex(), hash_guardado)


def gerar_pin() -> str:
    """Sorteia um PIN de 6 dígitos (pode começar com zero, ex.: 048213)."""
    return f"{secrets.randbelow(1_000_000):06d}"


# Ocupação = soma das entradas − soma das saídas, ignorando o que foi desfeito.
# O LEFT JOIN faz aparecer também os ambientes que ainda não têm nenhum evento (ocupação 0).
SQL_AMBIENTES_COM_OCUPACAO = """
    SELECT a.codigo, a.nome, a.tipo, a.capacidade,
           COALESCE(SUM(CASE e.tipo WHEN 'entrada' THEN e.quantidade
                                    ELSE -e.quantidade END), 0) AS ocupacao
    FROM ambientes a
    LEFT JOIN eventos e ON e.ambiente_codigo = a.codigo AND e.desfeito = 0
"""


def listar_ambientes(conn):
    linhas = conn.execute(
        SQL_AMBIENTES_COM_OCUPACAO + " GROUP BY a.codigo ORDER BY a.codigo"
    ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_ambiente(conn, codigo):
    """Devolve o ambiente com a ocupação atual, ou None se o código não existir."""
    linha = conn.execute(
        SQL_AMBIENTES_COM_OCUPACAO + " WHERE a.codigo = ? GROUP BY a.codigo", (codigo,)
    ).fetchone()
    return dict(linha) if linha else None


def situacao_ambientes(conn):
    """Para o painel da coordenação: totais de cada ambiente e o último registro."""
    linhas = conn.execute("""
        SELECT a.codigo, a.nome, a.capacidade,
               COALESCE(SUM(CASE e.tipo WHEN 'entrada' THEN e.quantidade END), 0) AS entradas,
               COALESCE(SUM(CASE e.tipo WHEN 'saida' THEN e.quantidade END), 0) AS saidas,
               MAX(e.horario) AS ultimo_registro,
               -- Nome de quem fez o último registro (que não foi desfeito) nesta sala.
               (SELECT v.nome FROM eventos e2
                JOIN voluntarios v ON v.id = e2.voluntario_id
                WHERE e2.ambiente_codigo = a.codigo AND e2.desfeito = 0
                ORDER BY e2.id DESC LIMIT 1) AS ultimo_voluntario
        FROM ambientes a
        LEFT JOIN eventos e ON e.ambiente_codigo = a.codigo AND e.desfeito = 0
        GROUP BY a.codigo ORDER BY a.codigo
    """).fetchall()
    resultado = []
    for linha in linhas:
        ambiente = dict(linha)
        ambiente["ocupacao"] = ambiente["entradas"] - ambiente["saidas"]
        resultado.append(ambiente)
    return resultado


def criar_banco(criar_voluntarios_exemplo: bool):
    """Cria as tabelas (se ainda não existirem) e coloca os dados de exemplo.

    Os voluntários de exemplo têm PINs conhecidos (1111...), então só são
    criados quando pedido: no computador de desenvolvimento, nunca no servidor.
    """
    with conectar() as conn:
        # WAL deixa o site ler o banco enquanto um voluntário está gravando.
        conn.execute("PRAGMA journal_mode = WAL")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ambientes (
                codigo     TEXT PRIMARY KEY,
                nome       TEXT NOT NULL,
                tipo       TEXT NOT NULL CHECK (tipo IN ('sala', 'auditorio', 'laboratorio')),
                capacidade INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS voluntarios (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                nome     TEXT NOT NULL,
                email    TEXT NOT NULL UNIQUE,
                pin_hash TEXT NOT NULL,
                ativo    INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS eventos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ambiente_codigo TEXT NOT NULL REFERENCES ambientes (codigo),
                tipo            TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
                quantidade      INTEGER NOT NULL DEFAULT 1 CHECK (quantidade > 0),
                horario        TEXT NOT NULL,
                voluntario_id   INTEGER NOT NULL REFERENCES voluntarios (id),
                desfeito        INTEGER NOT NULL DEFAULT 0
            );

            -- Índice: deixa rápido achar os eventos de uma sala.
            CREATE INDEX IF NOT EXISTS idx_eventos_ambiente
                ON eventos (ambiente_codigo, desfeito);

            CREATE TABLE IF NOT EXISTS sessoes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ambiente_codigo TEXT NOT NULL REFERENCES ambientes (codigo),
                titulo          TEXT NOT NULL,
                palestrante     TEXT,
                inicio          TEXT NOT NULL,
                fim             TEXT NOT NULL
            );
        """)

        # Bancos criados antes da coluna "ativo" existir: acrescenta a coluna.
        # (CREATE TABLE IF NOT EXISTS não mexe numa tabela que já existe.)
        colunas = [c["name"] for c in conn.execute("PRAGMA table_info(voluntarios)")]
        if "ativo" not in colunas:
            conn.execute("ALTER TABLE voluntarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")

        # Se o código já existe, atualiza nome e tipo (assim, trocar a lista acima e reiniciar
        # o site já corrige os dados). A capacidade fica como está: ela é mudada pela coordenação.
        # "excluded" = a linha que tentamos inserir.
        # Os eventos ficam ligados ao código, que não muda, então nada da contagem se perde.
        conn.executemany(
            """INSERT INTO ambientes (codigo, nome, tipo, capacidade) VALUES (?, ?, ?, ?)
               ON CONFLICT (codigo) DO UPDATE SET
                   nome = excluded.nome,
                   tipo = excluded.tipo""",
            AMBIENTES_EXEMPLO,
        )

        # Salas que saíram da lista: apaga, desde que não tenham nenhuma entrada ou saída
        # registrada (essas ficam, para não perder o histórico; o aviso aparece no log).
        codigos = [a[0] for a in AMBIENTES_EXEMPLO]
        marcadores = ", ".join("?" * len(codigos))
        sobrando = conn.execute(
            f"SELECT codigo FROM ambientes WHERE codigo NOT IN ({marcadores})", codigos
        ).fetchall()
        for (codigo,) in sobrando:
            if conn.execute("SELECT 1 FROM eventos WHERE ambiente_codigo = ?", (codigo,)).fetchone():
                print(f"Aviso: a sala {codigo} saiu da lista, mas tem registros; ela foi mantida.")
                continue
            conn.execute("DELETE FROM sessoes WHERE ambiente_codigo = ?", (codigo,))
            conn.execute("DELETE FROM ambientes WHERE codigo = ?", (codigo,))
        if not criar_voluntarios_exemplo:
            return
        for nome, email, pin in VOLUNTARIOS_EXEMPLO:
            conn.execute(
                "INSERT OR IGNORE INTO voluntarios (nome, email, pin_hash) VALUES (?, ?, ?)",
                (nome, email, gerar_hash_pin(pin)),
            )

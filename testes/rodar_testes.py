"""Roda todos os testes rápidos do projeto e mostra um resumo.

Uso (na pasta do projeto, com o ambiente virtual ativado):
    python testes/rodar_testes.py

Precisa do Node.js instalado para os testes das páginas (JavaScript).
Nenhum teste mexe no banco do projeto: cada um cria um banco temporário.
Os testes de carga (pasta testes/carga) não rodam aqui: eles acessam o site no ar. Veja testes/README.md.
"""
import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent

TESTES = [
    ["node", PASTA / "unidade" / "teste_publico.js", "pt"],
    ["node", PASTA / "unidade" / "teste_publico.js", "en"],
    ["node", PASTA / "unidade" / "teste_toques.js"],
    *[[sys.executable, arquivo] for arquivo in sorted((PASTA / "servidor").glob("teste_*.py"))],
]

falharam = 0
for comando in TESTES:
    nome = " ".join(str(c) if i else Path(c).stem for i, c in enumerate(comando[1:], start=1)).replace(str(PASTA) + "\\", "").replace(str(PASTA) + "/", "")
    resultado = subprocess.run([str(c) for c in comando], capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = resultado.stdout + resultado.stderr
    ok = resultado.returncode == 0 and "FALHOU" not in saida and "Traceback" not in saida
    falharam += not ok
    print(f"{'OK    ' if ok else 'FALHOU'} {nome}")
    if not ok:
        # Mostra só as linhas que interessam
        for linha in saida.splitlines():
            if "FALHOU" in linha or "Error" in linha or "error" in linha:
                print("         ", linha)

print(f"\n{len(TESTES) - falharam} de {len(TESTES)} passaram." if not falharam else f"\n{falharam} de {len(TESTES)} FALHARAM.")
sys.exit(1 if falharam else 0)

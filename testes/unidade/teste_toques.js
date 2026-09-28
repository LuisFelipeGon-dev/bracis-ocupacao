// Testa o voluntario.js no Node com uma página e um servidor falsos.
const fs = require("fs");
const vm = require("vm");

const codigo = fs.readFileSync(require("path").join(__dirname, "..", "..", "static", "voluntario.js"), "utf8");
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

function montar() {
  const els = {};
  const el = (id) =>
    (els[id] ??= {
      id, textContent: "", hidden: true, value: "", className: "", disabled: false,
      handlers: {},
      classList: { toggle() {} },
      addEventListener(t, f) { this.handlers[t] = f; },
      setAttribute() {}, removeAttribute() {}, append() {}, replaceChildren() {},
      querySelector() { return el("x"); },
    });
  for (const t of ["login", "ambientes", "contagem"]) el(`tela-${t}`);

  const servidor = { ocupacao: 0, eventos: [], falhar: 0, atraso: 300, perguntas: [] };
  let intervalo;
  const ctx = {
    console,
    document: {
      getElementById: el,
      querySelectorAll: (s) => (s === "section" ? ["login", "ambientes", "contagem"].map((t) => el(`tela-${t}`)) : []),
      addEventListener() {},
      createElement: () => el("novo"),
    },
    localStorage: { getItem: () => "A1", setItem() {}, removeItem() {} },
    navigator: {},
    confirm: (texto) => { servidor.perguntas.push(texto); return true; },
    setTimeout, clearTimeout,
    setInterval: (f) => (intervalo = f),
    fetch: async (rota, op) => {
      await espera(servidor.atraso);
      if (servidor.falhar > 0) { servidor.falhar--; throw new TypeError("rede"); }
      const dados = op.body ? JSON.parse(op.body) : null;
      const ok = (c) => ({ ok: true, status: 200, json: async () => c });
      const amb = () => ({ codigo: "A1", nome: "Sala A1", capacidade: 50, ocupacao: servidor.ocupacao });
      if (rota === "eu") return ok({ id: 1, nome: "Teste" });
      if (rota === "ambientes/A1") return ok(amb());
      if (rota === "eventos") {
        if (dados.tipo === "saida" && dados.quantidade > servidor.ocupacao)
          return { ok: false, status: 400, json: async () => ({ detail: "Só há poucas." }) };
        servidor.eventos.push({ ...dados, id: servidor.eventos.length + 100, horario: "2026-10-20T10:42:05-04:00" });
        servidor.ocupacao += dados.tipo === "entrada" ? dados.quantidade : -dados.quantidade;
        return ok(amb());
      }
      if (rota.startsWith("eventos/ultimo?")) return ok(servidor.eventos.at(-1));
      if (rota === "eventos/desfazer") {
        if (dados.evento_id !== servidor.eventos.at(-1).id) throw new Error("id errado");
        const e = (servidor.desfeito = servidor.eventos.pop());
        servidor.ocupacao -= e.tipo === "entrada" ? e.quantidade : -e.quantidade;
        return ok({ desfeito: e, ambiente: amb() });
      }
      throw new Error("rota " + rota);
    },
  };
  vm.createContext(ctx);
  vm.runInContext(codigo, ctx);
  return { ctx, els, servidor, tique: () => intervalo(), clicar: (id) => els[id].handlers.click() };
}

let falhas = 0;
function confere(nome, obtido, esperado) {
  const ok = obtido === esperado;
  if (!ok) falhas++;
  console.log(`${ok ? "OK  " : "FALHOU"} ${nome}: ${obtido} (esperado ${esperado})`);
}

(async () => {
  // 1. Dez toques rápidos (um a cada 50 ms) com o servidor demorando 300 ms.
  let p = montar();
  await espera(800); // login + abrir sala
  confere("tela de contagem aberta", p.els["tela-contagem"].hidden, false);
  for (let i = 0; i < 10; i++) { p.clicar("btn-entrou"); await espera(50); }
  confere("tela mostra 10 logo após os toques", p.els.ocupacao.textContent, 10);
  await espera(1500);
  confere("servidor recebeu 10 pessoas", p.servidor.ocupacao, 10);
  console.log("     eventos enviados:", p.servidor.eventos.map((e) => e.quantidade).join(", "));
  confere("tela continua 10", p.els.ocupacao.textContent, 10);

  // 2. Entradas e saídas misturadas.
  for (const b of ["btn-saiu", "btn-entrou", "btn-saiu", "btn-saiu", "btn-entrou"]) { p.clicar(b); await espera(30); }
  await espera(1500);
  confere("misturado: 10 -3 +2 = 9 no servidor", p.servidor.ocupacao, 9);
  confere("misturado: tela 9", p.els.ocupacao.textContent, 9);

  // 3. Sem conexão: toques guardados e reenviados pelo intervalo de 5 s.
  p.servidor.falhar = 1;
  p.clicar("btn-entrou"); p.clicar("btn-entrou"); p.clicar("btn-entrou");
  await espera(500);
  confere("sem conexão: tela mostra 12", p.els.ocupacao.textContent, 12);
  confere("sem conexão: servidor ainda 9", p.servidor.ocupacao, 9);
  console.log("     mensagem:", p.els.mensagem.textContent);
  await espera(4500);
  confere("erro continua na tela depois de 4 s", p.els.mensagem.className, "erro");
  p.tique(); // o intervalo de 5 s dispara
  await espera(500);
  confere("reenvio: servidor 12", p.servidor.ocupacao, 12);
  confere("reenvio: mensagem de erro sumiu", p.els.mensagem.textContent, "");

  // 4. Desfazer logo depois de toques: espera os toques e desfaz o último registro.
  p.clicar("btn-entrou"); p.clicar("btn-entrou");
  await p.clicar("btn-desfazer");
  await espera(100);
  console.log("     pergunta:", p.servidor.perguntas.at(-1));
  console.log("     mensagem:", p.els.mensagem.textContent);
  confere("desfazer: 12 + 2 toques - evento desfeito", p.servidor.ocupacao, 14 - p.servidor.desfeito.quantidade);
  confere("desfazer: tela igual ao servidor", p.els.ocupacao.textContent, p.servidor.ocupacao);

  // 5. Toques durante um grupo não se perdem.
  const antes = p.servidor.ocupacao;
  p.ctx.document.getElementById("qtd-grupo").value = "5";
  const grupo = p.clicar("btn-grupo-entrou");
  await espera(50);
  p.clicar("btn-entrou"); p.clicar("btn-entrou");
  await grupo; await espera(800);
  confere("grupo 5 + 2 toques no servidor", p.servidor.ocupacao, antes + 7);
  confere("grupo 5 + 2 toques na tela", p.els.ocupacao.textContent, antes + 7);

  // 6. Sala vazia: −1 não vai para o servidor.
  p = montar();
  await espera(800);
  p.clicar("btn-saiu");
  await espera(400);
  confere("sala vazia: servidor sem eventos", p.servidor.eventos.length, 0);
  confere("sala vazia: tela 0", p.els.ocupacao.textContent, 0);

  console.log(falhas ? `\n${falhas} FALHA(S)` : "\nTudo certo.");
  process.exit(falhas ? 1 : 0);
})();

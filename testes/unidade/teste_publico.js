// Testa as funções de lógica do comum.js (tela do totem) no Node, sem navegador.
// Uso: node teste_publico.js
const fs = require("fs");
const vm = require("vm");

const pasta = require("path").join(__dirname, "..", "..", "static") + "/";

function carregar() {
  const ctx = { console, Intl, Math, Date, document: { getElementById: () => null } };
  vm.createContext(ctx);
  // "const" do topo de um script não vira propriedade do contexto: expomos no fim o que o teste usa.
  const codigo = fs.readFileSync(pasta + "comum.js", "utf8") +
    "\n;globalThis.__f = { nivelDaSala, ordenarSalas, quandoProxima, rotuloDia };";
  vm.runInContext(codigo, ctx);
  return ctx.__f;
}

let falhas = 0;
function confere(nome, obtido, esperado) {
  const ok = obtido === esperado;
  falhas += !ok;
  console.log(`${ok ? "OK  " : "FALHOU"} ${nome}: ${JSON.stringify(obtido)}${ok ? "" : ` (esperado ${JSON.stringify(esperado)})`}`);
}

let f;
try {
  f = carregar();
} catch (erro) {
  console.log("FALHOU ao carregar:", erro.message);
  process.exit(1);
}
const { nivelDaSala, ordenarSalas, quandoProxima, rotuloDia } = f;

// nivelDaSala
confere("vazia sem sessão = livre", nivelDaSala({ ocupacao: 0, capacidade: 100, agora: null }).chave, "livre");
confere("sem sessão com gente = pela %", nivelDaSala({ ocupacao: 5, capacidade: 100, agora: null }).chave, "tranquila");
confere("39% = tranquila", nivelDaSala({ ocupacao: 39, capacidade: 100, agora: {} }).chave, "tranquila");
confere("40% = moderada", nivelDaSala({ ocupacao: 40, capacidade: 100, agora: {} }).chave, "moderada");
confere("74% = moderada", nivelDaSala({ ocupacao: 74, capacidade: 100, agora: {} }).chave, "moderada");
confere("75% = lotada", nivelDaSala({ ocupacao: 75, capacidade: 100, agora: {} }).chave, "lotada");
confere("99% = lotada", nivelDaSala({ ocupacao: 99, capacidade: 100, agora: {} }).chave, "lotada");
confere("100% = cheia", nivelDaSala({ ocupacao: 100, capacidade: 100, agora: {} }).chave, "cheia");
confere("acima da capacidade: pct real", nivelDaSala({ ocupacao: 130, capacidade: 100, agora: {} }).pct, 130);
confere("acima da capacidade = cheia", nivelDaSala({ ocupacao: 130, capacidade: 100, agora: {} }).chave, "cheia");
confere("capacidade 0: sem divisão por zero", nivelDaSala({ ocupacao: 3, capacidade: 0, agora: {} }).pct, 0);
confere("com sessão e vazia = tranquila (não livre)", nivelDaSala({ ocupacao: 0, capacidade: 100, agora: {} }).chave, "tranquila");
confere("arredonda a %", nivelDaSala({ ocupacao: 1, capacidade: 3, agora: {} }).pct, 33);
confere("rótulo em inglês", nivelDaSala({ ocupacao: 83, capacidade: 100, agora: {} }).rotulo, "Almost full");
confere("rótulo livre", nivelDaSala({ ocupacao: 0, capacidade: 100, agora: null }).rotulo, "Empty");
// A mesma sala com capacidade menor (momento diferente do congresso) fica mais cheia
confere("capacidade menor = % maior", nivelDaSala({ ocupacao: 60, capacidade: 80, agora: {} }).pct, 75);

// ordenarSalas
const lista = [{ tipo: "sala", codigo: "S1" }, { tipo: "auditorio", codigo: "A2" }, { tipo: "auditorio", codigo: "A1" }, { tipo: "sala", codigo: "S10" }];
confere("ordem fixa", ordenarSalas(lista).map((a) => a.codigo).join(), "A1,A2,S1,S10");
confere("não altera a lista original", lista[0].codigo, "S1");

// quandoProxima / rotuloDia
confere("próxima hoje: só a hora", quandoProxima({ inicio: "2026-10-20T14:00", hoje: true }), "14:00");
confere("próxima outro dia: dia e hora", quandoProxima({ inicio: "2026-10-21T09:00", hoje: false }), "Wed 21 Oct, 09:00");
confere("rótulo do dia", rotuloDia(new Date(2026, 9, 20)), "TUE 20 OCT");

console.log(falhas ? `\n${falhas} FALHA(S)` : "\nTudo certo.");
process.exit(falhas ? 1 : 0);

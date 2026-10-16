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
    "\n;globalThis.__f = { nivelDaSala, ordenarSalas, quandoProxima };";
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
const { nivelDaSala, ordenarSalas, quandoProxima } = f;

// nivelDaSala (a % vem da estimativa do voluntário)
const com = (porcentagem) => ({ estimativa: { porcentagem } });
confere("sem estimativa", nivelDaSala({ estimativa: null }).chave, "sem");
confere("sem estimativa: rótulo", nivelDaSala({ estimativa: null }).rotulo, "No estimate yet");
confere("sem estimativa: mostra um traço", nivelDaSala({ estimativa: null }).texto, "—");
confere("0% = livre", nivelDaSala(com(0)).chave, "livre");
confere("0%: rótulo", nivelDaSala(com(0)).rotulo, "Empty");
confere("10% = tranquila", nivelDaSala(com(10)).chave, "tranquila");
confere("30% = tranquila", nivelDaSala(com(30)).chave, "tranquila");
confere("40% = moderada", nivelDaSala(com(40)).chave, "moderada");
confere("70% = moderada", nivelDaSala(com(70)).chave, "moderada");
confere("80% = lotada", nivelDaSala(com(80)).chave, "lotada");
confere("90%: rótulo em inglês", nivelDaSala(com(90)).rotulo, "Almost full");
confere("100% = cheia", nivelDaSala(com(100)).chave, "cheia");
confere("gente em pé = cheia", nivelDaSala(com(110)).chave, "cheia");
confere("gente em pé aparece como 100%+", nivelDaSala(com(110)).texto, "100%+");
confere("60% aparece como 60%", nivelDaSala(com(60)).texto, "60%");

// ordenarSalas
const lista = [{ tipo: "sala", codigo: "S1" }, { tipo: "auditorio", codigo: "A2" }, { tipo: "auditorio", codigo: "A1" }, { tipo: "sala", codigo: "S10" }];
confere("ordem fixa", ordenarSalas(lista).map((a) => a.codigo).join(), "A1,A2,S1,S10");
confere("não altera a lista original", lista[0].codigo, "S1");
confere("sala sem código não quebra a ordem", ordenarSalas([{ tipo: "sala" }, { tipo: "auditorio", codigo: "A1" }]).length, 2);

// quandoProxima
confere("próxima hoje: só a hora", quandoProxima({ inicio: "2026-10-20T14:00", hoje: true }), "14:00");
confere("próxima outro dia: também só a hora", quandoProxima({ inicio: "2026-10-21T09:00", hoje: false }), "09:00");

console.log(falhas ? `\n${falhas} FALHA(S)` : "\nTudo certo.");
process.exit(falhas ? 1 : 0);

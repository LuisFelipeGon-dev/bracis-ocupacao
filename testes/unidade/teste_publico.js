// Testa as funções de lógica do comum.js (com o idioma.js) no Node, sem navegador.
// Uso: node teste_publico.js [pt|en]
const fs = require("fs");
const vm = require("vm");

const idioma = process.argv[2] || "pt";
const pasta = require("path").join(__dirname, "..", "..", "static") + "/";

function carregar() {
  const elemento = () => ({
    textContent: "", className: "", hidden: false, style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {}, removeAttribute() {}, append() {}, replaceChildren() {},
  });
  const ctx = {
    console, Intl, Math, Date, URLSearchParams,
    location: { search: `?lang=${idioma}`, pathname: "/live/" },
    navigator: { language: "pt-BR" },
    localStorage: { getItem: () => null, setItem() {} },
    setInterval: () => 0, setTimeout: () => 0,
    document: {
      documentElement: {},
      querySelectorAll: () => [],
      getElementById: () => null,
      createElement: elemento,
      addEventListener() {},
      hidden: false,
    },
  };
  vm.createContext(ctx);
  // "const" do topo de um script não vira propriedade do contexto: juntamos os arquivos
  // e expomos no fim o que o teste usa.
  const codigo = fs.readFileSync(pasta + "idioma.js", "utf8") + "\n" + fs.readFileSync(pasta + "comum.js", "utf8") +
    "\n;globalThis.__f = { nivelDaSala, textoNivel, ordenarSalas, periodoDoDia, rotuloDia, picosPorHora, aSeguir, diasDaProgramacao, diaInicial, blocosPorHorario, blocoParaRolar };";
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
const { nivelDaSala, textoNivel, ordenarSalas, periodoDoDia, rotuloDia, picosPorHora, aSeguir, diasDaProgramacao, diaInicial, blocosPorHorario, blocoParaRolar } = f;

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
const rotulos = idioma === "pt" ? ["Lotada · 83%", "Livre"] : ["Busy · 83%", "Free"];
confere("texto do nível", textoNivel(nivelDaSala({ ocupacao: 83, capacidade: 100, agora: {} })), rotulos[0]);
confere("texto do nível livre", textoNivel(nivelDaSala({ ocupacao: 0, capacidade: 100, agora: null })), rotulos[1]);

// ordenarSalas
const lista = [{ tipo: "sala", codigo: "S1" }, { tipo: "laboratorio", codigo: "L1" }, { tipo: "auditorio", codigo: "A2" }, { tipo: "auditorio", codigo: "A1" }, { tipo: "sala", codigo: "S10" }];
confere("ordem fixa", ordenarSalas(lista).map((a) => a.codigo).join(), "A1,A2,S1,S10,L1");
confere("não altera a lista original", lista[0].codigo, "S1");

// periodoDoDia / rotuloDia
confere("11h = manhã", periodoDoDia(11), "manha");
confere("12h = tarde", periodoDoDia(12), "tarde");
confere("17h = tarde", periodoDoDia(17), "tarde");
confere("18h = noite", periodoDoDia(18), "noite");
confere("rótulo do dia", rotuloDia(new Date(2026, 9, 20)), idioma === "pt" ? "TER 20 OUT" : "TUE 20 OCT");

// picosPorHora
const p = picosPorHora(
  [{ horario: "2026-10-20T09:10", ocupacao: 50 }, { horario: "2026-10-20T09:40", ocupacao: 20 }, { horario: "2026-10-20T11:05", ocupacao: 70 }],
  0, 11 * 60 + 30);
confere("começa às 8h", p[0].hora, 8);
confere("vai até 18h", p.at(-1).hora, 18);
confere("8h sem registro = valor inicial", p.find((h) => h.hora === 8).pico, 0);
confere("9h = maior valor dentro da hora", p.find((h) => h.hora === 9).pico, 50);
confere("10h = valor que veio da hora anterior", p.find((h) => h.hora === 10).pico, 20);
confere("11h = hora atual", p.find((h) => h.hora === 11).estado, "atual");
confere("11h pico", p.find((h) => h.hora === 11).pico, 70);
confere("9h = passada", p.find((h) => h.hora === 9).estado, "passada");
confere("12h = futura sem pico", p.find((h) => h.hora === 12).pico, null);
confere("12h estado", p.find((h) => h.hora === 12).estado, "futura");
const cedo = picosPorHora([{ horario: "2026-10-20T06:30", ocupacao: 5 }, { horario: "2026-10-20T20:10", ocupacao: 9 }], 0, 20 * 60 + 15);
confere("registro às 6h estende o começo", cedo[0].hora, 6);
confere("registro às 20h estende o fim", cedo.at(-1).hora, 20);
confere("sem registros: 8h a 18h", picosPorHora([], 0, 9 * 60).length, 11);
confere("valor inicial do dia (gente de ontem)", picosPorHora([], 7, 9 * 60)[0].pico, 7);

// Antes das 8h com gente de ontem: a hora atual tem que aparecer (senão o gráfico não tem nenhuma hora com dados)
const madrugada = picosPorHora([], 5, 7 * 60 + 10);
confere("antes das 8h: começa na hora atual", madrugada[0].hora, 7);
confere("antes das 8h: hora atual tem pico", madrugada[0].pico, 5);
confere("antes das 8h: hora atual marcada", madrugada[0].estado, "atual");

// ----- Programação -----
const sess = [
  { inicio: "2026-10-19T09:00", fim: "2026-10-19T10:00", ambiente_codigo: "A1" },
  { inicio: "2026-10-20T09:00", fim: "2026-10-20T10:00", ambiente_codigo: "A1" },
  { inicio: "2026-10-20T09:00", fim: "2026-10-20T10:30", ambiente_codigo: "S1" },
  { inicio: "2026-10-20T14:00", fim: "2026-10-20T15:00", ambiente_codigo: "A1" },
  { inicio: "2026-10-22T09:00", fim: "2026-10-22T10:00", ambiente_codigo: "A2" },
];
const dias = diasDaProgramacao(sess, "2026-10-20");
confere("dias distintos em ordem", dias.map((d) => d.dia).join(), "2026-10-19,2026-10-20,2026-10-22");
confere("dia de hoje marcado", dias.filter((d) => d.hoje).map((d) => d.dia).join(), "2026-10-20");
confere("sem sessões: sem dias", diasDaProgramacao([], "2026-10-20").length, 0);
confere("dia inicial = hoje", diaInicial(dias, "2026-10-20"), "2026-10-20");
confere("hoje sem sessão: próximo dia", diaInicial(dias, "2026-10-21"), "2026-10-22");
confere("antes do evento: primeiro dia", diaInicial(dias, "2026-09-27"), "2026-10-19");
confere("evento acabou: primeiro dia", diaInicial(dias, "2026-10-25"), "2026-10-19");
confere("sem dias: null", diaInicial([], "2026-10-20"), null);
const doDia = sess.filter((s) => s.inicio.startsWith("2026-10-20"));
let blocos = blocosPorHorario(doDia, "2026-10-20T10:15");
confere("blocos por horário de início", blocos.map((b) => b.inicio.slice(11)).join(), "09:00,14:00");
confere("bloco com uma sessão ainda rolando = agora", blocos[0].estado, "agora");
confere("sessões do bloco", blocos[0].sessoes.length, 2);
confere("bloco que não começou = futuro", blocos[1].estado, "futuro");
confere("rolar até o bloco agora", blocoParaRolar(blocos), 0);
blocos = blocosPorHorario(doDia, "2026-10-20T11:00");
confere("todas acabaram = passado", blocos[0].estado, "passado");
confere("sem bloco agora: rola até o próximo", blocoParaRolar(blocos), 1);
confere("dia inteiro passado: não rola", blocoParaRolar(blocosPorHorario(doDia, "2026-10-20T18:00")), -1);
confere("sem blocos", blocosPorHorario([], "2026-10-20T10:00").length, 0);

// aSeguir (programação vem do servidor em ordem de início)
const prog = [
  { inicio: "2026-10-20T09:00", fim: "2026-10-20T10:00", titulo: "A" },
  { inicio: "2026-10-20T14:00", fim: "2026-10-20T15:00", titulo: "B" },
  { inicio: "2026-10-20T15:30", fim: "2026-10-20T16:30", titulo: "C" },
  { inicio: "2026-10-21T09:00", fim: "2026-10-21T10:00", titulo: "D" },
  { inicio: "2026-10-21T11:00", fim: "2026-10-21T12:00", titulo: "E" },
];
const titulos = (r) => r.sessoes.map((s) => s.titulo).join();
let r = aSeguir(prog, "2026-10-20T14:30");
confere("a seguir hoje: sem a atual", titulos(r), "C");
confere("a seguir hoje: não é outro dia", r.outroDia, false);
r = aSeguir(prog, "2026-10-20T17:00");
confere("hoje acabou: sessões do próximo dia", titulos(r), "D,E");
confere("hoje acabou: outro dia", r.outroDia, true);
confere("hoje acabou: qual dia", r.dia, "2026-10-21");
confere("evento acabou: nada", titulos(aSeguir(prog, "2026-10-21T13:00")), "");
confere("antes do evento: primeiro dia", titulos(aSeguir(prog, "2026-10-19T08:00")), "A,B,C");
confere("sem programação: nada", aSeguir([], "2026-10-20T10:00").sessoes.length, 0);

console.log(falhas ? `\n${falhas} FALHA(S)` : "\nTudo certo.");
process.exit(falhas ? 1 : 0);

// Parte B do teste de carga: voluntários registrando entradas e saídas enquanto o site está cheio.
// Uso: node voluntarios_carga.js <email> <pin> <sala> <voluntarios> <segundos>
// Cada "voluntário" faz login (cookie próprio) e registra toques como o celular faz:
// um POST /eventos por vez, com 1 a 3 pessoas, a cada ~1,5 s. No fim, confere se a ocupação da sala
// no servidor bate exatamente com o que foi registrado.
const [EMAIL, PIN, SALA] = process.argv.slice(2, 5);
const VOLUNTARIOS = Number(process.argv[5] || 10);
const DURACAO = Number(process.argv[6] || 120) * 1000;
const BASE = "https://bracis.ic.ufmt.br/live/";
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

const tempos = [];
let erros = 0, entradas = 0, saidas = 0;

async function voluntario(n) {
  const login = await fetch(BASE + "login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, pin: PIN }),
  });
  if (!login.ok) throw new Error(`login ${login.status}: ${await login.text()}`);
  const cookie = login.headers.get("set-cookie").split(";")[0];
  const inicio = Date.now();
  await espera(n * 150);
  let dentroPorMim = 0; // saídas só de quem este voluntário pôs para dentro (a sala nunca fica negativa)
  while (Date.now() - inicio < DURACAO) {
    const tipo = dentroPorMim > 5 && Math.random() < 0.4 ? "saida" : "entrada";
    const quantidade = 1 + Math.floor(Math.random() * 3);
    const t0 = Date.now();
    try {
      const r = await fetch(BASE + "eventos", {
        method: "POST", headers: { "Content-Type": "application/json", Cookie: cookie },
        body: JSON.stringify({ ambiente_codigo: SALA, tipo, quantidade: tipo === "saida" ? Math.min(quantidade, dentroPorMim) : quantidade }),
        signal: AbortSignal.timeout(15000),
      });
      await r.arrayBuffer();
      tempos.push(Date.now() - t0);
      if (!r.ok) { erros++; } else if (tipo === "entrada") { entradas += quantidade; dentroPorMim += quantidade; }
      else { const q = Math.min(quantidade, dentroPorMim); saidas += q; dentroPorMim -= q; }
    } catch { erros++; }
    await espera(1500 * (0.7 + Math.random() * 0.6));
  }
}

const perc = (l, p) => l[Math.min(l.length - 1, Math.floor(l.length * p))] ?? 0;
(async () => {
  const antes = await (await fetch(`${BASE}ambientes/${SALA}`)).json();
  console.log(`${VOLUNTARIOS} voluntários por ${DURACAO / 1000} s na sala ${SALA} (ocupação antes: ${antes.ocupacao})`);
  await Promise.all(Array.from({ length: VOLUNTARIOS }, (_, n) => voluntario(n)));
  const depois = await (await fetch(`${BASE}ambientes/${SALA}`)).json();
  tempos.sort((a, b) => a - b);
  console.log(`registros enviados: ${tempos.length} | mediana ${perc(tempos, 0.5)} ms | 95% ${perc(tempos, 0.95)} ms | pior ${tempos.at(-1)} ms | erros ${erros}`);
  const esperado = antes.ocupacao + entradas - saidas;
  console.log(`entradas ${entradas}, saídas ${saidas} -> esperado ${esperado}, servidor diz ${depois.ocupacao} ` +
    (esperado === depois.ocupacao ? "-> BATE" : "-> NÃO BATE"));
})().catch((e) => { console.log("ERRO:", e.message); process.exit(1); });

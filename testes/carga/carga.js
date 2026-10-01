// Teste de carga da tela pública: simula muitas telas abertas ao mesmo tempo
// (o totem, e quem abrir o endereço no celular).
// Uso: node carga.js <telas> <segundos> [endereço base]
// Só faz leituras (GET): não muda nenhum dado do site.
const PARTICIPANTES = Number(process.argv[2] || 800);
const DURACAO = Number(process.argv[3] || 120) * 1000;
const BASE = process.argv[4] || "https://bracis.ic.ufmt.br/live/";

const medidas = [];      // { rota, ms, ok, instante }
let emAndamento = 0;
const inicio = Date.now();
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

async function pedir(rota) {
  const t0 = Date.now();
  emAndamento++;
  let ok = false;
  try {
    const resposta = await fetch(BASE + rota, { signal: AbortSignal.timeout(15000) });
    await resposta.arrayBuffer();
    ok = resposta.ok;
  } catch {}
  emAndamento--;
  medidas.push({ rota: rota.split("/")[0], ms: Date.now() - t0, ok, instante: Date.now() });
}

// Uma tela: como a página, repete a busca a cada 10 s (com uma variação,
// para as 800 não pedirem todas no mesmo milissegundo).
async function participante() {
  await espera(Math.random() * 10000); // as telas não abrem todas no mesmo segundo
  while (Date.now() - inicio < DURACAO) {
    await pedir("ambientes");
    await espera(10000 * (0.9 + Math.random() * 0.2));
  }
}

const perc = (lista, p) => (lista.length ? lista[Math.min(lista.length - 1, Math.floor(lista.length * p))] : 0);

// A cada 10 s, um resumo da janela
let ultimo = 0;
const relogio = setInterval(() => {
  const janela = medidas.slice(ultimo); ultimo = medidas.length;
  const tempos = janela.map((m) => m.ms).sort((a, b) => a - b);
  const erros = janela.filter((m) => !m.ok).length;
  console.log(`${String(Math.round((Date.now() - inicio) / 1000)).padStart(4)} s | ${String((janela.length / 10).toFixed(0)).padStart(4)} pedidos/s | ` +
    `mediana ${perc(tempos, 0.5)} ms | 95% abaixo de ${perc(tempos, 0.95)} ms | pior ${tempos.at(-1) ?? 0} ms | erros ${erros} | aguardando ${emAndamento}`);
}, 10000);

(async () => {
  console.log(`${PARTICIPANTES} telas por ${DURACAO / 1000} s contra ${BASE}`);
  await Promise.all(Array.from({ length: PARTICIPANTES }, participante));
  clearInterval(relogio);
  const aquecido = medidas.filter((m) => m.instante - inicio > 15000); // ignora os primeiros 15 s (abertura)
  console.log("\nResumo (depois dos primeiros 15 s):");
  const t = aquecido.map((m) => m.ms).sort((a, b) => a - b);
  console.log(`  ambientes ${String(t.length).padStart(6)} pedidos | mediana ${perc(t, 0.5)} ms | 95% ${perc(t, 0.95)} ms | 99% ${perc(t, 0.99)} ms`);
  const total = aquecido.length, erros = aquecido.filter((m) => !m.ok).length;
  console.log(`  TOTAL ${total} pedidos, ${(total / ((DURACAO - 15000) / 1000)).toFixed(0)} por segundo, ${erros} erros (${((erros / Math.max(total, 1)) * 100).toFixed(2)}%)`);
})();

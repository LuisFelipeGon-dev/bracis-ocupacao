// Tela do totem: uma linha por sala com a % de lotação, a sessão de agora e a próxima.
// Sem botões e sem rolagem: ninguém interage com o totem, ele só se atualiza sozinho.
// As regras (nível, ordem, horários) ficam no comum.js; aqui só montamos a página.

const INTERVALO = 10000;               // busca números novos a cada 10 segundos
const SEM_CONEXAO_APAGA = 2 * 60000;   // sem conexão por 2 min: apaga as salas (dados velhos)
const RECARREGAR_A_CADA = 60 * 60000;  // recarrega a página de hora em hora (pega versões novas do site)

const carregadaEm = Date.now();
let ultimaAtualizacao = null; // Date da última vez que os dados chegaram

const horaCurta = (data) => data.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });


// ---------- Montagem de cada sala ----------

// Lado esquerdo: nome, sessão de agora e a próxima
function criarInfo(ambiente) {
  const info = el("div", "sala-info");
  info.append(el("h2", "sala-nome", ambiente.nome));

  if (ambiente.agora) {
    const agora = el("p", "sala-agora");
    agora.append(
      el("span", "horario", `${hora(ambiente.agora.inicio)}–${hora(ambiente.agora.fim)}`),
      el("span", "sessao-titulo", ambiente.agora.titulo)
    );
    info.append(agora);
  } else {
    info.append(el("p", "sala-agora sem-sessao", "No session now"));
  }

  const depois = ambiente.depois;
  if (depois) {
    const proxima = el("p", "sala-proxima");
    proxima.append(el("span", "rotulo", "Next"), el("span", "horario", quandoProxima(depois)), el("span", "", depois.titulo));
    info.append(proxima);
  } else if (!ambiente.agora) {
    info.append(el("p", "sala-proxima", "No more sessions"));
  }
  return info;
}

// Lado direito: % grande, barra e o nível em palavras (o texto sempre acompanha a cor)
function criarLotacao(nivel) {
  const lotacao = el("div", "sala-lotacao");
  // Barra: o trilho é a capacidade; a parte colorida, quem está lá (no máximo 100%).
  const barra = el("div", "barra");
  const cheia = el("div", "barra-cheia");
  cheia.style.width = `${Math.min(nivel.pct, 100)}%`;
  barra.append(cheia);
  lotacao.append(el("span", "porcentagem", `${nivel.pct}%`), barra, el("span", "nivel", nivel.rotulo));
  return lotacao;
}

function criarSala(ambiente) {
  const nivel = nivelDaSala(ambiente);
  const sala = el("article", `sala nivel-${nivel.chave}`);
  sala.append(criarInfo(ambiente), criarLotacao(nivel));
  return sala;
}


// ---------- Relógio e conexão ----------

function mostrarRelogio() {
  const agora = new Date();
  $("dia").textContent = rotuloDia(agora);
  $("hora").textContent = horaCurta(agora);
}

function mostrarConexao(deuCerto) {
  if (deuCerto) ultimaAtualizacao = new Date();
  let texto = "Live";
  if (!deuCerto) texto = ultimaAtualizacao ? `Reconnecting · last update ${horaCurta(ultimaAtualizacao)}` : "Connecting";
  $("estado-texto").textContent = texto;
  $("estado").classList.toggle("sem-conexao", !deuCerto);
  const desatualizado = !ultimaAtualizacao || Date.now() - ultimaAtualizacao > SEM_CONEXAO_APAGA;
  $("salas").classList.toggle("desatualizado", !deuCerto && desatualizado);
}


// ---------- Atualização ----------

async function atualizar() {
  try {
    const resposta = await fetch("ambientes");
    if (!resposta.ok) throw new Error();
    const ambientes = await resposta.json();
    // Só recarrega com o servidor respondendo: offline, o totem ficaria preso numa página de erro.
    if (Date.now() - carregadaEm > RECARREGAR_A_CADA) {
      location.reload();
      return;
    }
    $("salas").replaceChildren(...ordenarSalas(ambientes).map(criarSala));
    mostrarConexao(true);
  } catch {
    // Mantém os últimos números na tela e só avisa no topo (e apaga as salas se demorar).
    mostrarConexao(false);
  }
}

setInterval(mostrarRelogio, 1000);
setInterval(atualizar, INTERVALO);
mostrarRelogio();
atualizar();

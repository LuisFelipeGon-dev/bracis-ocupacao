// Tela do totem: um cartão por sala com a % de lotação, a sessão de agora e a próxima.
// Sem botões e sem rolagem: ninguém interage com o totem, ele só se atualiza sozinho.
// As regras (nível, ordem, horários) ficam no comum.js; aqui só montamos a página.

const INTERVALO = 10000;               // busca números novos a cada 10 segundos
const SEM_CONEXAO_APAGA = 2 * 60000;   // sem conexão por 2 min: apaga os cartões (dados velhos)
const RECARREGAR_A_CADA = 60 * 60000;  // recarrega a página de hora em hora (pega versões novas do site)

const carregadaEm = Date.now();
let ultimaAtualizacao = null; // Date da última vez que os dados chegaram


// ---------- Montagem dos cartões ----------

// "NOW 10:30–12:00" + título (ou "No session now")
function criarAgora(ambiente) {
  const bloco = el("div", "cartao-agora");
  if (ambiente.agora) {
    bloco.append(
      el("span", "rotulo-linha", `Now · ${hora(ambiente.agora.inicio)}–${hora(ambiente.agora.fim)}`),
      el("p", "sessao-titulo", ambiente.agora.titulo)
    );
  } else {
    bloco.append(el("p", "sessao-titulo sem-sessao", "No session now"));
  }
  return bloco;
}

// "NEXT 14:00  Título" (some quando não há próxima sessão)
function criarProxima(ambiente) {
  const linha = el("p", "cartao-proxima");
  const depois = ambiente.depois;
  if (!depois) {
    if (!ambiente.agora) linha.append(el("span", "rotulo-linha", "No more sessions"));
    return linha;
  }
  linha.append(el("span", "rotulo-linha", `Next · ${quandoProxima(depois)}`), " ", el("span", "", depois.titulo));
  return linha;
}

function criarCartao(ambiente) {
  const nivel = nivelDaSala(ambiente);
  const cartao = el("article", `cartao nivel-${nivel.chave}`);

  const nomes = el("div", "cartao-nomes");
  nomes.append(el("span", "tipo", NOMES_TIPO[ambiente.tipo] ?? ambiente.tipo), el("h2", "cartao-nome", ambiente.nome));

  const lotacao = el("div", "cartao-lotacao");
  lotacao.append(el("span", "porcentagem", `${nivel.pct}%`), el("span", "nivel", nivel.rotulo));

  // Barra: o trilho é a capacidade; a parte colorida, quem está lá (no máximo 100%).
  const barra = el("div", "barra");
  const cheia = el("div", "barra-cheia");
  cheia.style.width = `${Math.min(nivel.pct, 100)}%`;
  barra.append(cheia);

  cartao.append(nomes, lotacao, criarAgora(ambiente), barra, criarProxima(ambiente));
  return cartao;
}


// ---------- Atualização ----------

function mostrarConexao(deuCerto) {
  if (deuCerto) ultimaAtualizacao = new Date();
  const horario = ultimaAtualizacao
    ? ultimaAtualizacao.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : "--:--";
  $("selo-texto").textContent = deuCerto ? `LIVE · ${horario}` : `RECONNECTING · ${horario}`;
  $("selo-ao-vivo").classList.toggle("sem-conexao", !deuCerto);
  const desatualizado = !ultimaAtualizacao || Date.now() - ultimaAtualizacao > SEM_CONEXAO_APAGA;
  $("cartoes").classList.toggle("desatualizado", !deuCerto && desatualizado);
}

async function atualizar() {
  $("dia").textContent = rotuloDia(new Date());
  try {
    const resposta = await fetch("ambientes");
    if (!resposta.ok) throw new Error();
    const ambientes = await resposta.json();
    // Só recarrega com o servidor respondendo: offline, o totem ficaria preso numa página de erro.
    if (Date.now() - carregadaEm > RECARREGAR_A_CADA) {
      location.reload();
      return;
    }
    $("cartoes").replaceChildren(...ordenarSalas(ambientes).map(criarCartao));
    mostrarConexao(true);
  } catch {
    // Mantém os últimos números na tela e só avisa no selo (e apaga os cartões se demorar).
    mostrarConexao(false);
  }
}

setInterval(atualizar, INTERVALO);
atualizar();

// Página inicial ("Agora"): total de pessoas e um cartão por sala. Sem login.
// As decisões (nível, ordem, período do dia) ficam no comum.js; aqui só montamos a página.

const INTERVALO = 10000; // busca números novos a cada 10 segundos

let ambientes = [];     // última resposta do servidor
let filtroTipo = "";    // "" = todos; ou "sala", "auditorio", "laboratorio"


// ---------- Montagem dos cartões ----------

// "248 / 300" + barra, na cor do nível
function criarLinhaLotacao(ambiente, nivel) {
  const linha = el("div", "cartao-lotacao");
  const contagem = el("span", "contagem", ambiente.ocupacao);
  contagem.append(el("span", "de-capacidade", ` / ${ambiente.capacidade}`));
  linha.append(criarBarra(nivel), contagem);
  return linha;
}

// "Sem sessão agora · próxima às 16:00" (ou em outro dia, ou sem mais sessões)
function textoSemSessao(ambiente) {
  const depois = ambiente.depois;
  if (!depois) return t("sem_sessao_sem_mais");
  if (depois.hoje) return t("sem_sessao_proxima_as", hora(depois.inicio));
  return t("sem_sessao_proxima_dia", diaMes(depois.inicio), hora(depois.inicio));
}

// O cartão inteiro é um link para a página da sala.
function criarCartao(ambiente) {
  const nivel = nivelDaSala(ambiente);
  const cartao = el("a", "cartao");
  cartao.href = `sala/${encodeURIComponent(ambiente.codigo)}`;

  const nomes = el("div");
  nomes.append(el("span", "tipo", NOMES_TIPO[ambiente.tipo] ?? ambiente.tipo), el("h3", "cartao-nome", ambiente.nome));
  const topo = el("div", "cartao-topo");
  topo.append(nomes, criarSeloNivel(nivel));
  cartao.append(topo);

  if (ambiente.agora) {
    const sessao = el("div", "cartao-sessao");
    sessao.append(
      el("span", "sessao-titulo", ambiente.agora.titulo),
      el("span", "sessao-horario", `${hora(ambiente.agora.inicio)} – ${hora(ambiente.agora.fim)}`)
    );
    cartao.append(sessao, criarLinhaLotacao(ambiente, nivel));
  } else {
    cartao.append(el("p", "cartao-livre", textoSemSessao(ambiente)));
    // Sem sessão, mas ainda tem gente: o número real importa mais que o rótulo.
    if (ambiente.ocupacao > 0) cartao.append(criarLinhaLotacao(ambiente, nivel));
  }
  return cartao;
}

function desenhar() {
  const visiveis = ordenarSalas(ambientes).filter((a) => !filtroTipo || a.tipo === filtroTipo);
  $("cartoes").replaceChildren(...visiveis.map(criarCartao));
  if (visiveis.length === 0 && ambientes.length > 0) {
    $("cartoes").append(el("p", "vazio", t("nenhuma_sala_tipo")));
  }
  $("cartoes").removeAttribute("aria-busy");
}


// ---------- Resumo do topo ----------

function desenharResumo() {
  const agora = new Date();
  $("dia-periodo").textContent = `${rotuloDia(agora)} · ${t(`periodo_${periodoDoDia(agora.getHours())}`)}`;

  // Só troca o total quando ele muda: o leitor de tela anuncia cada troca.
  const total = ambientes.reduce((soma, a) => soma + a.ocupacao, 0).toLocaleString(LOCALE);
  if ($("total-pessoas").textContent !== total) $("total-pessoas").textContent = total;

  const ativas = ambientes.filter((a) => a.agora || a.ocupacao > 0).length;
  $("salas-ativas").textContent = `${t("salas_com_atividade", ativas, ambientes.length)} · `;

  // Fora do horário das sessões: diz qual é a próxima (a que começa primeiro, em qualquer sala)
  const foraDoHorario = ambientes.length > 0 && !ambientes.some((a) => a.agora);
  $("fora-horario").hidden = !foraDoHorario;
  if (foraDoHorario) {
    const proximas = ambientes.map((a) => a.depois).filter(Boolean).sort((a, b) => a.inicio.localeCompare(b.inicio));
    $("fora-horario").textContent = proximas.length
      ? t("nenhuma_sessao_agora_proxima", proximas[0].titulo, quando(proximas[0]))
      : t("sem_sessao_agora");
  }
}


// ---------- Filtro por tipo ----------

document.querySelectorAll(".filtros button").forEach((botao) => {
  botao.addEventListener("click", () => {
    filtroTipo = botao.dataset.tipo;
    document.querySelectorAll(".filtros button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b === botao));
    });
    desenhar();
  });
});


// ---------- Atualização ----------

async function atualizar() {
  try {
    const resposta = await fetch("ambientes");
    if (!resposta.ok) throw new Error();
    ambientes = await resposta.json();
    desenharResumo();
    desenhar();
    mostrarAtualizado(true);
  } catch {
    // Mantém os últimos números na tela e só avisa (selo e linha de apoio).
    mostrarAtualizado(false);
  }
}

repetirEnquantoVisivel(atualizar, INTERVALO);

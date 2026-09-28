// Tela "Programação": as sessões de todas as salas, por dia e por horário. Sem login.
// As decisões (dias, dia inicial, blocos, para onde rolar) ficam no comum.js; aqui só montamos a página.

const INTERVALO = 30000; // a programação quase não muda; 30 s basta para os selos de lotação

let dados = null;         // última resposta do servidor
let diaEscolhido = null;  // "2026-10-20"
let filtroTipo = "";      // "" = todos; ou "sala", "auditorio", "laboratorio"
let jaRolou = false;      // rola até o bloco "AGORA" só na primeira vez

const hojeNoServidor = () => dados.horario_servidor.slice(0, 10);

// "2026-10-20" -> Date (meio-dia, para o fuso do celular não mudar o dia)
function dataDoDia(dia) {
  const [ano, mes, diaDoMes] = dia.split("-").map(Number);
  return new Date(ano, mes - 1, diaDoMes, 12);
}


// ---------- Botões dos dias ----------

function desenharDias() {
  const dias = diasDaProgramacao(dados.sessoes, hojeNoServidor());
  $("dias").hidden = dias.length === 0;
  const botoes = dias.map(({ dia, hoje }) => {
    const data = dataDoDia(dia);
    const botao = el("button", `dia${hoje ? " e-hoje" : ""}`);
    botao.type = "button";
    botao.setAttribute("aria-pressed", String(dia === diaEscolhido));

    const rotulo = el("span", "dia-rotulo");
    const semana = data.toLocaleDateString(LOCALE, { weekday: "short" }).replace(/\./g, "").slice(0, 3).toUpperCase();
    rotulo.append(el("span", "dia-semana", semana));
    if (hoje) {
      const marca = el("span", "dia-hoje");
      marca.append(el("span", "dia-separador", " · "), t("hoje_curto"));
      rotulo.append(marca);
    }
    // Leitor de tela: depois do texto visível, a data inteira ("terça-feira, 20 de outubro").
    // (O nome do botão começa pelo que aparece na tela, para quem usa controle por voz.)
    const completo = el("span", "so-leitor", `, ${data.toLocaleDateString(LOCALE, { weekday: "long", day: "numeric", month: "long" })}`);
    botao.append(rotulo, el("span", "dia-numero", data.getDate()), completo);
    botao.addEventListener("click", () => {
      diaEscolhido = dia;
      desenharDias();
      desenharBlocos();
    });
    return botao;
  });
  $("botoes-dias").replaceChildren(...botoes);
}


// ---------- Sessões por horário ----------

function criarCartaoSessao(sessao, ambiente, agora) {
  const cartao = el("a", "cartao cartao-prog");
  cartao.href = `sala/${encodeURIComponent(sessao.ambiente_codigo)}`;
  const textos = el("div", "cartao-prog-texto");
  textos.append(el("span", "tipo", sessao.ambiente_nome), el("span", "sessao-titulo", sessao.titulo));
  cartao.append(textos);
  // Sessão acontecendo agora: mostra como está a sala (o nível usa a regra única do comum.js)
  const acontecendo = sessao.inicio <= agora && agora < sessao.fim;
  if (acontecendo && ambiente) cartao.append(criarSeloNivel(nivelDaSala({ ...ambiente, agora: sessao })));
  return cartao;
}

function desenharBlocos() {
  const area = $("blocos");
  area.removeAttribute("aria-busy");
  if (!diaEscolhido) {
    area.replaceChildren(el("p", "vazio", t("nenhuma_sessao_cadastrada")));
    return;
  }
  const agora = dados.horario_servidor;
  const doDia = dados.sessoes.filter((s) => s.inicio.startsWith(diaEscolhido));
  const visiveis = doDia.filter((s) => !filtroTipo || s.tipo === filtroTipo);
  if (visiveis.length === 0) {
    area.replaceChildren(el("p", "vazio", t(doDia.length === 0 ? "nenhuma_sessao_dia" : "nenhuma_sessao_tipo_dia")));
    return;
  }

  const ambientes = Object.fromEntries(dados.ambientes.map((a) => [a.codigo, a]));
  const blocos = blocosPorHorario(visiveis, agora);
  const secoes = blocos.map((bloco) => {
    const secao = el("section", `bloco-horario${bloco.estado === "passado" ? " passado" : ""}`);
    const cabecalho = el("div", "bloco-cabecalho");
    const titulo = el("h2", "bloco-hora", hora(bloco.inicio));
    cabecalho.append(titulo);
    if (bloco.estado === "agora") cabecalho.append(el("span", "etiqueta-agora", t("etiqueta_agora")));
    cabecalho.append(el("span", "bloco-linha"));
    // Mesma ordem fixa da página inicial: auditórios, salas, laboratório
    const emOrdem = ordenarSalas(bloco.sessoes.map((s) => ({ ...s, codigo: s.ambiente_codigo })));
    const lista = el("div", "bloco-sessoes");
    lista.append(...emOrdem.map((s) => criarCartaoSessao(s, ambientes[s.ambiente_codigo], agora)));
    secao.append(cabecalho, lista);
    return secao;
  });
  area.replaceChildren(...secoes);

  // Na primeira vez, no dia de hoje: rola até o que está acontecendo (ou o próximo)
  if (!jaRolou && diaEscolhido === hojeNoServidor()) {
    const indice = blocoParaRolar(blocos);
    if (indice > 0) {
      const semAnimacao = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      secoes[indice].scrollIntoView({ block: "start", behavior: semAnimacao ? "auto" : "smooth" });
    }
  }
  jaRolou = true;
}


// ---------- Filtro por tipo ----------

document.querySelectorAll(".filtros button").forEach((botao) => {
  botao.addEventListener("click", () => {
    filtroTipo = botao.dataset.tipo;
    document.querySelectorAll(".filtros button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b === botao));
    });
    if (dados) desenharBlocos();
  });
});


// ---------- Atualização ----------

async function atualizar() {
  try {
    const resposta = await fetch("programacao-dados");
    if (!resposta.ok) throw new Error();
    dados = await resposta.json();
    // Mantém o dia escolhido; se ele sumiu da planilha (ou é a primeira vez), volta ao dia inicial.
    const dias = diasDaProgramacao(dados.sessoes, hojeNoServidor());
    if (!dias.some((d) => d.dia === diaEscolhido)) diaEscolhido = diaInicial(dias, hojeNoServidor());
    desenharDias();
    desenharBlocos();
    mostrarAtualizado(true);
  } catch {
    mostrarAtualizado(false);
  }
}

repetirEnquantoVisivel(atualizar, INTERVALO);

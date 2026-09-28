// Página de uma sala: lotação, sessão de agora, pico por hora e o que vem a seguir.
// As decisões (nível, picos por hora, "a seguir") ficam no comum.js; aqui só montamos a página.

const INTERVALO = 15000; // atualiza a cada 15 segundos

// O código da sala vem do endereço: /sala/A1 -> "A1"
const CODIGO = decodeURIComponent(location.pathname.split("/").pop());

let ultimosDados = null; // guardado para redesenhar o gráfico quando a tela muda de tamanho


// ---------- Busca dos dados ----------

async function atualizar() {
  let resposta;
  try {
    resposta = await fetch(`ambientes/${encodeURIComponent(CODIGO)}/detalhes`);
  } catch {
    mostrarAtualizado(false);
    return;
  }
  if (resposta.status === 404) {
    $("esqueleto-sala").hidden = true;
    $("conteudo").hidden = true;
    $("nao-encontrada").hidden = false;
    return;
  }
  if (!resposta.ok) {
    mostrarAtualizado(false);
    return;
  }
  ultimosDados = await resposta.json();
  desenhar(ultimosDados);
  mostrarAtualizado(true);
}


// ---------- Montagem da página ----------

function desenhar(dados) {
  document.title = `${dados.nome} — BRACIS 2026`;
  const nivel = nivelDaSala(dados);
  $("tipo").textContent = NOMES_TIPO[dados.tipo] ?? dados.tipo;
  $("nome").textContent = dados.nome;

  $("ocupacao").textContent = dados.ocupacao;
  $("capacidade").textContent = t("lugares", dados.capacidade);
  $("nivel").replaceChildren(criarSeloNivel(nivel));
  $("barra-lotacao").replaceChildren(criarBarra(nivel, "barra-grossa"));
  $("frase-lotacao").textContent = fraseLotacao(nivel, dados);
  $("entradas-saidas").textContent = t("hoje_entradas_saidas", dados.hoje.entradas, dados.hoje.saidas);

  // Mostra a página antes do gráfico: escondida, ela tem largura zero
  // e o gráfico não saberia quantos rótulos cabem.
  $("esqueleto-sala").hidden = true;
  $("conteudo").hidden = false;
  desenharAgora(dados);
  desenharGrafico(dados);
  desenharTabela(dados);
  desenharASeguir(dados);
  desenharProgramacao(dados);
}

// Frase de apoio embaixo da barra, conforme o nível
function fraseLotacao(nivel, dados) {
  if (nivel.chave === "cheia") return t("frase_cheia");
  if (nivel.chave === "lotada") return t("frase_lotada", Math.max(0, dados.capacidade - dados.ocupacao));
  if (nivel.chave === "moderada") return t("frase_moderada");
  if (nivel.chave === "tranquila") return t("frase_tranquila");
  return t("frase_livre");
}

// "2 h 10 min", "45 min"
function duracao(minutos) {
  if (minutos < 60) return `${minutos} min`;
  const resto = minutos % 60;
  return resto ? `${Math.floor(minutos / 60)} h ${resto} min` : `${minutos / 60} h`;
}

function desenharAgora(dados) {
  const bloco = $("bloco-agora");
  const sessao = dados.agora;

  if (!sessao) {
    const cartao = el("div", "cartao-branco");
    cartao.append(el("p", "vazio", t("nenhuma_sessao_agora_curto")));
    if (dados.depois) {
      const proxima = el("p", "proxima-sessao");
      proxima.append(el("strong", "", t("proxima")), `${dados.depois.titulo}, ${quando(dados.depois)}`);
      cartao.append(proxima);
    }
    bloco.replaceChildren(cartao);
    return;
  }

  // Quanto da sessão já passou, pelo relógio do servidor (não o do celular).
  const agora = minutosDoDia(dados.horario_servidor);
  const inicio = minutosDoDia(sessao.inicio);
  const fim = minutosDoDia(sessao.fim);

  const cartao = el("div", "cartao-agora");
  const linha = el("div", "linha-mono");
  linha.append(
    el("span", "", `${hora(sessao.inicio)} – ${hora(sessao.fim)}`),
    el("span", "", t("termina_em_caps", duracao(Math.max(0, fim - agora)).toUpperCase()))
  );
  cartao.append(linha, el("p", "agora-titulo", sessao.titulo));
  if (sessao.palestrante) cartao.append(el("p", "agora-palestrante", sessao.palestrante));

  // Barra fina do tempo que já passou (o "termina em" já diz isso em texto)
  const progresso = el("div", "progresso");
  progresso.setAttribute("aria-hidden", "true");
  const feito = el("div");
  feito.style.width = `${Math.min(100, Math.max(0, Math.round(((agora - inicio) / (fim - inicio)) * 100)))}%`;
  progresso.append(feito);
  cartao.append(progresso);
  bloco.replaceChildren(cartao);
}

// Uma barra por hora: altura = pico de pessoas naquela hora (em relação à capacidade)
function desenharGrafico(dados) {
  const area = $("grafico");
  const { pontos, inicial } = dados.hoje;
  if (pontos.length === 0 && inicial === 0) {
    area.replaceChildren(el("p", "vazio", t("nenhum_movimento_hoje")));
    return;
  }

  const horas = picosPorHora(pontos, inicial, minutosDoDia(dados.horario_servidor));
  const comDados = horas.filter((h) => h.pico !== null);
  const maior = Math.max(dados.capacidade, ...comDados.map((h) => h.pico), 1);
  const maiorPico = comDados.reduce((a, b) => (b.pico > a.pico ? b : a), comDados[0]);

  // Tela estreita (menos de 24 px por barra): barras mais juntas e rótulos de 2 em 2 horas
  const apertado = (area.clientWidth || 300) / horas.length < 24;
  const barras = el("div", `barras-horas${apertado ? " apertado" : ""}`);
  barras.setAttribute("role", "img");
  barras.setAttribute("aria-label", t("grafico_picos", maiorPico.pico, maiorPico.hora));
  const rotulos = el("div", `rotulos-horas${apertado ? " apertado" : ""}`);
  rotulos.setAttribute("aria-hidden", "true");

  horas.forEach((h, i) => {
    const barra = el("div", `barra-hora ${h.estado}`);
    const altura = h.pico === null ? 4 : Math.max(4, Math.round((h.pico / maior) * 100));
    barra.style.height = `${altura}%`;
    barras.append(barra);
    const mostrarRotulo = !apertado || i % 2 === 0 || h.estado === "atual";
    rotulos.append(el("span", h.estado === "atual" ? "atual" : "", mostrarRotulo ? String(h.hora) : ""));
  });
  area.replaceChildren(barras, rotulos);
}

// A mesma informação do gráfico em tabela (para leitor de tela), da hora mais recente para a mais antiga
function desenharTabela(dados) {
  const horas = picosPorHora(dados.hoje.pontos, dados.hoje.inicial, minutosDoDia(dados.horario_servidor))
    .filter((h) => h.pico !== null)
    .reverse();
  const temMovimento = dados.hoje.pontos.length > 0 || dados.hoje.inicial > 0;
  const linhas = temMovimento
    ? horas.map((h) => {
        const tr = el("tr");
        tr.append(el("td", "", `${String(h.hora).padStart(2, "0")}:00`), el("td", "", h.pico));
        return tr;
      })
    : [];
  if (linhas.length === 0) {
    const tr = el("tr");
    const td = el("td", "vazio", t("nenhum_registro_hoje"));
    td.colSpan = 2;
    tr.append(td);
    linhas.push(tr);
  }
  $("tabela-movimento").replaceChildren(...linhas);
}

// Uma linha da lista: horário + título (+ palestrante)
function linhaSessao(sessao, textoHorario) {
  const item = el("li");
  const textos = el("div");
  textos.append(el("span", "titulo", sessao.titulo));
  if (sessao.palestrante) textos.append(el("span", "palestrante", sessao.palestrante));
  item.append(el("span", "horario", textoHorario), textos);
  return item;
}

// "2026-10-21" -> "QUA 21 OUT"
function rotuloDoDia(dia) {
  const [ano, mes, diaDoMes] = dia.split("-").map(Number);
  return rotuloDia(new Date(ano, mes - 1, diaDoMes));
}

function desenharASeguir(dados) {
  const area = $("a-seguir");
  const { outroDia, dia, sessoes } = aSeguir(dados.programacao, dados.horario_servidor);
  if (sessoes.length === 0) {
    const vazio = el("div", "cartao-branco");
    vazio.append(el("p", "vazio", t("nada_a_seguir")));
    area.replaceChildren(vazio);
    return;
  }
  const lista = el("ul", "lista-seguir");
  lista.append(...sessoes.map((s) => linhaSessao(s, hora(s.inicio))));
  area.replaceChildren(...(outroDia ? [el("p", "rotulo-mono dia-programacao", rotuloDoDia(dia)), lista] : [lista]));
}

// Programação completa da sala, por dia (dentro do "Ver programação completa")
function desenharProgramacao(dados) {
  const area = $("programacao");
  if (dados.programacao.length === 0) {
    area.replaceChildren(el("p", "vazio", t("nenhuma_sessao_cadastrada")));
    return;
  }

  // Agrupa as sessões por dia: { "2026-10-20": [sessões], ... }
  const porDia = {};
  for (const sessao of dados.programacao) {
    (porDia[sessao.inicio.slice(0, 10)] ??= []).push(sessao);
  }

  const agora = dados.horario_servidor;
  const partes = [];
  for (const [dia, sessoes] of Object.entries(porDia)) {
    partes.push(el("p", "rotulo-mono dia-programacao", rotuloDoDia(dia)));
    const lista = el("ul", "lista-seguir com-fim");
    for (const sessao of sessoes) {
      const item = linhaSessao(sessao, `${hora(sessao.inicio)}–${hora(sessao.fim)}`);
      if (sessao.fim <= agora) item.className = "passada";
      else if (sessao.inicio <= agora) {
        item.className = "atual";
        item.querySelector(".titulo").append(el("span", "etiqueta-agora", t("etiqueta_agora")));
      }
      lista.append(item);
    }
    partes.push(lista);
  }
  area.replaceChildren(...partes);
}

// Redesenha o gráfico quando a tela muda de tamanho (ex.: celular girado).
window.addEventListener("resize", () => {
  if (ultimosDados) desenharGrafico(ultimosDados);
});

repetirEnquantoVisivel(atualizar, INTERVALO);

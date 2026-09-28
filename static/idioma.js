// Idioma das páginas públicas (inicial e de cada sala): português ou inglês.
// Para corrigir uma tradução, mexa só aqui.
//
// Como o idioma é escolhido:
//   1. endereço com ?lang=en ou ?lang=pt (ex.: para um QR code em inglês)
//   2. a escolha anterior, guardada no celular pelo botão EN/PT
//   3. o idioma do celular: português -> português; qualquer outro -> inglês
//
// Os textos fixos do HTML ficam em português no próprio HTML, marcados com data-t="chave".
// Em inglês, este arquivo troca cada um pelo texto de TEXTOS.en[chave].
// Os textos montados pelo JavaScript usam t("chave") (ou t("chave", valor) quando têm números).

const TEXTOS = {
  pt: {
    // ----- comum.js -----
    tipo_sala: "Sala",
    tipo_auditorio: "Auditório",
    tipo_laboratorio: "Laboratório",
    nivel_livre: "Livre",
    nivel_tranquila: "Tranquila",
    nivel_moderada: "Moderada",
    nivel_lotada: "Lotada",
    nivel_cheia: "Cheia",
    porcentagem_ocupado: (p) => `${p}% ocupado`,
    as_hora: (h) => `às ${h}`,
    dia_as_hora: (dia, h) => `${dia} às ${h}`,
    ao_vivo: "AO VIVO",
    periodo_manha: "SESSÃO DA MANHÃ",
    periodo_tarde: "SESSÃO DA TARDE",
    periodo_noite: "SESSÃO DA NOITE",
    atualizado_agora: "atualizado agora",
    atualizado_ha_s: (n) => `atualizado há ${n} s`,
    atualizado_ha_min: (n) => `atualizado há ${n} min`,
    sem_conexao_ultimos: (h) => `sem conexão · últimos dados de ${h}`,
    conexao_restabelecida: "Conexão restabelecida.",
    sem_conexao: "Sem conexão com o servidor.",

    // ----- página inicial (participante.js) -----
    salas_com_atividade: (x, y) => `${x} de ${y} salas com atividade`,
    sem_sessao_proxima_as: (h) => `Sem sessão agora · próxima às ${h}`,
    sem_sessao_proxima_dia: (d, h) => `Sem sessão agora · próxima: ${d} às ${h}`,
    sem_sessao_sem_mais: "Sem sessão agora · sem mais sessões",
    sem_sessao_agora: "Nenhuma sessão agora.",
    nenhuma_sessao_agora_proxima: (titulo, q) => `Nenhuma sessão agora · próxima: ${titulo}, ${q}`,
    nenhuma_sala_tipo: "Nenhuma sala desse tipo.",

    // ----- página da sala (sala.js) -----
    lugares: (c) => `/ ${c} lugares`,
    frase_cheia: "A sala está cheia.",
    frase_lotada: (n) => (n === 1 ? "Resta cerca de 1 lugar. Se for assistir, chegue logo."
                                  : `Restam cerca de ${n} lugares. Se for assistir, chegue logo.`),
    frase_moderada: "Ainda há lugares.",
    frase_tranquila: "Bastante lugar livre.",
    frase_livre: "Sala vazia agora.",
    hoje_entradas_saidas: (e, s) => `Hoje: ${e} ${e === 1 ? "entrada" : "entradas"} · ${s} ${s === 1 ? "saída" : "saídas"}`,
    termina_em_caps: (d) => `TERMINA EM ${d}`,
    nenhuma_sessao_agora_curto: "Nenhuma sessão agora.",
    proxima: "Próxima: ",
    grafico_picos: (max, h) => `Pico de pessoas por hora hoje. Maior pico: ${max}, às ${h}h.`,
    nenhum_movimento_hoje: "Nenhuma entrada ou saída registrada hoje.",
    nenhum_registro_hoje: "Nenhum registro hoje.",
    nada_a_seguir: "Nenhuma sessão a seguir nesta sala.",
    nenhuma_sessao_cadastrada: "Nenhuma sessão cadastrada para esta sala.",
    etiqueta_agora: "AGORA",

    // ----- programação (programacao.js) -----
    hoje_curto: "HOJE",
    nenhuma_sessao_dia: "Nenhuma sessão neste dia.",
    nenhuma_sessao_tipo_dia: "Nenhuma sessão desse tipo neste dia.",

    // ----- botão de idioma -----
    botao_idioma: "EN",
    botao_idioma_descricao: "Read in English",
  },

  en: {
    // ----- comum.js -----
    tipo_sala: "Room",
    tipo_auditorio: "Auditorium",
    tipo_laboratorio: "Lab",
    nivel_livre: "Free",
    nivel_tranquila: "Quiet",
    nivel_moderada: "Moderate",
    nivel_lotada: "Busy",
    nivel_cheia: "Full",
    porcentagem_ocupado: (p) => `${p}% full`,
    as_hora: (h) => `at ${h}`,
    dia_as_hora: (dia, h) => `${dia} at ${h}`,
    ao_vivo: "LIVE",
    periodo_manha: "MORNING SESSION",
    periodo_tarde: "AFTERNOON SESSION",
    periodo_noite: "EVENING SESSION",
    atualizado_agora: "updated just now",
    atualizado_ha_s: (n) => `updated ${n} s ago`,
    atualizado_ha_min: (n) => `updated ${n} min ago`,
    sem_conexao_ultimos: (h) => `no connection · last data from ${h}`,
    conexao_restabelecida: "Connection restored.",
    sem_conexao: "No connection to the server.",

    // ----- página inicial (participante.js) -----
    salas_com_atividade: (x, y) => `${x} of ${y} rooms active`,
    sem_sessao_proxima_as: (h) => `No session now · next at ${h}`,
    sem_sessao_proxima_dia: (d, h) => `No session now · next: ${d} at ${h}`,
    sem_sessao_sem_mais: "No session now · no more sessions",
    sem_sessao_agora: "No session right now.",
    nenhuma_sessao_agora_proxima: (titulo, q) => `No session right now · next: ${titulo}, ${q}`,
    nenhuma_sala_tipo: "No rooms of this type.",

    // ----- página da sala (sala.js) -----
    lugares: (c) => `/ ${c} seats`,
    frase_cheia: "The room is full.",
    frase_lotada: (n) => (n === 1 ? "About 1 seat left. If you want to watch, get there soon."
                                  : `About ${n} seats left. If you want to watch, get there soon.`),
    frase_moderada: "There are still seats.",
    frase_tranquila: "Plenty of free seats.",
    frase_livre: "The room is empty right now.",
    hoje_entradas_saidas: (e, s) => `Today: ${e} ${e === 1 ? "entry" : "entries"} · ${s} ${s === 1 ? "exit" : "exits"}`,
    termina_em_caps: (d) => `ENDS IN ${d}`,
    nenhuma_sessao_agora_curto: "No session right now.",
    proxima: "Next: ",
    grafico_picos: (max, h) => `Peak number of people per hour today. Highest: ${max}, at ${h}:00.`,
    nenhum_movimento_hoje: "No entries or exits recorded today.",
    nenhum_registro_hoje: "No records today.",
    nada_a_seguir: "No more sessions in this room.",
    nenhuma_sessao_cadastrada: "No sessions scheduled for this room.",
    etiqueta_agora: "NOW",

    // ----- programação (programacao.js) -----
    hoje_curto: "TODAY",
    nenhuma_sessao_dia: "No sessions on this day.",
    nenhuma_sessao_tipo_dia: "No sessions of this type on this day.",

    // ----- botão de idioma -----
    botao_idioma: "PT",
    botao_idioma_descricao: "Ver em português",

    // ----- Textos fixos do HTML (data-t): em português ficam no próprio HTML -----
    // topo e rodapé
    rodape_contagem: "Counting is done by volunteers at the door of each room.",
    nome_evento: "36th Brazilian Conference on Intelligent Systems",
    quando_onde: "October 19–22, 2026 · UniSENAI, Cuiabá (MT), Brazil",
    descricao_evento:
      "BRACIS is one of the main scientific events on Artificial Intelligence and " +
      "Computational Intelligence in Brazil, promoted by the Brazilian Computer Society. " +
      "On this page you can follow, in real time, the schedule and occupancy of each room " +
      "to choose where to watch.",
    // index.html
    titulo_inicio: "Rooms — BRACIS 2026",
    pessoas_nas_salas: "people in the rooms now",
    acontecendo_agora: "Happening now",
    toque_para_detalhes: "tap for details",
    filtrar_por_tipo: "Filter by type",
    filtro_todos: "All",
    filtro_auditorios: "Auditoriums",
    filtro_salas: "Rooms",
    filtro_laboratorio: "Lab",
    // sala.html
    titulo_sala: "Room — BRACIS 2026",
    todas_as_salas: "All rooms",
    sala_nao_encontrada: "Room not found",
    confira_endereco: "Check the address or",
    volte_para_lista: "go back to the room list",
    agora: "Now",
    movimento_hoje: "Today's movement",
    pico_por_hora: "peak per hour",
    ver_em_tabela: "View as table",
    hora: "Hour",
    pico: "Peak",
    a_seguir: "Up next in this room",
    ver_programacao_completa: "See the room's full schedule",
    // seletor Agora | Programação e programacao.html
    secoes: "Sections",
    aba_agora: "Now",
    aba_programacao: "Schedule",
    titulo_programacao: "Schedule — BRACIS 2026",
    dia_legenda: "Day",
  },
};

function escolherIdioma() {
  const pedido = new URLSearchParams(location.search).get("lang");
  if (pedido === "pt" || pedido === "en") {
    try { localStorage.setItem("idioma", pedido); } catch {} // em modo anônimo pode falhar, e tudo bem
    return pedido;
  }
  try {
    const salvo = localStorage.getItem("idioma");
    if (salvo === "pt" || salvo === "en") return salvo;
  } catch {}
  return (navigator.language || "").toLowerCase().startsWith("pt") ? "pt" : "en";
}

const IDIOMA = escolherIdioma();

// Formato de datas e números. Em inglês, "en-GB" mostra as horas em 24 h (14:30, e não 2:30 PM),
// igual à programação do evento.
const LOCALE = IDIOMA === "pt" ? "pt-BR" : "en-GB";

// Devolve o texto da chave no idioma atual. Se faltar em inglês, usa o português.
function t(chave, ...valores) {
  const texto = TEXTOS[IDIOMA][chave] ?? TEXTOS.pt[chave] ?? chave;
  return typeof texto === "function" ? texto(...valores) : texto;
}

// Troca os textos fixos do HTML e prepara o botão EN/PT.
// (Este arquivo é carregado no fim da página, então o HTML já existe aqui.)
document.documentElement.lang = IDIOMA === "pt" ? "pt-BR" : "en";
if (IDIOMA !== "pt") {
  for (const elemento of document.querySelectorAll("[data-t]")) {
    elemento.textContent = t(elemento.dataset.t);
  }
  for (const elemento of document.querySelectorAll("[data-t-aria]")) {
    elemento.setAttribute("aria-label", t(elemento.dataset.tAria));
  }
}

const botaoIdioma = document.getElementById("botao-idioma");
if (botaoIdioma) {
  const outro = IDIOMA === "pt" ? "en" : "pt";
  // location.pathname: continua na mesma página (o <base href> mandaria para a inicial)
  botaoIdioma.href = `${location.pathname}?lang=${outro}`;
  botaoIdioma.textContent = t("botao_idioma");
  botaoIdioma.lang = outro === "pt" ? "pt-BR" : "en"; // o leitor de tela pronuncia no idioma certo
  botaoIdioma.setAttribute("aria-label", t("botao_idioma_descricao"));
}

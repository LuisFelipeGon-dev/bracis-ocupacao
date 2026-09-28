// Funções usadas pela página inicial (participante.js) e pela página da sala (sala.js).
// Os textos vêm de t("chave"), do idioma.js (português ou inglês).
// As funções de decisão (nível, ordem, picos por hora...) não mexem na página:
// recebem dados e devolvem resultados, e por isso dá para testá-las no Node.

const NOMES_TIPO = { sala: t("tipo_sala"), auditorio: t("tipo_auditorio"), laboratorio: t("tipo_laboratorio") };

// Atalho para pegar um elemento pelo id.
const $ = (id) => document.getElementById(id);

// Cria um elemento com classe e texto. Usamos textContent (e não innerHTML) para
// que nenhum texto vindo do banco ou da planilha seja interpretado como código da página.
function el(tag, classe, texto) {
  const elemento = document.createElement(tag);
  if (classe) elemento.className = classe;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}


// ---------- Nível de lotação (regra única, usada em todas as telas) ----------
//   Livre:     sem sessão agora e ninguém dentro
//   Tranquila: menos de 40%   ·   Moderada: 40% a 74%
//   Lotada:    75% a 99%      ·   Cheia:    100% ou mais

function nivelDaSala(ambiente) {
  const pct = ambiente.capacidade > 0 ? Math.round((ambiente.ocupacao / ambiente.capacidade) * 100) : 0;
  let chave;
  if (!ambiente.agora && ambiente.ocupacao === 0) chave = "livre";
  else if (pct >= 100) chave = "cheia";
  else if (pct >= 75) chave = "lotada";
  else if (pct >= 40) chave = "moderada";
  else chave = "tranquila";
  return { chave, pct, rotulo: t(`nivel_${chave}`) };
}

// "Lotada · 83%" (ou só "Livre"). O texto sempre acompanha a cor, para quem não distingue cores.
function textoNivel(nivel) {
  return nivel.chave === "livre" ? nivel.rotulo : `${nivel.rotulo} · ${nivel.pct}%`;
}

function criarSeloNivel(nivel) {
  return el("span", `nivel nivel-${nivel.chave}`, textoNivel(nivel));
}

// Barra de lotação: o trilho é a capacidade; a parte colorida, quem está lá (no máximo 100%).
function criarBarra(nivel, classeExtra = "") {
  const trilho = el("div", `barra ${classeExtra}`.trim());
  trilho.setAttribute("role", "img");
  trilho.setAttribute("aria-label", t("porcentagem_ocupado", nivel.pct));
  const cheia = el("div", `barra-cheia nivel-${nivel.chave}`);
  cheia.style.width = `${Math.min(nivel.pct, 100)}%`;
  trilho.append(cheia);
  return trilho;
}


// ---------- Ordem, datas e horários ----------

// Sempre auditórios, depois salas, depois laboratório: cada pessoa acha a sala dela
// sempre no mesmo lugar. Dentro do tipo, pelo código (S2 antes de S10).
const ORDEM_TIPO = { auditorio: 0, sala: 1, laboratorio: 2 };
function ordenarSalas(lista) {
  return [...lista].sort((a, b) =>
    (ORDEM_TIPO[a.tipo] ?? 9) - (ORDEM_TIPO[b.tipo] ?? 9) ||
    a.codigo.localeCompare(b.codigo, undefined, { numeric: true }));
}

function periodoDoDia(horaDoDia) {
  if (horaDoDia < 12) return "manha";
  if (horaDoDia < 18) return "tarde";
  return "noite";
}

// "TER 20 OUT" / "TUE 20 OCT"
function rotuloDia(data) {
  const curto = (opcoes) => data.toLocaleDateString(LOCALE, opcoes).replace(/\./g, "").trim().slice(0, 3).toUpperCase();
  return `${curto({ weekday: "short" })} ${data.getDate()} ${curto({ month: "short" })}`;
}

// Os horários vêm do servidor como "2026-10-20T09:00" (horário de Cuiabá).
const hora = (horario) => horario.slice(11, 16);
const diaMes = (horario) => `${horario.slice(8, 10)}/${horario.slice(5, 7)}`;
const minutosDoDia = (horario) => Number(horario.slice(11, 13)) * 60 + Number(horario.slice(14, 16));

// "às 10:45" se for hoje; "20/10 às 10:45" se for outro dia.
function quando(sessao) {
  return sessao.hoje ? t("as_hora", hora(sessao.inicio)) : t("dia_as_hora", diaMes(sessao.inicio), hora(sessao.inicio));
}

// Maior número de pessoas em cada hora do dia, para o gráfico de barras.
//   pontos:   [{ horario: "2026-10-20T09:15", ocupacao: 42 }, ...] em ordem (vem da API)
//   inicial:  quem já estava na sala quando o dia começou
//   agoraMin: minuto atual do dia (ex.: 14:30 = 870)
// As horas vão de 8h a 18h, esticando se houver registro antes ou depois, ou se agora é antes das 8h
// ou depois das 18h (assim a hora atual sempre aparece).
// O pico de uma hora é o maior valor entre o que havia no começo dela e cada registro dentro dela.
function picosPorHora(pontos, inicial, agoraMin) {
  const minuto = (p) => minutosDoDia(p.horario);
  const horasComRegistro = pontos.map((p) => Math.floor(minuto(p) / 60));
  const horaAtual = Math.floor(agoraMin / 60);
  const primeira = Math.min(8, horaAtual, ...horasComRegistro); // antes das 8h, começa na hora atual
  const ultima = Math.min(23, Math.max(18, horaAtual, ...horasComRegistro));

  const resultado = [];
  let valor = inicial; // quantas pessoas havia no começo da hora
  let i = 0;
  for (let h = primeira; h <= ultima; h++) {
    let pico = valor;
    while (i < pontos.length && minuto(pontos[i]) < (h + 1) * 60) {
      valor = pontos[i].ocupacao;
      pico = Math.max(pico, valor);
      i++;
    }
    const estado = h < horaAtual ? "passada" : h === horaAtual ? "atual" : "futura";
    resultado.push({ hora: h, pico: estado === "futura" ? null : pico, estado });
  }
  return resultado;
}


// "A seguir nesta sala": o que ainda vai começar hoje (sem a sessão que já está acontecendo).
// Se hoje não tem mais nada, as sessões do próximo dia que tiver alguma.
//   programacao: sessões da sala em ordem de início ({ inicio: "2026-10-20T09:00", ... })
//   agora:       "2026-10-20T14:30" (relógio do servidor)
// Devolve { outroDia: false, sessoes } ou { outroDia: true, dia: "2026-10-21", sessoes }.
function aSeguir(programacao, agora) {
  const hoje = agora.slice(0, 10);
  const deHoje = programacao.filter((s) => s.inicio.slice(0, 10) === hoje && s.inicio > agora);
  if (deHoje.length > 0) return { outroDia: false, sessoes: deHoje };
  const proxima = programacao.find((s) => s.inicio.slice(0, 10) > hoje);
  if (!proxima) return { outroDia: false, sessoes: [] };
  const dia = proxima.inicio.slice(0, 10);
  return { outroDia: true, dia, sessoes: programacao.filter((s) => s.inicio.slice(0, 10) === dia) };
}


// ---------- Programação (tela com todas as sessões) ----------

// Os dias que têm sessão, em ordem: [{ dia: "2026-10-20", hoje: true }, ...]
// (vêm da planilha, então acompanham se a organização mudar as datas)
function diasDaProgramacao(sessoes, hoje) {
  const dias = [...new Set(sessoes.map((s) => s.inicio.slice(0, 10)))].sort();
  return dias.map((dia) => ({ dia, hoje: dia === hoje }));
}

// Em qual dia a tela abre: hoje, se tiver sessão; senão o próximo; senão (evento acabou) o primeiro.
function diaInicial(dias, hoje) {
  if (dias.length === 0) return null;
  const escolhido = dias.find((d) => d.dia === hoje) ?? dias.find((d) => d.dia > hoje) ?? dias[0];
  return escolhido.dia;
}

// Agrupa as sessões de um dia pelo horário de início.
// Estado do bloco: "agora" se alguma sessão dele está acontecendo; "passado" se todas já acabaram.
function blocosPorHorario(sessoes, agora) {
  const porInicio = new Map();
  for (const sessao of [...sessoes].sort((a, b) => a.inicio.localeCompare(b.inicio))) {
    if (!porInicio.has(sessao.inicio)) porInicio.set(sessao.inicio, []);
    porInicio.get(sessao.inicio).push(sessao);
  }
  return [...porInicio].map(([inicio, doBloco]) => {
    let estado = "futuro";
    if (doBloco.some((s) => s.inicio <= agora && agora < s.fim)) estado = "agora";
    else if (doBloco.every((s) => s.fim <= agora)) estado = "passado";
    return { inicio, estado, sessoes: doBloco };
  });
}

// Para onde rolar ao abrir: o bloco "agora"; senão o próximo que vai começar; senão nenhum (-1).
function blocoParaRolar(blocos) {
  const agora = blocos.findIndex((b) => b.estado === "agora");
  return agora !== -1 ? agora : blocos.findIndex((b) => b.estado === "futuro");
}


// ---------- Selo "AO VIVO" e "atualizado há N s" ----------
// O leitor de tela só é avisado quando a conexão cai ou volta: anunciar o horário
// a cada atualização interromperia quem está ouvindo a página.

let conexaoOk = null;         // null = ainda não sabemos
let ultimaAtualizacao = null; // Date da última vez que os dados chegaram

const horaCurta = (data) => data.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });

function mostrarAtualizado(deuCerto) {
  if (conexaoOk !== null && deuCerto !== conexaoOk) {
    $("aviso-conexao").textContent = deuCerto ? t("conexao_restabelecida") : t("sem_conexao");
  }
  conexaoOk = deuCerto;
  if (deuCerto) {
    ultimaAtualizacao = new Date();
    $("selo-hora").textContent = horaCurta(ultimaAtualizacao);
  }
  $("selo-ao-vivo").classList.toggle("sem-conexao", !deuCerto);
  mostrarEstadoAtualizacao();
}

// "atualizado há 12 s" ou "sem conexão · últimos dados de 14:32" (só na página inicial).
function mostrarEstadoAtualizacao() {
  const estado = $("estado-atualizacao");
  if (!estado) return;
  const linha = $("linha-apoio");
  if (conexaoOk === false) {
    estado.textContent = ultimaAtualizacao ? t("sem_conexao_ultimos", horaCurta(ultimaAtualizacao)) : t("sem_conexao");
    linha.classList.add("erro");
    return;
  }
  linha.classList.remove("erro");
  if (!ultimaAtualizacao) {
    estado.textContent = "";
    return;
  }
  const segundos = Math.round((Date.now() - ultimaAtualizacao) / 1000);
  if (segundos < 5) estado.textContent = t("atualizado_agora");
  else if (segundos < 60) estado.textContent = t("atualizado_ha_s", segundos);
  else estado.textContent = t("atualizado_ha_min", Math.floor(segundos / 60));
}

setInterval(mostrarEstadoAtualizacao, 1000);

// Chama a função a cada "intervalo" milissegundos, mas só com a página visível:
// se a pessoa trocar de aba ou bloquear o celular, para; quando voltar, atualiza na hora.
function repetirEnquantoVisivel(funcao, intervalo) {
  setInterval(() => {
    if (!document.hidden) funcao();
  }, intervalo);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) funcao();
  });
  funcao();
}

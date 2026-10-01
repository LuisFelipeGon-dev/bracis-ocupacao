// Regras da tela do totem (participante.js). Os textos são em inglês: o totem fica só em inglês.
// Estas funções não mexem na página: recebem dados e devolvem resultados,
// e por isso dá para testá-las no Node (testes/unidade/teste_publico.js).

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


// ---------- Nível de lotação ----------
// O totem mostra só a porcentagem (a capacidade muda conforme o momento do congresso).
//   Empty:            sem sessão agora e ninguém dentro
//   Plenty of seats:  menos de 40%   ·   Filling up: 40% a 74%
//   Almost full:      75% a 99%      ·   Full:       100% ou mais

const ROTULOS_NIVEL = {
  livre: "Empty",
  tranquila: "Plenty of seats",
  moderada: "Filling up",
  lotada: "Almost full",
  cheia: "Full",
};

function nivelDaSala(ambiente) {
  const pct = ambiente.capacidade > 0 ? Math.round((ambiente.ocupacao / ambiente.capacidade) * 100) : 0;
  let chave;
  if (!ambiente.agora && ambiente.ocupacao === 0) chave = "livre";
  else if (pct >= 100) chave = "cheia";
  else if (pct >= 75) chave = "lotada";
  else if (pct >= 40) chave = "moderada";
  else chave = "tranquila";
  return { chave, pct, rotulo: ROTULOS_NIVEL[chave] };
}


// ---------- Ordem, datas e horários ----------

// Sempre auditórios, depois salas: cada sala fica sempre no mesmo lugar da tela.
// Dentro do tipo, pelo código (S2 antes de S10).
const ORDEM_TIPO = { auditorio: 0, sala: 1, laboratorio: 2 };
function ordenarSalas(lista) {
  return [...lista].sort((a, b) =>
    (ORDEM_TIPO[a.tipo] ?? 9) - (ORDEM_TIPO[b.tipo] ?? 9) ||
    a.codigo.localeCompare(b.codigo, undefined, { numeric: true }));
}

// Os horários vêm do servidor como "2026-10-20T09:00" (horário de Cuiabá).
const hora = (horario) => horario.slice(11, 16);

// "2026-10-21T09:00" vira "Wed 21 Oct"
function diaCurto(horario) {
  const [ano, mes, dia] = horario.slice(0, 10).split("-").map(Number);
  return new Date(ano, mes - 1, dia)
    .toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    .replace(",", "");
}

// Quando é a próxima sessão: "14:00" se for hoje; "Wed 21 Oct, 09:00" se for outro dia.
function quandoProxima(sessao) {
  return sessao.hoje ? hora(sessao.inicio) : `${diaCurto(sessao.inicio)}, ${hora(sessao.inicio)}`;
}

// "Tue 20 Oct" (data do topo da tela)
function rotuloDia(data) {
  return data
    .toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    .replace(",", "");
}

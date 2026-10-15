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
// A % é a estimativa que o voluntário informou (0, 10 ... 100, ou 110 = gente em pé).
//   No estimate yet:  ninguém informou nesta sessão (a estimativa "zera" quando a sessão muda)
//   Empty:            0%
//   Plenty of seats:  10% a 30%      ·   Filling up: 40% a 70%
//   Almost full:      80% e 90%      ·   Full:       100% ou "gente em pé" (aparece "100%+")

const GENTE_EM_PE = 110;

const ROTULOS_NIVEL = {
  sem: "No estimate yet",
  livre: "Empty",
  tranquila: "Plenty of seats",
  moderada: "Filling up",
  lotada: "Almost full",
  cheia: "Full",
};

function nivelDaSala(ambiente) {
  const estimativa = ambiente.estimativa;
  if (!estimativa) return { chave: "sem", pct: null, texto: "—", rotulo: ROTULOS_NIVEL.sem };
  const pct = estimativa.porcentagem;
  let chave;
  if (pct === 0) chave = "livre";
  else if (pct >= 100) chave = "cheia";
  else if (pct >= 75) chave = "lotada";
  else if (pct >= 40) chave = "moderada";
  else chave = "tranquila";
  const texto = pct === GENTE_EM_PE ? "100%+" : `${pct}%`;
  return { chave, pct, texto, rotulo: ROTULOS_NIVEL[chave] };
}


// ---------- Ordem, datas e horários ----------

// Sempre salas, depois auditórios (ordem pedida pela organização): cada sala fica sempre
// no mesmo lugar da tela. Dentro do tipo, pelo código (S2 antes de S10).
const ORDEM_TIPO = { sala: 0, auditorio: 1, laboratorio: 2 };
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

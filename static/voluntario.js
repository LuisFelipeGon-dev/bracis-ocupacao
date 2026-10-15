// Página do voluntário: login, escolha da sala e estimativa da lotação em %.
// O voluntário olha a sala e toca na % que acha que está ocupada. Errou? É só tocar na certa:
// vale sempre a última estimativa.

// Os botões: 0% a 100% de 10 em 10, e 110 = lotada, com gente em pé (igual ao servidor).
const PORCENTAGENS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
const GENTE_EM_PE = 110;

let ambienteAtual = null; // código da sala escolhida, ex.: "A1"
let enviando = false;     // true enquanto uma estimativa está a caminho do servidor

// Atalho para pegar um elemento pelo id.
const $ = (id) => document.getElementById(id);


// ---------- Conversa com a API ----------

// Envia um pedido para o servidor e devolve a resposta.
// Se der erro, lança uma exceção com a mensagem que o servidor mandou.
async function api(metodo, rota, dados) {
  let resposta;
  try {
    resposta = await fetch(rota, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: dados ? JSON.stringify(dados) : undefined,
    });
  } catch {
    throw new Error("Sem conexão com o servidor. Tente de novo.");
  }
  const corpo = await resposta.json().catch(() => ({}));

  if (resposta.status === 401 && rota !== "login") {
    mostrarTela("login"); // o login expirou
  }
  if (!resposta.ok) {
    throw new Error(textoDoErro(corpo));
  }
  return corpo;
}

// Os erros que nós escrevemos vêm como texto. Os de formato (422, do FastAPI) vêm como
// lista, em inglês: aí dizemos só qual campo foi recusado.
const NOMES_CAMPOS = { usuario: "usuário", pin: "senha", porcentagem: "porcentagem" };
function textoDoErro(corpo) {
  if (typeof corpo.detail === "string") return corpo.detail;
  const campo = corpo.detail?.[0]?.loc?.at(-1);
  return campo ? `Confira o campo "${NOMES_CAMPOS[campo] ?? campo}".` : "O servidor recusou os dados.";
}


// ---------- Telas e mensagens ----------

function mostrarTela(nome) {
  for (const tela of document.querySelectorAll("section")) {
    tela.hidden = tela.id !== `tela-${nome}`;
  }
}

// Confirmações somem depois de 4 segundos. Erros ficam na tela até o próximo
// envio dar certo, para não passarem despercebidos (o iPhone não vibra pelo site).
let timerMensagem;
function mensagem(texto, tipo) {
  const el = $("mensagem");
  el.textContent = texto;
  el.className = tipo;
  clearTimeout(timerMensagem);
  if (tipo !== "erro") timerMensagem = setTimeout(() => (el.textContent = ""), 4000);
}

// O celular lembra a sala escolhida. Em modo anônimo isso pode falhar, e tudo bem.
function lembrarAmbiente(codigo) {
  try {
    if (codigo) localStorage.setItem("ambiente", codigo);
    else localStorage.removeItem("ambiente");
  } catch {}
}

function ambienteLembrado() {
  try {
    return localStorage.getItem("ambiente");
  } catch {
    return null;
  }
}

// 60 -> "60%"; 110 -> "100%+"
const textoPorcentagem = (p) => (p === GENTE_EM_PE ? "100%+" : `${p}%`);

// "2026-10-20T10:42:05-04:00" -> "10:42"
const hora = (horario) => horario.slice(11, 16);


// ---------- Login ----------

function entrou(voluntario) {
  for (const el of document.querySelectorAll(".nome-voluntario")) {
    el.textContent = voluntario.nome;
  }
  const salvo = ambienteLembrado();
  if (salvo) abrirSala(salvo);
  else mostrarAmbientes();
}

$("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault(); // não deixa o navegador recarregar a página
  const form = evento.target;
  const botao = form.querySelector("button");
  botao.setAttribute("aria-busy", "true"); // mostra a "rodinha" do Pico
  try {
    const voluntario = await api("POST", "login", {
      usuario: form.usuario.value,
      pin: form.pin.value,
    });
    form.reset();
    mensagem("", "");
    entrou(voluntario);
  } catch (erro) {
    form.pin.value = "";
    mensagem(erro.message, "erro");
  } finally {
    botao.removeAttribute("aria-busy");
  }
});

async function sair() {
  await api("POST", "logout").catch(() => {});
  mostrarTela("login");
}


// ---------- Escolha da sala ----------

async function mostrarAmbientes() {
  ambienteAtual = null;
  mostrarTela("ambientes");
  const lista = $("lista-ambientes");
  try {
    const ambientes = await api("GET", "ambientes");
    lista.replaceChildren(); // limpa a lista antes de montar de novo
    for (const ambiente of ambientes) {
      const botao = document.createElement("button");
      botao.className = "outline";
      botao.textContent = ambiente.nome;
      botao.addEventListener("click", () => abrirSala(ambiente.codigo));
      lista.append(botao);
    }
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function abrirSala(codigo) {
  ambienteAtual = codigo;
  lembrarAmbiente(codigo);
  try {
    mostrarSala(await api("GET", `ambientes/${codigo}`));
    mostrarTela("estimativa");
  } catch (erro) {
    // A sala lembrada não existe mais (ex.: dados trocados): volta para a lista.
    lembrarAmbiente(null);
    if (!$("tela-login").hidden) return; // era falta de login, fica no login
    mostrarAmbientes();
  }
}


// ---------- Estimativa ----------

// Cria os botões uma vez só: 0% a 100% numa grade e, embaixo, o "gente em pé".
function criarBotoes() {
  const caixa = $("botoes-porcentagem");
  for (const p of [...PORCENTAGENS, GENTE_EM_PE]) {
    const botao = document.createElement("button");
    botao.textContent = p === GENTE_EM_PE ? "Lotada, gente em pé" : `${p}%`;
    botao.dataset.porcentagem = p;
    botao.className = p === GENTE_EM_PE ? "secondary em-pe" : "outline";
    botao.addEventListener("click", () => informar(p));
    caixa.append(botao);
  }
}

// Mostra a sala: nome, sessão de agora e a estimativa que vale agora (a do botão marcado).
function mostrarSala(ambiente) {
  $("nome-ambiente").textContent = ambiente.nome;
  $("sessao-agora").textContent = ambiente.agora
    ? `Agora: ${ambiente.agora.titulo}`
    : "Nenhuma sessão agora";

  const estimativa = ambiente.estimativa;
  $("estimativa").textContent = estimativa ? textoPorcentagem(estimativa.porcentagem) : "—";
  $("estimativa-quando").textContent = estimativa
    ? `informada às ${hora(estimativa.horario)} por ${estimativa.voluntario}`
    : "Ainda sem estimativa nesta sessão";

  // Marca o botão da estimativa atual (aria-pressed: o leitor de tela também sabe qual é)
  for (const botao of document.querySelectorAll("#botoes-porcentagem button")) {
    const marcado = estimativa !== null && Number(botao.dataset.porcentagem) === estimativa.porcentagem;
    botao.setAttribute("aria-pressed", marcado ? "true" : "false");
  }
}

async function informar(porcentagem) {
  if (enviando) return; // um toque duplo não registra duas vezes
  enviando = true;
  navigator.vibrate?.(40); // vibração curta de confirmação (nem todo celular tem)
  try {
    const ambiente = await api("POST", "estimativas", { ambiente_codigo: ambienteAtual, porcentagem });
    mostrarSala(ambiente);
    mensagem(`Registrado: ${textoPorcentagem(porcentagem)} às ${hora(ambiente.estimativa.horario)}.`, "ok");
  } catch (erro) {
    mensagem(`${erro.message} A estimativa não foi registrada.`, "erro");
  } finally {
    enviando = false;
  }
}

// Botões "Trocar sala" e "Trocar voluntário"
document.addEventListener("click", (evento) => {
  const acao = evento.target.closest("[data-acao]")?.dataset.acao;
  if (!acao) return;
  evento.preventDefault();
  if (acao === "sair") sair();
  if (acao === "trocar-sala") mostrarAmbientes();
});

// A cada 10 segundos busca a sala de novo: outro voluntário pode ter informado,
// ou a sessão mudou e a estimativa "zerou".
setInterval(async () => {
  if ($("tela-estimativa").hidden || enviando) return;
  try {
    mostrarSala(await api("GET", `ambientes/${ambienteAtual}`));
  } catch {}
}, 10000);


// ---------- Início ----------

criarBotoes();
// Ao abrir a página: se já estiver logado, pula o login.
api("GET", "eu")
  .then(entrou)
  .catch(() => mostrarTela("login"));

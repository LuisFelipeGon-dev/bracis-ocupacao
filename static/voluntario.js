// Página do voluntário: login, escolha da sala e contagem.

const NOMES_TIPO = { entrada: "Entrada", saida: "Saída" };

let ambienteAtual = null; // código do ambiente escolhido, ex.: "A1"
let ultimoAmbiente = null; // última resposta do servidor sobre a sala (nome, ocupação, capacidade)
let ocupado = false;      // true enquanto um grupo ou um "Desfazer" está sendo enviado
let envios = 0;           // conta os registros feitos (usado na atualização automática)

// Toques de +1/−1 que o voluntário já fez mas o servidor ainda não recebeu.
// Guardados aqui para nenhum toque se perder enquanto outro está a caminho.
const pendentes = { entrada: 0, saida: 0 };
let envioToques = null;   // o envio de toques em andamento (null = nenhum)

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
    const erro = new Error(textoDoErro(corpo));
    erro.status = resposta.status; // usado para saber se vale tentar de novo
    throw erro;
  }
  return corpo;
}

// Os erros que nós escrevemos vêm como texto. Os de formato (422, do FastAPI) vêm como
// lista, em inglês: aí dizemos só qual campo foi recusado.
const NOMES_CAMPOS = { email: "e-mail", pin: "PIN", quantidade: "quantidade" };
function textoDoErro(corpo) {
  if (typeof corpo.detail === "string") return corpo.detail;
  const campo = corpo.detail?.[0]?.loc?.at(-1);
  return campo ? `Confira o campo "${NOMES_CAMPOS[campo] ?? campo}".` : "O servidor recusou os dados.";
}

// Para o grupo e o "Desfazer": trava esses botões enquanto o pedido está a caminho,
// assim um toque duplo não registra duas vezes. Os botões +1/−1 continuam livres.
async function enviar(rota, dados) {
  if (ocupado) return null;
  await enviarToques(); // primeiro manda os toques que ainda estão guardados
  if (ocupado) return null; // outro envio começou enquanto esperávamos
  if (temPendentes()) {
    mensagem("Ainda há toques não enviados. Espere a conexão voltar.", "erro");
    return null;
  }
  ocupado = true;
  travarBotoes(true);
  try {
    const resposta = await api("POST", rota, dados);
    envios++;
    mensagem("", "");
    return resposta;
  } catch (erro) {
    mensagem(erro.message, "erro");
    return null;
  } finally {
    ocupado = false;
    travarBotoes(false);
    enviarToques(); // toques feitos durante este envio
  }
}


// ---------- Envio dos toques de +1/−1 ----------

function temPendentes() {
  return pendentes.entrada > 0 || pendentes.saida > 0;
}

// Começa a mandar os toques guardados, se ainda não estiver mandando.
// Devolve uma promessa que termina quando não houver mais nada a enviar (ou der erro).
function enviarToques() {
  if (!envioToques && !ocupado && temPendentes()) {
    envioToques = lacoDeEnvio().finally(() => (envioToques = null));
  }
  return envioToques ?? Promise.resolve();
}

// Manda os toques acumulados, um tipo por vez, como um evento só com a quantidade total.
// Enquanto um pedido está a caminho, novos toques vão se somando e saem na próxima volta.
// Entradas vão antes das saídas: assim o servidor nunca acha que a sala está vazia demais.
async function lacoDeEnvio() {
  while (temPendentes()) {
    const tipo = pendentes.entrada > 0 ? "entrada" : "saida";
    const quantidade = pendentes[tipo];
    try {
      const ambiente = await api("POST", "eventos", {
        ambiente_codigo: ambienteAtual,
        tipo,
        quantidade,
      });
      pendentes[tipo] -= quantidade;
      envios++;
      mensagem("", ""); // se havia um erro na tela, ele já foi resolvido
      mostrarOcupacao(ambiente);
    } catch (erro) {
      // Sem conexão ou servidor reiniciando (5xx): guarda os toques e tenta de novo depois.
      // Outros erros (ex.: saída maior que o número de pessoas) não melhoram tentando de novo.
      const tentarDeNovo = erro.status === undefined || erro.status >= 500;
      if (tentarDeNovo) {
        const total = pendentes.entrada + pendentes.saida;
        const toques = total === 1 ? "1 toque guardado" : `${total} toques guardados`;
        mensagem(`Sem conexão: ${toques}, tentando de novo a cada 5 s.`, "erro");
      } else {
        pendentes.entrada = pendentes.saida = 0;
        mensagem(erro.message, "erro");
      }
      if (ultimoAmbiente) mostrarOcupacao(ultimoAmbiente);
      return;
    }
  }
}

// Um toque em +1 ou −1: guarda, mostra na hora e manda para o servidor.
function tocar(tipo) {
  if (tipo === "saida" && ocupacaoNaTela() <= 0) {
    mensagem("A sala já está vazia.", "erro");
    return;
  }
  pendentes[tipo]++;
  navigator.vibrate?.(40); // vibração curta de confirmação (nem todo celular tem)
  if (ultimoAmbiente) mostrarOcupacao(ultimoAmbiente);
  enviarToques();
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

// Trava grupo e "Desfazer". Os botões grandes (+1/−1) nunca travam: os toques são guardados.
function travarBotoes(travar) {
  for (const botao of document.querySelectorAll("#tela-contagem button:not(.btn-grande)")) {
    botao.disabled = travar;
  }
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


// ---------- Login ----------

function entrou(voluntario) {
  for (const el of document.querySelectorAll(".nome-voluntario")) {
    el.textContent = voluntario.nome;
  }
  const salvo = ambienteLembrado();
  if (salvo) abrirContagem(salvo);
  else mostrarAmbientes();
}

$("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault(); // não deixa o navegador recarregar a página
  const form = evento.target;
  const botao = form.querySelector("button");
  botao.setAttribute("aria-busy", "true"); // mostra a "rodinha" do Pico
  try {
    const voluntario = await api("POST", "login", {
      email: form.email.value,
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
      botao.addEventListener("click", () => abrirContagem(ambiente.codigo));
      lista.append(botao);
    }
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function abrirContagem(codigo) {
  ambienteAtual = codigo;
  lembrarAmbiente(codigo);
  try {
    mostrarOcupacao(await api("GET", `ambientes/${codigo}`));
    mostrarTela("contagem");
  } catch (erro) {
    // A sala lembrada não existe mais (ex.: dados trocados): volta para a lista.
    lembrarAmbiente(null);
    if (!$("tela-login").hidden) return; // era falta de login, fica no login
    mostrarAmbientes();
  }
}


// ---------- Contagem ----------

// O número mostrado = o que o servidor sabe + os toques que ainda estão a caminho.
function ocupacaoNaTela() {
  const base = ultimoAmbiente ? ultimoAmbiente.ocupacao : 0;
  return base + pendentes.entrada - pendentes.saida;
}

function mostrarOcupacao(ambiente) {
  ultimoAmbiente = ambiente;
  const ocupacao = ocupacaoNaTela();
  $("nome-ambiente").textContent = ambiente.nome;
  $("ocupacao").textContent = ocupacao;
  $("capacidade").textContent = ambiente.capacidade;
  const lotado = ocupacao >= ambiente.capacidade;
  $("ocupacao").classList.toggle("lotado", lotado);
  $("aviso-lotado").hidden = !lotado;
}

async function registrarGrupo(tipo) {
  const quantidade = Number($("qtd-grupo").value);
  if (!Number.isInteger(quantidade) || quantidade < 1 || quantidade > 500) {
    mensagem("Digite quantas pessoas: um número de 1 a 500.", "erro");
    return;
  }
  const nome = NOMES_TIPO[tipo];
  if (!confirm(`Confirmar ${nome.toLowerCase()} de ${pessoas(quantidade)}?`)) return;
  const ambiente = await enviar("eventos", {
    ambiente_codigo: ambienteAtual,
    tipo,
    quantidade,
  });
  if (ambiente) {
    mostrarOcupacao(ambiente);
    navigator.vibrate?.(40);
    $("qtd-grupo").value = "";
    mensagem(`${nome} de ${pessoas(quantidade)} registrada.`, "ok");
  }
}

// "1 pessoa" / "10 pessoas"
const pessoas = (n) => (n === 1 ? "1 pessoa" : `${n} pessoas`);

async function desfazer() {
  if (ocupado) return;
  await enviarToques(); // o último registro só existe depois que os toques chegam ao servidor
  if (temPendentes()) {
    mensagem("Ainda há toques não enviados. Espere a conexão voltar.", "erro");
    return;
  }
  // Pergunta ao servidor qual é o último registro deste voluntário, para dizer o que vai sumir.
  let ultimo;
  try {
    ultimo = await api("GET", `eventos/ultimo?ambiente_codigo=${encodeURIComponent(ambienteAtual)}`);
  } catch (erro) {
    mensagem(erro.message, "erro");
    return;
  }
  const nome = NOMES_TIPO[ultimo.tipo].toLowerCase();
  const horario = ultimo.horario.slice(11, 16); // "2026-10-20T10:42:05-04:00" -> "10:42"
  if (!confirm(`Desfazer ${nome} de ${pessoas(ultimo.quantidade)} (${horario})?`)) return;
  const resposta = await enviar("eventos/desfazer", {
    ambiente_codigo: ambienteAtual,
    evento_id: ultimo.id,
  });
  if (resposta) {
    mostrarOcupacao(resposta.ambiente);
    const { tipo, quantidade } = resposta.desfeito;
    mensagem(`Desfeito: ${NOMES_TIPO[tipo].toLowerCase()} de ${pessoas(quantidade)}.`, "ok");
  }
}

$("btn-entrou").addEventListener("click", () => tocar("entrada"));
$("btn-saiu").addEventListener("click", () => tocar("saida"));
$("btn-grupo-entrou").addEventListener("click", () => registrarGrupo("entrada"));
$("btn-grupo-saiu").addEventListener("click", () => registrarGrupo("saida"));
$("btn-desfazer").addEventListener("click", desfazer);

// Links "Trocar sala" e "Trocar voluntário"
document.addEventListener("click", (evento) => {
  const acao = evento.target.closest("[data-acao]")?.dataset.acao;
  if (!acao) return;
  evento.preventDefault();
  // Os toques guardados são desta sala: não deixa trocar antes de enviá-los.
  if (temPendentes()) {
    mensagem("Espere os toques desta sala serem enviados antes de trocar.", "erro");
    enviarToques();
    return;
  }
  if (acao === "sair") sair();
  if (acao === "trocar-sala") mostrarAmbientes();
});

// A cada 5 segundos: se há toques guardados (a conexão falhou), tenta mandar de novo;
// senão, busca o número atualizado (caso alguém tenha registrado por outro celular).
setInterval(async () => {
  if ($("tela-contagem").hidden || ocupado || envioToques) return;
  if (temPendentes()) {
    enviarToques();
    return;
  }
  const enviosAntes = envios;
  try {
    const ambiente = await api("GET", `ambientes/${ambienteAtual}`);
    // Se o voluntário tocou algo enquanto esperávamos, esta resposta já está velha.
    if (envios === enviosAntes && !ocupado && !temPendentes()) mostrarOcupacao(ambiente);
  } catch {}
}, 5000);


// ---------- Início ----------

// Ao abrir a página: se já estiver logado, pula o login.
api("GET", "eu")
  .then(entrou)
  .catch(() => mostrarTela("login"));

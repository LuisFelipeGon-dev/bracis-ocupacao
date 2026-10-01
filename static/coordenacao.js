// Painel da coordenação: situação das salas e gerenciamento dos voluntários.

const INTERVALO = 10000;         // atualiza a tabela das salas a cada 10 segundos
const MINUTOS_SEM_REGISTRO = 10; // a partir daqui, a linha da sala fica destacada

// Atalho para pegar um elemento pelo id.
const $ = (id) => document.getElementById(id);


// ---------- Conversa com a API ----------

// Mesma ideia do voluntario.js: devolve a resposta ou lança um erro com a mensagem do servidor.
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

  if (resposta.status === 401 && rota !== "coordenacao/login") {
    mostrarTela("login"); // o login expirou
  }
  if (!resposta.ok) {
    throw new Error(textoDoErro(corpo));
  }
  return corpo;
}

// Os erros que nós escrevemos vêm como texto. Os de formato (422, do FastAPI) vêm como
// lista, em inglês: aí dizemos só qual campo foi recusado.
const NOMES_CAMPOS = { nome: "nome", email: "e-mail", senha: "senha", texto: "lista", quantidade: "quantidade", capacidade: "nova capacidade" };
function textoDoErro(corpo) {
  if (typeof corpo.detail === "string") return corpo.detail;
  const campo = corpo.detail?.[0]?.loc?.at(-1);
  return campo ? `Confira o campo "${NOMES_CAMPOS[campo] ?? campo}".` : "O servidor recusou os dados.";
}

// plural(3, "sessão", "sessões") -> "3 sessões"
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;


// ---------- Telas e mensagens ----------

function mostrarTela(nome) {
  $("tela-login").hidden = nome !== "login";
  $("tela-painel").hidden = nome !== "painel";
}

let timerMensagem;
function mensagem(texto, tipo) {
  const el = $("mensagem");
  el.textContent = texto;
  el.className = tipo;
  clearTimeout(timerMensagem);
  timerMensagem = setTimeout(() => (el.textContent = ""), 5000);
}

// Cria uma linha de tabela com os textos dados (textContent: nada vira código).
function linhaTabela(textos) {
  const tr = document.createElement("tr");
  for (const texto of textos) {
    const td = document.createElement("td");
    td.textContent = texto;
    tr.append(td);
  }
  return tr;
}

// "há 3 min", "há 1 h 20 min"...
function tempoDesde(horario) {
  const minutos = Math.floor((Date.now() - new Date(horario)) / 60000);
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  return `há ${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}


// ---------- Login ----------

$("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = evento.target;
  try {
    await api("POST", "coordenacao/login", { senha: form.senha.value });
    form.reset();
    mensagem("", "");
    abrirPainel();
  } catch (erro) {
    form.senha.value = "";
    mensagem(erro.message, "erro");
  }
});

$("link-sair").addEventListener("click", async (evento) => {
  evento.preventDefault();
  await api("POST", "coordenacao/logout").catch(() => {});
  mostrarTela("login");
});

function abrirPainel() {
  mostrarTela("painel");
  atualizarSituacao();
  carregarVoluntarios();
  api("GET", "coordenacao/programacao").then(mostrarProgramacao).catch((erro) => mensagem(erro.message, "erro"));
  carregarRelatorio();
}


// ---------- Situação das salas ----------

async function atualizarSituacao() {
  try {
    const ambientes = await api("GET", "coordenacao/situacao");
    const linhas = ambientes.map((a) => {
      const ultimo = a.ultimo_registro
        ? `${tempoDesde(a.ultimo_registro)} (${a.ultimo_voluntario})`
        : "nenhum";
      const tr = linhaTabela([
        a.nome,
        `${a.ocupacao} (${porcentagem(a)})`,
        a.capacidade,
        a.entradas,
        a.saidas,
        ultimo,
      ]);
      const minutos = a.ultimo_registro
        ? (Date.now() - new Date(a.ultimo_registro)) / 60000
        : 0;
      tr.classList.toggle("parada", minutos > MINUTOS_SEM_REGISTRO);
      return tr;
    });
    $("tabela-situacao").replaceChildren(...linhas);
    $("atualizado").textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
    preencherSalas(ambientes);
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

// "45%": a mesma conta do totem (comum.js)
const porcentagem = (a) => `${a.capacidade > 0 ? Math.round((a.ocupacao / a.capacidade) * 100) : 0}%`;


// ---------- Capacidade ----------

// Preenche a lista de salas do formulário só uma vez (senão, a cada 10 s, a escolha se perderia).
function preencherSalas(ambientes) {
  const lista = $("form-capacidade").codigo;
  if (lista.options.length > 0) return;
  for (const a of ambientes) {
    const opcao = new Option(`${a.nome} (hoje: ${a.capacidade})`, a.codigo);
    opcao.dataset.nome = a.nome;
    lista.append(opcao);
  }
}

$("form-capacidade").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = evento.target;
  const opcao = form.codigo.selectedOptions[0];
  const nome = opcao.dataset.nome;
  try {
    const { capacidade } = await api("POST", `coordenacao/ambientes/${form.codigo.value}/capacidade`, {
      capacidade: Number(form.capacidade.value),
    });
    opcao.textContent = `${nome} (hoje: ${capacidade})`;
    form.capacidade.value = "";
    mensagem(`Capacidade de ${nome} agora é ${capacidade}.`, "ok");
    atualizarSituacao();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
});

setInterval(() => {
  if (!$("tela-painel").hidden && !document.hidden) atualizarSituacao();
}, INTERVALO);


// ---------- Relatório por sessão ----------

async function carregarRelatorio() {
  try {
    const dados = await api("GET", "coordenacao/relatorio");
    const linhas = dados.sessoes.map((s) =>
      linhaTabela([
        diaMes(s.inicio),
        `${hora(s.inicio)}–${hora(s.fim)}`,
        s.ambiente,
        s.titulo,
        s.entradas,
        s.saidas,
        // Pico vazio = a sessão ainda não começou
        s.pico === null ? "—" : `${s.pico} / ${s.capacidade}`,
      ])
    );
    if (linhas.length === 0) {
      linhas.push(linhaTabela(["Nenhuma sessão na programação.", "", "", "", "", "", ""]));
    }
    $("tabela-relatorio").replaceChildren(...linhas);

    const fora = dados.fora_da_programacao
      .map((f) => `${f.ambiente}: ${plural(f.entradas, "entrada", "entradas")}, ${plural(f.saidas, "saída", "saídas")}`)
      .join(" · ");
    $("relatorio-fora").firstElementChild.textContent = fora
      ? `Fora da programação (registros sem sessão perto do horário): ${fora}`
      : "";
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

$("btn-atualizar-relatorio").addEventListener("click", carregarRelatorio);


// ---------- Programação ----------

// "2026-10-20T09:00" vira "20/10"
const diaMes = (horario) => horario.slice(8, 10) + "/" + horario.slice(5, 7);
const hora = (horario) => horario.slice(11, 16);

function mostrarProgramacao(dados) {
  const lida = dados.horario ? new Date(dados.horario).toLocaleTimeString("pt-BR") : "ainda não";
  $("programacao-resumo").textContent =
    `${plural(dados.sessoes.length, "sessão carregada", "sessões carregadas")} do ${dados.origem ?? "?"}. Última leitura: ${lida}.`;
  $("programacao-falha").textContent = dados.falha ?? "";
  $("programacao-erros").replaceChildren(
    ...dados.erros.map((e) =>
      Object.assign(document.createElement("li"), {
        textContent: `Linha ${e.linha} da planilha ignorada: ${e.motivo}`,
      })
    )
  );
  $("tabela-programacao").replaceChildren(
    ...dados.sessoes.map((s) =>
      linhaTabela([
        diaMes(s.inicio),
        `${hora(s.inicio)}–${hora(s.fim)}`,
        s.ambiente,
        s.titulo,
        s.palestrante ?? "",
      ])
    )
  );
}

$("btn-atualizar-programacao").addEventListener("click", async (evento) => {
  const botao = evento.target;
  botao.setAttribute("aria-busy", "true"); // mostra a "rodinha" do Pico enquanto espera
  try {
    const dados = await api("POST", "coordenacao/programacao/atualizar");
    mostrarProgramacao(dados);
    if (dados.falha) mensagem(dados.falha, "erro");
    else mensagem(`Programação atualizada: ${plural(dados.sessoes.length, "sessão", "sessões")}.`, "ok");
  } catch (erro) {
    mensagem(erro.message, "erro");
  } finally {
    botao.removeAttribute("aria-busy");
  }
});


// ---------- Voluntários ----------

async function carregarVoluntarios() {
  try {
    const voluntarios = await api("GET", "coordenacao/voluntarios");
    const linhas = voluntarios.map((v) => {
      const tr = linhaTabela([v.nome, v.email, v.ativo ? "Ativo" : "Desativado"]);

      const acoes = document.createElement("td");
      const btnPin = document.createElement("button");
      btnPin.className = "secondary outline";
      btnPin.textContent = "Novo PIN";
      // O leitor de tela lê o nome junto ("Novo PIN para Maria"), já que o botão se repete em cada linha.
      btnPin.setAttribute("aria-label", `Novo PIN para ${v.nome}`);
      btnPin.addEventListener("click", () => novoPin(v));

      const btnAtivo = document.createElement("button");
      btnAtivo.className = v.ativo ? "contrast outline" : "outline";
      btnAtivo.textContent = v.ativo ? "Desativar" : "Reativar";
      btnAtivo.setAttribute("aria-label", `${btnAtivo.textContent} ${v.nome}`);
      btnAtivo.addEventListener("click", () => mudarAtivo(v));

      acoes.append(btnPin, btnAtivo);
      tr.append(acoes);
      return tr;
    });
    $("tabela-voluntarios").replaceChildren(...linhas);
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

// Mostra a caixa com os PINs recém-criados (e os erros de importação, se houver).
function mostrarPins(criados, erros = []) {
  $("tabela-pins").replaceChildren(
    ...criados.map((c) => {
      const tr = linhaTabela([c.nome, c.email, c.pin]);
      tr.lastChild.className = "pin";
      return tr;
    })
  );
  $("erros-importacao").replaceChildren(
    ...erros.map((e) =>
      Object.assign(document.createElement("li"), {
        textContent: `Linha ${e.linha} ("${e.texto}"): ${e.motivo}`,
      })
    )
  );
  $("pins-gerados").hidden = false;
  $("pins-gerados").scrollIntoView({ behavior: "smooth" });
}

$("btn-fechar-pins").addEventListener("click", () => {
  $("tabela-pins").replaceChildren(); // tira os PINs da tela
  $("pins-gerados").hidden = true;
});

async function novoPin(voluntario) {
  if (!confirm(`Gerar um PIN novo para ${voluntario.nome}? O PIN antigo deixa de funcionar.`)) return;
  try {
    const resposta = await api("POST", `coordenacao/voluntarios/${voluntario.id}/novo-pin`);
    mostrarPins([resposta]);
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function mudarAtivo(voluntario) {
  const acao = voluntario.ativo ? "Desativar" : "Reativar";
  if (!confirm(`${acao} ${voluntario.nome}?`)) return;
  try {
    await api("POST", `coordenacao/voluntarios/${voluntario.id}/ativo`, {
      ativo: !voluntario.ativo,
    });
    carregarVoluntarios();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

$("form-voluntario").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = evento.target;
  try {
    const criado = await api("POST", "coordenacao/voluntarios", {
      nome: form.nome.value,
      email: form.email.value,
    });
    form.reset();
    mostrarPins([criado]);
    carregarVoluntarios();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
});

$("form-importar").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = evento.target;
  try {
    const { criados, erros } = await api("POST", "coordenacao/voluntarios/importar", {
      texto: form.texto.value,
    });
    form.reset();
    mostrarPins(criados, erros);
    mensagem(`${plural(criados.length, "cadastrado", "cadastrados")}, ${erros.length} com erro.`, erros.length ? "erro" : "ok");
    carregarVoluntarios();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
});


// ---------- Início ----------

// Ao abrir a página: se já estiver logado, vai direto para o painel.
api("GET", "coordenacao/eu")
  .then(abrirPainel)
  .catch(() => mostrarTela("login"));

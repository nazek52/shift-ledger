const $ = (selector) => document.querySelector(selector);
let token = sessionStorage.getItem("shift-token") || "";
let me,
  responders = [],
  incidents = [],
  selected,
  nextCursor;
let selectionGeneration = 0;
const transitions = {
  open: ["investigating"],
  investigating: ["monitoring"],
  monitoring: ["investigating", "resolved"],
  resolved: ["investigating"],
};
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
function message(text) {
  $("#message").textContent = text;
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Please check the fields and try again.",
    );
    error.status = response.status;
    throw error;
  }
  return body;
}
function renderQueue() {
  const active = incidents.filter((row) => row.status !== "resolved");
  $("#active-count").textContent = active.length;
  $("#pending-count").textContent = incidents.filter(
    (row) => row.pending_owner === me.name,
  ).length;
  $("#owned-count").textContent = active.filter(
    (row) => row.owner === me.name,
  ).length;
  const filter = $("#filter").value;
  const visible = incidents.filter(
    (row) =>
      filter === "all" ||
      (filter === "active" && row.status !== "resolved") ||
      (filter === "mine" && row.owner === me.name) ||
      (filter === "incoming" && row.pending_owner === me.name),
  );
  $("#incidents").innerHTML =
    visible
      .map(
        (row) =>
          `<button class="incident" data-id="${row.id}" aria-pressed="${row.id === selected?.id}"><span class="badge ${row.severity.toLowerCase()}">${row.severity}</span><span class="pill">${escape(row.status)}</span><strong>${escape(row.title)}</strong><small>${escape(row.service)} · ${escape(row.owner)}${row.pending_owner ? " → " + escape(row.pending_owner) : ""}</small></button>`,
      )
      .join("") || '<p class="muted">No incidents match this view.</p>';
  $("#more").hidden = !nextCursor;
}
async function load(append = false) {
  const data = await api(
    "/api/incidents" + (append && nextCursor ? `?before=${nextCursor}` : ""),
  );
  incidents = append ? [...incidents, ...data.items] : data.items;
  nextCursor = data.next_cursor;
  renderQueue();
}
function renderDetail() {
  const row = selected;
  const owner = row.owner === me.name;
  const writable = me.role === "responder";
  const actions = [["note", "Add evidence"]];
  if (owner) {
    actions.push(["transition", "Change status"]);
    if (row.pending_owner) actions.push(["cancel", "Cancel handoff"]);
    else if (row.status !== "resolved")
      actions.push(["handoff", "Request handoff"]);
  }
  if (row.pending_owner === me.name)
    actions.push(["accept", "Accept ownership"]);
  $("#detail").innerHTML =
    `<span class="eyebrow">INCIDENT #${row.id} / VERSION ${row.version}</span><h2>${escape(row.title)}</h2><div class="meta"><span>${escape(row.service)}</span><span class="badge ${row.severity.toLowerCase()}">${row.severity}</span><span>${escape(row.status)}</span><span>Owner: <strong>${escape(row.owner)}</strong></span></div>${row.pending_owner ? `<div class="notice">Handoff requested to <strong>${escape(row.pending_owner)}</strong>. ${escape(row.owner)} remains responsible until acceptance.</div>` : ""}<h3>Investigation timeline</h3><ol class="timeline">${row.events.map((event) => `<li><span class="event-kind">${escape(event.actor)} · ${escape(event.kind)}</span><p>${escape(event.note)}</p><time datetime="${escape(event.at)}">${new Date(event.at).toLocaleString()}</time></li>`).join("")}</ol>${writable ? `<form id="command-form"><div class="form-grid"><label>Next action<select id="action">${actions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select></label><label id="target-label" hidden>Destination<select id="target"></select></label></div><label>Context / evidence<textarea id="note" required minlength="3" maxlength="2000" placeholder="Leave the next responder enough context to act."></textarea></label><button class="primary">Record update</button></form>` : '<p class="muted">You have read-only access.</p>'}`;
  if (!writable) return;
  $("#action").onchange = () => {
    const action = $("#action").value;
    $("#target-label").hidden = !["handoff", "transition"].includes(action);
    const options =
      action === "handoff"
        ? responders.filter((name) => name !== me.name)
        : transitions[row.status];
    $("#target").innerHTML = options
      .map((value) => `<option>${escape(value)}</option>`)
      .join("");
  };
  $("#command-form").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    const draft = $("#note").value;
    try {
      selected = await api(`/api/incidents/${row.id}/commands`, {
        method: "POST",
        body: JSON.stringify({
          version: row.version,
          action: $("#action").value,
          note: draft,
          target: $("#target-label").hidden ? null : $("#target").value,
        }),
      });
      renderDetail();
      await load();
      message("Update recorded.");
    } catch (error) {
      if (error.status === 409) {
        await select(row.id);
        $("#note").value = draft;
        message(
          "Someone updated this incident. Your note is preserved; review the new timeline and choose the action again.",
        );
      } else message(error.message);
    } finally {
      button.disabled = false;
    }
  };
}
async function select(id) {
  const generation = ++selectionGeneration;
  const row = await api(`/api/incidents/${id}`);
  if (generation !== selectionGeneration) return;
  selected = row;
  renderDetail();
  renderQueue();
}
async function login() {
  me = await api("/api/me");
  responders = await api("/api/responders");
  await load();
  sessionStorage.setItem("shift-token", token);
  $("#login").hidden = true;
  $("#workspace").hidden = false;
  $("#logout").hidden = false;
  $("#new").hidden = me.role !== "responder";
  $("#identity").textContent = `${me.name} / ${me.role}`;
}
$("#login-form").onsubmit = async (event) => {
  event.preventDefault();
  token = $("#token").value.trim();
  try {
    await login();
    $("#token").value = "";
    message("");
  } catch (error) {
    message(error.message);
  }
};
$("#logout").onclick = () => {
  sessionStorage.removeItem("shift-token");
  location.reload();
};
$("#filter").onchange = renderQueue;
$("#incidents").onclick = (event) => {
  const button = event.target.closest("[data-id]");
  if (button)
    select(Number(button.dataset.id)).catch((error) => message(error.message));
};
$("#refresh").onclick = async () => {
  try {
    await load();
    if (selected) await select(selected.id);
    message("Workspace refreshed.");
  } catch (error) {
    message(error.message);
  }
};
$("#more").onclick = async () => {
  const button = $("#more");
  button.disabled = true;
  try {
    await load(true);
  } catch (error) {
    message(error.message);
  } finally {
    button.disabled = false;
  }
};
$("#new").onclick = () => $("#create-dialog").showModal();
$("#close-dialog").onclick = () => $("#create-dialog").close();
$("#create-form").onsubmit = async (event) => {
  event.preventDefault();
  const button = event.target.querySelector("button.primary");
  button.disabled = true;
  try {
    selected = await api("/api/incidents", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(event.target))),
    });
    $("#create-dialog").close();
    event.target.reset();
    renderDetail();
    await load();
    message("Incident opened. You are the owner.");
  } catch (error) {
    message(error.message);
  } finally {
    button.disabled = false;
  }
};
if (token)
  login().catch((error) => {
    sessionStorage.removeItem("shift-token");
    message(error.message);
  });

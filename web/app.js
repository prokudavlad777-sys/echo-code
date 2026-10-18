"use strict";
const $ = (id) => document.getElementById(id);
const state = { chatId: null, busy: false };

async function api(method, path, body) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

function renderText(container, text) {
  container.textContent = "";
  const parts = text.split(/```/);
  parts.forEach((part, i) => {
    if (i % 2 === 0) {
      if (part) container.appendChild(document.createTextNode(part.replace(/^\n+|\n+$/g, "")));
      return;
    }
    const nl = part.indexOf("\n");
    const lang = nl > -1 ? part.slice(0, nl).trim() : "";
    const code = nl > -1 ? part.slice(nl + 1) : part;
    const pre = document.createElement("pre");
    pre.className = "code";
    if (lang) { const l = document.createElement("span"); l.className = "lang"; l.textContent = lang; pre.appendChild(l); }
    const btn = document.createElement("button");
    btn.textContent = "Copy";
    btn.onclick = () => navigator.clipboard.writeText(code.replace(/\n$/, "")).then(() => (btn.textContent = "Copied"));
    pre.appendChild(btn);
    pre.appendChild(document.createTextNode(code.replace(/\n$/, "")));
    container.appendChild(pre);
  });
}

function addMessage(role, text, extraClass) {
  const box = $("messages");
  const empty = box.querySelector(".empty");
  if (empty) empty.remove();
  const el = document.createElement("div");
  el.className = "msg " + role + (extraClass ? " " + extraClass : "");
  renderText(el, text);
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
  return el;
}

function showEmpty() {
  $("messages").innerHTML = '<div class="empty"><h1>◈ Echo Code</h1><p>Ask for code, a fix, or an explanation.</p></div>';
}

async function loadChats() {
  const chats = await api("GET", "/chats");
  const ul = $("chats");
  ul.textContent = "";
  chats.forEach((c) => {
    const li = document.createElement("li");
    if (c.chat_id === state.chatId) li.className = "active";
    const t = document.createElement("span");
    t.className = "t"; t.textContent = c.title;
    const x = document.createElement("button");
    x.className = "x"; x.textContent = "×"; x.title = "Delete";
    x.onclick = async (e) => {
      e.stopPropagation();
      await api("DELETE", "/chats/" + c.chat_id);
      if (state.chatId === c.chat_id) { state.chatId = null; showEmpty(); }
      loadChats();
    };
    li.append(t, x);
    li.onclick = () => openChat(c.chat_id);
    ul.appendChild(li);
  });
}

async function openChat(id) {
  const chat = await api("GET", "/chats/" + id);
  state.chatId = id;
  $("messages").textContent = "";
  if (!chat.messages.length) showEmpty();
  chat.messages.forEach((m) => addMessage(m.role, m.content));
  loadChats();
}

async function send() {
  const input = $("input");
  const text = input.value.trim();
  if (!text || state.busy) return;
  state.busy = true; $("send").disabled = true;
  input.value = ""; input.style.height = "auto";
  try {
    if (!state.chatId) state.chatId = (await api("POST", "/chats", {})).id;
    addMessage("user", text);
    const typing = addMessage("assistant", "Echo is thinking…", "typing");
    try {
      const r = await api("POST", `/chats/${state.chatId}/messages`, { content: text });
      typing.remove();
      addMessage("assistant", r.reply);
    } catch (e) { typing.remove(); addMessage("assistant", "Error: " + e.message); }
    loadChats();
  } finally { state.busy = false; $("send").disabled = false; input.focus(); }
}

$("send").onclick = send;
$("new-chat").onclick = () => { state.chatId = null; showEmpty(); loadChats(); $("input").focus(); };
$("input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
$("input").addEventListener("input", (e) => { e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; });

api("GET", "/health").then((h) => ($("model").textContent = h.model)).catch(() => ($("model").textContent = "offline"));
showEmpty();
loadChats();

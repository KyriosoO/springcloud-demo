"use strict";
let token = location.hash.slice(1);
history.replaceState(null, "", "/");
let nonce = null, caseId = null, stopped = false, busy = false, polling = false, generation = 0;
const byId = id => document.getElementById(id);
const labels = {faithful: "忠于原文，没有误导", relevant: "与问题相关",
  sufficientForInitialAnswer: "足以形成初步回答，显式条件未遗漏", useful: "对理解问题有实际帮助"};
for (const [name, label] of Object.entries(labels)) {
  const field = document.createElement("fieldset"), legend = document.createElement("legend");
  legend.textContent = label; field.append(legend);
  for (const [value, text] of [["true", "是"], ["false", "否"]]) {
    const wrapper = document.createElement("label"), input = document.createElement("input");
    input.type = "radio"; input.name = name; input.value = value; input.required = true;
    wrapper.append(input, document.createTextNode(text)); field.append(wrapper);
  }
  byId("rubric").append(field);
}
function clearPacket() {
  for (const id of ["question", "answer", "points", "evidence", "case"]) byId(id).replaceChildren();
  byId("form").reset(); byId("review").hidden = true; nonce = caseId = null;
}
async function request(path, body) {
  const response = await fetch(path, {method: body === undefined ? "GET" : "POST", cache: "no-store",
    credentials: "omit", headers: {"X-Review-Token": token, ...(body === undefined ? {} : {"Content-Type": "application/json"})},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  if (!response.ok) throw new Error("评审请求未接受，请勿刷新或重复运行。");
  return response.json();
}
function textBlock(parent, text) {
  const node = document.createElement("pre"); node.textContent = text; parent.append(node);
}
async function poll() {
  if (stopped || busy || polling) return;
  polling = true; const currentGeneration = generation;
  try {
    const state = await request("/state");
    if (stopped || busy || generation !== currentGeneration) return;
    byId("ready").hidden = state.status !== "ready_required";
    if (state.status === "review" && state.nonce !== nonce) {
      clearPacket(); nonce = state.nonce; const item = state.packet; caseId = item.caseId;
      byId("case").textContent = caseId; byId("question").textContent = item.question;
      byId("answer").textContent = item.answerSummary;
      for (const point of item.points) textBlock(byId("points"), point.quote + "\n" + JSON.stringify(point.citation, null, 2));
      for (const evidence of item.evidence) {
        const details = document.createElement("details"), summary = document.createElement("summary");
        summary.textContent = [evidence.evidenceRef, evidence.title, evidence.documentNumber, evidence.writtenDate].filter(Boolean).join(" · ");
        details.append(summary); textBlock(details, evidence.content); byId("evidence").append(details);
      }
      byId("review").hidden = false;
    } else if (state.status !== "review") clearPacket();
    byId("status").textContent = ({ready_required: "尚未执行：请确认本人已准备好逐题评价。",
      waiting: "已就绪，等待本题真实回答。", review: "请阅读并评价当前题。任何不通过均会停止本批。", closed: "本批已停止。"})[state.status];
    if (state.status === "closed") {stopped = true; token = "";}
  } catch (error) {
    if (!stopped && !busy && generation === currentGeneration) {
      clearPacket(); stopped = true; token = ""; byId("status").textContent = error.message;
    }
  } finally {polling = false;}
}
byId("ready").onclick = async () => {
  busy = true; generation++; byId("ready").disabled = true;
  try {await request("/ready", {ready: true});}
  catch (error) {byId("status").textContent = error.message; stopped = true;}
  finally {busy = false; await poll();}
};
byId("form").onsubmit = async event => {
  event.preventDefault(); if (busy || !nonce) return;
  const data = new FormData(byId("form")), decision = {caseId, nonce, acknowledged: byId("ack").checked, reason: byId("reason").value};
  for (const name of Object.keys(labels)) decision[name] = data.get(name) === "true";
  if (Object.keys(labels).every(name => decision[name]) !== (decision.reason === "none")) {
    byId("status").textContent = "原因与四项评价不一致，请检查。"; return;
  }
  busy = true; generation++;
  try {await request("/decision", decision); clearPacket();}
  catch (error) {byId("status").textContent = error.message; stopped = true; clearPacket();}
  finally {busy = false; await poll();}
};
byId("close").onclick = async () => {
  busy = true; generation++;
  try {await request("/close", {close: true});} finally {
    stopped = true; token = ""; clearPacket(); byId("ready").hidden = true; byId("status").textContent = "本批已停止。";
  }
};
window.addEventListener("pagehide", () => {
  if (token && !stopped) fetch("/close", {method: "POST", keepalive: true, cache: "no-store", credentials: "omit",
    headers: {"X-Review-Token": token, "Content-Type": "application/json"}, body: '{"close":true}'}).catch(() => {});
  generation++; clearPacket(); token = ""; stopped = true;
});
if (!token) {stopped = true; byId("status").textContent = "缺少本次临时会话。请从受控执行器打开，不要手动刷新。";}
else {poll(); setInterval(poll, 1000);}

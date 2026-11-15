/* Replay autonome : les chiffres futurs ne sont jamais utilisés pour cadrer la courbe. */
(function (root) {
  "use strict";
  const MAX_ACTIONS = 32;
  const MAX_ADDITIONS = 10;
  const allowed = new Set(["reduire", "vendre", "renforcer"]);
  function validValues(values) {
    return Array.isArray(values) && values.length > 1 && values.every(v => Number.isFinite(v) && v > 0);
  }
  function validateActions(actions, values, cursor) {
    if (!Array.isArray(actions) || actions.length > MAX_ACTIONS) return false;
    let previous = -1, additions = 0, sold = false;
    for (const item of actions) {
      if (!item || !allowed.has(item.action) || !Number.isInteger(item.index) || item.index < previous || item.index < 0 || item.index > cursor || item.index >= values.length || sold) return false;
      if (item.action === "renforcer" && ++additions > MAX_ADDITIONS) return false;
      if (item.action === "vendre") sold = true;
      previous = item.index;
    }
    return true;
  }
  function positionValue(values, position) {
    const cursor = Math.max(0, Math.min(values.length - 1, position));
    const i = Math.floor(cursor), f = cursor - i;
    return values[i] + ((values[i + 1] || values[i]) - values[i]) * f;
  }
  function accountAt(values, actions, position) {
    let invested = 10000, cash = 0, contributions = 10000, previous = 0;
    for (const item of actions) {
      if (item.index > position) break;
      invested *= values[item.index] / values[previous];
      previous = item.index;
      if (item.action === "reduire") { cash += invested / 2; invested /= 2; }
      if (item.action === "vendre") { cash += invested; invested = 0; }
      if (item.action === "renforcer") { invested += 2000; contributions += 2000; }
    }
    invested *= positionValue(values, position) / values[previous];
    return { investi: invested, cash, apports: contributions, total: invested + cash };
  }
  function visibleSeries(values, position) {
    const index = Math.floor(Math.max(0, Math.min(values.length - 1, position)));
    const out = values.slice(0, index + 1).map((value, i) => ({ index: i, value }));
    if (position > index && index < values.length - 1) out.push({ index: position, value: positionValue(values, position) });
    return out;
  }
  const api = { validValues, validateActions, positionValue, accountAt, visibleSeries, MAX_ACTIONS, MAX_ADDITIONS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  const $ = id => document.getElementById(id);
  const send = (type, data) => root.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, data || {}), "*");
  const money = value => new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(value);
  const percent = value => new Intl.NumberFormat("fr-CA", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" }).format(value);
  const reducedMotion = root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let args = {}, model = null, ctx = null, previousFrame = null, lastPersisted = 0, lastAnnouncement = -1, lastDraw = 0, lastDispatched = -1;
  try { ctx = $("chart").getContext("2d"); } catch (_) { /* Dégradation explicite ci-dessous. */ }
  function frameHeight() { send("streamlit:setFrameHeight", { height: Math.ceil(document.body.scrollHeight) + 2 }); }
  function storageKey() { return "awsome-ai.replay." + args.session_id; }
  function save() {
    if (!model) return;
    try { root.sessionStorage.setItem(storageKey(), JSON.stringify(model)); } catch (_) { /* Mode privé : la session serveur conserve les décisions. */ }
  }
  function dispatch() {
    save();
    lastDispatched = model.seq;
    send("streamlit:setComponentValue", { value: { session_id: args.session_id, seq: model.seq, cursor: Math.floor(model.position), actions: model.actions, complete: model.complete }, dataType: "json" });
  }
  function restore(next) {
    const state = next.state || {};
    const serverActions = Array.isArray(state.actions) ? state.actions : [];
    const cursor = Math.max(0, Math.min(next.values.length - 1, Number(state.cursor) || 0));
    let candidate = null;
    try { candidate = JSON.parse(root.sessionStorage.getItem(storageKey())); } catch (_) { /* Fresh session. */ }
    if (candidate && candidate.seq >= (Number(next.ack) || 0) && Number.isFinite(candidate.position) && candidate.position >= cursor && candidate.position <= next.values.length - 1 && validateActions(candidate.actions, next.values, Math.floor(candidate.position))) {
      model = candidate;
    } else {
      model = { position: cursor, actions: serverActions, seq: Number(next.ack) || 0, started: cursor > 0 || serverActions.length > 0, paused: cursor > 0, complete: !!next.finished };
    }
    if (next.finished) model.complete = true;
    previousFrame = null;
  }
  function finish() {
    model.complete = true;
    model.paused = false;
    model.seq += 1;
    dispatch();
  }
  function act(action) {
    if (!model || !model.started || model.complete || model.actions.length >= MAX_ACTIONS) return;
    const index = Math.floor(model.position);
    const next = model.actions.concat([{ index, action }]);
    if (!validateActions(next, args.values, index) || accountAt(args.values, model.actions, index).investi <= 0) return;
    // Les décisions sont prises au dernier cours quotidien effectivement révélé, jamais au prochain cours.
    model.position = index;
    model.actions = next;
    model.seq += 1;
    const labels = { reduire: "La moitié de votre placement est passée en liquidités.", vendre: "Votre placement est passé en liquidités. Le replay est terminé.", renforcer: "Vous avez ajouté 2 000 $ fictifs à votre placement." };
    $("event").textContent = labels[action];
    if (action === "vendre") model.complete = true;
    dispatch();
    update();
  }
  function draw() {
    if (!ctx || !model) return;
    const canvas = $("chart"), rect = canvas.getBoundingClientRect(), ratio = Math.min(root.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(rect.width * ratio) || canvas.height !== Math.round(rect.height * ratio)) { canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio); }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const w = rect.width, h = rect.height, left = 14, right = w < 460 ? 55 : 67, top = 22, bottom = 31, cw = w - left - right, ch = h - top - bottom;
    ctx.clearRect(0, 0, w, h);
    const series = visibleSeries(args.values, model.position), numbers = series.map(p => p.value);
    // Uniquement l'historique déjà affiché, afin que les axes ne dévoilent aucun creux futur.
    const low = Math.min(10000, ...numbers), high = Math.max(10000, ...numbers), span = Math.max(high - low, 800), min = low - span * .15, max = high + span * .2;
    const X = i => left + cw * (i / Math.max(args.values.length - 1, 1));
    const Y = value => top + ch - (value - min) / (max - min) * ch;
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    for (let tick = 0; tick <= 3; tick++) {
      const value = min + (max - min) * tick / 3, y = Y(value);
      ctx.beginPath(); ctx.strokeStyle = "#edf0e9"; ctx.lineWidth = 1; ctx.moveTo(left, y); ctx.lineTo(w - right, y); ctx.stroke();
      ctx.fillStyle = "#86928b"; ctx.fillText(new Intl.NumberFormat("fr-CA", { maximumFractionDigits: 0 }).format(value), w - right + 9, y);
    }
    ctx.beginPath(); ctx.setLineDash([4, 5]); ctx.strokeStyle = "#b7c4b6"; ctx.moveTo(left, Y(10000)); ctx.lineTo(w - right, Y(10000)); ctx.stroke(); ctx.setLineDash([]);
    const gradient = ctx.createLinearGradient(0, top, 0, h - bottom); gradient.addColorStop(0, "#d7e7d7aa"); gradient.addColorStop(1, "#eff5eb05");
    ctx.beginPath(); ctx.moveTo(X(0), h - bottom); for (const p of series) ctx.lineTo(X(p.index), Y(p.value)); ctx.lineTo(X(model.position), h - bottom); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
    ctx.beginPath(); for (let i = 0; i < series.length; i++) { const p = series[i]; if (i === 0) ctx.moveTo(X(p.index), Y(p.value)); else ctx.lineTo(X(p.index), Y(p.value)); }
    ctx.strokeStyle = "#235d50"; ctx.lineWidth = 2.25; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.stroke();
    const end = series[series.length - 1];
    ctx.beginPath(); ctx.fillStyle = "#235d50"; ctx.arc(X(end.index), Y(end.value), 3.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#86928b"; ctx.textBaseline = "bottom"; ctx.fillText("Départ", left, h - 5);
    const finalMonth = args.month_positions && args.month_positions.length ? args.month_positions[args.month_positions.length - 1] : 12;
    for (let step = 1; step <= 4; step++) {
      const x = left + cw * step / 4; ctx.textAlign = step === 4 ? "right" : "center";
      ctx.fillText("M" + Math.round(finalMonth * step / 4), x, h - 5);
    }
  }
  function currentMonth() {
    if (Array.isArray(args.month_positions) && args.month_positions.length === args.values.length) return positionValue(args.month_positions, model.position);
    return model.position / (args.values.length - 1) * 12;
  }
  function update() {
    if (!model) return;
    // La courbe s'interpole entre les séances ; les chiffres et les interventions utilisent
    // le dernier cours quotidien atteint, exactement comme la comptabilité du serveur.
    const cursor = Math.floor(model.position);
    const account = accountAt(args.values, model.actions, cursor), variation = args.values[cursor] / args.values[0] - 1;
    $("total").textContent = money(account.total); $("net").textContent = "Capital versé : " + money(account.apports);
    $("cash").textContent = money(account.cash); $("variation").textContent = percent(variation); $("variation").className = "value " + (variation < 0 ? "loss" : "gain");
    $("time").textContent = model.started ? "Mois " + Math.min(99, Math.floor(currentMonth())) + " de la simulation" : "Départ de la simulation";
    $("progress").style.width = (model.position / (args.values.length - 1) * 100) + "%";
    $("status").textContent = model.complete ? "Replay terminé" : model.paused ? "En pause" : model.started ? "Le marché évolue" : "Prêt à démarrer";
    $("play").textContent = model.complete ? "Replay terminé" : !model.started ? "Lancer le replay" : model.paused ? "Reprendre" : "Pause";
    $("play").disabled = model.complete;
    const disabled = !model.started || model.complete || account.investi <= 0 || model.actions.length >= MAX_ACTIONS;
    $("reduce").disabled = disabled; $("sell").disabled = disabled;
    $("add").disabled = disabled || model.actions.filter(a => a.action === "renforcer").length >= MAX_ADDITIONS;
    if (model.complete) { $("prompt").textContent = "Votre expérience est terminée. Vos décisions sont enregistrées ; découvrez la période et son résultat juste en dessous."; }
    const bucket = Math.floor(currentMonth());
    if (model.started && bucket !== lastAnnouncement) { $("accessible").textContent = "Mois " + bucket + ". Marché : " + percent(variation) + ". Votre portefeuille : " + money(account.total) + "."; lastAnnouncement = bucket; }
    draw();
  }
  function animate(now) {
    if (model && model.started && !model.paused && !model.complete) {
      if (previousFrame !== null) {
        // Ne pas avancer de plusieurs mois si l'onglet est masqué ou le navigateur suspendu.
        const elapsed = Math.min(Math.max(0, now - previousFrame), 150);
        model.position = Math.min(args.values.length - 1, model.position + elapsed / Math.max(1000, Number(args.duration_ms) || 55000) * (args.values.length - 1));
        if (model.position >= args.values.length - 1) finish();
      }
      previousFrame = now;
      if (!reducedMotion || now - lastDraw >= 120) { update(); lastDraw = now; }
      if (now - lastPersisted >= 1000) { save(); lastPersisted = now; }
    } else previousFrame = null;
    root.requestAnimationFrame(animate);
  }
  $("play").addEventListener("click", () => {
    if (!model || model.complete || !ctx) return;
    if (!model.started) model.started = true;
    else model.paused = !model.paused;
    previousFrame = null;
    $("event").textContent = model.paused ? "Prenez votre temps. Vous pouvez intervenir ou reprendre le replay." : "Le replay continue tout seul. Intervenez seulement si vous le souhaitez.";
    save(); update();
  });
  $("reduce").addEventListener("click", () => act("reduire"));
  $("sell").addEventListener("click", () => act("vendre"));
  $("add").addEventListener("click", () => act("renforcer"));
  root.addEventListener("message", event => {
    if (event.source !== root.parent || !event.data || event.data.type !== "streamlit:render") return;
    const next = event.data.args || {};
    if (!next.session_id || !validValues(next.values)) { $("chart-message").hidden = false; $("chart-message").textContent = "Les données du replay sont indisponibles. Rechargez la page pour réessayer."; frameHeight(); return; }
    const changed = next.session_id !== args.session_id;
    args = next;
    if (changed || !model) restore(next);
    else if (Number(next.ack) > model.seq) restore(next);
    // Si l'iframe a été remontée entre l'action et son accusé de réception, renvoyer
    // une seule fois le journal cumulatif conservé localement.
    if (model.seq > (Number(next.ack) || 0) && model.seq !== lastDispatched) dispatch();
    if (!ctx) { $("chart-message").hidden = false; $("chart-message").textContent = "Ce navigateur ne peut pas afficher le graphique. Ouvrez la page dans un navigateur récent pour lancer l'expérience."; $("play").disabled = true; }
    else { $("chart-message").hidden = true; update(); }
    frameHeight();
  });
  if (root.ResizeObserver) new root.ResizeObserver(() => { draw(); frameHeight(); }).observe(document.body);
  root.addEventListener("pagehide", save);
  document.addEventListener("visibilitychange", () => { if (document.hidden && model && model.started && !model.complete) { model.paused = true; previousFrame = null; save(); update(); } });
  send("streamlit:componentReady", { apiVersion: 1 });
  frameHeight();
  root.requestAnimationFrame(animate);
})(typeof window === "undefined" ? globalThis : window);

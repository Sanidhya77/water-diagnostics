"use strict";

const $ = (id) => document.getElementById(id);
const names = {
  check_freshness: "Timestamp freshness", check_variation: "Signal variation",
  check_device_status: "Device status", check_maintenance_context: "Maintenance context",
  check_related_measurements: "Related measurements"
};
const causeNames = {
  sensor_artifact_possible: "Possible sensor artifact", river_change_possible: "Possible river change",
  maintenance_association: "Cleaning association", data_availability_issue: "Data availability",
  sensor_problem: "Possible sensor problem", process_change: "Possible process change",
  communication_loss: "Possible communication loss", maintenance_disturbance: "Maintenance disturbance",
  normal_behaviour: "Current readings within the demo limits", insufficient_evidence: "Unresolved origin"
};
const state = {source: "river", case: "frozen", dataset: "udall-2024-04-01", publicDemo: false, at: "2024-04-03T00:00:00Z", busy: false,
  loading: false, guidanceBusy: false, recoveryBusy: false, chartHours: 6, generation: 0, replay: null, report: null,
  displayMode: null, signal: null, playback: null, completedTools: new Set(), evidence: new Map(), selectedTool: null};
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};
const icon = (name) => {
  const element = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  element.setAttribute("class", "icon"); element.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + name); element.appendChild(use); return element;
};
const choice = (mode = "offline") => ({source: state.source, case: state.case, dataset: state.dataset, at: state.at, mode});
const query = (mode) => new URLSearchParams(choice(mode)).toString();

async function request(path, options = {}) {
  const response = await fetch(path, {cache: "no-store", ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The local request could not finish.");
  return data;
}
function message(text, error = false) {
  $("message").hidden = !text;
  $("message").textContent = text;
  $("message").className = "message" + (error ? " error" : "");
}
function lockControls() {
  const disabled = state.busy || state.loading || state.guidanceBusy || state.recoveryBusy;
  for (const id of ["run-local", "river-tab", "simulation-tab", "before-visit", "after-visit", "update-replay", "replay-clock", "scenario", "river-period"]) $(id).disabled = disabled;
  $("run-ai").disabled = disabled || state.publicDemo;
  $("lookup-guidance").disabled = disabled || state.publicDemo;
  $("run-recovery").disabled = disabled;
  $("recovery-case").disabled = disabled;
  $("play-signal").disabled = disabled || !state.signal || state.signal.points.length < 2;
  $("signal-scrubber").disabled = disabled || !state.signal;
  document.body.classList.toggle("investigation-running", state.busy);
  $("run-local").firstChild.textContent = state.busy ? "Investigation running… " : "Run local checks ";
}

function playbackButton() {
  const button = $("play-signal");
  button.replaceChildren(icon(state.playback ? "pause" : reducedMotion.matches ? "arrow" : "play"),
    node("span", state.playback ? "Pause" : reducedMotion.matches ? "Next sample" : "Play signal"));
  if (reducedMotion.matches) button.removeAttribute("aria-pressed");
  else button.setAttribute("aria-pressed", String(Boolean(state.playback)));
}
function stopPlayback() {
  if (state.playback) {
    cancelAnimationFrame(state.playback.frame);
    state.playback = null;
    $("playback-state").textContent = "Paused";
  }
  playbackButton();
}
function selectSample(index, reveal = false, cursor = null) {
  const signal = state.signal;
  if (!signal) return;
  const point = signal.points[index];
  if (signal.index !== index) {
    signal.index = index;
    $("sample-value").textContent = Number.isFinite(point.value) ? point.value.toFixed(3) : "—";
    $("sample-time").textContent = signal.dateText(point.time) + " " + signal.timeText(point.time) + " UTC";
    $("sample-time").dateTime = new Date(point.time).toISOString();
    $("sample-position").textContent = `Sample ${index + 1} of ${signal.points.length}` + (Number.isFinite(point.value) ? "" : " · missing value");
    $("signal-scrubber").value = index;
    $("signal-scrubber").setAttribute("aria-valuetext", $("sample-time").textContent + ", " + (Number.isFinite(point.value) ? point.value.toFixed(3) + " NTU" : "missing value"));
  }
  const position = cursor ?? signal.x(point.time);
  signal.clip.setAttribute("width", reveal ? Math.max(0, position - signal.left) : signal.right - signal.left);
  signal.cursor.setAttribute("x1", position); signal.cursor.setAttribute("x2", position);
  signal.cursor.setAttribute("visibility", "visible");
  signal.dot.setAttribute("visibility", Number.isFinite(point.value) ? "visible" : "hidden");
  if (Number.isFinite(point.value)) {
    signal.dot.setAttribute("cx", signal.x(point.time)); signal.dot.setAttribute("cy", signal.y(point.value));
  }
}
function playSignal() {
  if (!state.signal || state.busy || state.loading || state.guidanceBusy) return;
  if (state.playback) { stopPlayback(); return; }
  const signal = state.signal, final = signal.points.length - 1;
  if (reducedMotion.matches) {
    selectSample(signal.index >= final ? 0 : signal.index + 1);
    $("playback-state").textContent = "Inspecting";
    return;
  }
  const start = signal.index >= final ? 0 : signal.index;
  const startTime = signal.points[start].time, endTime = signal.points[final].time;
  const duration = Math.min(8000, Math.max(2400, (final - start) * 90));
  const playback = {frame: 0, started: performance.now()};
  state.playback = playback;
  selectSample(start, true); playbackButton();
  $("playback-state").textContent = "Playing chart";
  const tick = (now) => {
    if (state.playback !== playback) return;
    const fraction = Math.min(1, (now - playback.started) / duration);
    const time = startTime + fraction * (endTime - startTime);
    let index = signal.index;
    while (index < final && signal.points[index + 1].time <= time) index++;
    // The mask follows elapsed chart time; every displayed measurement comes
    // from an original sample. No interpolated numeric values are created.
    selectSample(index, true, signal.x(time));
    if (fraction < 1) playback.frame = requestAnimationFrame(tick);
    else {
      state.playback = null; selectSample(final); playbackButton();
      $("playback-state").textContent = "Full window";
    }
  };
  playback.frame = requestAnimationFrame(tick);
}
function svgElement(tag, attributes, parent, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  parent.appendChild(element);
  return element;
}
function drawChart(data) {
  stopPlayback(); state.signal = null;
  const root = $("chart");
  root.replaceChildren();
  const width = Math.max(root.clientWidth, 240), height = root.clientHeight;
  const left = 40, top = 22, right = width - 10, bottom = height - 45;
  const observed = new Date(data.summary.clock).getTime();
  const points = data.points.map((p) => ({time: new Date(p.time).getTime(), value: p.value}))
    .filter((p) => state.source !== "river" || p.time >= observed - state.chartHours * 3600000);
  const valid = points.filter((p) => typeof p.value === "number" && Number.isFinite(p.value));
  const missingCount = points.filter((p) => p.value === null).length;
  $("signal-availability").textContent = state.source === "river"
    ? `${valid.length} numeric ${valid.length === 1 ? "value" : "values"} · ${missingCount} missing ${missingCount === 1 ? "entry" : "entries"} in this chart window`
    : `${valid.length} simulated ${valid.length === 1 ? "value" : "values"} in this chart window`;
  $("signal-availability").classList.toggle("has-gaps", missingCount > 0);
  if (!valid.length) {
    root.appendChild(node("p", "No usable observations in this window. Choose a wider window or inspect the freshness check.", "empty-state"));
    $("chart-range").textContent="No usable observations"; $("sample-value").textContent="—";
    $("sample-time").textContent="No recorded sample"; $("sample-position").textContent="Choose another window";
    $("playback-state").textContent="Unavailable"; lockControls(); return;
  }
  const first = points[0].time;
  const last = Math.max(new Date(data.summary.clock).getTime(), points.at(-1).time, first + 60000);
  const maximum = Math.max(...valid.map((p) => p.value), data.summary.threshold || 0, 0.01) * 1.16;
  const x = (time) => left + (time - first) / (last - first) * (right - left);
  const y = (value) => bottom - value / maximum * (bottom - top);
  const svg = svgElement("svg", {viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Original turbidity measurements up to the selected replay clock"}, root);
  const defs = svgElement("defs", {}, svg);
  const clipPath = svgElement("clipPath", {id:"signal-window",clipPathUnits:"userSpaceOnUse"}, defs);
  const clip = svgElement("rect", {x:left-3,y:0,width:right-left+6,height}, clipPath);
  const pattern = svgElement("pattern", {id:"missing-values",width:8,height:8,patternUnits:"userSpaceOnUse"}, defs);
  svgElement("path", {d:"M -2 2 L 2 -2 M 0 8 L 8 0 M 6 10 L 10 6",class:"gap-hatch"}, pattern);
  let gap = [];
  const paintGap = () => {
    if (!gap.length) return;
    const halfInterval = data.summary.interval_seconds * 500;
    const start = Math.max(left, x(gap[0].time - halfInterval));
    const end = Math.min(right, x(gap.at(-1).time + halfInterval));
    const group = svgElement("g", {class:"chart-gap","aria-label":`${gap.length} missing original entries`}, svg);
    svgElement("rect", {x:start,y:top,width:Math.max(0,end-start),height:bottom-top,fill:"url(#missing-values)"}, group);
    if (end - start > 100) {
      svgElement("text", {x:(start+end)/2,y:top+(bottom-top)/2-10,"text-anchor":"middle",class:"gap-label"}, group, `${gap.length} missing ${width < 500 ? "entries" : "original entries"}`);
      if (width >= 500) svgElement("text", {x:(start+end)/2,y:top+(bottom-top)/2+12,"text-anchor":"middle",class:"gap-caption"}, group, "No values filled or inferred");
    }
    gap = [];
  };
  for (const point of points) {
    if (point.value === null) gap.push(point); else paintGap();
  }
  paintGap();
  for (let i = 0; i <= 4; i++) {
    const value = maximum * i / 4;
    svgElement("line", {x1: left, y1: y(value), x2: right, y2: y(value), class: "chart-grid"}, svg);
    svgElement("text", {x: left - 10, y: y(value) + 3, "text-anchor": "end", class: "chart-axis"}, svg, value < 1 ? value.toFixed(2) : value.toFixed(1));
  }
  const timeText = (time) => new Date(time).toLocaleTimeString("en-GB", {timeZone: "UTC", hour: "2-digit", minute: "2-digit"});
  const dateText = (time) => new Date(time).toLocaleDateString("en-GB", {timeZone: "UTC", day: "2-digit", month: "short"});
  for (let i = 0; i <= 4; i++) {
    const time = first + (last - first) * i / 4;
    const anchor = i === 0 ? "start" : i === 4 ? "end" : "middle";
    svgElement("text", {x: x(time), y: bottom + 18, "text-anchor": anchor, class: "chart-axis"}, svg, timeText(time));
    if (last - first > 86400000) svgElement("text", {x: x(time), y: bottom + 31, "text-anchor": anchor, class: "chart-axis"}, svg, dateText(time));
  }
  let run = [];
  const plot = svgElement("g", {"clip-path":"url(#signal-window)"}, svg);
  const paint = () => {
    if (!run.length) return;
    const path = "M " + run.map((p) => `${x(p.time)} ${y(p.value)}`).join(" L ");
    svgElement("path", {d: `M ${x(run[0].time)} ${bottom} L ${path.slice(2)} L ${x(run.at(-1).time)} ${bottom} Z`, class: "chart-area"}, plot);
    svgElement("path", {d: path, class: "chart-line"}, plot);
    run = [];
  };
  for (const point of points) {
    if (point.value === null || !Number.isFinite(point.value)) paint();
    else {
      if (run.length && point.time - run.at(-1).time > data.summary.interval_seconds * 1000) paint();
      run.push(point);
    }
  }
  paint();
  if (data.summary.threshold !== null) {
    svgElement("line", {x1: left, x2: right, y1: y(data.summary.threshold), y2: y(data.summary.threshold), class: "chart-threshold"}, svg);
    svgElement("text", {x: right, y: y(data.summary.threshold) - 6, "text-anchor": "end", class: "chart-event-label"}, svg, "Demo threshold · " + data.summary.threshold + " NTU");
  }
  for (const event of data.events) {
    const time = new Date(event.time).getTime();
    if (time < first || time > last) continue;
    svgElement("line", {x1: x(time), x2: x(time), y1: top, y2: bottom, class: "chart-event"}, svg);
    const nearStart = x(time) < (left + right) / 2;
    const eventLabel = svgElement("text", {x: x(time) + (nearStart ? 7 : -7), y: top - 8, "text-anchor": nearStart ? "start" : "end", class: "chart-event-label"}, svg, width < 500 ? "Recorded visit" : event.label);
    svgElement("title", {}, eventLabel, event.label);
  }
  const hover = svgElement("circle", {r: 4, fill: "#d7e6d9", stroke: "#173b33", "stroke-width": 2, visibility: "hidden"}, svg);
  const crosshair = svgElement("line", {y1:top,y2:bottom,class:"chart-crosshair",visibility:"hidden"}, svg);
  const range = `${dateText(first)} ${timeText(first)} — ${dateText(last)} ${timeText(last)}`;
  $("chart-range").textContent = range;
  state.signal = {points,index:-1,x,y,left:left-3,right:right+3,clip,cursor:crosshair,dot:hover,dateText,timeText};
  $("signal-scrubber").max = points.length - 1;
  $("playback-state").textContent="Full window";
  selectSample(points.length - 1); lockControls();
  svg.addEventListener("pointermove", (event) => {
    if (state.playback || event.pointerType === "touch") return;
    const pixel = (event.clientX - svg.getBoundingClientRect().left) / svg.getBoundingClientRect().width * width;
    const point = valid.reduce((a, b) => Math.abs(x(a.time) - pixel) < Math.abs(x(b.time) - pixel) ? a : b);
    selectSample(points.indexOf(point)); $("playback-state").textContent="Inspecting";
  });
}

function openEvidence(name, scroll = false) {
  const result = state.evidence.get(name);
  if (!result) return;
  state.selectedTool = name;
  const inspector = $("evidence-inspector");
  inspector.hidden = false; inspector.open = true;
  $("evidence-inspector-title").textContent = names[name] + " · " + result.evidence_id;
  $("evidence-inspector-data").textContent = result.data
    ? JSON.stringify(result.data, null, 2)
    : "This check was performed. Its full evidence will appear when the report returns.";
  for (const button of $("check-list").querySelectorAll("button")) {
    const selected = button.dataset.tool === name;
    button.classList.toggle("selected",selected); button.setAttribute("aria-pressed",String(selected));
  }
  if (scroll) inspector.scrollIntoView({behavior:reducedMotion.matches ? "instant" : "smooth",block:"center"});
}
function renderTrace(observations = [], events = []) {
  const list = $("check-list"); list.replaceChildren();
  const byTool = new Map(observations.map((e) => [e.tool, e]));
  for (const event of events) {
    const match = event.match(/^([ER]\d+): (check_[a-z_]+) performed/);
    if (match && !byTool.has(match[2])) byTool.set(match[2], {evidence_id: match[1], data: null});
  }
  state.evidence = byTool;
  const order = [...new Set([...byTool.keys(), ...Object.keys(names)])].filter((name) => Object.hasOwn(names, name));
  order.forEach((name, index) => {
    const label = names[name];
    const item = node("li"); const result = byTool.get(name);
    const circle = node("span", result ? undefined : String(index + 1).padStart(2, "0"), "check-circle" + (result ? " done" : ""));
    if (result) {
      circle.appendChild(icon("check"));
      if (state.busy && !state.completedTools.has(name)) circle.classList.add("just-finished");
    }
    const button = node("button",undefined,"check-rail-button");
    button.dataset.tool=name; button.disabled=!result;
    button.setAttribute("aria-controls","evidence-inspector");
    button.setAttribute("aria-pressed",String(name===state.selectedTool));
    button.classList.toggle("selected",name===state.selectedTool);
    button.appendChild(circle);
    const text = node("span"); text.appendChild(node("strong",label));
    text.appendChild(node("span",result ? "Performed · " + result.evidence_id : "Ready to check","check-subtitle"));
    button.appendChild(text); button.addEventListener("click",()=>openEvidence(name));
    item.appendChild(button); list.appendChild(item);
  });
  $("trace-count").textContent = byTool.size + " / 5";
  let progress = $("check-progress");
  if (!progress) {
    progress = node("progress"); progress.id="check-progress"; progress.max=5;
    progress.setAttribute("aria-label","Executed diagnostic checks"); list.before(progress);
  }
  progress.value=byTool.size;
  state.completedTools = new Set(byTool.keys());
  if (state.selectedTool && byTool.has(state.selectedTool) && $("evidence-inspector").open) openEvidence(state.selectedTool);
  if (!byTool.size) { state.selectedTool=null; $("evidence-inspector").hidden=true; $("evidence-inspector").open=false; }
}

function renderReport(report, saved = false) {
  state.report = report;
  const content = $("report-content"); content.replaceChildren();
  $("download-report").hidden = !report;
  if (!report) {
    $("report-title").textContent = state.busy ? "Following the evidence…" : "Choose your next check.";
    $("report-provenance").textContent = state.busy ? "Only executed checks will appear in the report." : "Run local checks for a free reference investigation.";
    $("brief-title").textContent = state.busy ? "Investigation in progress" : "Ready to investigate";
    $("brief-provenance").textContent = state.busy ? "The report will use only executed checks." : "No investigation is available at this replay clock.";
    $("brief-next-label").textContent = state.busy ? "Following the evidence" : "Get started";
    $("brief-next").textContent = state.busy ? "Review the checks as their results arrive in the evidence workbench." : "Run the local checks or ask Nemotron to investigate this replay.";
    content.appendChild(node("p", "The report will connect each possible explanation to the checks actually performed.", "empty-state"));
    $("execution-log").textContent = "No investigation is available for this replay yet.";
    $("run-status").textContent = "Ready to investigate";
    $("run-status").className = "run-status";
    renderTrace(); return;
  }
  const ai = report.mode === "nebius_model";
  state.displayMode = ai ? "nebius" : "offline";
  $("download-report").href = "/api/download?" + query(state.displayMode);
  $("report-provenance").textContent = saved
    ? (ai ? "Saved Nemotron investigation · No new API request." : "Saved local reference · No model called.")
    : (ai ? "NVIDIA Nemotron · Investigated through the Nebius API." : "Local reference investigation · No model called.");
  const titles = {sensor_problem: "Evidence suggests a sensor problem.", normal_behaviour: "Review the earlier excursion.", process_change: "Corroborating process evidence.", communication_loss: "A gap in received telemetry.", maintenance_disturbance: "Review the maintenance timing."};
  const dataGap = report.hypotheses.some(item => item.name === "data_availability_issue");
  $("report-title").textContent = report.status === "incomplete" ? "Investigation stopped early." : (dataGap ? "Missing data needs operator review." : (titles[report.conclusion] || "The cause remains unresolved."));
  $("brief-title").textContent = $("report-title").textContent;
  $("brief-provenance").textContent = $("report-provenance").textContent;
  $("brief-next-label").textContent = "Next operator action · requested";
  $("brief-next").textContent = report.actions[0] || "Review the report's uncertainty before assigning a physical cause.";
  const status = node("div", undefined, "report-status");
  status.appendChild(node("span", report.status === "complete" ? "Investigation complete" : "Incomplete", "complete-label" + (report.status === "incomplete" ? " incomplete" : "")));
  status.appendChild(node("span", report.conclusion === "insufficient_evidence" ? "More evidence is needed to establish a cause." : "Operator confirmation is still required."));
  content.appendChild(status);
  for (const hypothesis of report.hypotheses) {
    const item = node("article", undefined, "hypothesis");
    const heading = node("div", undefined, "hypothesis-heading");
    heading.appendChild(node("h4", causeNames[hypothesis.name] || hypothesis.name));
    const tags = node("span", undefined, "evidence-tags");
    for (const id of hypothesis.support) {
      const tag = node("button", id, "evidence-tag");
      tag.setAttribute("aria-label", "Inspect evidence " + id);
      tag.addEventListener("click", () => {
        const evidence = report.observations.find((e) => e.evidence_id === id);
        if (evidence) openEvidence(evidence.tool,true);
      });
      tags.appendChild(tag);
    }
    heading.appendChild(tags); item.appendChild(heading);
    item.appendChild(node("p", hypothesis.text));
    if (hypothesis.conflict.length) item.appendChild(node("div", "Conflicting evidence: " + hypothesis.conflict.join(", "), "conflict-note"));
    content.appendChild(item);
  }
  content.appendChild(node("h4", "Next operator actions · requested, not performed", "action-heading"));
  for (const action of report.actions) {
    const item = node("div", undefined, "action-item"); item.appendChild(icon("arrow"));
    item.appendChild(node("span", action)); content.appendChild(item);
  }
  const details = node("details", undefined, "uncertainty");
  details.appendChild(node("summary", "Uncertainty and operating boundaries"));
  const list = node("ul");
  for (const text of [...report.uncertainty, ...report.boundaries]) list.appendChild(node("li", text));
  details.appendChild(list); content.appendChild(details);
  renderTrace(report.observations);
  $("run-status").textContent = saved ? "Saved investigation loaded · no credits used" : (report.status === "complete" ? "All five checks completed" : "Stopped · see report uncertainty");
  $("run-status").className = "run-status";
  $("execution-log").textContent = report.attempts.map((a) => `${a.evidence_id || "—"} ${names[a.tool] || a.tool}: ${a.status}${a.reason ? " · " + a.reason : ""}`).join("\n");
  if (!saved && !reducedMotion.matches) content.animate([{opacity:.45},{opacity:1}],{duration:200,easing:"ease-out"});
}

async function loadReplay() {
  stopPlayback();
  const generation = ++state.generation;
  state.loading = true; lockControls(); message("");
  try {
    const data = await request("/api/replay?" + query());
    if (generation !== state.generation) return;
    state.replay = data;
    state.publicDemo = Boolean(data.capabilities?.public_demo);
    document.body.classList.toggle("public-demo", state.publicDemo);
    $("deployment-note").hidden = !state.publicDemo;
    $("ai-run-note").textContent = state.publicDemo ? "Fresh API calls: use the local build" : "Uses credits · $0.02 guard";
    $("run-local").classList.toggle("primary", state.publicDemo);
    $("run-local").classList.toggle("secondary", !state.publicDemo);
    $("run-ai").classList.toggle("primary", !state.publicDemo);
    $("run-ai").classList.toggle("secondary", state.publicDemo);
    const summary = data.summary;
    $("source-badge").textContent = summary.source_label;
    $("source-badge").className = "source-badge" + (state.source === "simulated" ? " simulated" : "");
    $("site-name").textContent = summary.site;
    $("data-note").textContent = state.source === "river" ? "Original observations · 15-minute samples" : "Simulated observations · demo thresholds only";
    $("latest-value").textContent = summary.latest === null ? "—" : summary.latest.toFixed(3);
    $("freshness-badge").textContent = summary.fresh ? "Fresh" : "Stale / missing";
    $("freshness-badge").className = "pill" + (summary.fresh ? "" : " stale");
    $("device-value").textContent = summary.device_available ? "Recorded status" : "Not supplied";
    $("visit-value").textContent = summary.visits + " visible";
    $("reference-value").textContent = summary.independent ? "Recorded signal" : "Not supplied";
    $("reference-value").className = "metric-value" + (summary.independent ? "" : " missing");
    $("chart-caption").textContent = state.source === "river" ? "Original readings available at the replay clock" : "Simulated filter outlet · demonstration settings";
    $("chart-windows").hidden = state.source !== "river";
    $("confirmation-note").textContent = state.source === "river" ? "A time-matched independent measurement helps distinguish a sensor artifact from a change in the river." : "Review the recorded device status and an independent outlet measurement before assigning a physical cause.";
    drawChart(data); renderReport(data.report, true); renderGuidance(data.guidance);
    if (!data.report) $("run-status").textContent = "Ready to investigate";
  } catch (error) { message(error.message, true); }
  finally { if (generation === state.generation) { state.loading = false; lockControls(); } }
}

async function runInvestigation(mode) {
  if (state.busy || state.loading || state.recoveryBusy) return;
  stopPlayback(); state.busy = true; lockControls(); message(""); renderReport(null);
  $("run-status").textContent = mode === "nebius" ? "Nemotron is selecting the first check…" : "Running free local checks…";
  $("run-status").className = "run-status running";
  $("execution-log").textContent = "Investigation started.";
  try {
    const started = await request("/api/investigate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(choice(mode))});
    while (true) {
      const job = await request("/api/job?id=" + encodeURIComponent(started.id));
      renderTrace([], job.events);
      $("execution-log").textContent = job.events.join("\n") || "Waiting for the first tool selection…";
      $("run-status").textContent = job.events.at(-1)?.includes("Submitting") ? "Preparing the evidence-based report…" : "Investigation in progress…";
      if (job.status === "failed") throw new Error(job.error);
      if (job.status === "finished") {
        renderReport(job.result);
        message(job.result.status === "complete" ? (mode === "offline" ? "Local investigation complete. No API credits were used." : "Nemotron investigation complete. Review the evidence and remaining uncertainty.") : "The investigation is incomplete. Completed checks were preserved; see the report for the stopping reason.", job.result.status !== "complete");
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
  } catch (error) { message(error.message, true); $("run-status").textContent = "Investigation could not finish"; }
  finally { state.busy = false; lockControls(); }
}

function sourceTab(source) {
  if (state.busy || state.loading || state.recoveryBusy) return;
  state.source = source;
  $("river-controls").hidden = source !== "river"; $("simulation-controls").hidden = source !== "simulated";
  $("recovery-demo").hidden = source !== "simulated";
  $("river-tab").classList.toggle("selected", source === "river"); $("simulation-tab").classList.toggle("selected", source === "simulated");
  $("river-tab").setAttribute("aria-pressed", String(source === "river")); $("simulation-tab").setAttribute("aria-pressed", String(source === "simulated"));
  loadReplay();
}
function preset(at, before) {
  state.at = at;
  $("replay-clock").value = at.slice(0, 16);
  $("before-visit").classList.toggle("selected", before); $("after-visit").classList.toggle("selected", !before);
  loadReplay();
}
$("river-tab").addEventListener("click", () => sourceTab("river"));
$("simulation-tab").addEventListener("click", () => sourceTab("simulated"));
$("before-visit").addEventListener("click", () => preset(state.replay.river_replays[state.dataset].before, true));
$("after-visit").addEventListener("click", () => preset(state.replay.river_replays[state.dataset].after, false));
$("river-period").addEventListener("change", () => {
  state.dataset = $("river-period").value;
  const period = state.replay.river_replays[state.dataset];
  $("replay-clock").min = period.min; $("replay-clock").max = period.max;
  $("before-visit").textContent = period.before_label; $("after-visit").textContent = period.after_label;
  state.chartHours = period.hours;
  for (const button of $("chart-windows").querySelectorAll("button")) {
    const selected = Number(button.dataset.hours) === state.chartHours;
    button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", String(selected));
  }
  preset(period.after, false);
});
$("update-replay").addEventListener("click", () => {
  if (!$("replay-clock").reportValidity()) return;
  const clock = $("replay-clock").value;
  state.at = clock + (clock.length === 16 ? ":00Z" : "Z");
  $("before-visit").classList.remove("selected"); $("after-visit").classList.remove("selected");
  loadReplay();
});
$("scenario").addEventListener("change", () => { state.case = $("scenario").value; loadReplay(); });
$("run-local").addEventListener("click", () => runInvestigation("offline"));
$("run-ai").addEventListener("click", () => runInvestigation("nebius"));

function resetRecovery() {
  $("recovery-result").hidden = true;
  $("recovery-download").hidden = true;
  $("recovery-status").textContent = "Choose a scenario to inspect its policy decision, action record and verification.";
  $("recovery-status").className = "recovery-status";
}
function renderRecovery(data) {
  const report = data.report;
  const restored = report.outcome === "telemetry_restored";
  $("recovery-outcome").textContent = restored ? "Telemetry restored and verified." : report.outcome === "approval_required" ? "Operator approval required." : "Escalation recorded for operator review.";
  $("recovery-provenance").textContent = report.diagnostic_origin === "saved_nebius_investigation"
    ? "Saved Nemotron diagnosis revalidated locally. Recovery selected by the local evidence policy."
    : report.diagnostic_origin === "not_run" ? "Safety gate stopped recovery before diagnostic work."
    : "Five free reference checks completed. Recovery selected by the local evidence policy; Nemotron was not called.";
  $("recovery-scope").textContent = restored
    ? "The connection recovered in this simulation. Turbidity readings remain elevated and require a separate investigation."
    : "Escalation is recorded locally; no notification was sent. The operator must review the unverified recovery.";
  $("recovery-policy").textContent = report.policy.verdict.replaceAll("_", " ");
  $("recovery-attempts").textContent = report.attempts + " / 1";
  $("recovery-packets").textContent = String(report.verification.new_valid_packets);
  $("recovery-events").replaceChildren(...report.events.map((event) => node("li", event)));
  $("recovery-data").textContent = JSON.stringify({before: report.before, after: report.after, verification: report.verification, escalation: report.escalation}, null, 2);
  $("recovery-status").textContent = restored ? "Simulation completed · telemetry verification passed" : "Simulation completed · operator review required";
  $("recovery-status").className = "recovery-status" + (restored ? " verified" : " escalated");
  $("recovery-result").hidden = false;
  $("recovery-download").href = data.download_url;
  $("recovery-download").hidden = false;
}
$("recovery-case").addEventListener("change", resetRecovery);
$("run-recovery").addEventListener("click", async () => {
  if (state.busy || state.loading || state.guidanceBusy || state.recoveryBusy) return;
  stopPlayback(); state.recoveryBusy = true; resetRecovery(); lockControls();
  $("recovery-demo").setAttribute("aria-busy", "true");
  $("recovery-status").textContent = "Running the local recovery policy and verification…";
  try {
    renderRecovery(await request("/api/recovery-demo", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({case:$("recovery-case").value})}));
  } catch (error) {
    $("recovery-status").textContent = error.message === "Page not found." ? "Restart the local dashboard server to load recovery simulation, then try again." : error.message;
    $("recovery-status").className = "recovery-status escalated";
  } finally {
    state.recoveryBusy = false; $("recovery-demo").setAttribute("aria-busy", "false"); lockControls();
  }
});
for (const button of $("chart-windows").querySelectorAll("button")) button.addEventListener("click", () => {
  state.chartHours = Number(button.dataset.hours);
  for (const item of $("chart-windows").querySelectorAll("button")) {
    const selected = item === button; item.classList.toggle("selected", selected); item.setAttribute("aria-pressed", String(selected));
  }
  if (state.replay) drawChart(state.replay);
});
function renderGuidance(result) {
  const target = $("guidance-results"); target.replaceChildren();
  $("reference-provider").textContent = result ? "Tavily sources" : "Public sources";
  $("lookup-guidance").hidden = Boolean(result);
  if (!result) { $("guidance-cost").textContent = state.publicDemo ? "Fresh reference lookup is available in the local build." : "On request only · 1 Tavily credit · cached for 24 hours"; return; }
  const time = new Date(result.retrieved_at).toLocaleString("en-GB", {timeZone:"UTC"});
  $("guidance-cost").textContent = (result.cached ? "Cached Tavily sources · no new credit used" : "Retrieved through Tavily · " + (result.reported_credits ?? "1 reserved") + " search credit") + " · " + time + " UTC";
  if (!result.documents.length) target.appendChild(node("p", "No allowlisted source was returned. The diagnostic conclusion is unchanged.", "empty-state"));
  for (const document of result.documents) {
    const item = node("article",undefined,"guidance-document"); item.appendChild(node("span",document.reference_id,"document-id"));
    const body = node("div"); const link = node("a",document.title);
    link.href = document.url; link.target="_blank"; link.rel="noopener noreferrer";
    body.appendChild(link); body.appendChild(node("small",document.domain));
    const excerpt = document.excerpt.length >= 300 ? document.excerpt.replace(/\s+\S*$/, "") + "…" : document.excerpt;
    body.appendChild(node("p",excerpt)); item.appendChild(body); target.appendChild(item);
  }
}
$("lookup-guidance").addEventListener("click", async () => {
  if (state.busy || state.loading || state.guidanceBusy || state.recoveryBusy) return;
  state.guidanceBusy = true; lockControls();
  $("guidance-results").replaceChildren(node("p","Looking up allowlisted monitoring references…","empty-state"));
  try {
    const result = await request("/api/guidance",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(choice())});
    renderGuidance(result);
  } catch (error) { $("guidance-results").replaceChildren(node("p",error.message,"empty-state")); }
  finally { state.guidanceBusy=false; lockControls(); }
});
let resizeTimer;
$("play-signal").addEventListener("click",playSignal);
$("signal-scrubber").addEventListener("input",()=>{
  stopPlayback(); selectSample(Number($("signal-scrubber").value));
  $("playback-state").textContent="Inspecting";
});
reducedMotion.addEventListener("change",()=>{ stopPlayback(); });
document.addEventListener("visibilitychange",()=>{ if (document.hidden) stopPlayback(); });
new IntersectionObserver((entries)=>{ if (!entries[0].isIntersecting) stopPlayback(); }).observe($("chart"));
for (const link of document.querySelectorAll(".app-nav a")) link.addEventListener("click",()=>{
  for (const item of document.querySelectorAll(".app-nav a")) {
    item.classList.toggle("active",item===link);
    if (item===link) item.setAttribute("aria-current","location"); else item.removeAttribute("aria-current");
  }
});
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state.replay) drawChart(state.replay); }, 120); });
renderTrace(); loadReplay();

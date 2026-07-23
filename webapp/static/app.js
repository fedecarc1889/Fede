"use strict";

let sessionId = null;
let numPages = 0;
let currentPage = 0;
let pagesText = [];
let fieldSeq = 0;
let activeBBoxFieldId = null;
let drawing = false;
let drawStart = null;

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const providerSelect = $("#providerSelect");
const providerId = $("#providerId");
const providerLabel = $("#providerLabel");
const providerMatch = $("#providerMatch");
const uploadForm = $("#uploadForm");
const uploadStatus = $("#uploadStatus");
const previewPanel = $("#preview-panel");
const fieldsPanel = $("#fields-panel");
const pageSelect = $("#pageSelect");
const detectedHint = $("#detectedHint");
const pageImg = $("#pageImg");
const bboxCanvas = $("#bboxCanvas");
const ocrText = $("#ocrText");
const fieldsContainer = $("#fieldsContainer");
const fieldRowTemplate = $("#fieldRowTemplate");

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const contentType = res.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (body && body.description) || (typeof body === "string" ? body : JSON.stringify(body));
    throw new Error(message || `Error ${res.status}`);
  }
  return body;
}

// ---------- Selección / carga de plantilla de proveedor ----------

providerSelect.addEventListener("change", async () => {
  const pid = providerSelect.value;
  clearFields();
  if (!pid) {
    providerId.value = "";
    providerLabel.value = "";
    providerMatch.value = "";
    return;
  }
  try {
    const cfg = await api(`/providers/${encodeURIComponent(pid)}`);
    providerId.value = cfg.id;
    providerLabel.value = cfg.label || "";
    providerMatch.value = (cfg.match || []).join("\n");
    Object.entries(cfg.fields || {}).forEach(([name, def]) => addFieldRow(name, def));
  } catch (e) {
    alert(`No se pudo cargar la plantilla: ${e.message}`);
  }
});

// ---------- Subida de PDF de ejemplo ----------

uploadForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const file = $("#pdfFile").files[0];
  if (!file) return;

  const lang = $("#ocrLang").value.trim() || "spa";
  const formData = new FormData();
  formData.append("pdf", file);
  formData.append("lang", lang);

  uploadStatus.textContent = "Procesando OCR, puede tardar unos segundos...";
  try {
    const data = await api("/upload", { method: "POST", body: formData });
    sessionId = data.session_id;
    numPages = data.num_pages;
    pagesText = data.pages_text;
    currentPage = 0;

    pageSelect.innerHTML = "";
    for (let i = 0; i < numPages; i++) {
      const opt = document.createElement("option");
      opt.value = i;
      opt.textContent = `Página ${i + 1}`;
      pageSelect.appendChild(opt);
    }

    detectedHint.textContent = data.detected_provider
      ? `Proveedor detectado automáticamente: ${data.detected_provider}`
      : "Ningún proveedor detectado con las plantillas existentes.";

    uploadStatus.textContent = `Listo: ${numPages} página(s) analizada(s).`;
    previewPanel.hidden = false;
    fieldsPanel.hidden = false;
    showPage(0);
  } catch (e) {
    uploadStatus.textContent = `Error: ${e.message}`;
  }
});

pageSelect.addEventListener("change", () => showPage(parseInt(pageSelect.value, 10)));

function showPage(idx) {
  currentPage = idx;
  pageImg.onload = sizeCanvasToImage;
  pageImg.src = `/page-image/${sessionId}/${idx}`;
  ocrText.textContent = pagesText[idx] || "";
}

function sizeCanvasToImage() {
  bboxCanvas.width = pageImg.clientWidth;
  bboxCanvas.height = pageImg.clientHeight;
  redrawCanvas();
}
window.addEventListener("resize", () => { if (pageImg.src) sizeCanvasToImage(); });

// ---------- Dibujo de regiones (bbox) sobre la imagen ----------

function redrawCanvas(previewRect) {
  const ctx = bboxCanvas.getContext("2d");
  ctx.clearRect(0, 0, bboxCanvas.width, bboxCanvas.height);

  $$(".field-row").forEach((row) => {
    const bbox = row.dataset.bbox ? JSON.parse(row.dataset.bbox) : null;
    const bboxPage = parseInt($(".f-bbox-page", row).value || "0", 10);
    if (!bbox || bboxPage !== currentPage) return;
    const isActive = row.dataset.fieldId === activeBBoxFieldId;
    drawRect(ctx, bbox, isActive ? "#2a6df5" : "#00000066");
  });

  if (previewRect) drawRect(ctx, previewRect, "#2a6df5", true);
}

function drawRect(ctx, [x0, y0, x1, y1], color, dashed) {
  const x = x0 * bboxCanvas.width;
  const y = y0 * bboxCanvas.height;
  const w = (x1 - x0) * bboxCanvas.width;
  const h = (y1 - y0) * bboxCanvas.height;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash(dashed ? [5, 4] : []);
  ctx.strokeRect(x, y, w, h);
}

bboxCanvas.addEventListener("mousedown", (ev) => {
  if (!activeBBoxFieldId) return;
  drawing = true;
  drawStart = canvasPoint(ev);
});

bboxCanvas.addEventListener("mousemove", (ev) => {
  if (!drawing) return;
  const p = canvasPoint(ev);
  redrawCanvas(rectFromPoints(drawStart, p));
});

window.addEventListener("mouseup", (ev) => {
  if (!drawing) return;
  drawing = false;
  const p = canvasPoint(ev);
  const bbox = rectFromPoints(drawStart, p);
  const row = fieldsContainer.querySelector(`[data-field-id="${activeBBoxFieldId}"]`);
  if (row && bbox[2] - bbox[0] > 0.01 && bbox[3] - bbox[1] > 0.01) {
    row.dataset.bbox = JSON.stringify(bbox);
    $(".f-bbox-value", row).textContent =
      `x0=${bbox[0].toFixed(3)} y0=${bbox[1].toFixed(3)} x1=${bbox[2].toFixed(3)} y1=${bbox[3].toFixed(3)}`;
  }
  setActiveDrawField(null);
  redrawCanvas();
});

function canvasPoint(ev) {
  const rect = bboxCanvas.getBoundingClientRect();
  const x = Math.min(Math.max((ev.clientX - rect.left) / rect.width, 0), 1);
  const y = Math.min(Math.max((ev.clientY - rect.top) / rect.height, 0), 1);
  return [x, y];
}

function rectFromPoints([x0, y0], [x1, y1]) {
  return [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)];
}

function setActiveDrawField(fieldId) {
  activeBBoxFieldId = fieldId;
  $$(".f-draw").forEach((btn) => {
    const row = btn.closest(".field-row");
    const isActive = row.dataset.fieldId === fieldId;
    btn.textContent = isActive
      ? "Arrastrá sobre la imagen..."
      : "Dibujar región sobre la imagen";
    btn.classList.toggle("primary", isActive);
  });
}

// ---------- Filas de campos ----------

$("#addFieldBtn").addEventListener("click", () => addFieldRow());

$("#suggestFieldsBtn").addEventListener("click", async () => {
  const status = $("#suggestStatus");
  if (!sessionId) {
    alert("Subí un PDF de ejemplo primero.");
    return;
  }
  status.textContent = "Analizando...";
  try {
    const data = await api("/suggest-fields", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const entries = Object.entries(data.fields || {});
    entries.forEach(([name, def]) => addFieldRow(name, def));
    status.textContent = entries.length
      ? `Se agregaron ${entries.length} campo(s) sugeridos. Es un borrador: revisá nombres repetidos (con sufijo _2, _3...) y probá cada uno antes de guardar.`
      : "No se detectaron pares 'Etiqueta: valor' en este PDF.";
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
});

function clearFields() {
  fieldsContainer.innerHTML = "";
}

function addFieldRow(name = "", def = {}) {
  const fieldId = `f${++fieldSeq}`;
  const node = fieldRowTemplate.content.cloneNode(true);
  const row = node.querySelector(".field-row");
  row.dataset.fieldId = fieldId;

  $(".f-name", row).value = name;

  const method = def.bbox ? "bbox" : "regex";
  $$(".f-method", row).forEach((r) => {
    r.name = `method-${fieldId}`;
    r.checked = r.value === method;
    r.addEventListener("change", () => updateMethodVisibility(row));
  });

  $(".f-regex", row).value = (def.regex || []).join("\n");

  const hasPage = def.page !== undefined && def.page !== null;
  $(".f-limit-page", row).checked = method === "regex" && hasPage;
  $(".f-page", row).disabled = !(method === "regex" && hasPage);
  $(".f-page", row).value = hasPage ? def.page : 0;
  $(".f-limit-page", row).addEventListener("change", (ev) => {
    $(".f-page", row).disabled = !ev.target.checked;
  });

  $(".f-bbox-page", row).value = hasPage ? def.page : 0;
  if (def.bbox) {
    row.dataset.bbox = JSON.stringify(def.bbox);
    $(".f-bbox-value", row).textContent =
      `x0=${def.bbox[0].toFixed(3)} y0=${def.bbox[1].toFixed(3)} x1=${def.bbox[2].toFixed(3)} y1=${def.bbox[3].toFixed(3)}`;
  }
  $(".f-bbox-page", row).addEventListener("change", redrawCanvas);

  $(".f-draw", row).addEventListener("click", () => {
    if (!sessionId) { alert("Primero subí un PDF de ejemplo."); return; }
    setActiveDrawField(activeBBoxFieldId === fieldId ? null : fieldId);
  });

  $(".f-remove", row).addEventListener("click", () => {
    row.remove();
    redrawCanvas();
  });

  $(".f-test", row).addEventListener("click", () => testField(row));

  fieldsContainer.appendChild(node);
  updateMethodVisibility(row);
  redrawCanvas();
}

function updateMethodVisibility(row) {
  const method = $(".f-method:checked", row).value;
  $(".f-regex-block", row).hidden = method !== "regex";
  $(".f-bbox-block", row).hidden = method !== "bbox";
  redrawCanvas();
}

function fieldConfigFromRow(row) {
  const method = $(".f-method:checked", row).value;
  const cfg = {};
  if (method === "regex") {
    const patterns = $(".f-regex", row).value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (patterns.length) cfg.regex = patterns;
    if ($(".f-limit-page", row).checked) cfg.page = parseInt($(".f-page", row).value || "0", 10);
  } else {
    if (row.dataset.bbox) {
      cfg.bbox = JSON.parse(row.dataset.bbox);
      cfg.page = parseInt($(".f-bbox-page", row).value || "0", 10);
    }
  }
  return cfg;
}

function gatherFields() {
  const fields = {};
  $$(".field-row", fieldsContainer).forEach((row) => {
    const name = $(".f-name", row).value.trim();
    if (!name) return;
    fields[name] = fieldConfigFromRow(row);
  });
  return fields;
}

async function testField(row) {
  const resultSpan = $(".f-result", row);
  if (!sessionId) {
    resultSpan.textContent = "Subí un PDF de ejemplo primero.";
    resultSpan.className = "f-result err";
    return;
  }
  const cfg = fieldConfigFromRow(row);
  resultSpan.textContent = "Probando...";
  resultSpan.className = "f-result";
  try {
    const data = await api("/test-field", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, ...cfg }),
    });
    if (data.error) {
      resultSpan.textContent = data.error;
      resultSpan.className = "f-result err";
    } else if (data.value === null || data.value === undefined) {
      resultSpan.textContent = "(sin coincidencia)";
      resultSpan.className = "f-result empty";
    } else {
      resultSpan.textContent = `→ "${data.value}"`;
      resultSpan.className = "f-result ok";
    }
  } catch (e) {
    resultSpan.textContent = e.message;
    resultSpan.className = "f-result err";
  }
}

// ---------- Guardar plantilla / probar extracción completa ----------

$("#saveTemplateBtn").addEventListener("click", async () => {
  const saveStatus = $("#saveStatus");
  const pid = providerId.value.trim();
  if (!pid) {
    saveStatus.textContent = "Ingresá un ID de proveedor.";
    return;
  }
  const payload = {
    label: providerLabel.value.trim() || pid,
    match: providerMatch.value.split("\n").map((s) => s.trim()).filter(Boolean),
    fields: gatherFields(),
  };
  saveStatus.textContent = "Guardando...";
  try {
    await api(`/providers/${encodeURIComponent(pid)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    saveStatus.textContent = `Plantilla '${pid}' guardada en providers/${pid}.json`;
    if (!$$(`option[value="${pid}"]`, providerSelect).length) {
      const opt = document.createElement("option");
      opt.value = pid;
      opt.textContent = `${payload.label} (${pid})`;
      providerSelect.appendChild(opt);
    }
    providerSelect.value = pid;
  } catch (e) {
    saveStatus.textContent = `Error al guardar: ${e.message}`;
  }
});

$("#extractAllBtn").addEventListener("click", async () => {
  const box = $("#extractResult");
  if (!sessionId) {
    alert("Subí un PDF de ejemplo primero.");
    return;
  }
  box.hidden = false;
  box.textContent = "Extrayendo...";
  try {
    const data = await api("/extract-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, fields: gatherFields() }),
    });
    box.textContent = JSON.stringify(data.campos, null, 2);
  } catch (e) {
    box.textContent = `Error: ${e.message}`;
  }
});

$("#downloadExcelBtn").addEventListener("click", async () => {
  const saveStatus = $("#saveStatus");
  if (!sessionId) {
    alert("Subí un PDF de ejemplo primero.");
    return;
  }
  try {
    const res = await fetch("/extract-all/excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        provider_id: providerId.value.trim() || undefined,
        fields: gatherFields(),
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.description || `Error ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "remito.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    saveStatus.textContent = `Error al generar el Excel: ${e.message}`;
  }
});

// IndiaAnnotate – Frontend Script v1.1
// Fixes: session persistence, download annotations, drag-drop ZIP, conf slider, review export

const API_BASE_URL = window.API_BASE_URL || "http://127.0.0.1:5000";

let selectedFile = null;       // COCO JSON for validation
let selectedZipFile = null;    // Dataset ZIP for upload
let currentResult = null;      // Current validation result
let currentSessionId = localStorage.getItem("indiaAnnotate_sessionId") || null;

// ============================================================
// INIT
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  initializeTheme();
  checkAPIStatus();

  // Restore session if exists
  if (currentSessionId) {
    showSessionPanel(currentSessionId);
    checkSessionStatus(true); // silent check
  }

  // Drag-and-drop for JSON upload area
  const uploadArea = document.getElementById("uploadArea");
  if (uploadArea) {
    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("border-primary-500", "bg-primary-50/30");
    });
    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("border-primary-500", "bg-primary-50/30");
    });
    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("border-primary-500", "bg-primary-50/30");
      const file = e.dataTransfer.files[0];
      if (file) processJsonFile(file);
    });
  }
});

// ============================================================
// THEME
// ============================================================

function initializeTheme() {
  const toggle = document.getElementById("themeToggle");
  const sun = document.getElementById("sunIcon");
  const moon = document.getElementById("moonIcon");
  if (!toggle) return;

  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  const isDark = savedTheme === "dark" || (!savedTheme && prefersDark);
  applyTheme(isDark, sun, moon);

  toggle.addEventListener("click", () => {
    const dark = document.documentElement.classList.contains("dark");
    applyTheme(!dark, sun, moon);
    localStorage.setItem("theme", !dark ? "dark" : "light");
  });
}

function applyTheme(dark, sun, moon) {
  if (dark) {
    document.documentElement.classList.add("dark");
    sun && sun.classList.add("hidden");
    moon && moon.classList.remove("hidden");
  } else {
    document.documentElement.classList.remove("dark");
    sun && sun.classList.remove("hidden");
    moon && moon.classList.add("hidden");
  }
}

// ============================================================
// LOADING OVERLAY
// ============================================================

function showGlobalLoading(message = "Processing… please wait") {
  const overlay = document.getElementById("globalLoading");
  const msg = document.getElementById("loadingMessage");
  if (msg) msg.textContent = message;
  if (overlay) overlay.classList.add("active");
}

function hideGlobalLoading() {
  const overlay = document.getElementById("globalLoading");
  if (overlay) overlay.classList.remove("active");
}

// ============================================================
// API STATUS
// ============================================================

async function checkAPIStatus() {
  const status = document.getElementById("apiStatus");
  const dot = document.getElementById("apiDot");
  try {
    const res = await fetch(API_BASE_URL, { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      status.textContent = "Connected";
      status.className = "font-medium text-green-600 dark:text-green-400";
      if (dot) { dot.classList.remove("bg-yellow-400"); dot.classList.add("bg-green-500"); }
    } else {
      throw new Error("Non-OK status");
    }
  } catch {
    status.textContent = "Offline";
    status.className = "font-medium text-red-500 dark:text-red-400";
    if (dot) { dot.classList.remove("bg-yellow-400"); dot.classList.add("bg-red-500"); }
  }
}

// ============================================================
// ZIP UPLOAD — DRAG & DROP
// ============================================================

function handleZipDragOver(event) {
  event.preventDefault();
  const area = document.getElementById("zipDropArea");
  area.classList.add("border-indigo-500", "bg-indigo-50/40");
}

function handleZipDragLeave(event) {
  const area = document.getElementById("zipDropArea");
  area.classList.remove("border-indigo-500", "bg-indigo-50/40");
}

function handleZipDrop(event) {
  event.preventDefault();
  const area = document.getElementById("zipDropArea");
  area.classList.remove("border-indigo-500", "bg-indigo-50/40");
  const file = event.dataTransfer.files[0];
  if (file) processZipFile(file);
}

function handleZipSelect(event) {
  const file = event.target.files[0];
  if (file) processZipFile(file);
}

function processZipFile(file) {
  if (!file.name.toLowerCase().endsWith(".zip")) {
    showError("Please select a .zip file");
    return;
  }
  const maxMB = 200;
  if (file.size > maxMB * 1024 * 1024) {
    showError(`File too large. Max ${maxMB}MB`);
    return;
  }
  selectedZipFile = file;

  // Show selected zip info
  const info = document.getElementById("selectedZipInfo");
  document.getElementById("zipFileName").textContent = file.name;
  document.getElementById("zipFileSize").textContent = formatBytes(file.size);
  info.classList.remove("hidden");
}

function clearZip() {
  selectedZipFile = null;
  document.getElementById("datasetZip").value = "";
  document.getElementById("selectedZipInfo").classList.add("hidden");
}

// ============================================================
// UPLOAD DATASET
// ============================================================

async function uploadDataset() {
  if (!selectedZipFile) {
    showError("Please select a ZIP file first");
    return;
  }

  const btn = document.getElementById("uploadBtn");
  btn.disabled = true;
  showGlobalLoading("Uploading dataset… please wait");

  const formData = new FormData();
  formData.append("file", selectedZipFile);

  try {
    const res = await fetch(`${API_BASE_URL}/upload-dataset`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      showError(data.message || "Upload failed");
      return;
    }

    currentSessionId = data.session_id;
    localStorage.setItem("indiaAnnotate_sessionId", currentSessionId);

    showSessionPanel(currentSessionId, data.image_count, data.annotation_count);
    showSuccess(`✅ Uploaded! Found ${data.image_count} image(s). Session ready.`);
    clearZip();

  } catch (err) {
    showError("Network error: " + err.message);
  } finally {
    btn.disabled = false;
    hideGlobalLoading();
  }
}

// ============================================================
// SESSION PANEL
// ============================================================

function showSessionPanel(sessionId, imageCount, annotationCount) {
  const panel = document.getElementById("sessionPanel");
  const display = document.getElementById("sessionIdDisplay");
  const stats = document.getElementById("sessionStats");

  display.textContent = sessionId;
  panel.classList.remove("hidden");

  if (imageCount !== undefined) {
    stats.textContent = `${imageCount} image(s) · ${annotationCount || 0} annotation file(s)`;
  }
}

async function checkSessionStatus(silent = false) {
  if (!currentSessionId) {
    if (!silent) showError("No active session");
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/session/${currentSessionId}/status`);
    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      if (!silent) showError(data.message || "Session not found");
      return;
    }

    const stats = document.getElementById("sessionStats");
    if (stats) {
      stats.textContent = `${data.image_count} image(s) · annotations: ${data.annotation_files.join(", ") || "none"}`;
    }

    // Show download button if auto_annotations.json exists
    const dlBtn = document.getElementById("downloadAnnotationsBtn");
    if (dlBtn) {
      if (data.has_auto_annotations) {
        dlBtn.classList.remove("hidden");
      } else {
        dlBtn.classList.add("hidden");
      }
    }

    if (!silent) showSuccess("Session status refreshed");

  } catch (err) {
    if (!silent) showError("Failed to check session: " + err.message);
  }
}

function copySessionId() {
  if (!currentSessionId) return;
  navigator.clipboard.writeText(currentSessionId)
    .then(() => showSuccess("Session ID copied!"))
    .catch(() => showError("Failed to copy"));
}

function clearSession() {
  if (!confirm("Clear the current session? This only clears it locally.")) return;
  currentSessionId = null;
  localStorage.removeItem("indiaAnnotate_sessionId");
  document.getElementById("sessionPanel").classList.add("hidden");
  showSuccess("Session cleared");
}

// ============================================================
// DOWNLOAD ANNOTATIONS
// ============================================================

function downloadAnnotations() {
  if (!currentSessionId) {
    showError("No active session");
    return;
  }
  const url = `${API_BASE_URL}/session/${currentSessionId}/download-annotations`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `annotations_${currentSessionId.slice(0, 8)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showSuccess("Downloading annotations…");
}

// ============================================================
// AUTO-ANNOTATE
// ============================================================

async function runAutoAnnotate() {
  if (!currentSessionId) {
    showError("Upload a dataset first (Step 1).");
    return;
  }

  const btn = document.getElementById("autoAnnotateBtn");
  const spinner = document.getElementById("autoAnnSpinner");
  const text = document.getElementById("autoAnnText");
  const resultBox = document.getElementById("autoAnnResult");

  const conf = parseInt(document.getElementById("confSlider").value) / 100;

  btn.disabled = true;
  spinner.classList.remove("hidden");
  text.textContent = "Running YOLO…";
  resultBox.classList.add("hidden");
  showGlobalLoading("Running YOLO model on your images… this may take a minute.");

  try {
    const res = await fetch(`${API_BASE_URL}/auto-annotate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId, conf }),
    });

    const data = await res.json();

    if (!res.ok || data.status !== "success") {
      showError(data.message || "Auto-annotation failed");
      return;
    }

    // Show summary
    resultBox.innerHTML = `
      ✅ <strong>Auto-annotation complete!</strong><br>
      Processed <strong>${data.total_images}</strong> image(s), 
      found <strong>${data.total_detections}</strong> total detection(s).
    `;
    resultBox.classList.remove("hidden");

    // Show download button
    const dlBtn = document.getElementById("downloadAnnotationsBtn");
    if (dlBtn) dlBtn.classList.remove("hidden");

    // Display validation results inline
    if (data.validation_report) {
      currentResult = data.validation_report;
      displayResults(currentResult);
    }

    showSuccess(`Auto-annotation done! ${data.total_detections} objects detected.`);

  } catch (err) {
    showError("Auto-annotate error: " + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    text.textContent = "⚡ Auto-Annotate";
    hideGlobalLoading();
  }
}

// ============================================================
// JSON FILE SELECTION (for validation)
// ============================================================

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) processJsonFile(file);
}

function processJsonFile(file) {
  if (!file.name.toLowerCase().endsWith(".json")) {
    showError("Please select a .json file");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showError("File size must be under 10MB");
    return;
  }
  selectedFile = file;
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent = formatBytes(file.size);
  document.getElementById("selectedFile").classList.remove("hidden");
  document.getElementById("validateBtn").disabled = false;
}

function clearFile() {
  selectedFile = null;
  document.getElementById("fileInput").value = "";
  document.getElementById("selectedFile").classList.add("hidden");
  document.getElementById("validateBtn").disabled = true;
}

// ============================================================
// VALIDATE DATASET
// ============================================================

async function validateDataset() {
  if (!selectedFile) {
    showError("Please select a COCO JSON file first");
    return;
  }

  const btn = document.getElementById("validateBtn");
  const spinner = document.getElementById("loadingSpinner");
  const validateText = document.getElementById("validateText");

  btn.disabled = true;
  spinner.classList.remove("hidden");
  validateText.textContent = "Validating…";
  showGlobalLoading("Validating your COCO dataset…");

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const res = await fetch(`${API_BASE_URL}/validate`, {
      method: "POST",
      body: formData,
    });

    const result = await res.json();

    if (!res.ok || result.status !== "success") {
      showError(result.message || "Validation failed");
      return;
    }

    // The backend wraps the report in result.report
    currentResult = result.report || result;
    displayResults(currentResult);
    showSuccess("Dataset validated successfully!");

  } catch (err) {
    showError("Network error: " + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    validateText.textContent = "Validate Dataset";
    hideGlobalLoading();
  }
}

// ============================================================
// DISPLAY RESULTS
// ============================================================

function displayResults(result) {
  document.getElementById("emptyState").classList.add("hidden");
  document.getElementById("resultsSection").classList.remove("hidden");

  updateStatusCard(result);
  updateSummaryCards(result);
  updateWarnings(result);
  updateLabelDistribution(result);
  updateJSONViewer(result);
  handleHumanReview(result);

  // Update unannotated count badge
  const badge = document.getElementById("unannotatedCount");
  if (badge && result.summary) {
    badge.textContent = `(${result.summary.images_without_annotations || 0})`;
  }

  // Scroll to results
  document.getElementById("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateStatusCard(result) {
  const icon = document.getElementById("statusIcon");
  const title = document.getElementById("statusTitle");
  const message = document.getElementById("statusMessage");
  const qualityScore = document.getElementById("qualityScore");
  const scoreValue = document.getElementById("scoreValue");

  if (result.status === "success") {
    icon.innerHTML = `<div class="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-xl">✅</div>`;
    title.textContent = "Validation Successful";
    title.className = "font-semibold text-lg text-green-700 dark:text-green-400";

    const reviewStatus = result.review_status || "";
    if (reviewStatus === "approved") {
      message.textContent = "Dataset is valid and ready for training.";
    } else {
      message.textContent = "Dataset is valid. Human review recommended for full approval.";
    }

    const score = result.summary?.estimated_quality_score ?? null;
    if (score !== null) {
      qualityScore.classList.remove("hidden");
      scoreValue.textContent = score;
      scoreValue.className = `text-3xl font-bold ${
        score >= 80 ? "text-green-600 dark:text-green-400" :
        score >= 60 ? "text-yellow-600 dark:text-yellow-400" :
        "text-red-500 dark:text-red-400"
      }`;
    } else {
      qualityScore.classList.add("hidden");
    }
  } else {
    icon.innerHTML = `<div class="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-xl">❌</div>`;
    title.textContent = "Validation Failed";
    title.className = "font-semibold text-lg text-red-700 dark:text-red-400";
    message.textContent = result.message || "There was an error validating your dataset.";
    qualityScore.classList.add("hidden");
  }
}

function updateSummaryCards(result) {
  const container = document.getElementById("summaryCards");
  if (!result.summary) { container.innerHTML = ""; return; }

  const s = result.summary;

  const cards = [
    { label: "Images", value: s.num_images || 0, icon: "🖼️", color: "blue" },
    { label: "Annotations", value: s.num_annotations || 0, icon: "📝", color: "green" },
    { label: "Categories", value: s.num_categories || 0, icon: "🏷️", color: "purple" },
    { label: "Annotated", value: s.images_with_annotations || 0, icon: "✅", color: "teal" },
    { label: "Unannotated", value: s.images_without_annotations || 0, icon: "⭕", color: "orange" },
    { label: "Avg/Image", value: s.average_annotations_per_image ?? "—", icon: "📊", color: "indigo" },
  ];

  container.innerHTML = cards.map(c => `
    <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover-lift">
      <div class="flex items-center justify-between mb-2">
        <p class="text-xs text-gray-500 dark:text-gray-400 font-medium">${c.label}</p>
        <span class="text-lg">${c.icon}</span>
      </div>
      <p class="text-2xl font-bold text-gray-900 dark:text-white">${c.value}</p>
    </div>
  `).join("");
}

function updateWarnings(result) {
  const section = document.getElementById("warningsSection");
  const list = document.getElementById("warningsList");
  const warnings = result.warnings || [];

  if (!warnings.length) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  list.innerHTML = warnings.map(w => `<li>${w}</li>`).join("");
}

function handleHumanReview(result) {
  const banner = document.getElementById("humanReviewBanner");
  const role = document.getElementById("assignedRole");
  const next = document.getElementById("nextStage");
  const flow = document.getElementById("crowdFlow");

  if (result.requires_human_review) {
    banner.classList.remove("hidden");
    if (flow) flow.classList.remove("hidden");
    if (role) role.textContent = result.crowd_flow?.assigned_role || "Annotator";
    if (next) next.textContent = result.crowd_flow?.next_stage || "Reviewer Approval";
  } else {
    banner.classList.add("hidden");
    if (flow) flow.classList.add("hidden");
  }
}

function updateLabelDistribution(result) {
  const section = document.getElementById("distributionSection");
  const grid = document.getElementById("distributionGrid");
  const totalEl = document.getElementById("totalAnnotations");

  const dist = result.label_distribution;
  if (!dist || Object.keys(dist).length === 0) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  const total = result.summary?.num_annotations || 1;
  totalEl.textContent = `Total: ${total} annotations`;

  // Sort by count desc
  const sorted = Object.entries(dist).sort((a, b) => b[1].count - a[1].count);

  grid.innerHTML = sorted.map(([label, data]) => {
    const pct = ((data.count / total) * 100).toFixed(1);
    return `
      <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
        <div class="flex items-center justify-between mb-2">
          <span class="font-medium text-gray-900 dark:text-white text-sm truncate">${label}</span>
          <span class="text-sm font-semibold text-blue-600 dark:text-blue-400 ml-2">${data.count}</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="flex-1 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full transition-all" style="width:${Math.min(pct, 100)}%"></div>
          </div>
          <span class="text-xs text-gray-400 font-medium">${pct}%</span>
        </div>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">ID: ${data.category_id}</p>
      </div>
    `;
  }).join("");
}

function updateJSONViewer(result) {
  const output = document.getElementById("jsonOutput");
  const jsonStr = JSON.stringify(result, null, 2);

  const highlighted = jsonStr
    .replace(/(\"(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*\"(\s*:)?)/g, (match) => {
      if (/:$/.test(match)) return `<span class="json-key">${escHtml(match)}</span>`;
      return `<span class="json-string">${escHtml(match)}</span>`;
    })
    .replace(/\b(true|false)\b/g, '<span class="json-boolean">$1</span>')
    .replace(/\b(null)\b/g, '<span class="json-null">$1</span>')
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="json-number">$1</span>');

  output.innerHTML = highlighted;
}

function escHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ============================================================
// REVIEW QUEUE
// ============================================================

function reviewUnannotatedImages() {
  if (!currentResult?.summary) { showError("No validation data."); return; }

  const count = currentResult.summary.images_without_annotations || 0;
  if (count === 0) { showSuccess("All images are annotated 🎉"); return; }

  const unannotatedIds = currentResult.review_payload?.unannotated_images || [];

  document.getElementById("reviewImageCount").textContent = count;

  const list = document.getElementById("reviewImageList");
  list.innerHTML = unannotatedIds.slice(0, 12).map(id => `
    <div class="h-20 bg-gray-100 dark:bg-gray-700 rounded-lg flex flex-col items-center justify-center text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 gap-1">
      <span class="text-xl">🖼️</span>
      <span>ID: ${id}</span>
    </div>
  `).join("");

  if (unannotatedIds.length > 12) {
    list.innerHTML += `<div class="col-span-3 text-center text-xs text-gray-400 py-2">…and ${unannotatedIds.length - 12} more</div>`;
  }

  const modal = document.getElementById("reviewModal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function closeReviewModal() {
  const modal = document.getElementById("reviewModal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

function exportUnannotatedList() {
  if (!currentResult?.review_payload) return;

  const ids = currentResult.review_payload.unannotated_images || [];
  const blob = new Blob([JSON.stringify({ unannotated_image_ids: ids }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "unannotated_image_ids.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showSuccess("Exported unannotated image IDs");
}

// ============================================================
// JSON VIEWER CONTROLS
// ============================================================

function toggleRawJSON() {
  const viewer = document.getElementById("jsonViewer");
  const btn = document.querySelector('button[onclick="toggleRawJSON()"]');
  const isCollapsed = viewer.classList.contains("max-h-96");

  viewer.classList.toggle("max-h-96", !isCollapsed);
  viewer.classList.toggle("max-h-screen", isCollapsed);
  if (btn) btn.textContent = isCollapsed ? "Collapse View" : "Toggle Full View";
}

function copyJSON() {
  if (!currentResult) return;
  navigator.clipboard.writeText(JSON.stringify(currentResult, null, 2))
    .then(() => showSuccess("JSON copied to clipboard!"))
    .catch(() => showError("Copy failed"));
}

// ============================================================
// DOWNLOAD VALIDATION REPORT
// ============================================================

function downloadReport() {
  if (!currentResult) { showError("No results to download"); return; }

  const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `validation_report_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showSuccess("Report downloaded!");
}

// ============================================================
// RESET
// ============================================================

function resetResults() {
  selectedFile = null;
  currentResult = null;
  document.getElementById("fileInput").value = "";
  document.getElementById("selectedFile").classList.add("hidden");
  document.getElementById("validateBtn").disabled = true;
  document.getElementById("validateText").textContent = "Validate Dataset";
  document.getElementById("loadingSpinner").classList.add("hidden");
  document.getElementById("resultsSection").classList.add("hidden");
  document.getElementById("emptyState").classList.remove("hidden");
  document.getElementById("humanReviewBanner").classList.add("hidden");
  document.getElementById("warningsSection").classList.add("hidden");
  document.getElementById("autoAnnResult").classList.add("hidden");

  const viewer = document.getElementById("jsonViewer");
  viewer.classList.add("max-h-96");
  viewer.classList.remove("max-h-screen");

  showSuccess("Results cleared");
}

// ============================================================
// SAMPLE DATA
// ============================================================

function loadSample() {
  currentResult = {
    status: "success",
    review_status: "pending",
    requires_human_review: true,
    summary: {
      num_images: 145,
      num_annotations: 892,
      num_categories: 8,
      images_with_annotations: 142,
      images_without_annotations: 3,
      estimated_quality_score: 72,
      average_annotations_per_image: 6.15,
      average_confidence: 0.71,
    },
    label_distribution: {
      person: { category_id: "1", count: 234 },
      car: { category_id: "2", count: 312 },
      motorcycle: { category_id: "3", count: 89 },
      autorickshaw: { category_id: "4", count: 156 },
      bus: { category_id: "5", count: 45 },
      truck: { category_id: "6", count: 32 },
      "traffic light": { category_id: "7", count: 12 },
      "traffic sign": { category_id: "8", count: 12 },
    },
    crowd_flow: {
      assigned_role: "annotator",
      next_stage: "reviewer_approval",
      current_stage: "annotator_review",
    },
    warnings: [
      "3 image(s) have no annotations",
      "14 annotation(s) below confidence threshold (0.6)",
    ],
    review_payload: {
      unannotated_images: [101, 102, 103],
      low_confidence_annotations: [],
      orphan_annotations: [],
      invalid_category_annotations: [],
    },
    notes: [
      "COCO schema validated successfully",
      "Quality score: density (0–70) + coverage (0–30)",
      "Human-in-the-loop pipeline enabled",
    ],
  };

  displayResults(currentResult);
  showSuccess("Sample data loaded!");
}

// ============================================================
// NOTIFICATIONS
// ============================================================

function showError(msg) { showNotification(msg, "error"); }
function showSuccess(msg) { showNotification(msg, "success"); }

function showNotification(message, type = "info") {
  document.querySelectorAll(".notification").forEach(n => n.remove());

  const n = document.createElement("div");
  const colors = {
    error: "bg-red-50 dark:bg-red-900/40 border border-red-200 dark:border-red-700 text-red-700 dark:text-red-300",
    success: "bg-green-50 dark:bg-green-900/40 border border-green-200 dark:border-green-700 text-green-700 dark:text-green-300",
    info: "bg-blue-50 dark:bg-blue-900/40 border border-blue-200 dark:border-blue-700 text-blue-700 dark:text-blue-300",
  };
  const icons = { error: "❌", success: "✅", info: "ℹ️" };

  n.className = `fixed top-5 left-1/2 -translate-x-1/2 px-4 py-3 rounded-lg shadow-lg z-[9999] notification flex items-center gap-2 text-sm font-medium max-w-sm ${colors[type] || colors.info}`;
  n.innerHTML = `<span>${icons[type] || ""}</span><span>${message}</span>`;
  document.body.appendChild(n);

  setTimeout(() => { if (n.parentNode) n.remove(); }, 5000);
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

// Override fetch to always inject auth token
const _origFetch = window.fetch;
window.fetch = function(url, opts = {}) {
  const token = localStorage.getItem('ia_token');
  if (token && typeof url === 'string' && url.startsWith(API_BASE_URL)) {
    opts.headers = {
      ...(opts.headers || {}),
      'X-Auth-Token': token,
    };
  }
  return _origFetch(url, opts);
};

// Redirect to annotator from session panel
function openAnnotator() {
  if (!currentSessionId) { showError('No active session'); return; }
  window.location.href = `annotator.html?session=${currentSessionId}`;
}

// Logout
function logout() {
  localStorage.removeItem('ia_token');
  localStorage.removeItem('ia_username');
  localStorage.removeItem('ia_role');
  localStorage.removeItem('indiaAnnotate_sessionId');
  window.location.href = 'auth.html';
}

// Redirect to login if not authenticated (on page load)
(function checkAuth() {
  const token = localStorage.getItem('ia_token');
  if (!token && window.location.pathname !== '/auth.html') {
    window.location.href = 'auth.html';
  }
  const username = localStorage.getItem('ia_username');
  const role     = localStorage.getItem('ia_role');
  if (username) {
    const el = document.getElementById('headerUser');
    if (el) el.textContent = `👤 ${username}`;
  }
})();
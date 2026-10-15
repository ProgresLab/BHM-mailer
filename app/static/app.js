function updateSelectedCount(form) {
  const target = form.querySelector("[data-selected-count]");
  if (!target) return;
  const checked = form.querySelectorAll("input[name='contact_ids']:checked").length;
  target.textContent = String(checked);
}

document.addEventListener("change", (event) => {
  const selectAll = event.target.closest("[data-select-all]");
  if (selectAll) {
    const className = selectAll.getAttribute("data-select-all");
    const form = selectAll.closest("form") || document;
    form.querySelectorAll(`.${className}:not(:disabled)`).forEach((checkbox) => {
      checkbox.checked = selectAll.checked;
    });
    if (form instanceof HTMLFormElement) updateSelectedCount(form);
  }

  const checkbox = event.target.closest("input[name='contact_ids']");
  if (checkbox) {
    const form = checkbox.closest("form");
    if (form) updateSelectedCount(form);
  }
});

document.querySelectorAll("form").forEach(updateSelectedCount);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusLabel(status) {
  if (status === "sent") return "accepted_by_smtp (legacy)";
  if (status === "failed") return "smtp_failed (legacy)";
  return status || "—";
}

function badge(status, label) {
  return `<span class="badge badge-${escapeHtml(status)}">${escapeHtml(label || statusLabel(status))}</span>`;
}

function setStatusField(root, field, value) {
  const target = root.querySelector(`[data-status-field="${field}"]`);
  if (target) target.textContent = value || "—";
}

function updateSummaryRow(data) {
  const row = document.querySelector(`[data-campaign-summary-id="${data.campaign_id}"]`);
  if (!row) return;
  const statusTarget = row.querySelector("[data-campaign-status]");
  if (statusTarget) {
    statusTarget.className = `badge badge-${data.campaign_status}`;
    statusTarget.textContent = data.campaign_status;
  }
  const completedTarget = row.querySelector("[data-campaign-completed]");
  if (completedTarget) completedTarget.textContent = data.completed_at || "—";
  [
    "pending",
    "dry_run",
    "accepted_by_smtp",
    "smtp_failed",
    "rate_limited",
    "delivery_pending",
    "delivered_by_trace",
    "failed_by_trace",
    "quarantined_by_trace",
    "bounced_later",
    "skipped",
  ].forEach((key) => {
    const target = row.querySelector(`[data-counter="${key}"]`);
    if (target) target.textContent = String(data[key] ?? 0);
  });
}

function updateSendRows(events) {
  events.forEach((event) => {
    const row = document.querySelector(`[data-send-row="${event.id}"]`);
    if (!row) return;
    const statusTarget = row.querySelector("[data-send-status]");
    if (statusTarget) statusTarget.innerHTML = badge(event.status, event.status_label);
    const timestampTarget = row.querySelector("[data-send-timestamp]");
    if (timestampTarget) timestampTarget.textContent = event.timestamp || "—";
    const errorTarget = row.querySelector("[data-send-error]");
    if (errorTarget) errorTarget.textContent = event.error || "";
  });
}

function updateLiveEvents(root, events) {
  const target = root.querySelector("[data-live-events]");
  if (!target) return;
  target.innerHTML = events
    .map(
      (event) => `
        <tr>
          <td>${escapeHtml(event.email)}</td>
          <td>${badge(event.status, event.status_label)}</td>
          <td>${escapeHtml(event.timestamp || "—")}</td>
          <td>${escapeHtml(event.error || "")}</td>
        </tr>
      `,
    )
    .join("");
}

function applyCampaignStatus(root, data) {
  [
    "total",
    "processed",
    "percent",
    "current_email",
    "current_status",
    "campaign_status",
    "updated_at",
    "completed_at",
    "last_error",
  ].forEach((field) => setStatusField(root, field, data[field]));
  const bar = root.querySelector("[data-progress-bar]");
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, Number(data.percent) || 0))}%`;
  updateSummaryRow(data);
  updateSendRows(data.last_20_events || []);
  updateLiveEvents(root, data.last_20_events || []);
}

function initCampaignStatusPolling() {
  const root = document.querySelector("[data-campaign-status-url]");
  if (!root) return;
  const url = root.getAttribute("data-campaign-status-url");
  let timer = null;

  async function poll() {
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const data = await response.json();
      applyCampaignStatus(root, data);
      if (data.campaign_status !== "sending" && timer) {
        clearInterval(timer);
        timer = null;
      }
    } catch (error) {
      setStatusField(root, "last_error", "Could not refresh live status.");
    }
  }

  poll();
  timer = window.setInterval(poll, 2000);
}

initCampaignStatusPolling();

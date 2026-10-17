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

// Never rewrite the editor on input. Bounded history also captures checklist attributes.
function initRichEditor() {
  const form = document.querySelector('[data-editor-form]');
  if (!form) return;
  const editor = form.querySelector('[data-rich-editor]');
  const source = form.querySelector('[data-rich-source]');
  const message = form.querySelector('[data-editor-message]');
  editor.innerHTML = source.value; // Server-sanitized draft only.
  source.hidden = true;
  let range = null;
  let pasting = false;
  let history=[], historyIndex=-1, applying=false, lastTyping=0;
  function remember() {
    const selection = window.getSelection();
    if (selection.rangeCount && editor.contains(selection.anchorNode)) range = selection.getRangeAt(0).cloneRange();
  }
  function restore() {
    editor.focus();
    if (range) { const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); }
  }
  function nodePath(node) {
    const path=[];
    while(node && node!==editor) {path.unshift([...node.parentNode.childNodes].indexOf(node));node=node.parentNode;}
    return path;
  }
  function capture() {
    const valid=range && editor.contains(range.startContainer) && editor.contains(range.endContainer);
    return {html:editor.innerHTML,position:valid?{start:nodePath(range.startContainer),end:nodePath(range.endContainer),so:range.startOffset,eo:range.endOffset}:null};
  }
  function record(typing=false) {
    if(applying)return;
    remember();const entry=capture(),now=Date.now();
    if(history[historyIndex]?.html===entry.html)return;
    history=history.slice(0,historyIndex+1);
    if(typing && lastTyping && now-lastTyping<750 && historyIndex>0)history[historyIndex]=entry;
    else {history.push(entry);historyIndex++;}
    if(history.length>100){history.shift();historyIndex--;}
    lastTyping=typing?now:0;
  }
  function undoRedo(direction) {
    const index=historyIndex+direction;
    if(index<0 || index>=history.length)return;
    historyIndex=index;applying=true;editor.innerHTML=history[index].html;
    const p=history[index].position;
    const find=path=>path.reduce((node,i)=>node?.childNodes[i],editor);
    range=document.createRange();
    try {if(p){range.setStart(find(p.start),p.so);range.setEnd(find(p.end),p.eo);}else{range.selectNodeContents(editor);range.collapse(false);}}
    catch {range.selectNodeContents(editor);range.collapse(false);}
    restore();applying=false;lastTyping=0;
  }
  function command(name, value = null, recordChange=true) {
    if(name==='undo'){undoRedo(-1);return;}
    if(name==='redo'){undoRedo(1);return;}
    restore();
    if(history[historyIndex])history[historyIndex].position=capture().position;
    applying=true;
    try {document.execCommand(name, false, value);} finally {applying=false;}
    remember();
    if(recordChange)record();
  }
  record();
  editor.addEventListener('beforeinput',e=> {
    if(e.inputType==='historyUndo'||e.inputType==='historyRedo'){e.preventDefault();undoRedo(e.inputType==='historyUndo'?-1:1);return;}
    remember();if(history[historyIndex])history[historyIndex].position=capture().position;
  });
  editor.addEventListener('keydown',e=> {
    if((e.ctrlKey||e.metaKey)&&['z','y'].includes(e.key.toLowerCase())){e.preventDefault();undoRedo(e.key.toLowerCase()==='y'||e.shiftKey?1:-1);}
  });
  document.addEventListener('selectionchange', remember);
  form.querySelector('.editor-toolbar').addEventListener('mousedown', e => { if (e.target.closest('button')) e.preventDefault(); });
  form.querySelectorAll('[data-command]').forEach(b => b.addEventListener('click', () => command(b.dataset.command)));
  form.querySelector('[data-block]').addEventListener('change', e => command('formatBlock', e.target.value));
  form.querySelector('[data-size]').addEventListener('change', e => command('fontSize', e.target.value));
  editor.addEventListener('input',e=> {
    const sizes={1:'14px',2:'14px',3:'16px',4:'18px',5:'22px',6:'28px',7:'28px'};
    editor.querySelectorAll('font[size]').forEach(font=>font.style.fontSize=sizes[font.getAttribute('size')]||'16px');
    record(e.inputType==='insertText');
  });
  form.querySelector('[data-checklist]').addEventListener('click', () => {
    restore();
    let node = window.getSelection().anchorNode;
    let list = (node.nodeType === 1 ? node : node.parentElement).closest('ul');
    if (!list || !editor.contains(list)) { command('insertUnorderedList',null,false); node = window.getSelection().anchorNode; list = (node.nodeType === 1 ? node : node.parentElement).closest('ul'); }
    if (list) {
      if (list.dataset.list === 'check') delete list.dataset.list; else list.dataset.list = 'check';
    }
    remember();
    record();
  });
  const linkBox = form.querySelector('[data-link-editor]');
  const linkUrl = form.querySelector('[data-link-url]');
  let existingLink = null;
  form.querySelector('[data-link]').addEventListener('click', () => {
    restore();
    let node = window.getSelection().anchorNode;
    existingLink = (node.nodeType === 1 ? node : node.parentElement).closest('a');
    if (existingLink && !editor.contains(existingLink)) existingLink = null;
    linkUrl.value = existingLink?.getAttribute('href') || '';
    linkBox.hidden = false;
    linkUrl.focus();
  });
  form.querySelector('[data-link-cancel]').addEventListener('click', () => { linkBox.hidden = true; restore(); });
  form.querySelector('[data-link-save]').addEventListener('click', () => {
    let url = linkUrl.value.trim();
    try { if (!['https:', 'http:', 'mailto:'].includes(new URL(url).protocol)) throw new Error(); }
    catch { message.textContent = 'Podaj poprawny link https/http lub mailto.'; return; }
    if (existingLink) {
      range = document.createRange(); range.selectNodeContents(existingLink);
    }
    command('createLink', url);
    linkBox.hidden = true; message.textContent = '';
  });
  editor.addEventListener('paste', async e => {
    e.preventDefault(); remember();
    if (pasting) return;
    const raw = e.clipboardData.getData('text/html') || escapeHtml(e.clipboardData.getData('text/plain')).replaceAll('\n','<br>');
    pasting = true; editor.contentEditable = 'false';
    try {
      const response = await fetch('/editor/sanitize', {method:'POST',body:new URLSearchParams({html:raw})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      editor.contentEditable = 'true';
      command('insertHTML', data.html);
      message.textContent = 'Wklejono bezpieczną treść z obsługiwanym formatowaniem.';
    } catch { message.textContent = 'Nie udało się wkleić treści. Spróbuj ponownie.'; }
    finally { editor.contentEditable = 'true'; pasting = false; }
  });
  // Drop must not bypass the controlled paste path or insert external images.
  editor.addEventListener('drop', e => e.preventDefault());
  form.addEventListener('submit', e => {
    if (pasting) { e.preventDefault(); message.textContent = 'Poczekaj na zakończenie wklejania.'; return; }
    source.value = editor.innerHTML;
  });
  form.querySelector('[data-default-cta]').addEventListener('click', () => {
    const pl = form.elements.language.value === 'pl';
    form.elements.cta_label.value = pl ? 'Zobacz produkty' : 'Explore Products';
    form.elements.cta_url.value = pl ? 'https://bhm-chemicals.com/pl/produkty/' : 'https://bhm-chemicals.com/en/products/';
  });
  let imageUrl = null;
  form.querySelector('[data-banner-input]').addEventListener('change', e => {
    const img = form.querySelector('[data-banner-preview]');
    const file = e.target.files[0];
    if (!file) return;
    if (!['image/png','image/jpeg'].includes(file.type) || file.size > 5*1024*1024) {
      message.textContent = 'Baner musi być JPG/PNG, do 5 MB.'; e.target.value = ''; return;
    }
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = URL.createObjectURL(file); img.src = imageUrl; img.hidden = false;
  });
}

function initSelection() {
  const root = document.querySelector('[data-selection-url]');
  if (!root) return;
  const boxes = [...root.querySelectorAll('[data-recipient]')];
  const add = root.querySelector('[data-selection-add]');
  const clear = root.querySelector('[data-selection-clear]');
  const all = root.querySelector('[data-visible-all]');
  const summary = root.querySelector('[data-selection-summary]');
  const message = root.querySelector('[data-selection-message]');
  let added = new Set(boxes.filter(b => b.checked).map(b => Number(b.value)));
  let count = Number(root.dataset.selectionCount), eligible = Number(root.dataset.selectionEligible);
  // Templates/assets can change while an older Python process is still running.
  // Enable mutations only after the matching backend confirms this contract.
  let editable = false, ready = false, busy = false, revision = 0;
  const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('bhm-selection') : null;
  const pendingBoxes = () => boxes.filter(b => b.checked && !added.has(Number(b.value)) && b.dataset.eligible === 'true');
  function paint() {
    root.dataset.selectionReady = String(ready);
    boxes.forEach(b => {
      const saved = added.has(Number(b.value));
      b.disabled = busy || !editable || saved || b.dataset.eligible !== 'true';
      b.closest('td').querySelector('[data-membership]').textContent = saved ? 'Dodano' : '';
      b.closest('tr').dataset.added = String(saved);
    });
    const pending = pendingBoxes().length;
    root.querySelector('[data-pending-selected]').textContent = pending;
    root.querySelector('[data-total-selected]').textContent = count;
    add.disabled = busy || !editable || !pending;
    clear.disabled = busy || !editable || !count;
    summary.setAttribute('aria-disabled', String(busy || !editable || !eligible));
    const candidates = boxes.filter(b => b.dataset.eligible === 'true' && !added.has(Number(b.value)));
    all.disabled = busy || !editable || !candidates.length;
    all.checked = candidates.length > 0 && candidates.every(b => b.checked);
    all.indeterminate = pending > 0 && !all.checked;
  }
  function apply(data) {
    if (data.workflow !== 'explicit_add_v1' || !Array.isArray(data.selected_ids)) {
      throw new Error('Proces aplikacji nie obsługuje nowego wyboru odbiorców. Wymagana kontrolowana aktywacja.');
    }
    const previous = added;
    added = new Set(data.selected_ids);
    count = data.selected_count; eligible = data.eligible_count; editable = data.editable; ready = true;
    boxes.forEach(b => {
      const id = Number(b.value);
      if (added.has(id)) b.checked = true;
      else if (previous.has(id)) b.checked = false;
    });
    paint();
  }
  async function refresh() {
    if (busy) return;
    const atRevision = revision;
    try {
      const response = await fetch(root.dataset.selectionUrl, {cache:'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Błąd odczytu listy odbiorców.');
      if (!busy && revision === atRevision) apply(data);
    } catch {
      if (!busy && revision === atRevision) {
        ready = false; editable = false; paint();
        message.textContent = 'Nie można potwierdzić zgodności API ani odczytać listy. Wybór zablokowany. Sprawdź połączenie; starszy proces wymaga kontrolowanej aktywacji.';
      }
    }
  }
  async function save(isClear = false) {
    if (busy || !ready || !editable) return;
    const checked = pendingBoxes().map(b => b.value);
    if (!isClear && !checked.length) return;
    if (isClear && !window.confirm('Wyczyścić całą zapisaną listę odbiorców tej kampanii?')) return;
    busy = true; revision++; paint();
    message.textContent = 'Zapisywanie…';
    const body = new URLSearchParams({visible:boxes.map(b=>b.value).join(','), checked:checked.join(','),
      action:isClear?'clear':'add', confirm_clear:isClear?'1':'0'});
    try {
      const response = await fetch(root.dataset.selectionUrl, {method:'POST',body});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Nie udało się zapisać listy odbiorców.');
      apply(data);
      if (isClear) boxes.forEach(b => b.checked = false);
      message.textContent = isClear ? 'Wyczyszczono zapisaną listę odbiorców kampanii.' : `Zapisano odbiorców w kampanii. ${count} / 1000 dodanych.`;
      channel?.postMessage(root.dataset.selectionUrl);
    } catch (error) {
      message.textContent = `Nie potwierdzono zapisu. ${error.message || 'Sprawdź połączenie i odśwież stronę.'}`;
    } finally { busy = false; paint(); }
  }
  boxes.forEach(b => b.addEventListener('change', paint));
  all.addEventListener('change', () => {
    boxes.filter(b => !b.disabled).forEach(b => b.checked = all.checked);
    paint();
  });
  add.addEventListener('click', () => save());
  clear.addEventListener('click', () => save(true));
  summary.addEventListener('click', e => {if (summary.getAttribute('aria-disabled') === 'true') e.preventDefault();});
  channel?.addEventListener('message', e => {if(e.data === root.dataset.selectionUrl) refresh();});
  window.addEventListener('focus', refresh);
  window.addEventListener('pageshow', refresh);
  document.addEventListener('visibilitychange', () => {if(!document.hidden) refresh();});
  window.addEventListener('beforeunload', e => {if(busy){e.preventDefault();e.returnValue='';}});
  paint();
}

function duration(seconds) {
  seconds = Math.max(0, Math.round(seconds || 0));
  const hours = Math.floor(seconds/3600), minutes = Math.floor(seconds%3600/60), rest = seconds%60;
  return (hours ? `${hours}:` : '') + String(minutes).padStart(2,'0') + ':' + String(rest).padStart(2,'0');
}

function initMonitor() {
  const root = document.querySelector('[data-monitor-url]');
  if (!root) return;
  const labels = {running:'Wysyłanie',manual_paused:'Ręczna pauza',auto_break:'Automatyczna przerwa',auto_cooldown:'Tymczasowy cooldown SMTP',problem:'Problem — wymagana kontrola',interrupted:'Przerwane — sprawdź i wznów',completed:'Zakończone',completed_with_errors:'Zakończone z błędami'};
  const set = (key,value)=> {const target = root.querySelector(`[data-monitor="${key}"]`); if(target)target.textContent=String(value??'—');};
  async function poll() {
    try {
      const response = await fetch(root.dataset.monitorUrl,{cache:'no-store'});
      if (!response.ok) throw new Error();
      const d = await response.json();
      if (!d.execution_state) {set('state_label','Brak aktywnej kolejki');return;}
      const done = ['completed','completed_with_errors'].includes(d.execution_state);
      set('state_label',d.provider_wait?'Oczekiwanie na ograniczenia providera':labels[d.execution_state] || d.execution_state);
      set('mode', d.mode === 'dry_run' ? 'DRY-RUN / BEZ WYSYŁKI SMTP' : 'SMTP / WYSYŁKA KONTROLOWANA');
      Object.entries(d.counts).forEach(([key,value])=>set(key,value));
      set('current_email',d.current_email || 'Brak próby w toku'); set('next_email',d.next_email || 'Brak');
      set('elapsed',duration(d.elapsed_seconds)); set('active',duration(d.active_seconds));
      set('eta',d.eta_uncertain?'Wstrzymane / niepewne':`Około ${Math.ceil(d.eta_seconds/60)} min`);
      set('finish',d.eta_finish?`Około ${new Date(d.eta_finish).toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Warsaw'})}`:'Niepewne');
      set('interval','20 s / jedna próba'); set('next_attempt',done?'—':duration(d.next_attempt_seconds));
      set('next_break',done?'—':d.cooldown_seconds?`Trwa przerwa: ${duration(d.cooldown_seconds)}`:duration(d.next_break_seconds));
      set('progress',d.percent+'%'); root.querySelector('[data-monitor-progress]').style.width=d.percent+'%';
      set('notice',d.manual_pause ? (d.current_email?'Pauza zlecona — trwa kończenie rozpoczętej próby.':'Kampania oczekuje na ręczne wznowienie.') : d.execution_state==='auto_cooldown'?`${d.problem} Najwcześniejsza bezpieczna próba ${new Date(d.resume_at).toLocaleTimeString('pl-PL',{timeZone:'Europe/Warsaw'})}, za ${duration(d.smtp_cooldown_seconds)}. ${d.failure_detail}`:d.execution_state==='auto_break'?`Automatyczna przerwa 5 minut — wznowienie za ${duration(d.cooldown_seconds)}.`:d.problem || (done?'Kolejka rozliczona. Błędy i niepewne próby sprawdź w historii.':'Kolejka pracuje w tle.'));
      set('quality_warning',d.quality_warning || '');
      root.querySelector('[data-monitor="quality_warning"]').hidden=!d.quality_warning;
      root.querySelector('[data-control="pause"]').disabled=done || d.manual_pause;
      root.querySelector('[data-control="resume"]').disabled=done || (!d.manual_pause&&!['problem','interrupted'].includes(d.execution_state));
      root.querySelector('[data-monitor-events]').innerHTML=d.recent_events.map(e=>`<li><time>${escapeHtml(new Date(e.created*1000).toLocaleTimeString('pl-PL'))}</time> ${escapeHtml(e.message)}</li>`).join('');
    } catch {set('notice','Brak połączenia z aplikacją. Status może być nieaktualny.');}
  }
  root.querySelectorAll('[data-control]').forEach(button=>button.addEventListener('click',async()=> {
    button.disabled=true; const errorBox=root.querySelector('[data-control-error]');
    try {const response=await fetch(`/campaigns/${root.dataset.campaignId}/${button.dataset.control}`,{method:'POST'});const data=await response.json();if(!response.ok)throw new Error(data.error);errorBox.hidden=true;}
    catch(error){errorBox.textContent=error.message;errorBox.hidden=false;}
    await poll();
  }));
  poll(); window.setInterval(poll,2500);
}

const previewFrame=document.querySelector('[data-preview-frame]');
function fitPreview() {
  if(!previewFrame?.contentDocument?.body)return;
  previewFrame.style.minHeight='0'; previewFrame.style.height='1px';
  previewFrame.style.height=previewFrame.contentDocument.body.scrollHeight+'px';
}
previewFrame?.addEventListener('load',()=> {fitPreview();previewFrame.contentDocument.querySelectorAll('img').forEach(img=>img.addEventListener('load',fitPreview));});
document.querySelectorAll('[data-preview-size]').forEach(b=>b.addEventListener('click',()=> {previewFrame.style.width=b.dataset.previewSize==='mobile'?'360px':'100%';requestAnimationFrame(fitPreview);}));
document.querySelector('[data-preview-images]')?.addEventListener('click',()=> {
  const frame=document.querySelector('[data-preview-frame]');
  const body=frame.contentDocument?.body;
  if(!body)return;
  const hide=body.dataset.imagesHidden!=='true'; body.dataset.imagesHidden=String(hide);
  body.querySelectorAll('img').forEach(img=> {if(hide){img.dataset.originalSrc=img.src;img.removeAttribute('src');}else if(img.dataset.originalSrc)img.src=img.dataset.originalSrc;});
  requestAnimationFrame(fitPreview);
});
initRichEditor(); initSelection(); initMonitor();


function initMailSync() {
  const root = document.querySelector('[data-mail-sync]');
  if (!root) return;
  const button = root.querySelector('button');
  const set = (key,value) => { root.querySelector(`[data-sync="${key}"]`).textContent = value ?? '—'; };
  const date = value => value ? new Date(value*1000).toLocaleString('pl-PL',{timeZone:'Europe/Warsaw'}) : '—';
  let busy=false;
  async function refresh() {
    try {
      const r=await fetch('/mail-sync/status.json',{cache:'no-store'});
      if (!r.ok) throw new Error();
      const d=await r.json();
      set('connection',({active:'Aktywne',waiting:'Oczekiwanie na pierwszy skan',error:'Błąd',configuration_required:'Konfiguracja wymagana'})[d.connection]);
      set('last',date(d.last_success));set('next',d.scanning?'Skanowanie…':date(d.next_sync));
      for (const k of ['new_messages','hard_bounces','unsubscribes','reviews','alerts','contact_changes']) set(k,d[k]||0);
      set('error',d.last_error||'Brak');set('coverage',d.unsubscribe_coverage);
      button.disabled=busy || !d.enabled || d.connection==='configuration_required' || !!d.scanning || !!d.requested;
    } catch { set('connection','Brak połączenia z aplikacją');button.disabled=true; }
  }
  button.addEventListener('click',async()=>{
    busy=true;button.disabled=true;
    try {
      const r=await fetch('/mail-sync/check',{method:'POST'});
      if (!r.ok && r.status!==409) { const d=await r.json();set('error',d.error||'Błąd zlecenia skanu'); }
    } finally { busy=false;await refresh(); }
  });
  refresh();setInterval(refresh,5000);
}
if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',initMailSync); else initMailSync();

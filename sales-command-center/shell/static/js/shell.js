'use strict';

// ======================================================================
// Icons registry — SVG strings keyed by glyph name
// ======================================================================
const ICONS = {
  account: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>`,
  chart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
  </svg>`,
  pipeline: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>`,
  analytics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6" y1="20" x2="6" y2="14"/>
  </svg>`,
  team: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 00-3-3.87"/>
    <path d="M16 3.13a4 4 0 010 7.75"/>
  </svg>`,
  route: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M3 12h3l3-9 4 18 3-9h5"/>
  </svg>`,
  visit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
    <circle cx="12" cy="10" r="3"/>
  </svg>`,
  merch: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <rect x="2" y="3" width="20" height="5" rx="1"/>
    <path d="M2 8v13h20V8"/>
    <line x1="8" y1="14" x2="16" y2="14"/>
    <line x1="8" y1="18" x2="16" y2="18"/>
  </svg>`,
  survey: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
  </svg>`,
  orders: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>`,
};

// ======================================================================
// State
// ======================================================================
const state = {
  currentView: 'home',
  activeAppId: null,
  iframePool: new Map(),   // appId -> iframe element
  iframeLRU: [],           // [appId, ...] oldest first
  LRU_LIMIT: 5,
  recentApps: [],          // [{id, title, path, glyph, glyphColor}, ...]
  dreamReport: null,
};

// ======================================================================
// DOM refs
// ======================================================================
const $ = id => document.getElementById(id);
const dom = {
  appTitle:       $('app-title'),
  appSubtitle:    $('app-subtitle'),
  appGlyph:       $('app-glyph'),
  searchInput:    $('search-input'),
  searchResults:  $('search-results'),
  iframePool:     $('iframe-pool'),
  dreamRunBtn:    $('dream-run-btn'),
  dreamOutput:    $('dream-output'),
  dreamHistoryList: $('dream-history-list'),
};

// ======================================================================
// Toast
// ======================================================================
let toastContainer = null;
function ensureToastContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }
}
function toast(msg, type = 'success') {
  ensureToastContainer();
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ======================================================================
// Navigation
// ======================================================================
function activateSidebarItem(viewName) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const map = {
    'home': 'nav-dashboard',
    'section-internal': 'nav-internal',
    'section-external': 'nav-external',
    'favorites': 'nav-favorites',
    'recent': 'nav-recent',
    'dream': 'nav-dream',
    'ai-chat': 'nav-ai-chat',
    'settings': 'nav-settings',
  };
  const navId = map[viewName] || map['home'];
  const el = $(navId);
  if (el) el.classList.add('active');
}

function showView(viewName) {
  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.style.display = 'none');

  const mapping = {
    'home':             'view-home',
    'section-internal': 'view-home',
    'section-external': 'view-home',
    'app':              'view-app',
    'concept':          'view-concept',
    'dream':            'view-dream',
    'settings':         'view-settings',
    'favorites':        'view-favorites',
    'recent':           'view-recent',
    'ai-chat':          'view-ai-chat',
  };

  const viewId = mapping[viewName] || 'view-home';
  const viewEl = $(viewId);
  if (viewEl) viewEl.style.display = 'block';

  // Scroll section into view for section-specific nav
  if (viewName === 'section-internal' || viewName === 'section-external') {
    const sectionId = viewName === 'section-internal' ? 'internal' : 'external';
    setTimeout(() => {
      const block = document.querySelector(`.section-block[data-section="${sectionId}"]`);
      if (block) block.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }

  activateSidebarItem(viewName);
  state.currentView = viewName;
}

function setHeaderForApp(appInfo) {
  dom.appTitle.textContent = appInfo.title;
  dom.appSubtitle.textContent = appInfo.subtitle;
  dom.appGlyph.style.display = 'flex';
  dom.appGlyph.style.background = appInfo.glyph_color + '22';
  dom.appGlyph.style.border = '1px solid ' + appInfo.glyph_color + '44';
  dom.appGlyph.style.color = appInfo.glyph_color;
  dom.appGlyph.innerHTML = ICONS[appInfo.glyph] || ICONS['analytics'];
}

function filterSections(sectionId) {
  document.querySelectorAll('.section-block').forEach(block => {
    block.style.display = (!sectionId || block.dataset.section === sectionId) ? '' : 'none';
  });
}

function setHeaderForShell(title, subtitle) {
  dom.appTitle.textContent = title || 'Sales Command Center';
  dom.appSubtitle.textContent = subtitle || 'One unified platform. All your sales tools.';
  dom.appGlyph.style.display = 'none';
}

// ======================================================================
// App launching + iframe pool
// ======================================================================
function showConceptImage(appInfo) {
  setHeaderForApp(appInfo);
  showView('concept');
  document.getElementById('concept-img').src = `/static/${appInfo.concept_image}`;
  document.getElementById('concept-app-label').textContent = appInfo.title;
}

function launchApp(appInfo) {
  logActivity('app_open', appInfo.title);
  addToRecent(appInfo);

  if (appInfo.concept_image) {
    showConceptImage(appInfo);
    return;
  }

  setHeaderForApp(appInfo);
  showView('app');

  // Check if iframe exists in pool
  if (!state.iframePool.has(appInfo.id)) {
    // Evict LRU if at limit
    if (state.iframeLRU.length >= state.LRU_LIMIT) {
      const evictId = state.iframeLRU.shift();
      const evictFrame = state.iframePool.get(evictId);
      if (evictFrame) {
        evictFrame.src = 'about:blank';
        evictFrame.remove();
        state.iframePool.delete(evictId);
      }
    }

    const iframe = document.createElement('iframe');
    iframe.src = `/apps/${appInfo.path}/`;
    iframe.dataset.appId = appInfo.id;
    iframe.title = appInfo.title;
    dom.iframePool.appendChild(iframe);
    state.iframePool.set(appInfo.id, iframe);
    state.iframeLRU.push(appInfo.id);
  } else {
    // Move to end of LRU (most recently used)
    state.iframeLRU = state.iframeLRU.filter(id => id !== appInfo.id);
    state.iframeLRU.push(appInfo.id);
  }

  // Show only the active iframe
  state.iframePool.forEach((iframe, id) => {
    iframe.classList.toggle('active', id === appInfo.id);
  });

  state.activeAppId = appInfo.id;
}

function addToRecent(appInfo) {
  state.recentApps = state.recentApps.filter(a => a.id !== appInfo.id);
  state.recentApps.unshift(appInfo);
  if (state.recentApps.length > 10) state.recentApps.pop();
}

// Tear down all iframes (on logout, called by server redirect)
function teardownPool() {
  state.iframePool.forEach((iframe) => {
    iframe.src = 'about:blank';
    iframe.remove();
  });
  state.iframePool.clear();
  state.iframeLRU = [];
  state.activeAppId = null;
}

// ======================================================================
// All apps flat list (from config)
// ======================================================================
function getAllApps() {
  const all = [];
  for (const section of APPS_CONFIG.sections) {
    for (const app of section.apps) {
      all.push({ ...app, sectionId: section.id, sectionLabel: section.label });
    }
  }
  return all;
}

// ======================================================================
// Inject card icons after render
// ======================================================================
function injectCardIcons() {
  document.querySelectorAll('.card-icon[data-glyph]').forEach(el => {
    const glyph = el.dataset.glyph;
    el.innerHTML = ICONS[glyph] || ICONS['analytics'];
  });
}

// ======================================================================
// Search
// ======================================================================
const allApps = getAllApps();

function doSearch(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    dom.searchResults.classList.remove('open');
    return;
  }
  const matches = allApps.filter(a =>
    a.title.toLowerCase().includes(q) ||
    a.subtitle.toLowerCase().includes(q)
  );
  if (matches.length === 0) {
    dom.searchResults.innerHTML = '<div style="padding:12px 14px;font-size:0.83rem;color:var(--text-dim);">No results</div>';
  } else {
    dom.searchResults.innerHTML = matches.map(a => `
      <div class="search-result-item" data-app-id="${a.id}">
        <span class="search-result-dot" style="background:${a.glyph_color}"></span>
        <div>
          <div class="sri-title">${a.title}</div>
          <div class="sri-sub">${a.sectionLabel}</div>
        </div>
      </div>
    `).join('');
    dom.searchResults.querySelectorAll('.search-result-item').forEach(el => {
      el.addEventListener('click', () => {
        const app = allApps.find(a => a.id === el.dataset.appId);
        if (app) launchApp(app);
        dom.searchInput.value = '';
        dom.searchResults.classList.remove('open');
      });
    });
  }
  dom.searchResults.classList.add('open');
}

dom.searchInput.addEventListener('input', e => doSearch(e.target.value));
dom.searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    dom.searchInput.value = '';
    dom.searchResults.classList.remove('open');
  }
});
document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrap')) dom.searchResults.classList.remove('open');
});

// ======================================================================
// Activity logging
// ======================================================================
function logActivity(type, detail) {
  fetch('/api/activity/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, detail }),
  }).catch(() => {});
}

// ======================================================================
// Dream
// ======================================================================
function renderDreamReport(report) {
  if (!report) return;
  state.dreamReport = report;

  let html = `<div class="dream-report">
    <h3>Dream Report</h3>
    <div class="dream-meta">Generated ${report.saved_at || ''} &mdash; ${report.role || ''} view</div>`;

  if (report.tardy_accounts && report.tardy_accounts.length > 0) {
    html += `<div class="dream-section">
      <h4>Potentially Tardy Orders (&gt;${report.tardy_days} days)</h4>
      <table class="dream-table">
        <thead><tr><th>Account</th><th>Last Order</th><th>Days Ago</th><th>State</th></tr></thead>
        <tbody>`;
    for (const a of report.tardy_accounts) {
      html += `<tr>
        <td>${a.account_name}</td>
        <td>${a.last_order_date || 'N/A'}</td>
        <td><span class="flag-badge flag-tardy">${a.days_since_order}d</span></td>
        <td>${a.state}</td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  if (report.stale_quotes && report.stale_quotes.length > 0) {
    html += `<div class="dream-section">
      <h4>Expired Quotes – Follow Up (&gt;${report.quote_stale_days} days open)</h4>
      <table class="dream-table">
        <thead><tr><th>Account</th><th>Quote ID</th><th>Amount</th><th>Created</th><th>Days Open</th></tr></thead>
        <tbody>`;
    for (const q of report.stale_quotes) {
      html += `<tr>
        <td>${q.account_name}</td>
        <td>${q.quote_id}</td>
        <td>$${q.amount.toLocaleString()}</td>
        <td>${q.created_date}</td>
        <td><span class="flag-badge flag-stale">${q.days_open}d</span></td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  if (report.new_equipment_quotes && report.new_equipment_quotes.length > 0) {
    html += `<div class="dream-section">
      <h4>New Equipment Quotes (last ${report.new_equipment_days} days) — Your Territory</h4>
      <table class="dream-table">
        <thead><tr><th>Account</th><th>Quote ID</th><th>Amount</th><th>Created</th><th>State</th></tr></thead>
        <tbody>`;
    for (const q of report.new_equipment_quotes) {
      html += `<tr>
        <td>${q.account_name}</td>
        <td>${q.quote_id}</td>
        <td>$${q.amount.toLocaleString()}</td>
        <td>${q.created_date}</td>
        <td><span class="flag-badge flag-new">${q.state}</span></td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  if (report.expired_equipment_quotes && report.expired_equipment_quotes.length > 0) {
    html += `<div class="dream-section">
      <h4>Equipment Quotes Expired &gt;${report.equipment_expired_days} days — Your Territory</h4>
      <table class="dream-table">
        <thead><tr><th>Account</th><th>Quote ID</th><th>Amount</th><th>Expires</th><th>State</th></tr></thead>
        <tbody>`;
    for (const q of report.expired_equipment_quotes) {
      html += `<tr>
        <td>${q.account_name}</td>
        <td>${q.quote_id}</td>
        <td>$${q.amount.toLocaleString()}</td>
        <td>${q.expires_date}</td>
        <td><span class="flag-badge flag-stale">${q.state}</span></td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  if (!report.tardy_accounts?.length && !report.stale_quotes?.length &&
      !report.new_equipment_quotes?.length && !report.expired_equipment_quotes?.length) {
    html += `<div style="padding:20px;color:var(--text-dim);font-size:0.85rem;">
      No flags found. All accounts are in good standing.
    </div>`;
  }

  html += `</div>`;
  dom.dreamOutput.innerHTML = html;
}

async function runDream() {
  dom.dreamRunBtn.textContent = 'Running…';
  dom.dreamRunBtn.classList.add('loading');
  try {
    const res = await fetch('/api/dream/run', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      renderDreamReport(data.report);
      toast('Dream report complete.', 'success');
      loadDreamHistory();
    } else {
      toast('Dream failed: ' + (data.error || 'Unknown error'), 'error');
    }
  } catch (e) {
    toast('Network error running Dream.', 'error');
  } finally {
    dom.dreamRunBtn.textContent = 'Run Dream Now';
    dom.dreamRunBtn.classList.remove('loading');
  }
}

async function loadDreamHistory() {
  try {
    const res = await fetch('/api/dream/history');
    const history = await res.json();
    if (!history.length) {
      dom.dreamHistoryList.innerHTML = '<p style="font-size:0.82rem;color:var(--text-dim);">No history yet.</p>';
      return;
    }
    dom.dreamHistoryList.innerHTML = history.map((r, i) => `
      <div class="dream-history-item" data-idx="${i}">
        <span>Dream Report — ${r.saved_at || 'Unknown date'}</span>
        <span class="dhi-date">${r.role || ''}</span>
      </div>
    `).join('');
    dom.dreamHistoryList.querySelectorAll('.dream-history-item').forEach(el => {
      el.addEventListener('click', () => {
        renderDreamReport(history[parseInt(el.dataset.idx)]);
        dom.dreamOutput.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  } catch (e) {}
}

dom.dreamRunBtn?.addEventListener('click', runDream);

// ======================================================================
// Settings
// ======================================================================
function initSettingsTabs() {
  document.querySelectorAll('.settings-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const name = tab.dataset.tab;
      document.querySelectorAll('.settings-section').forEach(s => s.style.display = 'none');
      $(`settings-${name}`).style.display = 'block';
    });
  });
}

function buildCardsConfig() {
  const list = $('cards-config-list');
  if (!list) return;
  list.innerHTML = '';
  for (const section of APPS_CONFIG.sections) {
    for (const app of section.apps) {
      const item = document.createElement('div');
      item.className = 'card-config-item';
      item.dataset.appId = app.id;
      const hasImage = !!app.concept_image;
      item.innerHTML = `
        <h4>${app.title} <span style="color:var(--text-dim);font-size:0.75rem;font-weight:400;">(${section.label})</span></h4>
        <div class="card-config-grid">
          <div class="form-group">
            <label>Title</label>
            <input type="text" data-field="title" value="${app.title}">
          </div>

          <div class="form-group" style="grid-column:1/-1;">
            <label>Subtitle / Description</label>
            <input type="text" data-field="subtitle" value="${app.subtitle}">
          </div>
          <div class="form-group">
            <label>Glyph Color</label>
            <input type="text" data-field="glyph_color" value="${app.glyph_color}">
          </div>
        </div>
        <div class="concept-upload-row">
          <label>Concept Image</label>
          <div class="concept-upload-inner" id="concept-inner-${app.id}">
            ${hasImage
              ? `<img class="concept-thumb" src="/static/${app.concept_image}" alt="">`
              : `<span class="concept-none">No image set</span>`}
            <label class="btn-upload">
              ${hasImage ? 'Replace' : 'Choose Image'}
              <input type="file" class="concept-file-input" accept="image/*" data-app-id="${app.id}">
            </label>
            ${hasImage
              ? `<button class="btn-clear-concept" data-app-id="${app.id}">Clear</button>`
              : ''}
          </div>
        </div>
      `;
      list.appendChild(item);

      // File upload handler
      item.querySelector('.concept-file-input').addEventListener('change', async function () {
        if (!this.files.length) return;
        const appId = this.dataset.appId;
        const formData = new FormData();
        formData.append('image', this.files[0]);
        try {
          const res = await fetch(`/api/upload/concept/${appId}`, { method: 'POST', body: formData });
          const data = await res.json();
          if (data.ok) {
            // Update in-memory config
            const appEntry = getAllApps().find(a => a.id === appId);
            if (appEntry) appEntry.concept_image = data.path;
            for (const section of APPS_CONFIG.sections) {
              const a = section.apps.find(x => x.id === appId);
              if (a) a.concept_image = data.path;
            }
            toast(`Concept image set for ${appId}.`, 'success');
            buildCardsConfig(); // refresh the settings panel
          } else {
            toast('Upload failed: ' + (data.error || 'Unknown'), 'error');
          }
        } catch (e) {
          toast('Network error during upload.', 'error');
        }
      });

      // Clear button handler (only present when image is set)
      const clearBtn = item.querySelector('.btn-clear-concept');
      if (clearBtn) {
        clearBtn.addEventListener('click', async function () {
          const appId = this.dataset.appId;
          try {
            const res = await fetch(`/api/upload/concept/${appId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.ok) {
              for (const section of APPS_CONFIG.sections) {
                const a = section.apps.find(x => x.id === appId);
                if (a) delete a.concept_image;
              }
              toast(`Concept image cleared for ${appId}.`, 'success');
              buildCardsConfig();
            } else {
              toast('Clear failed.', 'error');
            }
          } catch (e) {
            toast('Network error clearing image.', 'error');
          }
        });
      }
    }
  }
}

async function saveCardsConfig() {
  // Read edited values back into APPS_CONFIG
  document.querySelectorAll('.card-config-item').forEach(item => {
    const appId = item.dataset.appId;
    for (const section of APPS_CONFIG.sections) {
      const app = section.apps.find(a => a.id === appId);
      if (app) {
        item.querySelectorAll('[data-field]').forEach(input => {
          const field = input.dataset.field;
          app[field] = input.value;
        });
      }
    }
  });
  try {
    const res = await fetch('/api/config/apps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(APPS_CONFIG),
    });
    const data = await res.json();
    if (data.ok) toast('Card config saved.', 'success');
    else toast('Save failed.', 'error');
  } catch (e) {
    toast('Network error saving config.', 'error');
  }
}

async function loadDreamConfig() {
  try {
    const res = await fetch('/api/config/dream');
    const cfg = await res.json();
    $('cfg-tardy-days').value = cfg.tardy_days_threshold ?? 35;
    $('cfg-top-accounts').value = cfg.top_accounts_count ?? 200;
    $('cfg-quote-stale').value = cfg.quote_stale_days ?? 30;
    $('cfg-equip-new').value = cfg.new_equipment_days ?? 7;
    $('cfg-equip-expired').value = cfg.equipment_expired_days ?? 30;
    $('cfg-cities').value = (cfg.monitored_cities || []).join(', ');
  } catch (e) {}
}

async function saveDreamConfig() {
  const cfg = {
    tardy_days_threshold: parseInt($('cfg-tardy-days').value) || 35,
    top_accounts_count:   parseInt($('cfg-top-accounts').value) || 200,
    quote_stale_days:     parseInt($('cfg-quote-stale').value) || 30,
    new_equipment_days:   parseInt($('cfg-equip-new').value) || 7,
    equipment_expired_days: parseInt($('cfg-equip-expired').value) || 30,
    monitored_cities:     $('cfg-cities').value.split(',').map(s => s.trim()).filter(Boolean),
    schedule: '0 6 * * 0',
  };
  try {
    const res = await fetch('/api/config/dream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
    const data = await res.json();
    if (data.ok) toast('Dream config saved.', 'success');
    else toast('Save failed.', 'error');
  } catch (e) {
    toast('Network error saving dream config.', 'error');
  }
}

$('save-cards-btn')?.addEventListener('click', saveCardsConfig);
$('save-dream-cfg-btn')?.addEventListener('click', saveDreamConfig);

// ======================================================================
// Sidebar navigation clicks
// ======================================================================
document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    const view = el.dataset.view;

    if (view === 'home') {
      setHeaderForShell();
      state.activeAppId = null;
      filterSections(null);
    }
    if (view === 'section-internal') {
      setHeaderForShell('Internal Rep', 'Tools and insights designed for internal sales teams.');
      state.activeAppId = null;
      filterSections('internal');
    }
    if (view === 'section-external') {
      setHeaderForShell('External Rep', 'Essential tools for reps in the field.');
      state.activeAppId = null;
      filterSections('external');
    }

    if (view === 'settings') {
      setHeaderForShell('Settings', 'Global configuration');
      buildCardsConfig();
      loadDreamConfig();
    }

    if (view === 'dream') {
      setHeaderForShell('Dream', 'Weekly account health analysis');
      loadDreamHistory();
    }

    if (view === 'recent') {
      setHeaderForShell('Recently Used', '');
      buildRecentGrid();
    }

    if (view === 'ai-chat') {
      setHeaderForShell('AI Chat', 'Your eye-care assistant.');
      const iframe = $('ai-chat-iframe');
      if (iframe && !iframe.dataset.loaded) {
        iframe.src = '/apps/eyecare-assistant/';
        iframe.dataset.loaded = '1';
      }
    }

    showView(view);
  });
});

// ======================================================================
// Card clicks
// ======================================================================
document.querySelectorAll('.app-card').forEach(card => {
  card.addEventListener('click', () => {
    const appId = card.dataset.appId;
    const app = allApps.find(a => a.id === appId);
    if (app) launchApp(app);
  });
});

// View all links
document.querySelectorAll('.view-all-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const sectionId = link.dataset.section;
    filterSections(sectionId);
    showView(`section-${sectionId}`);
  });
});

// ======================================================================
// Recent grid
// ======================================================================
function buildRecentGrid() {
  const grid = $('recent-cards-grid');
  if (!grid) return;
  if (!state.recentApps.length) {
    grid.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;">No recently used apps.</p>';
    return;
  }
  grid.innerHTML = state.recentApps.map(app => `
    <div class="app-card" style="cursor:pointer;" data-app-id="${app.id}">
      <div class="card-hero" style="background:linear-gradient(135deg,${app.glyph_color}18,${app.glyph_color}08);height:70px;"></div>
      <div class="card-body">
        <div class="card-icon-wrap" style="background:${app.glyph_color}22;border-color:${app.glyph_color}33;">
          <div class="card-icon" style="color:${app.glyph_color};">${ICONS[app.glyph] || ''}</div>
        </div>
        <div class="card-text">
          <h3 class="card-title">${app.title}</h3>
        </div>
      </div>
    </div>
  `).join('');
  grid.querySelectorAll('.app-card').forEach(card => {
    card.addEventListener('click', () => {
      const app = allApps.find(a => a.id === card.dataset.appId);
      if (app) launchApp(app);
    });
  });
}

// ======================================================================
// Init
// ======================================================================
function init() {
  injectCardIcons();
  initSettingsTabs();
  filterSections(null);
  showView('home');
  setHeaderForShell();
}

init();

'use strict';

// --- Map setup ---
const map = L.map('map', { zoomControl: true }).setView([37.5, -95.5], 4);
// Dark tile layer via CartoDB Dark Matter (free, no key)
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19,
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
}).addTo(map);

let routeLayer = null;
let markerLayer = L.layerGroup().addTo(map);
let allResults = [];

// --- Marker icons ---
function makeIcon(color) {
  const colors = { green: '#4ade80', orange: '#fb923c', gray: '#6b7280' };
  const fill = colors[color] || colors.gray;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
    <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z"
      fill="${fill}" stroke="#fff" stroke-width="1.5"/>
    <circle cx="12" cy="12" r="5" fill="#fff"/>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [24, 36],
    iconAnchor: [12, 36],
    popupAnchor: [0, -36],
  });
}

// --- Form submission ---
document.getElementById('search-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitSearch();
});

async function submitSearch() {
  const form = document.getElementById('search-form');
  const fileInput = document.getElementById('doc-file');
  const hasFile = fileInput.files.length > 0;

  setLoading(true);
  hideError();

  let body;
  let fetchOptions;

  if (hasFile) {
    body = new FormData(form);
    fetchOptions = { method: 'POST', body };
  } else {
    const keywords = document.getElementById('keywords').value
      .split(',').map(k => k.trim()).filter(Boolean);
    body = {
      origin: document.getElementById('origin').value.trim(),
      destination: document.getElementById('destination').value.trim(),
      corridor_miles: parseFloat(document.getElementById('corridor').value),
      query: document.getElementById('query').value.trim(),
      criteria_keywords: keywords,
      document_url: document.getElementById('gsheet-url').value.trim() || null,
    };
    fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    };
  }

  try {
    const resp = await fetch('api/search', fetchOptions);
    const data = await resp.json();

    if (!resp.ok || data.error) {
      showError(data.error || `Server error ${resp.status}`);
      setLoading(false);
      return;
    }

    renderMap(data);
    renderResults(data);
    showMeta(data.meta);
  } catch (err) {
    showError('Network error: ' + err.message);
  }

  setLoading(false);
}

// --- Map rendering ---
function renderMap(data) {
  // Clear previous layers
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
  markerLayer.clearLayers();

  // Draw route polyline (GeoJSON coords are [lon, lat])
  const latLngs = data.route_geojson.coordinates.map(c => [c[1], c[0]]);
  routeLayer = L.polyline(latLngs, { color: '#4f9cf9', weight: 4, opacity: 0.9 }).addTo(map);

  // Origin / destination markers
  const pinIcon = makeIcon('gray');
  L.marker([data.origin.lat, data.origin.lon], { icon: pinIcon })
    .bindPopup(`<strong>Start:</strong><br>${data.origin.label}`)
    .addTo(markerLayer);
  L.marker([data.destination.lat, data.destination.lon], { icon: pinIcon })
    .bindPopup(`<strong>End:</strong><br>${data.destination.label}`)
    .addTo(markerLayer);

  // Result markers
  data.results.forEach((r, i) => {
    const hasMatches = r.keyword_matches && r.keyword_matches.length > 0;
    const wasScraped = r.scraped !== false;
    const color = hasMatches ? 'green' : wasScraped ? 'orange' : 'gray';

    const marker = L.marker([r.lat, r.lon], { icon: makeIcon(color) })
      .bindPopup(buildPopup(r, i + 1))
      .addTo(markerLayer);

    // Store marker ref so result cards can trigger flyTo
    r._marker = marker;
  });

  map.fitBounds(routeLayer.getBounds().pad(0.1));
}

function buildPopup(r, n) {
  const scraped = r.scraped !== false;
  const matchBadges = scraped ? (r.keyword_matches || []).map(k =>
    `<span class="badge badge-match">${k}</span>`).join(' ') : '';
  const missBadges = scraped ? (r.keyword_misses || []).map(k =>
    `<span class="badge badge-miss">${k}</span>`).join(' ') : '';
  const websiteLink = r.website_url
    ? `<a href="${r.website_url}" target="_blank" rel="noopener">Visit website</a>` : '';
  const addr = r.address ? `<div class="popup-addr">${r.address}</div>` : '';
  const dist = r.distance_off_route_miles != null
    ? `<div class="popup-dist">${r.distance_off_route_miles} mi off route</div>` : '';

  return `
    <div class="popup-content">
      <strong>#${n} ${r.name}</strong>
      ${addr}${dist}
      <div class="popup-badges">${matchBadges}${missBadges}</div>
      ${websiteLink}
    </div>`;
}

// --- Results list rendering ---
function renderResults(data) {
  const header = document.getElementById('results-header');
  const count = document.getElementById('results-count');
  const subtitle = document.getElementById('results-subtitle');

  allResults = data.results || [];
  allResults.forEach((r, i) => { r._origIdx = i; });

  count.textContent = `${allResults.length} result${allResults.length !== 1 ? 's' : ''}`;
  subtitle.textContent = `along ${data.meta.route_distance_km} km route`;
  header.classList.remove('hidden');

  document.getElementById('filter-matched').onchange = applyFilters;
  document.getElementById('filter-unmatched').onchange = applyFilters;

  applyFilters();
}

function applyFilters() {
  const showMatched = document.getElementById('filter-matched').checked;
  const showUnmatched = document.getElementById('filter-unmatched').checked;

  const filtered = allResults.filter(r => {
    const hasMatches = r.keyword_matches && r.keyword_matches.length > 0;
    return hasMatches ? showMatched : showUnmatched;
  });

  renderCards(filtered);
}

function renderCards(results) {
  const list = document.getElementById('results-list');

  if (results.length === 0) {
    list.innerHTML = '<div class="empty-state"><p>No results match the current filter.</p></div>';
    return;
  }

  list.innerHTML = results.map((r, i) => buildCard(r, i + 1, r._origIdx)).join('');

  list.querySelectorAll('.result-card').forEach(card => {
    card.addEventListener('click', () => {
      const r = allResults[parseInt(card.dataset.index)];
      map.flyTo([r.lat, r.lon], 14, { duration: 0.8 });
      if (r._marker) r._marker.openPopup();
      list.querySelectorAll('.result-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
    });
  });
}

function buildCard(r, num, origIdx) {
  const hasMatches = r.keyword_matches && r.keyword_matches.length > 0;
  const wasScraped = r.scraped !== false;
  const borderClass = hasMatches ? 'card-green' : wasScraped ? 'card-orange' : 'card-gray';

  const matchBadges = wasScraped ? (r.keyword_matches || []).map(k =>
    `<span class="badge badge-match">${k}</span>`).join('') : '';
  const missBadges = wasScraped ? (r.keyword_misses || []).map(k =>
    `<span class="badge badge-miss">${k}</span>`).join('') : '';

  const distText = r.distance_off_route_miles != null
    ? `<span class="card-dist">${r.distance_off_route_miles} mi off route</span>` : '';
  const addrText = r.address ? `<div class="card-addr">${r.address}</div>` : '';
  const phoneText = r.phone ? `<div class="card-phone">${r.phone}</div>` : '';

  const websiteText = r.website_url
    ? `<a class="card-link" href="${r.website_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">&#8599; website</a>` : '';
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${r.lat},${r.lon}`;
  const directionsText = `<a class="card-link" href="${directionsUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()">&#8599; directions</a>`;

  const scrapeNote = !wasScraped && r.scrape_error
    ? `<div class="scrape-note">&#9888; Could not scrape website</div>` : '';

  return `
    <div class="result-card ${borderClass}" data-index="${origIdx}">
      <div class="card-header">
        <span class="card-num">${num}</span>
        <div class="card-title-wrap">
          <strong class="card-name">${r.name}</strong>
          ${distText}
        </div>
        <div class="card-links">${websiteText}${directionsText}</div>
      </div>
      ${addrText}
      ${phoneText}
      <div class="card-badges">${matchBadges}${missBadges}</div>
      ${scrapeNote}
    </div>`;
}

// --- UI helpers ---
function setLoading(on) {
  const btn = document.getElementById('search-btn');
  const label = document.getElementById('btn-label');
  const spinner = document.getElementById('btn-spinner');
  btn.disabled = on;
  label.textContent = on ? 'Searching...' : 'Search Route';
  spinner.classList.toggle('hidden', !on);
}

function showError(msg) {
  const box = document.getElementById('error-box');
  box.textContent = msg;
  box.classList.remove('hidden');
}

function hideError() {
  document.getElementById('error-box').classList.add('hidden');
}

function showMeta(meta) {
  const box = document.getElementById('meta-box');
  const text = document.getElementById('meta-text');
  text.textContent = `${meta.total_candidates} candidates found → ${meta.after_corridor_filter} in corridor → ${meta.scrape_attempted} websites checked · ${meta.duration_seconds}s`;
  box.classList.remove('hidden');
}

function handleFileSelect(input) {
  const display = document.getElementById('file-name-display');
  display.textContent = input.files.length > 0 ? input.files[0].name : 'Choose file...';
  if (input.files.length > 0) {
    document.getElementById('gsheet-url').value = '';
  }
}

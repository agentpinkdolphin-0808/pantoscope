(function () {
  "use strict";

  var BAND_CLASS = { High: "band-high", Medium: "band-medium", Low: "band-low" };
  var INITIAL_CENTER = [47.55, -122.35];
  var INITIAL_ZOOM = 9;

  var state = {
    practices: [],
    byId: {},
    byCounty: {},
    selectedCounties: new Set(),
    favorites: new Set(),
    clusterOn: true,
    activePracticeId: null,
    activeTab: "overview",
  };

  var map, countyLayer, markerLayer;
  var countyLayerByName = {};
  var countyHover = {};

  function bandClass(p) {
    return p.at_risk ? "band-risk" : (BAND_CLASS[p.band] || "band-medium");
  }

  function bandLabel(p) {
    return p.at_risk ? "At Risk" : p.band;
  }

  function fmtMoney(n) {
    return "$" + Math.round(n).toLocaleString("en-US");
  }

  function fmtSignedPct(n) {
    var sign = n > 0 ? "+" : "";
    return sign + n + "%";
  }

  function daysAgo(dateStr) {
    var then = new Date(dateStr + "T00:00:00");
    var now = new Date();
    var diff = Math.round((now - then) / 86400000);
    if (diff < 0) return "in " + Math.abs(diff) + " days";
    if (diff === 0) return "today";
    if (diff === 1) return "1 day ago";
    return diff + " days ago";
  }

  function fmtDate(dateStr) {
    var d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  }

  function initials(name) {
    return name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map(function (w) { return w[0].toUpperCase(); })
      .join("");
  }

  // ---------------- data loading ----------------

  function loadPractices() {
    return fetch("api/practices")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.practices = data;
        data.forEach(function (p) {
          state.byId[p.practice_id] = p;
          if (!state.byCounty[p.county]) state.byCounty[p.county] = [];
          state.byCounty[p.county].push(p);
        });
      });
  }

  // ---------------- map setup ----------------

  function initMap() {
    map = L.map("map", {
      zoomControl: false,
      attributionControl: true,
      minZoom: 7,
      maxZoom: 14,
    }).setView(INITIAL_CENTER, INITIAL_ZOOM);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    map.on("contextmenu", function (e) {
      L.DomEvent.preventDefault(e);
    });

    loadCounties();
  }

  var COUNTY_STYLE = {
    base: { color: "#3a4358", weight: 1, fillColor: "#2a3142", fillOpacity: 0.25 },
    hover: { color: "#f97316", weight: 2, fillColor: "#f97316", fillOpacity: 0.08 },
    selected: { color: "#7c5cf4", weight: 2.5, fillColor: "#7c5cf4", fillOpacity: 0.16 },
    selectedHover: { color: "#7c5cf4", weight: 2.5, fillColor: "#7c5cf4", fillOpacity: 0.22 },
  };

  function loadCounties() {
    fetch("static/geo/puget_counties.json")
      .then(function (r) { return r.json(); })
      .then(function (geo) {
        countyLayer = L.geoJson(geo, {
          style: function () { return COUNTY_STYLE.base; },
          onEachFeature: function (feature, layer) {
            var name = feature.properties.NAME;
            countyLayerByName[name] = layer;
            countyHover[name] = false;
            layer.on({
              mouseover: function () {
                countyHover[name] = true;
                refreshCountyStyle(name);
              },
              mouseout: function () {
                countyHover[name] = false;
                refreshCountyStyle(name);
              },
              click: function () {
                selectCounty(name);
              },
              contextmenu: function (e) {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
                deselectCounty(name);
              },
            });
          },
        }).addTo(map);
      });
  }

  function refreshCountyStyle(name) {
    var layer = countyLayerByName[name];
    if (!layer) return;
    var selected = state.selectedCounties.has(name);
    var hovered = countyHover[name];

    var style;
    if (selected && hovered) style = COUNTY_STYLE.selectedHover;
    else if (selected) style = COUNTY_STYLE.selected;
    else if (hovered) style = COUNTY_STYLE.hover;
    else style = COUNTY_STYLE.base;

    layer.setStyle(style);

    var el = layer.getElement && layer.getElement();
    if (el) el.classList.toggle("county-glow", selected);
    if (selected) layer.bringToFront();
  }

  function selectCounty(name) {
    if (!state.byCounty[name]) return;
    if (state.selectedCounties.has(name)) return;
    state.selectedCounties.add(name);
    refreshCountyStyle(name);
    renderMarkers();
    renderKPIs();
  }

  function deselectCounty(name) {
    if (!state.selectedCounties.has(name)) return;
    state.selectedCounties.delete(name);
    refreshCountyStyle(name);

    var active = state.activePracticeId ? state.byId[state.activePracticeId] : null;
    if (active && active.county === name) {
      closeDetail();
    }

    renderMarkers();
    renderKPIs();
  }

  // ---------------- markers ----------------

  function visiblePractices() {
    return state.practices.filter(function (p) {
      return state.selectedCounties.has(p.county);
    });
  }

  function makeMarker(p) {
    var icon = L.divIcon({
      className: "",
      html:
        '<div class="blimp-pin ' + bandClass(p) + '"><span class="blimp-dot"></span></div>',
      iconSize: [26, 26],
      iconAnchor: [13, 26],
    });
    var marker = L.marker([p.lat, p.lng], { icon: icon });

    var tooltipHtml =
      '<div class="tt-name">' + p.practice_name + "</div>" +
      '<div class="tt-location">' + p.city + ", " + p.state + "</div>" +
      '<div class="tt-revenue">' + fmtMoney(p.revenue_12mo) + "</div>" +
      '<div class="tt-band ' + bandClass(p) + '">' + bandLabel(p) + "</div>" +
      '<div class="tt-opportunity">Opportunity: ' + fmtMoney(p.opportunity_total) + "</div>";

    marker.bindTooltip(tooltipHtml, {
      direction: "top",
      offset: [0, -14],
      className: "blimp-tooltip",
      opacity: 1,
    });

    marker.on("click", function () {
      openDetail(p.practice_id);
    });
    marker.on("contextmenu", function (e) {
      L.DomEvent.preventDefault(e);
    });

    return marker;
  }

  function renderMarkers() {
    if (markerLayer) {
      map.removeLayer(markerLayer);
      markerLayer = null;
    }

    var visible = visiblePractices();
    if (visible.length === 0) return;

    if (state.clusterOn) {
      markerLayer = L.markerClusterGroup({
        maxClusterRadius: 60,
        iconCreateFunction: function (cluster) {
          var count = cluster.getChildCount();
          var size = count > 9 ? 44 : 36;
          return L.divIcon({
            html: '<div class="marker-cluster-custom" style="width:' + size + "px;height:" + size + 'px;">' + count + "</div>",
            className: "",
            iconSize: [size, size],
          });
        },
      });
    } else {
      markerLayer = L.layerGroup();
    }

    visible.forEach(function (p) {
      markerLayer.addLayer(makeMarker(p));
    });

    map.addLayer(markerLayer);
  }

  // ---------------- KPI strip ----------------

  function renderKPIs() {
    var visible = visiblePractices();
    var totalAccounts = visible.length;
    var totalRevenue = visible.reduce(function (s, p) { return s + p.revenue_12mo; }, 0);
    var activeOpportunities = visible.reduce(function (s, p) { return s + p.opportunities.length; }, 0);
    var atRisk = visible.filter(function (p) { return p.at_risk; }).length;

    var topOpp = null;
    visible.forEach(function (p) {
      p.opportunities.forEach(function (o) {
        if (!topOpp || o.value > topOpp.value) {
          topOpp = { value: o.value, name: o.opportunity_name, practice: p.practice_name };
        }
      });
    });

    document.getElementById("kpi-accounts").textContent = totalAccounts;
    document.getElementById("kpi-revenue").textContent = fmtMoney(totalRevenue);
    document.getElementById("kpi-opportunities").textContent = activeOpportunities;
    document.getElementById("kpi-at-risk").textContent = atRisk;
    document.getElementById("kpi-top-value").textContent = topOpp ? fmtMoney(topOpp.value) : "$0";
    document.getElementById("kpi-top-name").textContent = topOpp ? topOpp.practice : "—";
  }

  // ---------------- detail panel ----------------

  function openDetail(practiceId) {
    state.activePracticeId = practiceId;
    state.activeTab = "overview";

    var panel = document.getElementById("detail-panel");
    panel.hidden = false;

    var p = state.byId[practiceId];
    document.getElementById("detail-name").textContent = p.practice_name;
    document.getElementById("detail-location").textContent = p.city + ", " + p.state;

    var badge = document.getElementById("detail-badge");
    badge.textContent = p.value_badge;
    badge.className = "detail-badge " + bandClass(p);

    var star = document.getElementById("detail-star");
    star.classList.toggle("is-active", state.favorites.has(practiceId));
    star.innerHTML = state.favorites.has(practiceId) ? "&#9733;" : "&#9734;";

    document.querySelectorAll(".detail-tab").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.tab === "overview");
    });

    renderTabBody();
  }

  function closeDetail() {
    state.activePracticeId = null;
    document.getElementById("detail-panel").hidden = true;
  }

  function switchTab(tab) {
    state.activeTab = tab;
    document.querySelectorAll(".detail-tab").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.tab === tab);
    });
    renderTabBody();
  }

  function renderTabBody() {
    var body = document.getElementById("detail-body");
    var p = state.byId[state.activePracticeId];
    if (!p) {
      body.innerHTML = "";
      return;
    }
    if (state.activeTab === "overview") body.innerHTML = renderOverview(p);
    else if (state.activeTab === "opportunities") body.innerHTML = renderOpportunitiesTab(p);
    else if (state.activeTab === "history") body.innerHTML = renderHistoryTab(p);
    else if (state.activeTab === "contacts") body.innerHTML = renderContactsTab(p);

    var jumpBtn = body.querySelector("[data-jump-opportunities]");
    if (jumpBtn) {
      jumpBtn.addEventListener("click", function () { switchTab("opportunities"); });
    }
  }

  function deltaHtml(value) {
    var up = value >= 0;
    var arrow = up ? "↑" : "↓";
    return '<span class="perf-cell-delta ' + (up ? "is-up" : "is-down") + '">' + arrow + " " + fmtSignedPct(value) + " vs prior 12mo</span>";
  }

  function renderOverview(p) {
    var productsHtml = p.products
      .map(function (prod) {
        return (
          '<div class="product-row">' +
          '<div class="product-name">' + prod.product + "</div>" +
          '<div class="product-spend">' + fmtMoney(prod.spend) + "</div>" +
          '<div class="product-bar-wrap"><div class="product-bar-track"><div class="product-bar-fill" style="width:' + prod.pct_of_spend + '%"></div></div>' +
          '<div class="product-pct">' + prod.pct_of_spend + "%</div></div>" +
          "</div>"
        );
      })
      .join("");

    var oppsHtml = p.opportunities
      .map(function (o) {
        return (
          '<div class="opportunity-row">' +
          '<div class="opportunity-name">' + o.opportunity_name + "</div>" +
          '<div class="opportunity-value">' + fmtMoney(o.value) + "</div>" +
          '<div class="impact-badge impact-' + o.impact.toLowerCase() + '">' + o.impact + "</div>" +
          "</div>"
        );
      })
      .join("");

    var historyEvents = p.history.slice().sort(function (a, b) { return b.event_date.localeCompare(a.event_date); });
    var lastContactDate = historyEvents.length ? historyEvents[0].event_date : p.last_contact;

    return (
      '<div class="detail-section">' +
      '<div class="detail-section-header"><span class="detail-section-title">Performance (12 Months)</span></div>' +
      '<div class="perf-grid">' +
      '<div><div class="perf-cell-label">Revenue</div><div class="perf-cell-value">' + fmtMoney(p.revenue_12mo) + "</div>" + deltaHtml(p.revenue_delta) + "</div>" +
      '<div><div class="perf-cell-label">Orders</div><div class="perf-cell-value">' + p.orders_12mo + "</div>" + deltaHtml(p.orders_delta) + "</div>" +
      '<div><div class="perf-cell-label">Avg Order Value</div><div class="perf-cell-value">' + fmtMoney(p.avg_order_value) + "</div>" + deltaHtml(p.aov_delta) + "</div>" +
      "</div></div>" +

      '<div class="detail-section">' +
      '<div class="detail-section-header"><span class="detail-section-title">Top Products</span><span class="detail-link">View all products &rarr;</span></div>' +
      productsHtml +
      "</div>" +

      '<div class="detail-section">' +
      '<div class="detail-section-header"><span class="detail-section-title">Active Opportunities (' + p.opportunities.length + ')</span><span class="detail-section-total">' + fmtMoney(p.opportunity_total) + "</span></div>" +
      oppsHtml +
      '<div class="detail-link" data-jump-opportunities style="margin-top:8px;cursor:pointer;">View all opportunities &rarr;</div>' +
      "</div>" +

      '<div class="detail-footer">' +
      '<div><div class="footer-label">Last Contact</div><div class="footer-value">' + fmtDate(lastContactDate) + '</div><div class="footer-subtext">' + daysAgo(lastContactDate) + "</div></div>" +
      '<div><div class="footer-label">Account Owner</div><div class="owner-row"><div class="owner-avatar">' + initials(p.account_owner) + '</div><div class="footer-value">' + p.account_owner + "</div></div></div>" +
      "</div>"
    );
  }

  function renderOpportunitiesTab(p) {
    if (!p.opportunities.length) {
      return '<div class="empty-state">No opportunities on record.</div>';
    }
    return p.opportunities
      .map(function (o) {
        return (
          '<div class="opp-list-row">' +
          '<div class="opportunity-name">' + o.opportunity_name + "</div>" +
          '<div class="opportunity-value">' + fmtMoney(o.value) + "</div>" +
          '<div class="impact-badge impact-' + o.impact.toLowerCase() + '">' + o.impact + "</div>" +
          '<div class="opp-stage">' + o.stage + "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  function renderHistoryTab(p) {
    var events = p.history.slice().sort(function (a, b) { return b.event_date.localeCompare(a.event_date); });
    if (!events.length) {
      return '<div class="empty-state">No history on record.</div>';
    }
    return events
      .map(function (e) {
        var isOrder = e.event_type === "order";
        return (
          '<div class="history-row">' +
          '<div class="history-icon type-' + e.event_type + '">' + (isOrder ? "$" : "☎") + "</div>" +
          '<div class="history-content">' +
          '<div class="history-desc">' + e.description + "</div>" +
          '<div class="history-meta">' + fmtDate(e.event_date) + " &middot; " + daysAgo(e.event_date) + "</div>" +
          "</div>" +
          (isOrder ? '<div class="history-amount">' + fmtMoney(e.amount) + "</div>" : "") +
          "</div>"
        );
      })
      .join("");
  }

  function renderContactsTab(p) {
    if (!p.contacts.length) {
      return '<div class="empty-state">No contacts on record.</div>';
    }
    return p.contacts
      .map(function (c) {
        return (
          '<div class="contact-card">' +
          '<div class="contact-name">' + c.contact_name + "</div>" +
          '<div class="contact-role">' + c.role + "</div>" +
          '<div class="contact-line">' + c.email + "</div>" +
          '<div class="contact-line">' + c.phone + "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  // ---------------- UI wiring ----------------

  function wireUI() {
    document.getElementById("zoom-in-btn").addEventListener("click", function () { map.zoomIn(); });
    document.getElementById("zoom-out-btn").addEventListener("click", function () { map.zoomOut(); });
    document.getElementById("recenter-btn").addEventListener("click", function () {
      map.setView(INITIAL_CENTER, INITIAL_ZOOM);
    });

    document.getElementById("detail-close").addEventListener("click", closeDetail);
    document.getElementById("detail-star").addEventListener("click", function () {
      if (!state.activePracticeId) return;
      if (state.favorites.has(state.activePracticeId)) {
        state.favorites.delete(state.activePracticeId);
      } else {
        state.favorites.add(state.activePracticeId);
      }
      var star = document.getElementById("detail-star");
      star.classList.toggle("is-active", state.favorites.has(state.activePracticeId));
      star.innerHTML = state.favorites.has(state.activePracticeId) ? "&#9733;" : "&#9734;";
    });

    document.querySelectorAll(".detail-tab").forEach(function (btn) {
      btn.addEventListener("click", function () { switchTab(btn.dataset.tab); });
    });

    var clusterToggle = document.getElementById("cluster-toggle");
    clusterToggle.addEventListener("click", function () {
      state.clusterOn = !state.clusterOn;
      clusterToggle.classList.toggle("is-on", state.clusterOn);
      clusterToggle.setAttribute("aria-checked", String(state.clusterOn));
      renderMarkers();
    });
  }

  // ---------------- boot ----------------

  document.addEventListener("DOMContentLoaded", function () {
    initMap();
    wireUI();
    loadPractices().then(function () {
      renderKPIs();
    });
  });
})();

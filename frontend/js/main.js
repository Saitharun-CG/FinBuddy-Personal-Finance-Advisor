/* FinPilot – main.js  (shared across all pages) */

const API = 'http://localhost:5000/api';

/* ── SESSION ──────────────────────────────────────────────────── */
function getUser()  { return JSON.parse(sessionStorage.getItem('fp_user') || 'null'); }
function setUser(u) { sessionStorage.setItem('fp_user', JSON.stringify(u)); }
function logout()   { sessionStorage.removeItem('fp_user'); window.location.href = '../index.html'; }

/* ── FETCH HELPERS ────────────────────────────────────────────── */
async function api(path, method='GET', body=null) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  return r.json();
}

/* ── FORMAT ───────────────────────────────────────────────────── */
function inr(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
function pct(n) { return n.toFixed(1) + '%'; }

/* ── NAVBAR SCROLL ────────────────────────────────────────────── */
const nb = document.getElementById('navbar');
if (nb) window.addEventListener('scroll', () => nb.classList.toggle('scrolled', window.scrollY > 30));

/* ── HAMBURGER ────────────────────────────────────────────────── */
const ham = document.getElementById('ham');
if (ham) ham.addEventListener('click', () => {
  document.querySelector('.nav-links')?.classList.toggle('open');
});

/* ── ALERT HELPER ─────────────────────────────────────────────── */
function showAlert(id, msg, type='success') {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 4000);
}

/* ── SIDEBAR ACTIVE LINK ──────────────────────────────────────── */
document.querySelectorAll('.sb-item').forEach(a => {
  if (a.href && window.location.href.includes(a.getAttribute('href'))) {
    a.classList.add('active');
  }
});

/* ── SIDEBAR TOGGLE MOBILE ────────────────────────────────────── */
const sb = document.querySelector('.sidebar');
const sbBtn = document.getElementById('sb-toggle');
if (sbBtn && sb) sbBtn.addEventListener('click', () => sb.classList.toggle('open'));

/* ── SCORE RING DRAW ──────────────────────────────────────────── */
function drawScoreRing(svgId, score) {
  const svg = document.getElementById(svgId);
  if (!svg) return;
  const r = 52, cx = 60, cy = 60;
  const circumference = 2 * Math.PI * r;
  const dashoffset = circumference - (score / 100) * circumference;
  svg.innerHTML = `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#2a2e3d" stroke-width="8"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#f5a623" stroke-width="8"
      stroke-dasharray="${circumference}" stroke-dashoffset="${dashoffset}"
      stroke-linecap="round" style="transition:stroke-dashoffset .8s ease"/>
  `;
}

/* ── MINI PIE CHART (canvas-free, CSS conic) ──────────────────── */
function renderPie(containerId, data) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const colors = ['#f5a623','#3b82f6','#22c55e','#ef4444','#a78bfa','#ec4899','#14b8a6'];
  const total = Object.values(data).reduce((a,b)=>a+b,0);
  if (!total) return;
  let cumulPct = 0;
  const stops = Object.entries(data).map(([k,v],i) => {
    const p = (v/total)*100;
    const stop = `${colors[i%colors.length]} ${cumulPct}% ${cumulPct+p}%`;
    cumulPct += p;
    return stop;
  }).join(', ');

  el.style.background = `conic-gradient(${stops})`;
  el.style.borderRadius = '50%';

  // Legend
  const legend = document.getElementById(containerId + '-legend');
  if (legend) {
    legend.innerHTML = Object.entries(data).map(([k,v],i) => `
      <div style="display:flex;align-items:center;gap:.5rem;margin:.25rem 0">
        <span style="width:12px;height:12px;border-radius:50%;background:${colors[i%colors.length]};flex-shrink:0"></span>
        <span style="font-size:.82rem;color:#6b7280">${k}</span>
        <span style="margin-left:auto;font-size:.82rem;font-weight:600">₹${Number(v).toLocaleString('en-IN')}</span>
      </div>
    `).join('');
  }
}

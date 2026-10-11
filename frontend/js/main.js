
/* Smart Finance System - main.js */

const API_URL =
  "https://finbuddy-personal-finance-advisor-api.onrender.com";

/* SESSION */
function getUser() {
  try {
    return JSON.parse(sessionStorage.getItem("fp_user") || "null");
  } catch {
    return null;
  }
}

function setUser(user) {
  sessionStorage.setItem("fp_user", JSON.stringify(user));
}

function logout() {
  sessionStorage.removeItem("fp_user");
  window.location.href = "../index.html";
}

/* FETCH HELPERS */
async function api(path, method = "GET", body = null) {
  const options = {
    method,
    headers: {
      "Content-Type": "application/json"
    }
  };

  if (body !== null) {
    options.body = JSON.stringify(body);
  }

  let response;

  try {
    response = await fetch(API_URL + path, options);
  } catch (error) {
    console.error("Cannot connect to backend:", error);
    throw new Error(
      "Cannot reach server. Please check your internet connection and try again."
    );
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      `Server returned an invalid response (${response.status}).`
    );
  }

  if (!response.ok) {
    throw new Error(
      data.error || data.message || `Request failed (${response.status})`
    );
  }

  return data;
}

/* FORMAT */
function inr(value) {
  return "₹" + Number(value || 0).toLocaleString("en-IN");
}

function pct(value) {
  return Number(value || 0).toFixed(1) + "%";
}

/* NAVBAR SCROLL */
const navbar = document.getElementById("navbar");

if (navbar) {
  window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 30);
  });
}

/* HAMBURGER */
const hamburger = document.getElementById("ham");

if (hamburger) {
  hamburger.addEventListener("click", () => {
    document.querySelector(".nav-links")?.classList.toggle("open");
  });
}

/* ALERT HELPER */
function showAlert(id, message, type = "success") {
  const element = document.getElementById(id);

  if (!element) return;

  element.className = `alert alert-${type}`;
  element.textContent = message;
  element.style.display = "block";

  setTimeout(() => {
    element.style.display = "none";
  }, 4000);
}

/* SIDEBAR ACTIVE LINK */
document.querySelectorAll(".sb-item").forEach(link => {
  if (link.href && link.getAttribute("href")) {
    const target = new URL(link.href, window.location.href);

    if (target.pathname === window.location.pathname) {
      link.classList.add("active");
    }
  }
});

/* SIDEBAR TOGGLE */
const sidebar = document.querySelector(".sidebar");
const sidebarButton = document.getElementById("sb-toggle");

if (sidebarButton && sidebar) {
  sidebarButton.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });
}

/* SCORE RING */
function drawScoreRing(svgId, score) {
  const svg = document.getElementById(svgId);

  if (!svg) return;

  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
  const radius = 52;
  const centerX = 60;
  const centerY = 60;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeScore / 100) * circumference;

  svg.innerHTML = `
    <circle
      cx="${centerX}" cy="${centerY}" r="${radius}"
      fill="none" stroke="#2a2e3d" stroke-width="8"
    />
    <circle
      cx="${centerX}" cy="${centerY}" r="${radius}"
      fill="none" stroke="#f5a623" stroke-width="8"
      stroke-dasharray="${circumference}"
      stroke-dashoffset="${offset}"
      stroke-linecap="round"
      style="transition:stroke-dashoffset .8s ease"
    />
  `;
}

/* MINI PIE CHART */
function renderPie(containerId, data) {
  const element = document.getElementById(containerId);

  if (!element) return;

  const colors = [
    "#f5a623", "#3b82f6", "#22c55e",
    "#ef4444", "#a78bfa", "#ec4899", "#14b8a6"
  ];

  const entries = Object.entries(data || {}).filter(
    ([, value]) => Number(value) > 0
  );

  const total = entries.reduce(
    (sum, [, value]) => sum + Number(value),
    0
  );

  if (!total) {
    element.style.background = "transparent";
    return;
  }

  let accumulated = 0;

  const stops = entries.map(([category, value], index) => {
    const percentage = (Number(value) / total) * 100;
    const stop = `${colors[index % colors.length]} ${accumulated}% ${accumulated + percentage}%`;
    accumulated += percentage;
    return stop;
  });

  element.style.background = `conic-gradient(${stops.join(", ")})`;
  element.style.borderRadius = "50%";

  const legend = document.getElementById(containerId + "-legend");

  if (legend) {
    legend.innerHTML = entries.map(([category, value], index) => `
      <div style="display:flex;align-items:center;gap:.5rem;margin:.25rem 0">
        <span style="width:12px;height:12px;border-radius:50%;background:${colors[index % colors.length]};flex-shrink:0"></span>
        <span style="font-size:.82rem;color:#6b7280">${category}</span>
        <span style="margin-left:auto;font-size:.82rem;font-weight:600">₹${Number(value).toLocaleString("en-IN")}</span>
      </div>
    `).join("");
  }
}

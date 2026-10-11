
/* Smart Finance System - main.js */

const API_URL =
  "https://finbuddy-personal-finance-advisor-api.onrender.com";

/* SESSION */
function getUser() {
  try {
    const saved = sessionStorage.getItem("fp_user");

    if (!saved) return null;

    const user = JSON.parse(saved);

    if (!user || !user.email) {
      sessionStorage.removeItem("fp_user");
      return null;
    }

    return user;
  } catch (error) {
    console.error("Could not read user session:", error);
    sessionStorage.removeItem("fp_user");
    return null;
  }
}

function setUser(user) {
  if (!user || !user.email) {
    throw new Error("Cannot save invalid user information.");
  }

  sessionStorage.setItem("fp_user", JSON.stringify(user));
}

function logout() {
  sessionStorage.removeItem("fp_user");
  window.location.href = "../index.html";
}

/* API REQUESTS */
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
      "Cannot reach the server. Check your internet connection or try again later."
    );
  }

  let result;

  try {
    result = await response.json();
  } catch {
    throw new Error(
      `The server returned an invalid response (${response.status}).`
    );
  }

  if (!response.ok) {
    throw new Error(
      result.error ||
      result.message ||
      `Request failed (${response.status}).`
    );
  }

  return result;
}

/* FORMAT */
function inr(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return "₹0";

  return number.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  });
}

function pct(value) {
  const number = Number(value);

  return `${(Number.isFinite(number) ? number : 0).toFixed(1)}%`;
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
  const href = link.getAttribute("href");

  if (!href) return;

  try {
    const target = new URL(href, window.location.href);

    if (target.pathname === window.location.pathname) {
      link.classList.add("active");
    }
  } catch (error) {
    console.warn("Could not check sidebar link:", error);
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

/* FINANCIAL SCORE RING */
function drawScoreRing(svgId, score) {
  const svg = document.getElementById(svgId);

  if (!svg) return;

  const safeScore = Math.max(
    0,
    Math.min(100, Number(score) || 0)
  );

  const radius = 52;
  const centerX = 60;
  const centerY = 60;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeScore / 100) * circumference;

  svg.innerHTML = `
    <circle
      cx="${centerX}"
      cy="${centerY}"
      r="${radius}"
      fill="none"
      stroke="#2a2e3d"
      stroke-width="8"
    />
    <circle
      cx="${centerX}"
      cy="${centerY}"
      r="${radius}"
      fill="none"
      stroke="#f5a623"
      stroke-width="8"
      stroke-dasharray="${circumference}"
      stroke-dashoffset="${offset}"
      stroke-linecap="round"
      style="transition:stroke-dashoffset .8s ease"
    />
  `;
}

/* EXPENSE PIE CHART */
function renderPie(containerId, data) {
  const element = document.getElementById(containerId);

  if (!element) return;

  const colors = [
    "#f5a623",
    "#3b82f6",
    "#22c55e",
    "#ef4444",
    "#a78bfa",
    "#ec4899",
    "#14b8a6"
  ];

  const entries = Object.entries(data || {})
    .map(([name, value]) => [name, Number(value)])
    .filter(([, value]) => Number.isFinite(value) && value > 0);

  const total = entries.reduce(
    (sum, [, value]) => sum + value,
    0
  );

  if (!total) {
    element.style.background = "transparent";

    const emptyLegend = document.getElementById(
      containerId + "-legend"
    );

    if (emptyLegend) {
      emptyLegend.replaceChildren();
    }

    return;
  }

  let cumulative = 0;

  const stops = entries.map(([name, value], index) => {
    const start = cumulative;
    cumulative += (value / total) * 100;

    return `${colors[index % colors.length]} ${start}% ${cumulative}%`;
  });

  element.style.background =
    `conic-gradient(${stops.join(", ")})`;

  element.style.borderRadius = "50%";

  const legend = document.getElementById(
    containerId + "-legend"
  );

  if (legend) {
    legend.replaceChildren();

    entries.forEach(([name, value], index) => {
      const row = document.createElement("div");

      row.style.cssText =
        "display:flex;align-items:center;gap:.5rem;margin:.25rem 0";

      const dot = document.createElement("span");

      dot.style.cssText =
        `width:12px;height:12px;border-radius:50%;flex-shrink:0;background:${colors[index % colors.length]}`;

      const label = document.createElement("span");

      label.style.cssText =
        "font-size:.82rem;color:#6b7280";

      label.textContent = name;

      const amount = document.createElement("span");

      amount.style.cssText =
        "margin-left:auto;font-size:.82rem;font-weight:600";

      amount.textContent = inr(value);

      row.append(dot, label, amount);
      legend.appendChild(row);
    });
  }
}

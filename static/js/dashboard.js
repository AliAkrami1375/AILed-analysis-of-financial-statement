const token = localStorage.getItem("token");
function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
}
const userPayload = parseJwt(token);
const currentUser = userPayload?.username;
if (!token) window.location.href = "/";

function showTab(tabId) {
  document.querySelectorAll("main section").forEach(sec => sec.classList.add("hidden"));
  document.getElementById(tabId).classList.remove("hidden");

  const sidebar = document.getElementById("sidebar");
  if (window.innerWidth < 768) {
    sidebar.classList.add("hidden");
  }
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "/";
}

function openModal(content) {
  console.log(content);
  let parsed;
  try {
    parsed = typeof content === 'string' ? JSON.parse(content) : content;
    
  } catch (e) {
    console.error("JSON parse error in openModal:", e, content);
    alert("Error: Invalid content in modal.");
    return;
  }

  const modal = document.getElementById("modalContent");

  modal.innerHTML = `
    <h3 class="text-lg font-bold mb-2">Company Summary</h3>
    <p class="mb-4">${parsed.summary || "No summary provided."}</p>

    <div>
      <h4 class="font-semibold">Ratios</h4>
      <ul class="ml-4 list-disc">
        ${(parsed.ratios || []).map(r => `
          <li>
            <strong>${r.ratio}</strong>: ${r.value || 'N/A'}
            <div class="text-sm text-gray-600 ml-2">Formula: ${r.formula || ''}</div>
          </li>
        `).join('')}
      </ul>
    </div>

    <div class="mt-4">
      <h4 class="font-semibold">Raw Data</h4>
      <ul class="ml-4 list-disc">
        ${Object.entries(parsed.raw_data || {}).map(([key, val]) => `
          <li><strong>${key}</strong>: ${val}</li>
        `).join('')}
      </ul>
    </div>
  `;

  document.getElementById("resultModal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("resultModal").classList.add("hidden");
}

document.addEventListener("click", function (e) {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("menuToggle");
  if (!sidebar.contains(e.target) && !toggle.contains(e.target) && window.innerWidth < 768) {
    sidebar.classList.add("hidden");
  }
});

window.addEventListener("resize", () => {
  const sidebar = document.getElementById("sidebar");
  if (window.innerWidth >= 768) sidebar.classList.remove("hidden");
});

const searchForm = document.getElementById("searchForm");
searchForm?.addEventListener("submit", async function (e) {
  e.preventDefault();
  const btn = this.querySelector("button");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Loading...";

  const company = document.getElementById("company_name").value;
  const year = document.getElementById("fiscal_year").value;

  const res = await fetch("/api/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ company_name: company, fiscal_year: year })
  });

  const data = await res.json();
  const resultDiv = document.getElementById("searchResult");
  const resultJson = document.getElementById("resultJson");
  const ratioList = document.getElementById("ratioList");
  ratioList.innerHTML = "";

  if (res.ok) {
    resultJson.textContent = data.result.summary;
    resultDiv.classList.remove("hidden");
    if (Array.isArray(data.result.ratios)) {
      data.result.ratios.forEach(r => {
        const li = document.createElement("li");
        li.className = "border px-4 py-2 rounded bg-gray-50";
        li.innerHTML = `<strong>${r.ratio}</strong>: ${r.value || 'Not Found Formula'} <br/><span class='text-xs text-gray-600'>${r.formula}</span>`;
        ratioList.appendChild(li);
      });
    }
    loadArchive();
  } else {
    resultJson.textContent = "Error: " + data.error;
    resultDiv.classList.remove("hidden");
  }

  btn.disabled = false;
  btn.textContent = originalText;
});

var AllData = {}

async function loadArchive() {
  const res = await fetch("/api/archive", {
    headers: { "Authorization": "Bearer " + token }
  });
  const data = await res.json();
  const tbody = document.getElementById("archiveTable");
  tbody.innerHTML = "";

  data.archive.forEach((entry, index) => {
    const tr = document.createElement("tr");
    const summary = entry.result.summary;
    console.log(entry.result);
    
    const fullContent = {
      summary: entry.result.summary,
      ratios: entry.result.ratios,
      raw_data: entry.result.raw_data
    };
    var key = entry.company_name+entry.fiscal_year
    AllData[key] = JSON.stringify(fullContent);
    console.log(key,AllData[key]);
    
    tr.innerHTML = `
      <td class="p-3">${entry.company_name}</td>
      <td class="p-3">${entry.fiscal_year}</td>
      <td class="p-3 flex items-center justify-between">
        ${summary}
        <button class="ml-2 text-blue-600 underline text-sm" data-result='${key}' onclick="handleShowResult(this)">Show Result</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function handleShowResult(btn) {
  try {
    const decoded = AllData[btn.dataset.result];
    openModal(decoded);
  } catch (e) {
    console.error("Error decoding result dataset:", e);
    alert("Invalid result format.");
  }
}


window.addEventListener("load", () => {
  loadArchive();
  loadConfig();
});

async function loadConfig() {
  const res = await fetch("/api/config", {
    headers: { "Authorization": "Bearer " + token }
  });
  const data = await res.json();

  if (data.openai_api_key !== undefined) {
    document.getElementById("openai_key").value = data.openai_api_key || "";
    document.getElementById("default_prompt").value = data.default_prompt || "";

    if (currentUser === "admin") {
      document.getElementById("settingsTabBtn").classList.remove("hidden");
    }

    const userList = document.getElementById("userList");
    userList.innerHTML = "";
    data.users.forEach(user => {
      const li = document.createElement("li");
      li.className = "flex justify-between items-center";
      li.innerHTML = `
        <span>${user.username}</span>
        ${user.username !== "admin" ? `<button onclick="deleteUser('${user.username}')" class="text-red-500 text-sm">Delete</button>` : ""}
      `;
      userList.appendChild(li);
    });

    const fieldsList = document.getElementById("fieldsList");
    fieldsList.innerHTML = "";
    (data.fields || []).forEach(field => {
      const li = document.createElement("li");
      li.className = "flex justify-between items-center";
      li.innerHTML = `
        <span>${field}</span>
        <button onclick="removeField('${field}')" class="text-red-500 text-sm">Remove</button>
      `;
      fieldsList.appendChild(li);
    });
  }
}

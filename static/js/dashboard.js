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

  // Collapse sidebar after selecting tab (for mobile)
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
  document.getElementById("modalContent").textContent = content;
  document.getElementById("resultModal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("resultModal").classList.add("hidden");
}

// Collapse menu on outside click (optional enhancement)
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

// Search form submission
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

  if (res.ok) {
    resultJson.textContent = JSON.stringify(data.result, null, 2);
    resultDiv.classList.remove("hidden");
    loadArchive();
  } else {
    resultJson.textContent = "Error: " + data.error;
    resultDiv.classList.remove("hidden");
  }

  btn.disabled = false;
  btn.textContent = originalText;
});

// Load archive table
async function loadArchive() {
  const res = await fetch("/api/archive", {
    headers: { "Authorization": "Bearer " + token }
  });
  const data = await res.json();
  const tbody = document.getElementById("archiveTable");
  tbody.innerHTML = "";

  data.archive.forEach(entry => {
    const tr = document.createElement("tr");
    const safeSummary = JSON.stringify(entry.result.summary);
    tr.innerHTML = `
      <td class="p-3">\${entry.company_name}</td>
      <td class="p-3">\${entry.fiscal_year}</td>
      <td class="p-3 flex items-center justify-between">
        \${entry.result.summary}
        <button class="ml-2 text-blue-600 underline text-sm" onclick='openModal(\${safeSummary})'>Show Result</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Initial load
window.addEventListener("load", () => {
  loadArchive();
  loadConfig();
});

// Load config and users/fields
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

document.getElementById("configForm")?.addEventListener("submit", async function (e) {
  e.preventDefault();
  const key = document.getElementById("openai_key").value;
  const prompt = document.getElementById("default_prompt").value;

  await fetch("/api/config", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ openai_api_key: key, default_prompt: prompt })
  });
  alert("Configuration updated.");
});

document.getElementById("addUserForm")?.addEventListener("submit", async function (e) {
  e.preventDefault();
  const username = document.getElementById("newUsername").value;
  const password = document.getElementById("newPassword").value;

  const res = await fetch("/api/users", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ username, password })
  });

  if (res.ok) {
    loadConfig();
    this.reset();
  } else {
    alert("Error: " + (await res.json()).error);
  }
});

async function deleteUser(username) {
  const res = await fetch("/api/users", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify({ username })
  });
  if (res.ok) loadConfig();
  else alert("Error: " + (await res.json()).error);
}

document.getElementById("addFieldForm")?.addEventListener("submit", async function (e) {
  e.preventDefault();
  const newField = document.getElementById("newField").value.trim();

  const configRes = await fetch("/api/config", {
    headers: { "Authorization": "Bearer " + token }
  });
  const config = await configRes.json();

  if (!config.fields.includes(newField)) {
    config.fields.push(newField);
    await fetch("/api/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
      },
      body: JSON.stringify(config)
    });
    loadConfig();
    this.reset();
  }
});

async function removeField(field) {
  const configRes = await fetch("/api/config", {
    headers: { "Authorization": "Bearer " + token }
  });
  const config = await configRes.json();
  config.fields = config.fields.filter(f => f !== field);

  await fetch("/api/config", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token
    },
    body: JSON.stringify(config)
  });
  loadConfig();
}

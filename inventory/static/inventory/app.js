const accessStorageKey = "terreno-access";
const refreshStorageKey = "terreno-refresh";
const userStorageKey = "terreno-user";
const state = {
  access: sessionStorage.getItem(accessStorageKey),
  refresh: sessionStorage.getItem(refreshStorageKey),
  user: JSON.parse(sessionStorage.getItem(userStorageKey) || "null"),
  page: "catalog",
  machines: [],
  categories: [],
  catalogPage: 1,
  catalogHasPrevious: false,
  catalogHasNext: false,
  catalogLoading: false,
  toastTimer: null,
};

const byId = (id) => document.getElementById(id);
const money = (amount) => new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Number(amount || 0));
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const listResults = (payload) => Array.isArray(payload) ? payload : payload?.results || [];
const demoMachinePhotos = {
  "DEMO-EXC-020": "excavator.jpg",
  "DEMO-EXC-035": "mini-excavator.jpg",
  "DEMO-RET-4X4": "backhoe-loader.jpg",
  "DEMO-CAR-03": "wheel-loader.jpg",
  "DEMO-ROD-10": "roller.jpg",
  "DEMO-PLA-090": "plate-compactor.jpg",
};

function machinePhoto(machine) {
  const description = `${machine.nombre} ${machine.categoria_nombre || "maquinaria"}`;
  const normalized = description.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  let file = demoMachinePhotos[machine.sku];
  if (!file) {
    if (normalized.includes("mini")) file = "mini-excavator.jpg";
    else if (normalized.includes("retro")) file = "backhoe-loader.jpg";
    else if (normalized.includes("excav")) file = "excavator.jpg";
    else if (normalized.includes("cargador") || normalized.includes("loader")) file = "wheel-loader.jpg";
    else if (normalized.includes("placa") || normalized.includes("compactadora")) file = "plate-compactor.jpg";
    else if (normalized.includes("rodillo") || normalized.includes("roller")) file = "roller.jpg";
    else file = "excavator.jpg";
  }
  return { src: `/static/inventory/images/${file}`, alt: `Imagen de ${description}` };
}

function showToast(message, isError = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("is-error", isError);
  toast.classList.add("is-visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 3600);
}

function apiError(payload, fallback) {
  if (typeof payload === "string") return payload;
  if (payload?.detail) return payload.detail;
  if (payload && typeof payload === "object") {
    return Object.entries(payload).map(([key, value]) => {
      const message = Array.isArray(value) ? value.join(" ") : typeof value === "object" ? JSON.stringify(value) : value;
      return `${key}: ${message}`;
    }).join(" · ") || fallback;
  }
  return fallback;
}

async function refreshAccessToken() {
  if (!state.refresh) return false;
  try {
    const response = await fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: state.refresh }),
    });
    if (!response.ok) return false;
    const tokens = await response.json();
    state.access = tokens.access;
    state.refresh = tokens.refresh || state.refresh;
    sessionStorage.setItem(accessStorageKey, state.access);
    sessionStorage.setItem(refreshStorageKey, state.refresh);
    return true;
  } catch {
    return false;
  }
}

async function request(path, options = {}, canRefresh = true) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("Accept", "application/json");
  if (state.access) headers.set("Authorization", `Bearer ${state.access}`);
  let response = await fetch(path, { ...options, headers, cache: "no-store" });
  if (response.status === 401 && canRefresh && await refreshAccessToken()) {
    return request(path, options, false);
  }
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && state.access) clearSession(false);
    throw new Error(apiError(payload, `La solicitud falló (${response.status}).`));
  }
  return payload;
}

function setSession(tokens) {
  state.access = tokens.access;
  state.refresh = tokens.refresh;
  state.user = tokens.user;
  sessionStorage.setItem(accessStorageKey, state.access);
  sessionStorage.setItem(refreshStorageKey, state.refresh);
  sessionStorage.setItem(userStorageKey, JSON.stringify(state.user));
  renderAccount();
}

function clearSession(showMessage = true) {
  state.access = null;
  state.refresh = null;
  state.user = null;
  sessionStorage.removeItem(accessStorageKey);
  sessionStorage.removeItem(refreshStorageKey);
  sessionStorage.removeItem(userStorageKey);
  renderAccount();
  updateCartCount(0);
  if (showMessage) showToast("Sesión cerrada.");
}

function isExecutive() {
  return Boolean(state.user?.is_staff) || String(state.user?.role || "").toLowerCase().includes("ejecutivo");
}

function renderAccount() {
  const signedIn = Boolean(state.access && state.user);
  const isExecutiveRole = String(state.user?.role || "").toLowerCase().includes("ejecutivo");
  const accountRole = state.user?.is_staff && !isExecutiveRole ? "Administrador" : state.user?.role;
  byId("user-label").textContent = signedIn ? `${state.user.username} · ${accountRole}` : "Sesión no iniciada";
  byId("account-button").textContent = signedIn ? "Mi cuenta" : "Ingresar";
  byId("logout-button").hidden = !signedIn;
  byId("manager-nav").hidden = !isExecutive();
}

function setView(view) {
  if (["cart", "contracts"].includes(view) && !state.access) {
    view = "auth";
    showToast("Inicia sesión para continuar.");
  }
  if (view === "manager" && !isExecutive()) {
    view = "auth";
    showToast("Esta sección requiere una cuenta ejecutiva.", true);
  }
  state.page = view;
  document.querySelectorAll(".view-pane").forEach((pane) => { pane.hidden = pane.id !== `${view}-view`; });
  document.querySelectorAll(".nav-link").forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  if (view === "auth") setAuthMode("login");
  if (view === "catalog") loadCatalog();
  if (view === "cart") loadCart();
  if (view === "contracts") loadCustomerContracts();
  if (view === "manager") loadManager();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateCartCount(count) {
  const badge = byId("cart-count");
  badge.textContent = count;
  badge.hidden = !count;
}

async function loadCategories() {
  try {
    const payload = await request("/api/categorias/");
    state.categories = listResults(payload);
    const filter = byId("category-filter");
    const managerSelect = byId("machine-category");
    const inventoryFilter = byId("inventory-category");
    filter.innerHTML = '<option value="">Todas las categorías</option>' + state.categories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
    managerSelect.innerHTML = '<option value="">Selecciona categoría</option>' + state.categories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
    inventoryFilter.innerHTML = '<option value="">Todas las categorías</option>' + state.categories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
  } catch (error) {
    showToast(error.message, true);
  }
}

function catalogQuery() {
  const form = new FormData(byId("catalog-filters"));
  const query = new URLSearchParams({ page: String(state.catalogPage) });
  for (const key of ["search", "category", "tarifa_min", "tarifa_max"]) {
    const value = String(form.get(key) || "").trim();
    if (value) query.set(key, value);
  }
  return query.toString();
}

async function loadCatalog() {
  if (state.catalogLoading) return;
  state.catalogLoading = true;
  byId("catalog-summary").textContent = "Cargando catálogo...";
  try {
    const payload = await request(`/api/maquinarias/?${catalogQuery()}`);
    state.machines = listResults(payload);
    state.catalogHasPrevious = Boolean(payload.previous);
    state.catalogHasNext = Boolean(payload.next);
    const pageCount = Math.max(1, Math.ceil((payload.count || state.machines.length) / 20));
    byId("catalog-summary").textContent = `${payload.count ?? state.machines.length} equipos disponibles en el catálogo`;
    byId("catalog-pager").hidden = !(state.catalogHasPrevious || state.catalogHasNext);
    byId("page-label").textContent = `Página ${state.catalogPage} de ${pageCount}`;
    byId("previous-page").disabled = !state.catalogHasPrevious;
    byId("next-page").disabled = !state.catalogHasNext;
    renderMachines();
  } catch (error) {
    byId("catalog-summary").textContent = "No se pudo cargar el catálogo.";
    byId("machine-grid").innerHTML = `<div class="empty-state"><h3>Catálogo no disponible</h3><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    state.catalogLoading = false;
  }
}

function renderMachines() {
  const grid = byId("machine-grid");
  if (!state.machines.length) {
    grid.innerHTML = '<div class="empty-state"><h3>Aún no hay equipos para mostrar</h3><p>Prueba con otros filtros o vuelve más tarde.</p></div>';
    return;
  }
  grid.innerHTML = state.machines.map((machine) => {
    const available = Number(machine.unidades_disponibles || 0);
    const image = machinePhoto(machine);
    return `<article class="machine-card">
      <div class="machine-visual"><img class="machine-photo" src="${image.src}" alt="${escapeHtml(image.alt)}" loading="lazy" decoding="async"><span class="category-tag">${escapeHtml(machine.categoria_nombre || "Maquinaria")}</span><span class="stock-tag">${available ? `${available} disponibles` : "Sin disponibilidad"}</span></div>
      <div class="machine-info"><h3>${escapeHtml(machine.nombre)}</h3><p class="machine-subtitle">${escapeHtml([machine.marca, machine.modelo].filter(Boolean).join(" · "))} <span>· ${escapeHtml(machine.sku)}</span></p>
        <div class="machine-specs"><div class="rate"><strong>${money(machine.tarifa_diaria)}</strong><span>por día · garantía ${money(machine.garantia_fija)}</span></div><button class="button button-accent button-small" type="button" data-action="rent" data-id="${machine.id}" ${available < 1 ? "disabled" : ""}>${available ? "Solicitar" : "No disponible"}</button></div>
      </div>
    </article>`;
  }).join("");
}

function setAuthMode(mode) {
  const register = mode === "register";
  byId("login-form").hidden = register;
  byId("register-form").hidden = !register;
  byId("auth-title").textContent = register ? "Crea tu cuenta" : "Bienvenido de vuelta";
  byId("auth-description").textContent = register ? "Registra tu empresa constructora para solicitar arriendos." : "Accede a tu cuenta de empresa constructora.";
  document.querySelectorAll("[data-auth-mode]").forEach((button) => button.classList.toggle("is-active", button.dataset.authMode === mode));
}

function showRentDialog(machineId) {
  const machine = state.machines.find((item) => String(item.id) === String(machineId));
  if (!machine) return;
  if (!state.access) {
    setView("auth");
    showToast("Inicia sesión para agregar equipos al carro.");
    return;
  }
  const form = byId("rent-form");
  form.elements.maquinaria.value = machine.id;
  form.elements.cantidad.max = Math.max(1, Number(machine.unidades_disponibles || 1));
  form.elements.cantidad.value = "1";
  byId("rent-title").textContent = machine.nombre;
  const start = new Date();
  start.setDate(start.getDate() + 1);
  const end = new Date(start);
  end.setDate(end.getDate() + 3);
  form.elements.fecha_inicio.value = start.toISOString().slice(0, 10);
  form.elements.fecha_inicio.min = new Date().toISOString().slice(0, 10);
  form.elements.fecha_fin.value = end.toISOString().slice(0, 10);
  form.elements.fecha_fin.min = start.toISOString().slice(0, 10);
  byId("rent-dialog").showModal();
}

function dateLabel(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
}

async function loadCart() {
  const container = byId("cart-content");
  container.innerHTML = '<div class="empty-state">Cargando carro...</div>';
  try {
    const cart = await request("/api/carro-arriendo/");
    updateCartCount(cart.items.length);
    if (!cart.items.length) {
      container.innerHTML = '<div class="empty-state"><h3>Tu carro está vacío</h3><p>Explora el catálogo y agrega equipos con tus fechas de arriendo.</p><button class="button button-accent" type="button" data-view="catalog">Ir al catálogo</button></div>';
      return;
    }
    container.innerHTML = `<div class="cart-layout"><div class="cart-lines">${cart.items.map((item) => `<article class="cart-line"><div><h3>${escapeHtml(item.maquinaria_nombre)}</h3><p>SKU ${escapeHtml(item.maquinaria_sku)} · ${item.cantidad} unidad${item.cantidad === 1 ? "" : "es"}</p><p>${dateLabel(item.fecha_inicio)} — ${dateLabel(item.fecha_fin)} · ${item.dias} días</p></div><span class="line-price">${money(item.costo_total)}</span><button class="remove-button" type="button" data-action="remove-cart" data-id="${item.maquinaria}">Quitar</button></article>`).join("")}</div>
      <aside class="summary-panel"><h2>Resumen</h2><div class="summary-row"><span>Equipos</span><strong>${cart.items.length}</strong></div><div class="summary-row summary-total"><span>Total estimado</span><strong>${money(cart.costo_total)}</strong></div><button class="button button-accent button-wide" type="button" data-action="checkout">Crear contrato</button><p class="muted small-copy">El contrato quedará pendiente de confirmación.</p></aside></div>`;
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>No se pudo cargar el carro</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function contractCard(contract, showCustomer = false) {
  const items = (contract.items || []).map((item) => `<span class="contract-item">${escapeHtml(item.maquinaria_nombre)} · ${item.cantidad} u. · ${dateLabel(item.fecha_inicio)} – ${dateLabel(item.fecha_fin)}</span>`).join("");
  return `<article class="contract-card"><div class="contract-card-head"><div><p class="contract-ref">Contrato ${escapeHtml(String(contract.reference).slice(0, 13))}…</p><p class="contract-meta">${showCustomer ? `${escapeHtml(contract.user_name)} · ` : ""}${dateLabel(contract.created_at?.slice(0, 10))}</p></div><span class="status-pill" data-status="${escapeHtml(contract.status)}">${escapeHtml(contract.status)}</span></div><div class="contract-items">${items || '<span class="contract-item">Sin equipos</span>'}</div><p class="contract-total">Total ${money(contract.costo_total)}</p></article>`;
}

async function loadCustomerContracts() {
  const container = byId("customer-contracts");
  container.innerHTML = '<div class="empty-state">Cargando contratos...</div>';
  try {
    const payload = await request("/api/mis-contratos/");
    const contracts = listResults(payload);
    container.innerHTML = contracts.length ? `<div class="contract-list">${contracts.map((contract) => contractCard(contract)).join("")}</div>` : '<div class="empty-state"><h3>Aún no tienes contratos</h3><p>Cuando confirmes un carro, aparecerá aquí el seguimiento del arriendo.</p></div>';
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>No se pudieron cargar tus contratos</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function resetMachineForm() {
  const form = byId("machine-form");
  form.reset();
  form.elements.id.value = "";
  byId("machine-form").hidden = true;
}

function renderInventory() {
  const rows = byId("inventory-rows");
  const search = byId("inventory-search").value.trim().toLocaleLowerCase("es");
  const category = byId("inventory-category").value;
  const machines = state.machines.filter((machine) => {
    const searchable = [machine.nombre, machine.marca, machine.modelo, machine.sku].join(" ").toLocaleLowerCase("es");
    return (!search || searchable.includes(search)) && (!category || String(machine.categoria) === category);
  });
  byId("inventory-summary").textContent = `${machines.length} de ${state.machines.length} equipos`;
  if (!machines.length) {
    rows.innerHTML = '<tr><td colspan="5">No hay equipos registrados.</td></tr>';
    return;
  }
  rows.innerHTML = machines.map((machine) => `<tr><td><strong>${escapeHtml(machine.nombre)}</strong><small>${escapeHtml(machine.marca)} ${escapeHtml(machine.modelo || "")}</small></td><td>${escapeHtml(machine.sku)}</td><td>${money(machine.tarifa_diaria)}</td><td>${machine.unidades_disponibles} / ${machine.unidades_totales}</td><td><div class="table-actions"><button class="table-action" type="button" data-action="add-stock" data-id="${machine.id}">Agregar stock</button><button class="table-action danger" type="button" data-action="remove-stock" data-id="${machine.id}" ${machine.unidades_disponibles < 1 ? "disabled" : ""}>Retirar stock</button><button class="table-action" type="button" data-action="edit-machine" data-id="${machine.id}">Editar</button><button class="table-action danger" type="button" data-action="delete-machine" data-id="${machine.id}">Eliminar</button></div></td></tr>`).join("");
}

function allowedStatuses(current) {
  const transitions = {
    PENDIENTE: ["PAGADO", "CANCELADO"],
    PAGADO: ["ENTREGADO", "CANCELADO"],
    ENTREGADO: ["COMPLETADO", "CANCELADO"],
  };
  return transitions[current] || [];
}

function renderExecutiveContracts(contracts) {
  const container = byId("executive-contracts");
  if (!contracts.length) {
    container.innerHTML = '<div class="empty-state"><h3>No hay contratos</h3><p>Los nuevos contratos aparecerán aquí.</p></div>';
    return;
  }
  container.innerHTML = contracts.map((contract) => {
    const options = allowedStatuses(contract.status);
    const selector = options.length ? `<select aria-label="Cambiar estado del contrato ${contract.id}" data-contract-status="${contract.id}"><option value="">${escapeHtml(contract.status)}</option>${options.map((option) => `<option value="${option}">${option}</option>`).join("")}</select>` : `<span class="status-pill" data-status="${escapeHtml(contract.status)}">${escapeHtml(contract.status)}</span>`;
    return `<article class="executive-contract"><div><strong>${escapeHtml(contract.user_name)} · ${money(contract.costo_total)}</strong><p>Contrato #${contract.id} · ${escapeHtml(contract.items?.length || 0)} equipo(s) · ${dateLabel(contract.created_at?.slice(0, 10))}</p></div>${selector}</article>`;
  }).join("");
}

async function loadManager() {
  try {
    const [machines, contracts] = await Promise.all([
      loadAllMachines(),
      request("/api/contratos/"),
    ]);
    state.machines = machines;
    renderInventory();
    renderExecutiveContracts(listResults(contracts));
    if (!state.categories.length) await loadCategories();
  } catch (error) {
    byId("inventory-rows").innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
    byId("executive-contracts").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

async function loadAllMachines() {
  const machines = [];
  let path = "/api/maquinarias/";
  while (path) {
    const payload = await request(path);
    machines.push(...listResults(payload));
    if (payload?.next) {
      const next = new URL(payload.next, window.location.origin);
      path = `${next.pathname}${next.search}`;
    } else {
      path = null;
    }
  }
  return machines;
}

function editMachine(machineId) {
  const machine = state.machines.find((item) => String(item.id) === String(machineId));
  if (!machine) return;
  const form = byId("machine-form");
  for (const field of ["id", "nombre", "marca", "modelo", "sku", "descripcion", "categoria", "tarifa_diaria", "garantia_fija", "unidades_totales"]) {
    form.elements[field].value = machine[field] ?? "";
  }
  form.hidden = false;
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showStockDialog(machineId, operation = "agregar") {
  const machine = state.machines.find((item) => String(item.id) === String(machineId));
  if (!machine) return;
  const form = byId("stock-form");
  form.elements.maquinaria.value = machine.id;
  form.elements.operacion.value = operation;
  form.elements.cantidad.value = "1";
  const removing = operation === "retirar";
  byId("stock-title").textContent = `${removing ? "Retirar stock de" : "Agregar stock a"} ${machine.nombre}`;
  byId("stock-current").textContent = `${machine.unidades_disponibles} disponibles de ${machine.unidades_totales} unidades totales.`;
  form.elements.cantidad.max = removing ? machine.unidades_disponibles : "";
  form.querySelector("label").firstChild.textContent = removing ? "Unidades a retirar" : "Unidades a agregar";
  byId("stock-submit").textContent = removing ? "Retirar del inventario" : "Agregar al inventario";
  byId("stock-dialog").showModal();
}

async function handleAction(button) {
  const id = button.dataset.id;
  if (button.dataset.action === "rent") showRentDialog(id);
  if (button.dataset.action === "add-stock") showStockDialog(id);
  if (button.dataset.action === "remove-stock") showStockDialog(id, "retirar");
  if (button.dataset.action === "remove-cart") {
    try {
      await request(`/api/carro-arriendo/?machinery_id=${encodeURIComponent(id)}`, { method: "DELETE" });
      showToast("Equipo eliminado del carro.");
      await loadCart();
    } catch (error) { showToast(error.message, true); }
  }
  if (button.dataset.action === "checkout") {
    button.disabled = true;
    try {
      const contract = await request("/api/contratos/checkout/", { method: "POST", body: JSON.stringify({}) });
      showToast(`Contrato creado: ${String(contract.reference).slice(0, 8)}.`);
      await loadCart();
    } catch (error) { showToast(error.message, true); button.disabled = false; }
  }
  if (button.dataset.action === "edit-machine") editMachine(id);
  if (button.dataset.action === "delete-machine" && window.confirm("¿Eliminar este equipo del catálogo?")) {
    try {
      await request(`/api/maquinarias/${id}/`, { method: "DELETE" });
      showToast("Equipo eliminado.");
      await loadManager();
    } catch (error) { showToast(error.message, true); }
  }
}

document.addEventListener("click", (event) => {
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) { setView(viewButton.dataset.view); return; }
  const authModeButton = event.target.closest("[data-auth-mode]");
  if (authModeButton) { setAuthMode(authModeButton.dataset.authMode); return; }
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) handleAction(actionButton);
});

byId("logout-button").addEventListener("click", () => { clearSession(); setView("catalog"); });
byId("catalog-filters").addEventListener("submit", (event) => { event.preventDefault(); state.catalogPage = 1; loadCatalog(); });
byId("clear-filters").addEventListener("click", () => { byId("catalog-filters").reset(); state.catalogPage = 1; loadCatalog(); });
byId("previous-page").addEventListener("click", () => { if (state.catalogHasPrevious) { state.catalogPage -= 1; loadCatalog(); } });
byId("next-page").addEventListener("click", () => { if (state.catalogHasNext) { state.catalogPage += 1; loadCatalog(); } });
byId("close-rent").addEventListener("click", () => byId("rent-dialog").close());
byId("close-stock").addEventListener("click", () => byId("stock-dialog").close());
byId("stock-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector('[type="submit"]');
  const machineryId = form.elements.maquinaria.value;
  const quantity = Number(form.elements.cantidad.value);
  const operation = form.elements.operacion.value;
  submitButton.disabled = true;
  try {
    await request(`/api/maquinarias/${machineryId}/${operation === "retirar" ? "retirar-stock" : "agregar-stock"}/`, {
      method: "PATCH",
      body: JSON.stringify({ cantidad: quantity }),
    });
    byId("stock-dialog").close();
    showToast(`${operation === "retirar" ? "Se retiraron" : "Se agregaron"} ${quantity} unidad${quantity === 1 ? "" : "es"} ${operation === "retirar" ? "del" : "al"} inventario.`);
    await loadManager();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submitButton.disabled = false;
  }
});
byId("rent-form").elements.fecha_inicio.addEventListener("change", (event) => {
  const nextDay = new Date(`${event.target.value}T12:00:00`);
  nextDay.setDate(nextDay.getDate() + 1);
  const endInput = byId("rent-form").elements.fecha_fin;
  endInput.min = nextDay.toISOString().slice(0, 10);
  if (endInput.value < endInput.min) endInput.value = endInput.min;
});
byId("rent-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = Object.fromEntries(new FormData(form));
  payload.maquinaria = Number(payload.maquinaria);
  payload.cantidad = Number(payload.cantidad);
  try {
    await request("/api/carro-arriendo/", { method: "POST", body: JSON.stringify(payload) });
    byId("rent-dialog").close();
    showToast("Equipo agregado al carro.");
    const cart = await request("/api/carro-arriendo/");
    updateCartCount(cart.items.length);
  } catch (error) { showToast(error.message, true); }
});

byId("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const tokens = await request("/api/auth/token/", { method: "POST", body: JSON.stringify(form) });
    setSession(tokens);
    showToast(`Sesión iniciada como ${tokens.user.username}.`);
    setView(tokens.user.is_staff ? "manager" : "catalog");
  } catch (error) { showToast(error.message, true); }
});

byId("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  try {
    await request("/api/auth/register/", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    setAuthMode("login");
    byId("login-form").elements.username.value = payload.username;
    showToast("Cuenta creada. Ahora puedes iniciar sesión.");
  } catch (error) { showToast(error.message, true); }
});

byId("new-machine").addEventListener("click", () => {
  resetMachineForm();
  byId("machine-form").hidden = false;
  byId("machine-form").scrollIntoView({ behavior: "smooth", block: "center" });
});
byId("cancel-machine").addEventListener("click", resetMachineForm);
byId("machine-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  const id = values.id;
  delete values.id;
  values.categoria = Number(values.categoria);
  values.tarifa_diaria = Number(values.tarifa_diaria).toFixed(2);
  values.garantia_fija = Number(values.garantia_fija).toFixed(2);
  values.unidades_totales = Number(values.unidades_totales);
  try {
    await request(id ? `/api/maquinarias/${id}/` : "/api/maquinarias/", { method: id ? "PATCH" : "POST", body: JSON.stringify(values) });
    resetMachineForm();
    showToast(id ? "Equipo actualizado." : "Equipo agregado al catálogo.");
    await loadManager();
  } catch (error) { showToast(error.message, true); }
});
byId("refresh-contracts").addEventListener("click", loadManager);
byId("inventory-search").addEventListener("input", renderInventory);
byId("inventory-category").addEventListener("change", renderInventory);
byId("clear-inventory-filters").addEventListener("click", () => {
  byId("inventory-search").value = "";
  byId("inventory-category").value = "";
  renderInventory();
});
byId("executive-contracts").addEventListener("change", async (event) => {
  const select = event.target.closest("[data-contract-status]");
  if (!select || !select.value) return;
  const contractId = select.dataset.contractStatus;
  try {
    await request(`/api/contratos/${contractId}/estado/`, { method: "PATCH", body: JSON.stringify({ status: select.value }) });
    showToast("Estado del contrato actualizado.");
    await loadManager();
  } catch (error) { showToast(error.message, true); await loadManager(); }
});

renderAccount();
loadCategories().then(loadCatalog);
setInterval(() => {
  if (state.page === "catalog" && document.visibilityState === "visible") loadCatalog();
}, 5000);
document.addEventListener("visibilitychange", () => {
  if (state.page === "catalog" && document.visibilityState === "visible") loadCatalog();
});
window.addEventListener("focus", () => {
  if (state.page === "catalog") loadCatalog();
});

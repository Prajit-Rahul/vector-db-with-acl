let embeddingDims = 1536;

const DEMO_IDS = {
  tenantId: "11111111-1111-1111-1111-111111111111",
  userId: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
  documentId: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1",
  groupA: "cccccccc-cccc-cccc-cccc-ccccccccccc1",
  groupB: "cccccccc-cccc-cccc-cccc-ccccccccccc2",
};

const storage = {
  tenant: "acl_console_tenant_id",
  user: "acl_console_user_id",
};

const el = {
  tenantId: document.getElementById("tenant-id"),
  userId: document.getElementById("user-id"),
  saveIdentity: document.getElementById("save-identity"),
  loadDemo: document.getElementById("load-demo"),
  identitySaveStatus: document.getElementById("identity-save-status"),

  ingestDocumentId: document.getElementById("ingest-document-id"),
  ingestChunkIndex: document.getElementById("ingest-chunk-index"),
  ingestTokenCount: document.getElementById("ingest-token-count"),
  ingestContent: document.getElementById("ingest-content"),
  ingestGroupIds: document.getElementById("ingest-group-ids"),
  ingestMetadata: document.getElementById("ingest-metadata"),
  ingestAutoEmbed: document.getElementById("ingest-auto-embed"),
  ingestEmbedding: document.getElementById("ingest-embedding"),
  ingestSubmit: document.getElementById("ingest-submit"),

  searchQueryText: document.getElementById("search-query-text"),
  searchTopK: document.getElementById("search-top-k"),
  searchAutoEmbed: document.getElementById("search-auto-embed"),
  searchEmbedding: document.getElementById("search-embedding"),
  searchSubmit: document.getElementById("search-submit"),

  aclUserId: document.getElementById("acl-user-id"),
  aclUserGroups: document.getElementById("acl-user-groups"),
  replaceUserGroups: document.getElementById("replace-user-groups"),

  aclChunkId: document.getElementById("acl-chunk-id"),
  aclChunkGroups: document.getElementById("acl-chunk-groups"),
  replaceChunkAcl: document.getElementById("replace-chunk-acl"),

  resultMeta: document.getElementById("result-meta"),
  resultList: document.getElementById("result-list"),
  eventLog: document.getElementById("event-log"),
};

let identitySaveStatusTimer = null;

function log(message, level = "info") {
  const stamp = new Date().toISOString();
  const line = `[${stamp}] ${message}`;
  el.eventLog.textContent = `${line}\n${el.eventLog.textContent}`.trim();
  if (level === "error") {
    el.eventLog.classList.add("log-error");
    setTimeout(() => el.eventLog.classList.remove("log-error"), 500);
  }
}

function setDemoValues() {
  el.tenantId.value = DEMO_IDS.tenantId;
  el.userId.value = DEMO_IDS.userId;
  el.ingestDocumentId.value = DEMO_IDS.documentId;
  el.ingestGroupIds.value = DEMO_IDS.groupA;
  el.aclUserId.value = DEMO_IDS.userId;
  el.aclUserGroups.value = `${DEMO_IDS.groupA}, ${DEMO_IDS.groupB}`;
  el.aclChunkGroups.value = DEMO_IDS.groupA;
  el.ingestMetadata.value = '{"source":"ui-demo","category":"finance"}';
  el.ingestContent.value = "Q4 revenue increased 18 percent year over year across enterprise accounts.";
  el.searchQueryText.value = "quarterly enterprise revenue growth";
  log("Loaded demo IDs and sample inputs");
}

function setIdentitySaveStatus(message, saved = false) {
  if (!el.identitySaveStatus) {
    return;
  }

  el.identitySaveStatus.textContent = message;
  el.identitySaveStatus.classList.toggle("is-saved", saved);
}

function markIdentitySaved() {
  const stamp = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

  setIdentitySaveStatus(`Saved identity to browser storage at ${stamp}.`, true);

  if (identitySaveStatusTimer) {
    clearTimeout(identitySaveStatusTimer);
  }

  identitySaveStatusTimer = setTimeout(() => {
    setIdentitySaveStatus("Identity is saved. Update fields and click Save Identity to store changes.");
  }, 3200);
}

function persistIdentity(options = {}) {
  const { showFeedback = false } = options;
  localStorage.setItem(storage.tenant, el.tenantId.value.trim());
  localStorage.setItem(storage.user, el.userId.value.trim());
  if (!el.aclUserId.value.trim()) {
    el.aclUserId.value = el.userId.value.trim();
  }
  log("Saved identity context to browser storage");

  if (showFeedback) {
    markIdentitySaved();
  }
}

function hydrateIdentity() {
  const tenant = localStorage.getItem(storage.tenant);
  const user = localStorage.getItem(storage.user);
  if (tenant) {
    el.tenantId.value = tenant;
  }
  if (user) {
    el.userId.value = user;
    el.aclUserId.value = user;
  }

  if (!tenant || !user) {
    setDemoValues();
    persistIdentity();
    setIdentitySaveStatus("Demo identity was auto-loaded and saved for this session.", true);
    return;
  }

  setIdentitySaveStatus("Loaded saved identity from browser storage.");
}

function getAuthHeaders() {
  const tenant = el.tenantId.value.trim();
  const user = el.userId.value.trim();
  if (!tenant || !user) {
    throw new Error("Tenant ID and User ID are required");
  }
  return {
    "x-authenticated-tenant-id": tenant,
    "x-authenticated-user-id": user,
  };
}

function parseCsvUUIDs(input) {
  if (!input.trim()) {
    return [];
  }
  return input
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function parseJsonField(text, label) {
  if (!text.trim()) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label} must be valid JSON`);
  }
}

function parseEmbeddingField(text, label) {
  const parsed = parseJsonField(text, label);
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON array of numbers`);
  }
  if (parsed.length !== embeddingDims) {
    throw new Error(`${label} must contain exactly ${embeddingDims} numbers`);
  }

  parsed.forEach((value) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new Error(`${label} contains non-numeric values`);
    }
  });

  return parsed;
}

function fnv1a32(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function deterministicEmbedding(text, dims = embeddingDims) {
  const normalized = text.trim().toLowerCase();
  if (!normalized) {
    throw new Error("Text is required to generate embedding");
  }

  const output = new Array(dims).fill(0);
  for (let index = 0; index < normalized.length; index += 1) {
    const code = normalized.charCodeAt(index);
    const idxA = (Math.imul(code + 31, 131) + index * 17) % dims;
    const idxB = (Math.imul(code + 7, 197) + index * 29) % dims;
    output[idxA] += (code % 29) / 29;
    output[idxB] -= (code % 31) / 31;
  }

  let state = fnv1a32(normalized);
  for (let idx = 0; idx < dims; idx += 1) {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    const noise = ((state >>> 0) / 4294967295) * 2 - 1;
    output[idx] += noise * 0.04;
  }

  let norm = 0;
  output.forEach((value) => {
    norm += value * value;
  });
  norm = Math.sqrt(norm) || 1;

  return output.map((value) => Number((value / norm).toFixed(10)));
}

async function requestJson(path, options = {}) {
  const headers = {
    "content-type": "application/json",
    ...getAuthHeaders(),
    ...(options.headers || {}),
  };

  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body,
  });

  const raw = await response.text();
  let payload = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = { raw };
    }
  }

  if (!response.ok) {
    const reason = payload && payload.detail ? payload.detail : response.statusText;
    throw new Error(`${response.status} ${reason}`);
  }

  return payload;
}

function renderResults(results, meta) {
  el.resultMeta.textContent = meta;
  el.resultList.innerHTML = "";

  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "result-item";
    empty.textContent = "No authorized chunks found.";
    el.resultList.appendChild(empty);
    return;
  }

  results.forEach((result) => {
    const row = document.createElement("article");
    row.className = "result-item";

    const heading = document.createElement("strong");
    heading.textContent = `chunk:${result.chunk_id} | doc:${result.document_id}`;

    const content = document.createElement("p");
    content.textContent = result.content;

    const details = document.createElement("div");
    details.className = "result-meta-inline";
    details.textContent = `similarity=${Number(result.similarity).toFixed(6)}  chunk_index=${result.chunk_index}`;

    row.append(heading, content, details);
    el.resultList.appendChild(row);
  });
}

async function onIngest() {
  try {
    persistIdentity();

    const content = el.ingestContent.value.trim();
    if (!content) {
      throw new Error("Chunk content is required");
    }

    const groupIds = parseCsvUUIDs(el.ingestGroupIds.value);
    if (!groupIds.length) {
      throw new Error("At least one ACL group ID is required");
    }

    const metadata = parseJsonField(el.ingestMetadata.value, "Metadata JSON") || {};

    const embedding = el.ingestAutoEmbed.checked
      ? deterministicEmbedding(content)
      : parseEmbeddingField(el.ingestEmbedding.value, "Embedding JSON");

    const tokenCountRaw = el.ingestTokenCount.value.trim();
    const payload = {
      document_id: el.ingestDocumentId.value.trim(),
      chunk_index: Number(el.ingestChunkIndex.value),
      content,
      embedding,
      token_count: tokenCountRaw ? Number(tokenCountRaw) : null,
      metadata,
      acl_group_ids: groupIds,
    };

    const result = await requestJson("/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    el.aclChunkId.value = String(result.chunk_id);
    log(`Ingested chunk ${result.chunk_id} and assigned ${result.assigned_group_ids.length} ACL groups`);
  } catch (error) {
    log(`Ingest failed: ${error.message}`, "error");
  }
}

async function onSearch() {
  try {
    persistIdentity();

    const queryText = el.searchQueryText.value.trim();
    const queryEmbedding = el.searchAutoEmbed.checked
      ? deterministicEmbedding(queryText)
      : parseEmbeddingField(el.searchEmbedding.value, "Query embedding JSON");

    const payload = {
      user_id: el.userId.value.trim(),
      query_embedding: queryEmbedding,
      top_k: Number(el.searchTopK.value),
    };

    const response = await requestJson("/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    renderResults(
      response.results || [],
      `Returned ${response.results.length} authorized chunks for user ${response.user_id}`
    );
    log(`Search succeeded. Authorized results: ${response.results.length}`);
  } catch (error) {
    log(`Search failed: ${error.message}`, "error");
  }
}

async function onReplaceUserGroups() {
  try {
    persistIdentity();

    const userId = el.aclUserId.value.trim();
    if (!userId) {
      throw new Error("Target user ID is required");
    }

    const payload = {
      group_ids: parseCsvUUIDs(el.aclUserGroups.value),
    };

    const response = await requestJson(`/users/${encodeURIComponent(userId)}/groups`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });

    log(`Updated user groups for ${response.user_id}. Count=${response.group_ids.length}`);
  } catch (error) {
    log(`Update user groups failed: ${error.message}`, "error");
  }
}

async function onReplaceChunkAcl() {
  try {
    persistIdentity();

    const chunkId = Number(el.aclChunkId.value);
    if (!chunkId) {
      throw new Error("Chunk ID is required");
    }

    const payload = {
      group_ids: parseCsvUUIDs(el.aclChunkGroups.value),
    };

    const response = await requestJson(`/chunks/${chunkId}/acl-groups`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });

    log(`Updated ACL groups for chunk ${response.chunk_id}. Count=${response.assigned_group_ids.length}`);
  } catch (error) {
    log(`Update chunk ACL failed: ${error.message}`, "error");
  }
}

function bindEvents() {
  el.saveIdentity.addEventListener("click", () => persistIdentity({ showFeedback: true }));
  el.loadDemo.addEventListener("click", () => {
    setDemoValues();
    persistIdentity({ showFeedback: true });
  });

  el.ingestSubmit.addEventListener("click", onIngest);
  el.searchSubmit.addEventListener("click", onSearch);
  el.replaceUserGroups.addEventListener("click", onReplaceUserGroups);
  el.replaceChunkAcl.addEventListener("click", onReplaceChunkAcl);
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(`health status=${response.status}`);
    }
    const payload = await response.json();
    if (typeof payload.embedding_dimensions === "number" && payload.embedding_dimensions > 0) {
      embeddingDims = payload.embedding_dimensions;
    }
    log(
      `API health check passed. embedding_dims=${embeddingDims}, demo_embeddings=${Boolean(
        payload.demo_embeddings_enabled
      )}`
    );
  } catch (error) {
    log(`Health check failed: ${error.message}`, "error");
  }
}

function init() {
  hydrateIdentity();
  bindEvents();
  checkHealth();
  log("Console ready");
}

init();

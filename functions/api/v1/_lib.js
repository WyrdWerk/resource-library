// Shared engine for the /api/v1 Pages Functions.
//
// This is a faithful port of scripts/search.py (deterministic lexical
// search) plus the request handling of scripts/api_server.py. Behavior
// must stay identical to the local adapter — scripts/edge_parity.py
// gates this by comparing live function output against the adapter.
//
// Data is loaded from the deployment's own static assets
// (api/v1/resources.json, taxonomy.json, index.json) so the function
// and the static catalog can never skew across deploys.

export const MAX_LIMIT = 100;

// field weights — fixed, must match scripts/search.py
const W_TITLE_TOKEN = 5.0;
const W_TITLE_PHRASE = 8.0;
const W_BRIEF_TOKEN = 2.0;
const W_BRIEF_PHRASE = 4.0;
const W_TAX_LABEL = 3.0; // resource-type / topic / use-case / interface / technology labels
const W_ALIAS = 3.0; // curated synonym -> slug expansions

const TOKEN_RE = /[a-z0-9]+(?:[._-][a-z0-9]+)?/g;
const STOP = new Set((
  "a an the and or of to in on for with by from as at is are was were be been " +
  "it its this that these those you your we our they their he she his her " +
  "with without into over under between through during each other more most " +
  "very can will just than then so such no not only own same too s t d ll m re ve " +
  "com org net www http https html"
).split(" "));

export const FIELD_ALLOW = new Set([
  "schema_version", "id", "title", "canonical_url", "brief", "caveat",
  "resource_type", "topics", "use_cases", "interfaces", "technologies",
  "license", "open_source", "display_period", "legacy_categories",
  "source", "shared_on", "verification",
]);

function _stemVariants(t) {
  // Deterministic light stemming; applied symmetrically to index and
  // query tokens. Must match _stem_variants() in scripts/search.py.
  const v = new Set();
  if (t.length > 6 && t.endsWith("ation")) v.add(t.slice(0, -5) + "ate"); // generation -> generate
  if (t.length > 5 && t.endsWith("ator")) v.add(t.slice(0, -4) + "ate"); // generator -> generate
  if (t.length > 5 && t.endsWith("ing")) {
    let s = t.slice(0, -3);
    if (s.length >= 3 && s[s.length - 1] === s[s.length - 2]) s = s.slice(0, -1); // running -> run
    v.add(s);
  }
  if (t.length > 4 && t.endsWith("ed")) {
    let s = t.slice(0, -2);
    if (s.length >= 3 && s[s.length - 1] === s[s.length - 2]) s = s.slice(0, -1);
    v.add(s); // hosted -> host
  }
  if (t.length > 4 && t.endsWith("es")) v.add(t.slice(0, -2)); // watches -> watch
  if (t.length > 3 && t.endsWith("s") && !["ss", "us", "is"].some((x) => t.endsWith(x))) {
    v.add(t.slice(0, -1)); // models -> model
  }
  const out = [];
  for (const s of v) if (s.length > 2 && s !== t) out.push(s);
  return out.sort();
}

export function tokenize(text) {
  const toks = [];
  for (let t of (text || "").toLowerCase().match(TOKEN_RE) || []) {
    t = t.replace(/^[._-]+|[._-]+$/g, "");
    if (t && !STOP.has(t) && t.length > 1) {
      toks.push(t);
      toks.push(..._stemVariants(t));
    }
  }
  return toks;
}

export function normUrl(u) {
  u = (u || "").toLowerCase().trim();
  u = u.replace(/^https?:\/\//, "");
  u = u.replace(/^www\./, "");
  return u.replace(/\/+$/, "");
}

function counts(tokens) {
  const m = new Map();
  for (const t of tokens) m.set(t, (m.get(t) || 0) + 1);
  return m;
}

function sortedKeys(set) {
  return set ? Array.from(set).sort() : [];
}

function slugLabels(tax) {
  // slug -> set of label+alias tokens across all registries
  const out = new Map();
  for (const reg of ["resource-types", "topics", "use-cases", "interfaces", "technologies"]) {
    for (const [slug, entry] of Object.entries(tax[reg].values)) {
      let toks = tokenize(entry.label || "");
      for (const a of entry.aliases || []) toks = toks.concat(tokenize(a));
      if (!out.has(slug)) out.set(slug, new Set());
      for (const t of toks) out.get(slug).add(t);
    }
  }
  return out;
}

export function buildIndex(records, tax) {
  const labels = slugLabels(tax);
  // invert curated synonyms: slug -> alias tokens
  const slugAliases = new Map();
  for (const [alias, slug] of Object.entries(tax.synonyms.synonyms)) {
    if (!slugAliases.has(slug)) slugAliases.set(slug, new Set());
    for (const t of tokenize(alias)) slugAliases.get(slug).add(t);
  }

  const docs = new Map();
  const df = new Map();
  for (const r of records) {
    const rid = r.id;
    const titleToks = tokenize(r.title);
    const briefToks = tokenize(r.brief || "");
    const taxToks = [];
    for (const s of [r.resource_type, ...r.topics, ...r.use_cases, ...r.interfaces, ...r.technologies]) {
      taxToks.push(...sortedKeys(labels.get(s)));
      taxToks.push(...sortedKeys(slugAliases.get(s)));
    }
    docs.set(rid, {
      title: counts(titleToks),
      brief: counts(briefToks),
      tax: counts(taxToks),
      alias: counts([]),
      titleText: r.title.toLowerCase(),
      briefText: (r.brief || "").toLowerCase(),
      url: normUrl(r.canonical_url),
      record: r,
    });
    const seen = new Set([...titleToks, ...briefToks, ...taxToks]);
    for (const t of seen) df.set(t, (df.get(t) || 0) + 1);
  }
  const n = records.length;
  const idf = new Map();
  for (const [t, c] of df) idf.set(t, Math.log((1 + n) / (1 + c)) + 1.0);
  return { docs, idf, n };
}

export function buildFacets(taxonomy) {
  const reg = (name) => new Set(Object.keys(taxonomy[name].values));
  return {
    resource_type: reg("resource-types"),
    topic: reg("topics"),
    use_case: reg("use-cases"),
    interface: reg("interfaces"),
    technology: reg("technologies"),
    channel: new Set(["share-tech", "providers"]),
    sort: new Set(["relevance", "newest", "oldest"]),
  };
}

function matchesFilters(r, f) {
  if (!f) return true;
  if (f.resource_type && r.resource_type !== f.resource_type) return false;
  if (f.topic && !r.topics.includes(f.topic)) return false;
  if (f.use_case && !r.use_cases.includes(f.use_case)) return false;
  if (f.interface && !r.interfaces.includes(f.interface)) return false;
  if (f.technology && !r.technologies.includes(f.technology)) return false;
  if (f.channel && r.source.channel !== f.channel) return false;
  if (f.open_source != null && !!r.open_source !== f.open_source) return false;
  return true;
}

function cmpStr(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

export function search(index, query, filters = null, sort = "relevance", limit = 20, cursor = null) {
  // Returns [page, nextCursor]; page = [[id, score], ...].
  const { docs, idf } = index;
  const q = (query || "").trim();
  const ql = q.toLowerCase();
  let qtoks = tokenize(q);
  if (q.includes(".")) {
    // domain-style queries ("openrouter.com"): also try dots as separators
    for (const t of tokenize(q.replace(/\./g, " "))) {
      if (!qtoks.includes(t)) qtoks.push(t);
    }
  }
  let scored = [];

  // exact id / url short-circuit: rank 1 with a fixed top score
  if (ql) {
    for (const [rid, d] of docs) {
      if (rid === ql || d.url === normUrl(q)) {
        if (matchesFilters(d.record, filters)) scored = [[rid, 1e9]];
        break;
      }
    }
  }

  if (!scored.length && qtoks.length) {
    for (const [rid, d] of docs) {
      if (!matchesFilters(d.record, filters)) continue;
      let s = 0.0;
      for (const t of qtoks) {
        const w = idf.get(t) || 0.0;
        if (!w) continue;
        s += W_TITLE_TOKEN * w * Math.min(d.title.get(t) || 0, 3);
        s += W_BRIEF_TOKEN * w * Math.min(d.brief.get(t) || 0, 3);
        s += W_TAX_LABEL * w * Math.min(d.tax.get(t) || 0, 2);
        s += W_ALIAS * w * Math.min(d.alias.get(t) || 0, 2);
      }
      if (qtoks.length > 1) {
        if (d.titleText.includes(ql)) s += W_TITLE_PHRASE;
        else if (d.briefText.includes(ql)) s += W_BRIEF_PHRASE;
      }
      if (s > 0) scored.push([rid, s]);
    }
  }

  const son = (x) => docs.get(x[0]).record.shared_on;
  if (sort === "newest") {
    scored.sort((a, b) => cmpStr(son(b), son(a)) || cmpStr(b[0], a[0]));
    if (!qtoks.length) scored = scored.map(([rid]) => [rid, 0.0]);
    else {
      scored.sort((a, b) => (a[1] - b[1]) || cmpStr(son(a), son(b)) || cmpStr(a[0], b[0]));
      scored.sort((a, b) => cmpStr(son(b), son(a)) || cmpStr(b[0], a[0]));
    }
  } else if (sort === "oldest") {
    scored.sort((a, b) => cmpStr(son(a), son(b)) || cmpStr(a[0], b[0]));
  } else {
    scored.sort((a, b) => (b[1] - a[1]) || cmpStr(a[0], b[0]));
  }

  // stable cursor: last id of the previous page
  let start = 0;
  if (cursor) {
    for (let i = 0; i < scored.length; i++) {
      if (scored[i][0] === cursor) {
        start = i + 1;
        break;
      }
    }
  }
  const page = scored.slice(start, start + limit);
  const nextCursor = scored.length > start + limit ? page[page.length - 1][0] : null;
  return [page, nextCursor];
}

// ---------------------------------------------------------------------------
// Request/response helpers (mirror scripts/api_server.py semantics)
// ---------------------------------------------------------------------------

export function errorPayload(code, message) {
  return { error: { code, message } };
}

// Mirrors urllib.parse.parse_qs defaults: blank values are dropped,
// first occurrence wins.
export function queryParams(request) {
  const sp = new URL(request.url).searchParams;
  const values = (name) => sp.getAll(name).filter((v) => v !== "");
  return {
    get: (name) => values(name)[0] ?? null,
    has: (name) => values(name).length > 0,
  };
}

// Python int(str) semantics for our purposes: optional sign, ASCII digits.
function parseIntStrict(v) {
  const t = v.trim();
  return /^[+-]?\d+$/.test(t) ? Number(t) : NaN;
}

export function parseFields(qs) {
  const raw = qs.get("fields");
  if (!raw) return [null, null];
  const fields = raw.split(",").map((f) => f.trim()).filter((f) => f !== "");
  const bad = fields.filter((f) => !FIELD_ALLOW.has(f));
  if (bad.length) return [null, errorPayload("bad_fields", `unknown fields: ${bad.join(", ")}`)];
  return [fields, null];
}

export function sparse(rec, fields) {
  if (!fields) return rec;
  const out = {};
  for (const k of fields) if (k in rec) out[k] = rec[k];
  return out;
}

export function parseLimitCursor(qs) {
  const raw = qs.has("limit") ? qs.get("limit") : "20";
  const limit = parseIntStrict(raw);
  if (Number.isNaN(limit)) return [null, null, errorPayload("bad_limit", "limit must be an integer")];
  if (!(limit >= 1 && limit <= MAX_LIMIT)) return [null, null, errorPayload("bad_limit", `limit must be 1..${MAX_LIMIT}`)];
  return [limit, qs.get("cursor"), null];
}

export function paginate(ids, limit, cursor) {
  let start = 0;
  if (cursor) {
    const i = ids.indexOf(cursor);
    if (i === -1) return [null, errorPayload("bad_cursor", "unknown cursor")];
    start = i + 1;
  }
  const page = ids.slice(start, start + limit);
  const nxt = ids.length > start + limit ? page[page.length - 1] : null;
  return [[page, nxt], null];
}

export function parseFilters(qs, facets) {
  const filters = {};
  for (const key of ["resource_type", "topic", "use_case", "interface", "technology", "channel"]) {
    const v = qs.get(key);
    if (v) {
      if (!facets[key].has(v)) return [null, errorPayload("bad_filter", `unknown ${key}: ${v}`)];
      filters[key] = v;
    }
  }
  // `type` is accepted as an alias of resource_type
  if (qs.has("type") && !("resource_type" in filters)) {
    const v = qs.get("type");
    if (!facets.resource_type.has(v)) return [null, errorPayload("bad_filter", `unknown resource_type: ${v}`)];
    filters.resource_type = v;
  }
  const osRaw = qs.has("open_source") ? qs.get("open_source") : null;
  if (osRaw !== null) {
    if (osRaw === "true") filters.open_source = true;
    else if (osRaw === "false") filters.open_source = false;
    else return [null, errorPayload("bad_filter", "open_source must be true or false")];
  }
  const sort = qs.get("sort") || "relevance";
  if (!facets.sort.has(sort)) return [null, errorPayload("bad_sort", "sort must be relevance|newest|oldest")];
  return [filters, null];
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function etagMatches(request, etag) {
  const inm = request.headers.get("if-none-match");
  if (!inm) return false;
  const candidates = inm.split(",").map((v) => v.trim());
  if (candidates.includes("*")) return true;
  const unquoted = etag.replace(/^"|"$/g, "");
  return candidates.some((v) => {
    const t = v.replace(/^W\//, "");
    return t === etag || t.replace(/^"|"$/g, "") === unquoted;
  });
}

// Build a JSON response with the adapter's header contract:
// ETag + If-None-Match -> 304, CORS *, HEAD mirrors GET headers.
export async function sendJson(request, payload, { status = 200, cacheControl = null, lastModified = null } = {}) {
  const body = JSON.stringify(payload);
  const etag = `"${await sha256Hex(body)}"`;
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "ETag": etag,
    "Access-Control-Allow-Origin": "*",
  };
  if (cacheControl) headers["Cache-Control"] = cacheControl;
  if (lastModified) headers["Last-Modified"] = lastModified;
  if (status === 200 && etagMatches(request, etag)) {
    const h304 = { "ETag": etag, "Access-Control-Allow-Origin": "*", "Cache-Control": cacheControl || "no-store" };
    return new Response(null, { status: 304, headers: h304 });
  }
  if (request.method === "HEAD") {
    headers["Content-Length"] = String(new TextEncoder().encode(body).length);
    return new Response(null, { status, headers });
  }
  return new Response(body, { status, headers });
}

export function optionsResponse() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
      "Access-Control-Allow-Headers": "If-None-Match",
      "Content-Length": "0",
    },
  });
}

export function methodNotAllowed() {
  return {
    status: 405,
    payload: errorPayload("method_not_allowed", "method not allowed; use GET, HEAD, or OPTIONS"),
  };
}

// ---------------------------------------------------------------------------
// Catalog loading (isolate-scoped cache; assets change only on redeploy)
// ---------------------------------------------------------------------------

let _state = null;

async function fetchAsset(env, request, path) {
  const res = await env.ASSETS.fetch(new Request(new URL(path, request.url)));
  if (!res.ok) throw new Error(`asset ${path} -> HTTP ${res.status}`);
  return res.json();
}

export async function getState(env, request) {
  if (_state) return _state;
  const [records, taxonomy, manifest] = await Promise.all([
    fetchAsset(env, request, "/api/v1/resources.json"),
    fetchAsset(env, request, "/api/v1/taxonomy.json"),
    fetchAsset(env, request, "/api/v1/index.json"),
  ]);
  const byId = new Map(records.map((r) => [r.id, r]));
  const lastModified = manifest.generated_at ? new Date(manifest.generated_at).toUTCString() : null;
  _state = {
    records,
    byId,
    taxonomy,
    manifest,
    lastModified,
    index: buildIndex(records, taxonomy),
    facets: buildFacets(taxonomy),
  };
  return _state;
}

// Route dispatch shared by all /api/v1 function files:
// OPTIONS -> CORS preflight; non-read methods -> 405; load errors -> 503.
export async function handle(context, handler) {
  const { request } = context;
  if (request.method === "OPTIONS") return optionsResponse();
  if (!["GET", "HEAD"].includes(request.method)) {
    const m = methodNotAllowed();
    return sendJson(request, m.payload, { status: m.status, cacheControl: "no-store" });
  }
  let state;
  try {
    state = await getState(context.env, request);
  } catch {
    return sendJson(request, errorPayload("catalog_unavailable", "catalog assets unavailable"), {
      status: 503, cacheControl: "no-store",
    });
  }
  try {
    return await handler(request, state);
  } catch {
    return sendJson(request, errorPayload("internal", "unexpected error"), {
      status: 500, cacheControl: "no-store",
    });
  }
}

// GET /api/v1/resources/{id} — one canonical record by id.
// Mirrors the /api/v1/resources/<id> route of scripts/api_server.py.
// Cache-Control 3600s per docs/api-spec.md §8 (single record: 1 hour).
import { handle, parseFields, queryParams, sendJson, sparse } from "../_lib.js";

export async function onRequest(context) {
  return handle(context, async (request, state) => {
    // take the raw (still percent-encoded) segment, like the adapter does
    const raw = new URL(request.url).pathname.slice("/api/v1/resources/".length);
    let rid = raw;
    try {
      rid = decodeURIComponent(raw);
    } catch {
      rid = raw;
    }
    const rec = state.byId.get(rid);
    if (!rec) {
      return sendJson(request, { error: { code: "not_found", message: `no resource '${rid}'` } }, {
        status: 404, cacheControl: "no-store",
      });
    }
    const qs = queryParams(request);
    const [fields, fieldsErr] = parseFields(qs);
    if (fieldsErr) return sendJson(request, fieldsErr, { status: 400, cacheControl: "no-store" });
    return sendJson(request, sparse(rec, fields), {
      cacheControl: "public, max-age=3600",
      lastModified: state.lastModified,
    });
  });
}

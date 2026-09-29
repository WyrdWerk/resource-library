// GET /api/v1/resources — canonical records in stable order, paginated.
// Mirrors the /api/v1/resources.json collection route of
// scripts/api_server.py (the static api/v1/resources.json asset stays the
// full raw array; this route adds fields/limit/cursor).
// Cache-Control 300s per docs/api-spec.md §8 (resources: 5 min).
import { handle, paginate, parseFields, parseLimitCursor, queryParams, sendJson, sparse } from "./_lib.js";

export async function onRequest(context) {
  return handle(context, async (request, state) => {
    const qs = queryParams(context.request);
    const [fields, fieldsErr] = parseFields(qs);
    if (fieldsErr) return sendJson(request, fieldsErr, { status: 400, cacheControl: "no-store" });
    const [limit, cursor, limitErr] = parseLimitCursor(qs);
    if (limitErr) return sendJson(request, limitErr, { status: 400, cacheControl: "no-store" });

    const ids = state.records.map((r) => r.id);
    const [res, cursorErr] = paginate(ids, limit, cursor);
    if (cursorErr) return sendJson(request, cursorErr, { status: 400, cacheControl: "no-store" });
    const [page, nextCursor] = res;
    return sendJson(request, {
      records: page.map((id) => sparse(state.byId.get(id), fields)),
      next_cursor: nextCursor,
      total: ids.length,
    }, {
      cacheControl: "public, max-age=300",
      lastModified: state.lastModified,
    });
  });
}

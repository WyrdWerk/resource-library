// GET /api/v1/search — deterministic lexical search.
// Mirrors route_search() in scripts/api_server.py; Cache-Control 60s per
// docs/api-spec.md §8 (search: 1 min).
import { handle, parseFields, parseFilters, parseLimitCursor, queryParams, search, sendJson, sparse } from "./_lib.js";

export async function onRequest(context) {
  return handle(context, async (request, state) => {
    const qs = queryParams(context.request);
    const q = qs.get("q") || "";
    const [filters, filterErr] = parseFilters(qs, state.facets);
    if (filterErr) return sendJson(request, filterErr, { status: 400, cacheControl: "no-store" });
    const [fields, fieldsErr] = parseFields(qs);
    if (fieldsErr) return sendJson(request, fieldsErr, { status: 400, cacheControl: "no-store" });
    const [limit, cursor, limitErr] = parseLimitCursor(qs);
    if (limitErr) return sendJson(request, limitErr, { status: 400, cacheControl: "no-store" });

    const sort = qs.get("sort") || "relevance";
    const [page, nextCursor] = search(state.index, q, filters, sort, limit, cursor);
    const docs = state.index.docs;
    return sendJson(request, {
      query: q,
      filters,
      sort,
      limit,
      results: page.map(([rid]) => sparse(docs.get(rid).record, fields)),
      next_cursor: nextCursor,
    }, {
      cacheControl: "public, max-age=60",
      lastModified: state.lastModified,
    });
  });
}

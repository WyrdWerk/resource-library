#!/usr/bin/env python3
"""Validate the canonical catalog: taxonomy registries + resource records.

Checks:
  - every taxonomy file validates against schemas/taxonomy.schema.json
  - no duplicate aliases within or across registries; every synonym target
    resolves to exactly one registry slug; no alias shadows a real slug
    from another registry (ambiguity guard)
  - every catalog/resources/<id>.json validates against
    schemas/resource.schema.json (JSON Schema 2020-12, format assertions on)
  - filename stem == record id; IDs unique; canonical_urls unique

Usage: python3 scripts/validate_catalog.py [repo-root]
Exit 0 when clean, 1 with a printed error list otherwise.
Requires: jsonschema (pip install jsonschema)
"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    sys.exit("validate_catalog.py requires the 'jsonschema' package: pip install jsonschema")

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
TAX_DIR = ROOT / "catalog" / "taxonomy"
RES_DIR = ROOT / "catalog" / "resources"

TAX_FILES = {
    "resource-types.json": "resource_type",
    "topics.json": "topics",
    "use-cases.json": "use_cases",
    "interfaces.json": "interfaces",
    "technologies.json": "technologies",
}
FACET_TO_SCHEMA_KEY = {
    "resource_type": "resource_type",
    "topics": "topics",
    "use_cases": "use_cases",
    "interfaces": "interfaces",
    "technologies": "technologies",
}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    errors = []
    tax_schema = load(SCHEMAS / "taxonomy.schema.json")
    res_schema = load(SCHEMAS / "resource.schema.json")

    registries = {}
    slug_to_facet = {}
    alias_to_slugs = {}
    for fname, facet in TAX_FILES.items():
        p = TAX_DIR / fname
        if not p.exists():
            errors.append(f"missing taxonomy file: {fname}")
            continue
        doc = load(p)
        for e in Draft202012Validator(tax_schema).iter_errors(doc):
            errors.append(f"{fname}: schema: {e.message}")
        registries[facet] = doc
        for slug, val in doc.get("values", {}).items():
            if slug in slug_to_facet:
                errors.append(f"slug {slug!r} defined in more than one registry")
            slug_to_facet[slug] = facet
            for a in val.get("aliases", []):
                alias_to_slugs.setdefault(a, []).append((facet, slug))

    # alias integrity
    for alias, targets in alias_to_slugs.items():
        if len({t[1] for t in targets}) > 1:
            errors.append(f"alias {alias!r} maps to multiple slugs: {targets}")
        if alias in slug_to_facet:
            errors.append(f"alias {alias!r} shadows a real slug ({slug_to_facet[alias]})")
    syn_path = TAX_DIR / "synonyms.json"
    if syn_path.exists():
        syns = load(syn_path)["synonyms"]
        for term, target in syns.items():
            facets = {f for s, f in slug_to_facet.items() if s == target}
            if not facets:
                errors.append(f"synonym {term!r} -> unknown slug {target!r}")
            elif len(facets) > 1:
                errors.append(f"synonym {term!r} -> ambiguous slug {target!r}")
    else:
        errors.append("missing taxonomy file: synonyms.json")

    # records
    if not RES_DIR.is_dir():
        errors.append(f"missing resources dir: {RES_DIR}")
        return report(errors)
    validator = Draft202012Validator(res_schema, format_checker=FormatChecker())
    seen_ids, seen_urls = {}, {}
    n = 0
    for p in sorted(RES_DIR.glob("*.json")):
        n += 1
        try:
            rec = load(p)
        except json.JSONDecodeError as e:
            errors.append(f"{p.name}: invalid JSON: {e}")
            continue
        for e in validator.iter_errors(rec):
            errors.append(f"{p.name}: schema: {'/'.join(map(str, e.path))}: {e.message}")
        if p.stem != rec.get("id"):
            errors.append(f"{p.name}: filename does not match record id {rec.get('id')!r}")
        rid = rec.get("id")
        if rid in seen_ids:
            errors.append(f"duplicate id {rid!r} in {p.name} and {seen_ids[rid]}")
        seen_ids[rid] = p.name
        url = rec.get("canonical_url")
        if url in seen_urls:
            errors.append(f"duplicate canonical_url {url!r} in {p.name} and {seen_urls[url]}")
        seen_urls[url] = p.name
        # taxonomy membership (belt-and-braces; schema enums cover it too)
        for facet in ("topics", "use_cases", "interfaces", "technologies"):
            for slug in rec.get(facet, []) or []:
                if slug_to_facet.get(slug) != facet:
                    errors.append(f"{p.name}: {facet} slug {slug!r} not in {facet} registry")
        rt = rec.get("resource_type")
        if rt and slug_to_facet.get(rt) != "resource_type":
            errors.append(f"{p.name}: resource_type {rt!r} not in registry")

    print(f"validated {len(registries)} taxonomy files, {n} resource records")
    return report(errors)


def report(errors):
    if errors:
        print(f"{len(errors)} ERRORS:")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("catalog valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

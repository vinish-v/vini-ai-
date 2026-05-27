from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PLUGIN_ROOT / "open_design_catalog"
MANIFEST_PATH = CATALOG_ROOT / "manifest.json"

VINI_NATIVE_SKILLS = [
    {
        "id": "canvas-design-director",
        "title": "Vini Canvas Design Director",
        "summary": "Turns a vague app request into a concrete visual direction, section plan, and quality gate.",
    },
    {
        "id": "frontend-ui-engineering",
        "title": "Frontend UI Engineering",
        "summary": "Builds polished, responsive frontend implementation with real files and maintainable component structure.",
    },
    {
        "id": "browser-visual-qa",
        "title": "Browser Visual QA",
        "summary": "Checks the generated app for blank screens, clipped text, overlap, contrast, and missing requested content.",
    },
    {
        "id": "preview-debugging",
        "title": "Preview Debugging",
        "summary": "Uses real build, preview, stderr, and HTTP evidence to diagnose why a generated app is not visible.",
    },
    {
        "id": "ship-proof",
        "title": "Ship Proof",
        "summary": "Requires build, preview, logs, screenshots or concrete verification before calling work complete.",
    },
]

DOMAIN_KEYWORDS = {
    "restaurant": {"restaurant", "dining", "menu", "chef", "reservation", "table", "food", "wine"},
    "cafe": {"cafe", "coffee", "bakery", "espresso", "latte", "brunch", "pastry"},
    "saas": {"saas", "dashboard", "analytics", "subscription", "workspace", "team", "metrics"},
    "portfolio": {"portfolio", "resume", "cv", "profile", "case", "work", "personal"},
    "ecommerce": {"shop", "store", "product", "cart", "checkout", "ecommerce", "catalog"},
    "landing": {"landing", "hero", "waitlist", "marketing", "launch", "signup"},
    "admin": {"admin", "internal", "crm", "ops", "table", "records", "workflow"},
}

PREFERRED_SKILLS_BY_DOMAIN = {
    "restaurant": {"creative-director", "design-brief", "frontend-design", "web-design-guidelines", "canvas-design"},
    "cafe": {"creative-director", "design-brief", "frontend-design", "web-design-guidelines", "canvas-design"},
    "saas": {"frontend-design", "frontend-dev", "shadcn-ui", "ui-ux-pro-max", "platform-design"},
    "portfolio": {"creative-director", "frontend-design", "web-design-guidelines", "brand-guidelines", "canvas-design"},
    "ecommerce": {"ad-creative", "frontend-design", "web-design-guidelines", "brand-guidelines", "copywriting"},
    "landing": {"ad-creative", "creative-director", "frontend-design", "web-design-guidelines", "copywriting"},
    "admin": {"frontend-dev", "shadcn-ui", "platform-design", "ui-skills", "frontend-design"},
    "web-app": {"creative-director", "frontend-design", "web-design-guidelines", "canvas-design", "design-brief"},
}

PREFERRED_DESIGNS_BY_DOMAIN = {
    "restaurant": {"cafe", "luxury", "warm-editorial", "editorial", "minimal"},
    "cafe": {"cafe", "warm-editorial", "airbnb", "bento", "minimal"},
    "saas": {"linear-app", "application", "airtable", "bento", "framer"},
    "portfolio": {"minimal", "editorial", "framer", "apple", "bento"},
    "ecommerce": {"airbnb", "bento", "apple", "luxury", "webflow"},
    "landing": {"framer", "webflow", "bento", "apple", "minimal"},
    "admin": {"application", "linear-app", "airtable", "ant", "bento"},
    "web-app": {"bento", "application", "framer", "apple", "minimal"},
}


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    title: str
    summary: str
    relative_path: str
    content: str
    kind: str

    def public(self, include_content: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "path": self.relative_path,
            "kind": self.kind,
        }
        if include_content:
            data["content"] = self.content
        return data


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _entry_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        clean = line.strip()
        if clean.startswith("#"):
            return clean.lstrip("#").strip() or fallback
    return fallback


def _entry_summary(content: str) -> str:
    lines = []
    for line in content.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        lines.append(clean.lstrip("> ").strip())
        if len(" ".join(lines)) > 260:
            break
    return " ".join(lines)[:420]


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", str(value or "").lower())
        if token
        not in {
            "and",
            "app",
            "build",
            "create",
            "for",
            "from",
            "make",
            "new",
            "page",
            "site",
            "the",
            "with",
            "website",
        }
    }


def catalog_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {
            "source": "https://github.com/nexu-io/open-design",
            "commit": None,
            "license": "Apache-2.0",
            "skills_count": 0,
            "design_systems_count": 0,
            "available": False,
        }
    data = json.loads(_read_text(MANIFEST_PATH))
    data["available"] = True
    return data


def _load_entries(root_name: str, file_name: str, kind: str) -> list[CatalogEntry]:
    root = CATALOG_ROOT / root_name
    if not root.is_dir():
        return []
    entries = []
    for path in sorted(root.glob(f"*/{file_name}")):
        entry_id = path.parent.name
        content = _read_text(path)
        entries.append(
            CatalogEntry(
                id=entry_id,
                title=_entry_title(content, entry_id.replace("-", " ").title()),
                summary=_entry_summary(content),
                relative_path=path.relative_to(CATALOG_ROOT).as_posix(),
                content=content,
                kind=kind,
            )
        )
    return entries


@lru_cache(maxsize=1)
def skills() -> tuple[CatalogEntry, ...]:
    return tuple(_load_entries("skills", "SKILL.md", "open-design-skill"))


@lru_cache(maxsize=1)
def design_systems() -> tuple[CatalogEntry, ...]:
    return tuple(_load_entries("design-systems", "DESIGN.md", "open-design-system"))


def _classify_domain(prompt: str) -> str:
    prompt_tokens = _tokens(prompt)
    scored = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = len(prompt_tokens & keywords)
        if domain in prompt.lower():
            score += 2
        scored.append((score, domain))
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else "web-app"


def _score(entry: CatalogEntry, prompt_tokens: set[str], domain: str) -> int:
    haystack = f"{entry.id} {entry.title} {entry.summary}".lower()
    entry_tokens = _tokens(haystack)
    score = len(prompt_tokens & entry_tokens) * 6
    for token in prompt_tokens:
        if token in haystack:
            score += 2
    if domain != "web-app" and domain in haystack:
        score += 18
    if entry.kind == "open-design-skill" and entry.id in PREFERRED_SKILLS_BY_DOMAIN.get(domain, set()):
        score += 80
    if entry.kind == "open-design-system" and entry.id in PREFERRED_DESIGNS_BY_DOMAIN.get(domain, set()):
        score += 80
    if entry.id in {"creative-director", "canvas-design", "frontend-ui-engineering", "open-design-landing"}:
        score += 6
    return score


def _select(entries: tuple[CatalogEntry, ...], prompt: str, domain: str, limit: int) -> list[CatalogEntry]:
    prompt_tokens = _tokens(prompt)
    ranked = sorted(entries, key=lambda entry: (_score(entry, prompt_tokens, domain), entry.id), reverse=True)
    selected = [entry for entry in ranked if _score(entry, prompt_tokens, domain) > 0][:limit]
    if not selected:
        selected = ranked[:limit]
    return selected


def select_design_context(prompt: str) -> dict[str, Any]:
    domain = _classify_domain(prompt)
    selected_skills = _select(skills(), prompt, domain, 5)
    selected_designs = _select(design_systems(), prompt, domain, 3)

    return {
        "open_design_commit": catalog_manifest().get("commit"),
        "domain": domain,
        "selected_open_design_skills": [entry.public() for entry in selected_skills],
        "selected_open_design_systems": [entry.public() for entry in selected_designs],
        "selected_vini_skills": VINI_NATIVE_SKILLS,
    }


def create_design_brief(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    domain = str(context.get("domain") or "web-app")
    skill_titles = [item["title"] for item in context.get("selected_open_design_skills", [])[:4]]
    system_titles = [item["title"] for item in context.get("selected_open_design_systems", [])[:3]]
    return {
        "source": "vini-design-director",
        "user_request": prompt,
        "domain": domain,
        "design_system_direction": system_titles,
        "skill_workflow": skill_titles,
        "brand_and_tone": f"Create a publish-ready {domain} experience with specific, non-generic copy and a clear product identity.",
        "layout_plan": [
            "First viewport must communicate the product/place/app immediately.",
            "Use clear section hierarchy with responsive spacing and no nested decorative cards.",
            "Include every section explicitly requested by the user before optional content.",
        ],
        "visual_rules": [
            "Avoid clipped hero text, overlapping sticky navigation, unreadable contrast, and horizontal scrolling.",
            "Use a restrained palette with strong contrast and purposeful accent color.",
            "Prefer real UI structure and domain-specific copy over placeholder proof cards.",
        ],
        "responsive_rules": [
            "Desktop and mobile layouts must both be readable without text overlap.",
            "Long headings must wrap naturally and fit their containers.",
            "Navigation, forms, and calls to action must remain usable on narrow viewports.",
        ],
        "quality_gate": [
            "Real npm install/build must pass.",
            "Preview must return HTTP success.",
            "Generated page must contain user-requested domain content.",
            "Visual QA must not find blank, clipped, overlapped, or placeholder-heavy output.",
        ],
    }


def prompt_context_block(context: dict[str, Any], design_brief: dict[str, Any]) -> str:
    skill_entries = []
    skill_ids = [item.get("id") for item in context.get("selected_open_design_skills", [])]
    design_ids = [item.get("id") for item in context.get("selected_open_design_systems", [])]
    skill_lookup = {entry.id: entry for entry in skills()}
    design_lookup = {entry.id: entry for entry in design_systems()}
    for entry_id in skill_ids:
        entry = skill_lookup.get(str(entry_id))
        if entry:
            skill_entries.append(f"## Skill: {entry.title} ({entry.id})\n{entry.content[:5000]}")
    for entry_id in design_ids:
        entry = design_lookup.get(str(entry_id))
        if entry:
            skill_entries.append(f"## Design System: {entry.title} ({entry.id})\n{entry.content[:5000]}")
    return (
        "Vini Design Director brief:\n"
        + json.dumps(design_brief, indent=2)
        + "\n\nSelected Open Design catalog guidance:\n"
        + "\n\n".join(skill_entries)
    )


def catalog_counts() -> dict[str, int]:
    return {
        "skills": len(skills()),
        "design_systems": len(design_systems()),
    }

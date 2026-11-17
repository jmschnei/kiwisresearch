"""Real references for the paper: built from retrieved papers, never from LLM output.

The Librarian retrieves papers from arXiv / Semantic Scholar (and recalls earlier ones from the vector
store). This module turns them into a reference list with stable citation keys, checks the keys the writer
cites against that list, drops invented ones, and renders the bibliography (LaTeX and BibTeX).

Only the *existence* and metadata of a reference are guaranteed (it came from a scholarly index); whether a
cited claim is actually supported by that paper is not verified here.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

MAX_REFERENCES = 40
_STOPWORDS = {
    "a", "an", "the", "on", "of", "for", "in", "with", "and", "to", "via", "from", "by", "at", "is", "are",
    "towards", "toward", "using", "based", "into", "as", "its", "their", "new", "novel", "do", "does", "how",
}


# ------------------------------------------------------------------ building references

def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _ascii(title).lower())


def _last_name(author: str) -> str:
    author = author.strip()
    if "," in author:  # "Last, First"
        author = author.split(",")[0]
    else:
        author = author.split()[-1] if author.split() else author
    return re.sub(r"[^a-z]", "", _ascii(author).lower()) or "anon"


def _title_word(title: str) -> str:
    for w in re.findall(r"[A-Za-z]+", _ascii(title)):
        if w.lower() not in _STOPWORDS and len(w) > 2:
            return w.lower()
    return "paper"


def normalize_paper(p: dict) -> Optional[dict]:
    """Convert a retrieved paper (arXiv / Semantic Scholar / vector-store hit) into a reference without a key."""
    if not isinstance(p, dict) or "error" in p:
        return None
    title = re.sub(r"\s+", " ", str(p.get("title") or "")).strip()
    if not title or title.lower() == "unknown":
        return None
    pid = str(p.get("id") or "")
    url = p.get("url") or ""
    if not url and pid.startswith("arxiv:"):
        url = f"https://arxiv.org/abs/{pid[6:]}"
    elif not url and pid.startswith("s2:"):
        url = f"https://www.semanticscholar.org/paper/{pid[3:]}"
    year = p.get("year")
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = None
    authors = p.get("authors") or []
    if isinstance(authors, str):
        authors = [a for a in authors.split(", ") if a]
    venue = p.get("venue") or ""
    return {
        "id": pid, "title": title, "authors": [str(a) for a in authors], "year": year,
        "venue": "" if str(venue).lower() == "unknown" else str(venue), "url": url, "doi": p.get("doi") or "",
        "abstract": re.sub(r"\s+", " ", str(p.get("summary") or p.get("abstract") or "")).strip(),
        "source": p.get("source", ""),
    }


def build_references(papers: Iterable[dict], limit: int = MAX_REFERENCES) -> list[dict]:
    """Deduplicate (by title), cap and assign unique citation keys. Order of ``papers`` is kept."""
    refs: list[dict] = []
    seen: dict[str, dict] = {}
    for p in papers:
        ref = normalize_paper(p)
        if ref is None:
            continue
        norm = _norm_title(ref["title"])
        if norm in seen:  # same paper from another index: fill in what the first copy lacks
            first = seen[norm]
            for field in ("venue", "url", "doi", "year", "abstract"):
                if not first[field] and ref[field]:
                    first[field] = ref[field]
            continue
        seen[norm] = ref
        refs.append(ref)
        if len(refs) >= limit:
            break

    used: set[str] = set()
    for ref in refs:
        base = f"{_last_name(ref['authors'][0]) if ref['authors'] else 'anon'}{ref['year'] or ''}{_title_word(ref['title'])}"
        key, n = base, 0
        while key in used:
            n += 1
            key = f"{base}{chr(ord('a') + (n - 1) % 26)}{'' if n <= 26 else n}"
        used.add(key)
        ref["key"] = key
    return refs


# ------------------------------------------------------------------ rendering

_LATEX_SPECIALS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
                   "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def latex_escape(text: str) -> str:
    return "".join(_LATEX_SPECIALS.get(c, c) for c in text)


def _authors_text(authors: list[str], max_authors: int = 6) -> str:
    if len(authors) > max_authors:
        return ", ".join(authors[:max_authors]) + ", et al."
    return " and ".join([", ".join(authors[:-1]), authors[-1]]) if len(authors) > 1 else (authors[0] if authors else "Anonymous")


def format_reference(ref: dict, escape: bool = False) -> str:
    """One bibliography entry as text (``escape=True`` for LaTeX)."""
    esc = latex_escape if escape else (lambda s: s)
    parts = [esc(_authors_text(ref["authors"])) + "."]
    parts.append(f"{esc(ref['title'])}.")
    tail = ", ".join(x for x in (esc(ref["venue"]) if ref["venue"] else "", str(ref["year"] or "")) if x)
    if tail:
        parts.append(tail + ".")
    link = f"https://doi.org/{ref['doi']}" if ref.get("doi") else ref.get("url", "")
    if link:
        parts.append(f"\\url{{{link}}}" if escape else link)
    return " ".join(parts)


def to_bibtex(ref: dict) -> str:
    def field(name, value):
        return f"  {name} = {{{value}}},\n" if value else ""

    is_arxiv = ref["id"].startswith("arxiv:")
    entry = "article" if ref["venue"] and not is_arxiv else "misc"
    out = f"@{entry}{{{ref['key']},\n"
    out += field("title", "{" + ref["title"] + "}")
    out += field("author", " and ".join(ref["authors"]))
    out += field("year", ref["year"] or "")
    if ref["venue"] and not is_arxiv:
        out += field("journal", ref["venue"])
    if is_arxiv:
        out += field("eprint", ref["id"][6:]) + field("archivePrefix", "arXiv")
    out += field("doi", ref.get("doi", "")) + field("url", ref.get("url", ""))
    return out.rstrip(",\n") + "\n}\n"


def bibtex_file(refs: list[dict]) -> str:
    return "\n".join(to_bibtex(r) for r in refs)


def bibliography_items(refs: list[dict], cited: list[str]) -> list[str]:
    """``\\bibitem`` lines for the cited references, in order of first citation."""
    by_key = {r["key"]: r for r in refs}
    return [f"\\bibitem{{{k}}} {format_reference(by_key[k], escape=True)}" for k in cited if k in by_key]


# ------------------------------------------------------------------ checking citations

_CITE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
_BRACKET = re.compile(r"\[([A-Za-z][A-Za-z0-9_:\-]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_:\-]*)*)\]")


def extract_citations(text: str) -> list[str]:
    """Citation keys used in ``text`` via ``\\cite``-style commands, in order of first appearance."""
    out: list[str] = []
    for m in _CITE.finditer(text):
        for key in (k.strip() for k in m.group(1).split(",")):
            if key and key not in out:
                out.append(key)
    return out


def _bracket_to_cite(text: str, known: set[str]) -> str:
    """``[smith2023graph]`` / ``[a2020x, b2021y]`` -> ``\\cite{...}`` when at least one key is a known reference
    (unknown keys of the group are then dropped as invented). Brackets with no known key are ordinary text."""
    def repl(m):
        keys = [k.strip() for k in m.group(1).split(",")]
        return "\\cite{" + ",".join(keys) + "}" if any(k in known for k in keys) else m.group(0)
    return _BRACKET.sub(repl, text)


def _drop_unknown(text: str, known: set[str], unknown: set[str]) -> str:
    def repl(m):
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        bad = [k for k in keys if k not in known]
        unknown.update(bad)
        good = [k for k in keys if k in known]
        if not bad:
            return m.group(0)
        return m.group(0).replace(m.group(1), ",".join(good)) if good else ""
    return re.sub(r"\s?" + _CITE.pattern, repl, text)


def check_citations(paper: dict, references: list[dict]) -> tuple[dict, dict]:
    """Return ``(paper, report)`` with invented citation keys removed.

    Citations are checked in the abstract, sections and table captions. Bracket-style citations of real keys
    are converted to ``\\cite``. The report lists which references were cited (ordered), which cited keys do not
    exist (and were removed), and which retrieved references were never cited.
    """
    known = {r["key"] for r in references}
    unknown: set[str] = set()
    cited: list[str] = []

    def clean(text):
        if not isinstance(text, str):
            return text
        text = _drop_unknown(_bracket_to_cite(text, known), known, unknown)
        for k in extract_citations(text):
            if k not in cited:
                cited.append(k)
        return text

    out = dict(paper)
    if "abstract" in out:
        out["abstract"] = clean(out["abstract"])
    out["sections"] = {k: clean(v) for k, v in (paper.get("sections") or {}).items()}
    out["tables"] = [{**t, "caption": clean(t.get("caption", ""))} if isinstance(t, dict) else t
                     for t in (paper.get("tables") or [])]
    report = {
        "total": len(references),
        "cited": cited,
        "unknown": sorted(unknown),
        "uncited": [r["key"] for r in references if r["key"] not in cited],
    }
    return out, report

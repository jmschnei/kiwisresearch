"""Scientific Librarian Agent (RAG-based literature review).

Queries academic APIs, extracts papers, and synthesizes the state of the art.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from ..papers.references import MAX_REFERENCES, build_references
from .base import AgentContext, AgentOutput, AgentState, BaseAgent
from ..models.defaults import DEFAULT_MODEL
from .parsing import extract_json

logger = logging.getLogger(__name__)

_QUERY_STOPWORDS = {"a", "an", "the", "of", "for", "in", "on", "with", "and", "to", "via", "using", "from", "by", "is", "are"}


class LibrarianAgent(BaseAgent):
    ROLE = "librarian"
    DESCRIPTION = (
        "You are the Scientific Librarian agent. You query academic databases (arXiv, Semantic Scholar, "
        "Crossref) to find relevant papers, extract their key findings, and synthesize a state-of-the-art "
        "review. You identify gaps in current research that motivate new hypotheses."
    )

    SYSTEM_PROMPT = """You are the Scientific Librarian agent for a research automation system.

Your responsibilities:
1. Study the papers you are given (each has a citation key in square brackets)
2. Extract key information (methodology, datasets, results, limitations)
3. Synthesize findings into a structured state-of-the-art review
4. Identify research gaps that motivate new hypotheses

Rules: use ONLY the papers provided and refer to them by their citation key. Never invent papers, authors, years
or results; if the provided papers do not cover something, say so.

Respond in structured JSON:
```json
{
  "summary": "One-paragraph summary of the field",
  "key_findings": ["finding1", "finding2", ...],
  "gaps": ["gap1", "gap2", ...],
  "methodology_trends": ["trend1", ...],
  "datasets_used": ["dataset1", ...],
  "papers": [
    {
      "key": "citation key exactly as given",
      "key_contributions": ["...", ...],
      "limitations": ["...", ...],
      "relevance_score": 0.95
    }
  ],
  "research_gaps_for_hypothesis": "Specific gap description for hypothesis generation"
}
```"""

    def __init__(self, llm_provider=None, model_config=None, vector_store=None, top_k_related: int = 10):
        super().__init__("librarian-agent")
        self._llm = llm_provider
        self._model_config = model_config
        self._store = vector_store
        self._top_k_related = top_k_related

    async def _index_and_recall(self, topic: str, papers: list[dict]) -> list[dict]:
        """Index fresh papers in the vector store and recall related ones saved in earlier runs.

        Never raises: a broken store must not break the literature review.
        """
        if self._store is None:
            return []
        try:
            from ..memory.vector_store import MemoryRecord

            await self._store.initialize()
            records = []
            for p in papers:
                text = f"{p.get('title', '')}\n{p.get('summary') or p.get('abstract') or ''}".strip()
                if p.get("id") and text:
                    meta = {k: p.get(k) for k in ("title", "authors", "year", "source", "venue", "url", "doi")}
                    records.append(MemoryRecord(id=p["id"], text=text, metadata=meta))
            await self._store.add_documents(records)

            known = {p.get("id") for p in papers}
            related = []
            for doc_id, score in await self._store.search(topic, top_k=self._top_k_related):
                if doc_id in known:
                    continue
                doc = await self._store.get_document(doc_id)
                if doc:
                    related.append({
                        "id": doc.id,
                        "title": doc.metadata.get("title", "Unknown"),
                        "authors": [a for a in str(doc.metadata.get("authors", "")).split(", ") if a],
                        "year": doc.metadata.get("year"),
                        "venue": doc.metadata.get("venue", ""),
                        "url": doc.metadata.get("url", ""),
                        "doi": doc.metadata.get("doi", ""),
                        "source": "vector_store",
                        "summary": doc.text.split("\n", 1)[1] if "\n" in doc.text else "",
                        "relevance_score": round(score, 3),
                    })
            return related
        except Exception as e:
            logger.warning(f"Vector store unavailable for literature indexing: {e}")
            return []

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        topic = context.research_topic or "no topic specified"
        
        # Step 1: Search academic APIs in parallel
        papers_from_arxiv, papers_from_s2 = await asyncio.gather(
            self._search_arxiv(topic), self._search_semantic_scholar(topic)
        )
        found = papers_from_arxiv + papers_from_s2
        sources = {"arxiv": self._source_status(papers_from_arxiv), "semantic_scholar": self._source_status(papers_from_s2)}
        for name, st in sources.items():
            if not st["ok"]:
                logger.warning("Literature source %s unavailable: %s", name, st["error"])
        valid_papers = [p for p in found if "error" not in p]

        # Index new papers and recall related ones from previous runs
        related_papers = await self._index_and_recall(topic, valid_papers)
        all_papers = found + related_papers

        # The reference list used by the paper comes from here, never from LLM output
        references = build_references(valid_papers + related_papers, limit=MAX_REFERENCES)
        context.references = references

        prompt = f"""Research Topic: {topic}

Retrieved papers ({len(references)}); cite them by the key in square brackets:
{self._format_reference_list(references, found)}

Synthesize a comprehensive state-of-the-art review. Identify key trends, methodologies, datasets, and research gaps."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name=DEFAULT_MODEL, temperature=0.2)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response_text = (await self._llm.chat(msgs, config)).content
        else:
            response_text = "# Librarian placeholder: LLM not configured"

        # Parse output
        try:
            data = extract_json(response_text) or {}
        except Exception:
            data = {"summary": "Synthesis of literature for: " + topic, "papers": [], "gaps": [], "key_findings": []}

        # Store in context
        context.literature_review.update(data)
        
        # Store raw papers for vector indexing
        context.artifacts["literature_papers"] = json.dumps(all_papers)

        self.state = AgentState.COMPLETED
        self.output = AgentOutput(
            agent_name=self.name,
            state=AgentState.COMPLETED,
            data={
                "num_papers_found": len(valid_papers),
                "num_references": len(references),
                "sources": sources,
                "num_related_from_memory": len(related_papers),
                "summary": data.get("summary", ""),
                "gaps_identified": data.get("gaps", []),
            },
        )
        return self.output

    @staticmethod
    def _source_status(papers: list[dict]) -> dict:
        """``{"ok", "papers", "error"}`` for one search result list (an error entry means the source failed)."""
        errors = [p["error"] for p in papers if "error" in p]
        return {"ok": not errors, "papers": len([p for p in papers if "error" not in p]), "error": errors[0] if errors else ""}

    @staticmethod
    def _search_error(source: str, e: Exception) -> str:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status == 429:
            hint = " Set SEMANTIC_SCHOLAR_API_KEY to avoid this." if source == "Semantic Scholar" else ""
            return f"{source} rate limit reached (HTTP 429).{hint}"
        return f"{source} search failed: {e}"

    @staticmethod
    def _keywords(query: str, n: int = 6) -> list[str]:
        """Most useful query terms: long research topics make strict AND searches return nothing."""
        words = [w for w in re.findall(r"[\w\-]+", query.lower()) if w not in _QUERY_STOPWORDS and len(w) > 1]
        seen = list(dict.fromkeys(words))
        return sorted(seen, key=lambda w: -len(w))[:n] if len(seen) > n else seen

    @staticmethod
    async def _get(url: str, headers: dict | None = None, retries: int = 1) -> bytes:
        """GET with one retry on rate limiting. Uses httpx (certifi CA bundle), not urllib: some Python
        installs (e.g. python.org builds on macOS) ship without root certificates."""
        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                     headers={"User-Agent": "KiwisResearch/1.0", **(headers or {})}) as client:
            for attempt in range(retries + 1):
                resp = await client.get(url)
                if resp.status_code == 429 and attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.content
        raise RuntimeError("unreachable")

    async def _search_arxiv(self, query: str, max_results: int = 10) -> list[dict]:
        """Search the arXiv API. A strict AND of all terms often finds almost nothing for long topics, so
        the query is relaxed (fewer terms) until enough papers are found."""
        terms = self._keywords(query)
        if not terms:
            return []
        try:
            papers: list[dict] = []
            for n in dict.fromkeys([len(terms), 4, 3, 2]):
                if n > len(terms):
                    continue
                search = "+AND+".join(f"all:{urllib.parse.quote_plus(t)}" for t in terms[:n])
                url = (f"https://export.arxiv.org/api/query?search_query={search}"
                       f"&start=0&max_results={max_results}&sortBy=relevance")
                papers = self._parse_arxiv((await self._get(url)).decode("utf-8"))
                if len(papers) >= min(5, max_results):
                    break
            return papers
        except Exception as e:
            return [{"error": self._search_error("arXiv", e)}]

    @staticmethod
    def _parse_arxiv(xml_data: str) -> list[dict]:
        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            def text(tag):
                el = entry.find(tag, ns)
                return re.sub(r"\s+", " ", el.text).strip() if el is not None and el.text else ""

            arxiv_id = re.sub(r"v\d+$", "", text("atom:id").split("/abs/")[-1])
            published = text("atom:published")
            papers.append({
                "source": "arxiv",
                "id": f"arxiv:{arxiv_id}",
                "title": text("atom:title"),
                "authors": [a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)],
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "summary": text("atom:summary")[:1000],
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "doi": text("arxiv:doi"),
                "venue": "arXiv preprint",
                "relevance_score": 0.9,
            })
        return papers

    async def _search_semantic_scholar(self, query: str, max_results: int = 10) -> list[dict]:
        """Search Semantic Scholar (set SEMANTIC_SCHOLAR_API_KEY for higher rate limits)."""
        terms = self._keywords(query)
        if not terms:
            return []
        fields = "paperId,title,authors,year,abstract,venue,citationCount,referenceCount,externalIds,url"
        url = (f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote_plus(' '.join(terms))}"
               f"&limit={max_results}&fields={fields}")
        key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        try:
            data = json.loads(await self._get(url, {"x-api-key": key} if key else None))
            papers = []
            for p in data.get("data", []):
                ext = p.get("externalIds") or {}
                papers.append({
                    "source": "semantic_scholar",
                    "id": f"s2:{p.get('paperId', 'unknown')}",
                    "title": p.get("title") or "",
                    "authors": [a.get("name", "?") for a in (p.get("authors") or [])[:8]],
                    "year": p.get("year"),
                    "abstract": (p.get("abstract") or "")[:1000],
                    "venue": p.get("venue") or "",
                    "url": p.get("url") or "",
                    "doi": ext.get("DOI", ""),
                    "citation_count": p.get("citationCount", 0),
                    "reference_count": p.get("referenceCount", 0),
                    "relevance_score": 0.85,
                })
            return papers
        except Exception as e:
            return [{"error": self._search_error("Semantic Scholar", e)}]

    @staticmethod
    def _format_reference_list(references: list[dict], found: list[dict]) -> str:
        lines = [f"(search problem: {p['error']})" for p in found if "error" in p]
        for r in references:
            authors = ", ".join(r["authors"][:3]) + (" et al." if len(r["authors"]) > 3 else "")
            lines.append(f"[{r['key']}] {r['title']} - {authors} ({r['year'] or 'n.d.'}){' - ' + r['venue'] if r['venue'] else ''}\n"
                         f"    Abstract: {r['abstract'][:300]}{'...' if len(r['abstract']) > 300 else ''}")
        return "\n".join(lines) if references else "No papers could be retrieved; do not invent any.\n" + "\n".join(lines)

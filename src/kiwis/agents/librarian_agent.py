"""Scientific Librarian Agent (RAG-based literature review).

Queries academic APIs, extracts papers, and synthesizes the state of the art.
"""

from __future__ import annotations

import asyncio
import json
import re
from .base import AgentContext, AgentOutput, AgentState, BaseAgent


class LibrarianAgent(BaseAgent):
    ROLE = "librarian"
    DESCRIPTION = (
        "You are the Scientific Librarian agent. You query academic databases (arXiv, Semantic Scholar, "
        "Crossref) to find relevant papers, extract their key findings, and synthesize a state-of-the-art "
        "review. You identify gaps in current research that motivate new hypotheses."
    )

    SYSTEM_PROMPT = """You are the Scientific Librarian agent for a research automation system.

Your responsibilities:
1. Search academic databases for papers relevant to a given topic
2. Extract key information (methodology, datasets, results, limitations)
3. Synthesize findings into a structured state-of-the-art review
4. Identify research gaps that motivate new hypotheses

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
      "id": "arxiv:xxxx.xxxxx",
      "title": "...",
      "authors": ["..."],
      "year": 2024,
      "summary": "...",
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
                    meta = {k: p.get(k) for k in ("title", "authors", "year", "source", "venue")}
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
                        "year": doc.metadata.get("year", "?"),
                        "source": "vector_store",
                        "summary": doc.text,
                        "relevance_score": round(score, 3),
                    })
            return related
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Vector store unavailable for literature indexing: {e}")
            return []

    async def execute(self, context: AgentContext) -> AgentOutput:
        self.state = AgentState.RUNNING
        
        topic = context.research_topic or "no topic specified"
        
        # Step 1: Search academic APIs in parallel
        papers_from_arxiv = await self._search_arxiv(topic)
        papers_from_s2 = await self._search_semantic_scholar(topic)
        found = papers_from_arxiv + papers_from_s2
        valid_papers = [p for p in found if "error" not in p]

        # Index new papers and recall related ones from previous runs
        related_papers = await self._index_and_recall(topic, valid_papers)
        all_papers = found + related_papers

        prompt = f"""Research Topic: {topic}

Found Papers ({len(all_papers)} results):
{self._format_paper_list(all_papers)}

Synthesize a comprehensive state-of-the-art review. Identify key trends, methodologies, datasets, and research gaps."""

        if self._llm:
            from ..models.base import ChatMessage, ModelConfig
            config = self._model_config or ModelConfig(model_name="gpt-4o", temperature=0.2)
            msgs = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]
            response_text = (await self._llm.chat(msgs, config)).content
        else:
            response_text = "# Librarian placeholder: LLM not configured"

        # Parse output
        try:
            match = re.search(r'```(?:json)?\s*\n(.*?)```', response_text, re.DOTALL)
            data = json.loads(match.group(1)) if match else {}
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
                "num_related_from_memory": len(related_papers),
                "summary": data.get("summary", ""),
                "gaps_identified": data.get("gaps", []),
            },
        )
        return self.output

    async def _search_arxiv(self, query: str, max_results: int = 10) -> list[dict]:
        """Search arXiv API."""
        import urllib.request
        import xml.etree.ElementTree as ET
        
        base_url = "http://export.arxiv.org/api/query"
        search_query = f'all:{query.replace(" ", "+")}'
        
        try:
            url = f"{base_url}?search_query={search_query}&start=0&max_results={max_results}"
            with urllib.request.urlopen(url, timeout=30) as response:
                xml_data = response.read().decode("utf-8")
            
            root = ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom", "opensearch": "http://a9.com/-/spec/opensearch/1.1/"}
            
            total = root.find("opensearch:totalResults", ns)
            papers = []
            
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
                
                published = entry.find("atom:published", ns)
                year = int(published.text[:4]) if published is not None else 2024
                
                id_elem = entry.find("atom:id", ns)
                arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem is not None else ""
                
                papers.append({
                    "source": "arxiv",
                    "id": f"arxiv:{arxiv_id}",
                    "title": title,
                    "authors": authors[:5],
                    "year": year,
                    "summary": summary[:1000],
                    "relevance_score": 0.9,
                })
            
            return papers
        except Exception as e:
            return [{"error": f"arXiv search failed: {str(e)}"}]

    async def _search_semantic_scholar(self, query: str, max_results: int = 10) -> list[dict]:
        """Search Semantic Scholar API."""
        import urllib.request
        import json as json_mod
        
        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query.replace(' ', '+')}&limit={max_results}&fields=title,authors,year,abstract,venue,publicationDates,referencesCount,citationCount"
            
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "KiwisResearch/1.0")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json_mod.loads(response.read().decode())
            
            papers = []
            for p in data.get("data", []):
                authors_list = [a.get("name", "?") for a in (p.get("authors") or [])[:5]]
                papers.append({
                    "source": "semantic_scholar",
                    "id": f"s2:{p.get('paperId', 'unknown')}",
                    "title": p.get("title", "Unknown"),
                    "authors": authors_list,
                    "year": p.get("year") or 2024,
                    "abstract": (p.get("abstract") or "")[:1000],
                    "venue": p.get("venue", "Unknown"),
                    "citation_count": p.get("citationCount", 0),
                    "reference_count": p.get("referenceCount", 0),
                    "relevance_score": 0.85,
                })
            
            return papers
        except Exception as e:
            return [{"error": f"Semantic Scholar search failed: {str(e)}"}]

    def _format_paper_list(self, papers: list[dict]) -> str:
        lines = []
        for i, p in enumerate(papers[:15]):
            if "error" in p:
                lines.append(f"[{i+1}] Error: {p['error']}")
            else:
                title = p.get("title", "Unknown")
                authors = ", ".join(p.get("authors", [])[:3])
                year = p.get("year", "?")
                venue = p.get("venue", "") or p.get("source", "")
                summary = (p.get("summary") or p.get("abstract") or "")[:200]
                lines.append(f"[{i+1}] [{p.get('id', '?')}] {title}\n    Authors: {authors} ({year})\n    Venue: {venue}\n    Abstract: {summary}...")
        return "\n".join(lines) if lines else "No papers found."

"""Real references: building, citation checking, Librarian retrieval, and the writer's use of them."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.agents import LibrarianAgent, ReviewerAgent, WriterAgent
from kiwis.orchestrator.pipeline import PipelineState
from kiwis.papers.references import (build_references, check_citations, extract_citations, format_reference,
                                     latex_escape, normalize_paper, to_bibtex)

SMITH = {"id": "arxiv:2001.00001", "title": "Graph Neural Networks for Molecules", "authors": ["Jane Smith", "Bo Li"],
         "year": 2020, "summary": "We study GNNs.", "source": "arxiv", "venue": "arXiv preprint"}
GARCIA = {"id": "s2:abc", "title": "On the Privacy of Federated Learning", "authors": ["Luis García-Márquez"],
          "year": 2021, "abstract": "Privacy analysis.", "venue": "NeurIPS", "doi": "10.1000/xyz", "source": "semantic_scholar"}


# ------------------------------------------------------------------ building

def test_keys_are_stable_unique_and_ascii():
    dup = dict(SMITH, id="s2:other", title="Graph neural networks for molecules!")  # same paper, other index
    other = dict(SMITH, id="arxiv:2001.00002", title="Graph Methods for Molecules II")  # same author/year/word clash
    refs = build_references([SMITH, GARCIA, dup, other, {"error": "arXiv search failed"}, {"title": ""}])
    assert [r["key"] for r in refs] == ["smith2020graph", "garciamarquez2021privacy", "smith2020grapha"]  # dup merged, errors skipped
    assert len({r["key"] for r in refs}) == len(refs)
    assert all(r["key"].isascii() for r in refs)


def test_duplicate_fills_missing_metadata():
    thin = dict(SMITH, venue="", doi="")
    rich = dict(SMITH, id="s2:zzz", venue="ICML", doi="10.1/abc")
    (ref,) = build_references([thin, rich])
    assert ref["venue"] == "ICML" and ref["doi"] == "10.1/abc" and ref["id"] == "arxiv:2001.00001"


def test_urls_and_vector_store_shaped_papers():
    ref = normalize_paper(SMITH)
    assert ref["url"] == "https://arxiv.org/abs/2001.00001"
    assert normalize_paper(GARCIA)["url"] == "https://www.semanticscholar.org/paper/abc"
    recalled = normalize_paper({"id": "arxiv:1", "title": "T", "authors": "A B, C D", "year": "2019"})  # metadata strings
    assert recalled["authors"] == ["A B", "C D"] and recalled["year"] == 2019


def test_reference_cap():
    papers = [{"id": f"arxiv:{i}", "title": f"Unique title number {i}", "authors": ["A B"], "year": 2020} for i in range(60)]
    assert len(build_references(papers, limit=40)) == 40


# ------------------------------------------------------------------ rendering

def test_latex_escaping_and_formatting():
    ref = build_references([dict(GARCIA, title="Q&A: 50% of data_sets cost $5 #1")])[0]
    text = format_reference(ref, escape=True)
    assert r"Q\&A: 50\% of data\_sets cost \$5 \#1" in text
    assert "\\url{https://doi.org/10.1000/xyz}" in text  # DOI preferred over the index URL
    assert "Luis García-Márquez." in text
    plain = format_reference(build_references([SMITH])[0])
    assert plain.startswith("Jane Smith and Bo Li. Graph Neural Networks") and "\\url" not in plain


def test_bibtex_entries():
    arxiv, journal = build_references([SMITH, GARCIA])
    assert "@misc{smith2020graph," in to_bibtex(arxiv) and "eprint = {2001.00001}" in to_bibtex(arxiv)
    assert "@article{garciamarquez2021privacy," in to_bibtex(journal) and "journal = {NeurIPS}" in to_bibtex(journal)


# ------------------------------------------------------------------ citation checking

def test_extract_citations_in_order():
    assert extract_citations(r"A \cite{a, b} then \citep[see][p. 3]{c} and \cite{a}") == ["a", "b", "c"]


def test_check_citations_removes_invented_keys_and_reports():
    refs = build_references([SMITH, GARCIA])
    paper = {
        "abstract": r"Prior work \cite{smith2020graph,invented2099x}. Claim \cite{invented2099x}.",
        "sections": {
            "introduction": r"GNNs [smith2020graph] and privacy [garciamarquez2021privacy, ghost2000x] and [note] text.",
            "methodology": r"Only fake \cite{ghost2000x}. Done.",
        },
        "tables": [{"caption": r"Results \cite{garciamarquez2021privacy}", "content": "x"}],
    }
    fixed, report = check_citations(paper, refs)
    # a fake key inside a group is dropped; a lone fake citation is removed with its leading space
    assert fixed["abstract"] == r"Prior work \cite{smith2020graph}. Claim."
    assert r"\cite{smith2020graph}" in fixed["sections"]["introduction"]
    assert r"[note]" in fixed["sections"]["introduction"]  # non-key brackets untouched
    assert "ghost2000x" not in json.dumps(fixed)
    assert fixed["sections"]["methodology"] == "Only fake. Done."
    assert report["cited"] == ["smith2020graph", "garciamarquez2021privacy"]
    assert report["unknown"] == ["ghost2000x", "invented2099x"]
    assert report["uncited"] == [] and report["total"] == 2
    assert "invented2099x" in paper["abstract"]  # input is not mutated


def test_check_citations_without_references_strips_all_citations():
    fixed, report = check_citations({"sections": {"introduction": r"Claim \cite{made_up}."}}, [])
    assert fixed["sections"]["introduction"] == "Claim." and report["unknown"] == ["made_up"] and report["total"] == 0


def test_latex_escape_basics():
    assert latex_escape(r"a_b & c%") == r"a\_b \& c\%"


# ------------------------------------------------------------------ librarian

ARXIV_XML = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
 <entry>
  <id>http://arxiv.org/abs/2301.01234v3</id>
  <published>2023-01-03T10:00:00Z</published>
  <title>Message Passing
     for  Molecules</title>
  <summary>  We propose
  a method.  </summary>
  <author><name>Ada Lovelace</name></author><author><name>Alan Turing</name></author>
  <arxiv:doi>10.1234/mp</arxiv:doi>
 </entry>
</feed>"""


def test_parse_arxiv_entry():
    (p,) = LibrarianAgent._parse_arxiv(ARXIV_XML)
    assert p["id"] == "arxiv:2301.01234"  # version stripped
    assert p["title"] == "Message Passing for Molecules" and p["summary"] == "We propose a method."
    assert p["authors"] == ["Ada Lovelace", "Alan Turing"] and p["year"] == 2023
    assert p["url"] == "https://arxiv.org/abs/2301.01234" and p["doi"] == "10.1234/mp"


def test_query_keywords():
    kw = LibrarianAgent._keywords("Improving the graph neural networks for molecular property prediction")
    assert len(kw) == 6 and "the" not in kw and "for" not in kw
    assert LibrarianAgent._keywords("graph networks") == ["graph", "networks"]


class CaptureLLM:
    def __init__(self, reply="```json\n{}\n```"):
        self.reply, self.prompts = reply, []

    async def chat(self, messages, config):
        from kiwis.models.base import ChatMessage
        self.prompts.append(messages)
        return ChatMessage(role="assistant", content=self.reply)


def stub_search(lib, arxiv=(), s2=()):
    async def a(*_a, **_k):
        return list(arxiv)

    async def s(*_a, **_k):
        return list(s2)

    lib._search_arxiv, lib._search_semantic_scholar = a, s
    return lib


def test_librarian_builds_references_from_retrieved_papers_only():
    llm = CaptureLLM()
    lib = stub_search(LibrarianAgent(llm_provider=llm), arxiv=[SMITH], s2=[GARCIA, {"error": "Semantic Scholar search failed: 429"}])
    state = PipelineState(research_topic="graphs")
    out = asyncio.run(lib.execute(state))
    assert [r["key"] for r in state.references] == ["smith2020graph", "garciamarquez2021privacy"]
    assert out.data["num_references"] == 2 and out.data["num_papers_found"] == 2
    user = llm.prompts[0][1].content
    assert "[smith2020graph]" in user and "[garciamarquez2021privacy]" in user
    assert "Semantic Scholar search failed" in user  # the model is told retrieval was incomplete
    assert "ONLY the papers provided" in llm.prompts[0][0].content


def test_librarian_with_no_papers_tells_the_model_not_to_invent():
    llm = CaptureLLM()
    state = PipelineState(research_topic="x")
    asyncio.run(stub_search(LibrarianAgent(llm_provider=llm)).execute(state))
    assert state.references == [] and "do not invent" in llm.prompts[0][1].content


def test_recalled_papers_keep_their_metadata_as_references(tmp_path):
    pytest.importorskip("qdrant_client")
    from kiwis.memory.qdrant_store import QdrantStore

    store = QdrantStore(path=str(tmp_path / "q"))  # hashed lexical embedder
    asyncio.run(stub_search(LibrarianAgent(vector_store=store), arxiv=[GARCIA]).execute(PipelineState(research_topic="federated privacy")))

    state = PipelineState(research_topic="federated privacy learning")
    asyncio.run(stub_search(LibrarianAgent(vector_store=store), arxiv=[SMITH]).execute(state))
    recalled = next(r for r in state.references if r["id"] == "s2:abc")
    assert recalled["title"] == "On the Privacy of Federated Learning" and recalled["venue"] == "NeurIPS"
    assert recalled["doi"] == "10.1000/xyz" and recalled["abstract"] == "Privacy analysis."
    assert recalled["authors"] == ["Luis García-Márquez"] and recalled["year"] == 2021


# ------------------------------------------------------------------ writer + reviewer

PAPER_WITH_FAKES = json.dumps({
    "title": "T", "abstract": r"Based on \cite{smith2020graph}.",
    "sections": {"introduction": r"See [garciamarquez2021privacy] and \cite{ghost2000x}.", "related_work": "None."},
    "bibliography_entries": [{"key": "ghost2000x", "text": "Totally Invented et al. 2000"}],
})


def write(llm, references, tmp_path):
    state = PipelineState(research_topic="t", references=references)
    out = asyncio.run(WriterAgent(llm_provider=llm, output_dir=tmp_path).execute(state))
    return state, out


def test_writer_bibliography_comes_from_real_references(tmp_path):
    refs = build_references([SMITH, GARCIA])
    llm = CaptureLLM("```json\n" + PAPER_WITH_FAKES + "\n```")
    state, out = write(llm, refs, tmp_path)

    system, user = llm.prompts[0][0].content, llm.prompts[0][1].content
    assert "ONLY" in system and "smith2020graph" in user and "garciamarquez2021privacy" in user

    tex = (tmp_path / "paper.tex").read_text()
    assert r"\bibitem{smith2020graph} Jane Smith and Bo Li. Graph Neural Networks for Molecules." in tex
    assert r"\bibitem{garciamarquez2021privacy}" in tex and r"\cite{garciamarquez2021privacy}" in tex  # [key] converted
    assert "ghost2000x" not in tex and "Totally Invented" not in tex
    assert "bibliography_entries" not in state.paper_draft["content"]

    report = state.paper_draft["citation_report"]
    assert report["cited"] == ["smith2020graph", "garciamarquez2021privacy"] and report["unknown"] == ["ghost2000x"]
    assert out.data["citations"] == {"cited": 2, "unknown_removed": 1, "available": 2}
    bib = (tmp_path / "references.bib").read_text()
    assert "@misc{smith2020graph" in bib and "@article{garciamarquez2021privacy" in bib


def test_writer_without_references_cites_nothing(tmp_path):
    llm = CaptureLLM("```json\n" + PAPER_WITH_FAKES + "\n```")
    state, _ = write(llm, [], tmp_path)
    assert "none were retrieved" in llm.prompts[0][1].content
    tex = (tmp_path / "paper.tex").read_text()
    assert "ghost2000x" not in tex and "smith2020graph" not in tex and "thebibliography" not in tex
    assert not (tmp_path / "references.bib").exists()


def test_uncited_references_are_not_listed_in_the_bibliography(tmp_path):
    refs = build_references([SMITH, GARCIA])
    llm = CaptureLLM("```json\n" + json.dumps({"title": "T", "sections": {"introduction": r"Only \cite{smith2020graph}."}}) + "\n```")
    state, _ = write(llm, refs, tmp_path)
    tex = (tmp_path / "paper.tex").read_text()
    assert "bibitem{smith2020graph}" in tex and "garciamarquez2021privacy" not in tex
    assert state.paper_draft["citation_report"]["uncited"] == ["garciamarquez2021privacy"]


def test_reviewer_sees_the_system_computed_reference_check():
    refs = build_references([SMITH, GARCIA])
    state = PipelineState(research_topic="t", references=refs,
                          paper_draft={"content": {"title": "P", "sections": {"introduction": "x"}},
                                       "citation_report": {"total": 2, "cited": ["smith2020graph"], "unknown": ["ghost"], "uncited": []}})
    llm = CaptureLLM("```json\n{}\n```")
    asyncio.run(ReviewerAgent(llm_provider=llm).execute(state))
    user = llm.prompts[0][1].content
    assert "REFERENCE CHECK" in user and "smith2020graph = Graph Neural Networks for Molecules" in user
    assert "Invented citation keys removed automatically: 1" in user


def test_references_survive_state_serialization():
    refs = build_references([SMITH])
    state = PipelineState(research_topic="t", references=refs)
    restored = PipelineState.from_dict(json.loads(json.dumps(state.to_dict(), default=str)))
    assert restored.references == refs


def test_generated_latex_compiles_with_resolved_citations(tmp_path):
    import shutil
    if shutil.which("pdflatex") is None:
        pytest.skip("pdflatex not installed")
    refs = build_references([SMITH, dict(GARCIA, title="Q&A on 50% of data_sets: a $5 study")])
    paper = {"title": "T", "abstract": r"We build on \cite{smith2020graph}.",
             "sections": {"introduction": r"See \cite{garciamarquez2021data, smith2020graph}."}}
    llm = CaptureLLM("```json\n" + json.dumps(paper) + "\n```")
    out = asyncio.run(WriterAgent(llm_provider=llm, output_dir=tmp_path).execute(PipelineState(research_topic="t", references=refs)))
    log = (tmp_path / "paper.log").read_text()
    assert out.data["latex_compiled"], log[-800:]
    assert "undefined" not in log.lower().replace("undefined control sequence", "")  # citations resolved on pass 2
    assert not [l for l in log.splitlines() if l.startswith("!")]

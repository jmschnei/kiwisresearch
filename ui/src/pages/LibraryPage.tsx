import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorBox, Spinner } from '@/components/common/Spinner';
import { usePaperSearch } from '@/hooks/useApi';

export function LibraryPage() {
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const { data, isFetching, error, refetch } = usePaperSearch(query);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(input.trim());
  };

  return (
    <div className="page-scroll">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Biblioteca</h1>
          <p className="text-sm text-gray-500">Explora la literatura en arXiv antes de lanzar una investigación.</p>
        </div>

        <form onSubmit={submit} className="flex gap-3">
          <input value={input} onChange={(e) => setInput(e.target.value)} aria-label="Buscar artículos"
            placeholder="Buscar artículos (p. ej. graph neural networks molecules)…" className="form-field-input" />
          <button type="submit" className="btn-primary shrink-0" disabled={!input.trim()}>Buscar</button>
        </form>

        {isFetching && <Spinner label="Buscando en arXiv…" />}
        {error && <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />}
        {!query && !isFetching && <p className="text-center text-gray-600 py-12">Escribe una consulta para empezar.</p>}
        {data && data.length === 0 && !isFetching && <p className="text-center text-gray-600 py-12">Sin resultados para «{query}».</p>}

        <div className="space-y-3">
          {data?.map((p) => (
            <article key={p.id} className="metric-card !p-5">
              <h2 className="text-sm font-semibold text-gray-100">{p.title}</h2>
              <div className="text-[11px] text-gray-500 mt-1">
                {p.authors?.join(', ')} {p.year ? `· ${p.year}` : ''} · {p.source}
              </div>
              {p.summary && <p className="text-[12px] text-gray-400 mt-2 line-clamp-4">{p.summary}</p>}
              <div className="flex items-center gap-4 mt-3 text-xs">
                {p.id.startsWith('arxiv:') && (
                  <a href={`https://arxiv.org/abs/${p.id.slice(6)}`} target="_blank" rel="noreferrer" className="text-cyber-blue hover:underline">Ver en arXiv ↗</a>
                )}
                <button onClick={() => navigate('/', { state: { topic: p.title } })} className="text-cyber-purple hover:underline">
                  🚀 Investigar este tema
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

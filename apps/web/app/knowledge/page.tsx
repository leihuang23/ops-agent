'use client';

import { useState, useTransition } from 'react';

import type { KnowledgeSearchItem, KnowledgeSearchResponse } from '@/lib/api';
import { searchKnowledge } from '@/lib/api';
import { formatCount } from '@/lib/format';

export default function KnowledgePage() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<KnowledgeSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const q = String(formData.get('q') ?? '');
    setQuery(q);
    setError(null);
    startTransition(async () => {
      const response = await searchKnowledge(q);
      if (response.ok) {
        setResult(response.data);
      } else {
        setResult(null);
        setError(response.error);
      }
    });
  }

  const resultCount = result?.results.length ?? 0;

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Knowledge base</p>
          <h1>Internal source search</h1>
        </div>
        <div className="header-actions">
          <span className="status-pill incident-status">
            {formatCount(resultCount)} chunks
          </span>
        </div>
      </header>

      <section className="panel knowledge-search-panel">
        <form className="knowledge-search-form" onSubmit={handleSubmit}>
          <input
            aria-label="Search knowledge base"
            className="knowledge-search-input"
            defaultValue={query}
            name="q"
            placeholder="retry webhook failed renewals"
            type="search"
          />
          <button className="action-button" disabled={isPending} type="submit">
            {isPending ? 'Searching…' : 'Search'}
          </button>
        </form>
      </section>

      {isPending ? (
        <section className="panel">
          <div className="panel-message">Searching knowledge base…</div>
        </section>
      ) : error ? (
        <section className="empty-state">
          <h2>Knowledge search unavailable</h2>
          <p className="error-detail">{error}</p>
        </section>
      ) : result?.query ? (
        <section className="knowledge-results" aria-label="Knowledge search results">
          {result.results.length === 0 ? (
            <div className="empty-state">
              <h2>No matching chunks</h2>
              <p>No internal document chunks matched this query.</p>
            </div>
          ) : (
            result.results.map((item) => (
              <KnowledgeResult item={item} key={item.citation.chunk_id} />
            ))
          )}
        </section>
      ) : null}
    </main>
  );
}

function KnowledgeResult({ item }: { item: KnowledgeSearchItem }) {
  return (
    <article className="panel knowledge-result">
      <div className="panel-header">
        <div>
          <span className="label">{item.source_id}</span>
          <h2>{item.title}</h2>
        </div>
        <span>{Math.round(item.score * 100)} score</span>
      </div>
      <p className="knowledge-snippet">{item.snippet}</p>
      <dl className="citation-grid">
        <div>
          <dt>Chunk</dt>
          <dd>{item.citation.chunk_id}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{item.citation.document_type}</dd>
        </div>
        <div>
          <dt>Heading</dt>
          <dd>{item.citation.heading_path}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>
            {item.citation.source_uri ? (
              <a
                href={item.citation.source_uri}
                target="_blank"
                rel="noreferrer"
              >
                {item.citation.source_path}
              </a>
            ) : (
              item.citation.source_path
            )}
          </dd>
        </div>
      </dl>
    </article>
  );
}

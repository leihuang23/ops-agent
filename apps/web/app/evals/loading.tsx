export default function EvalStudioLoading() {
  return (
    <main className="dashboard-shell" aria-busy="true" aria-live="polite">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Quality control plane</p>
          <h1>Eval Studio</h1>
        </div>
      </header>
      <section className="eval-loading-grid" aria-label="Loading eval studio">
        <div className="panel eval-loading-block" />
        <div className="eval-studio-main">
          <div className="panel eval-loading-block eval-loading-tall" />
          <div className="panel eval-loading-block" />
        </div>
      </section>
    </main>
  );
}

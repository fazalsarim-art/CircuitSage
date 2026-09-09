// Placeholder feature pages. Benchmark/evals arrive in Phase 9, feedback in Phase 10.

function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <main className="page">
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  );
}

export const BenchmarkPage = () => (
  <Placeholder title="Benchmark" description="Benchmark authoring. Coming in Phase 9." />
);
export const EvalRunsPage = () => (
  <Placeholder title="Eval runs" description="Evaluation runs and comparisons. Coming in Phase 9." />
);
export const FeedbackPage = () => (
  <Placeholder title="Feedback" description="Feedback review queue. Coming in Phase 10." />
);
export const SystemPage = () => (
  <Placeholder title="System" description="Runtime configuration and health. Coming later." />
);

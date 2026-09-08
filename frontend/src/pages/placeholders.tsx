// Placeholder feature pages. Real Ask/Documents UIs arrive in Phase 8, benchmark/evals in
// Phase 9, feedback in Phase 10.

function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <main className="page">
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  );
}

export const AskPage = () => (
  <Placeholder title="Ask" description="Ask a grounded debugging question. Coming in Phase 8." />
);
export const DocumentsPage = () => (
  <Placeholder title="Documents" description="Manage the document corpus. Coming in Phase 8." />
);
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

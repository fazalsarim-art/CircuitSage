// Placeholder feature pages. Feedback arrives in Phase 10; System later.

function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <main className="page">
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  );
}

export const FeedbackPage = () => (
  <Placeholder title="Feedback" description="Feedback review queue. Coming in Phase 10." />
);
export const SystemPage = () => (
  <Placeholder title="System" description="Runtime configuration and health. Coming later." />
);

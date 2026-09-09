// Placeholder feature pages. System page arrives in a later phase.

function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <main className="page">
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  );
}

export const SystemPage = () => (
  <Placeholder title="System" description="Runtime configuration and health. Coming later." />
);

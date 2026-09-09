import type { Feedback } from "./types";

interface Props {
  items: Feedback[];
  selectedId: string | null;
  onSelect: (feedback: Feedback) => void;
}

function statusClass(status: string): string {
  if (status === "resolved" || status === "promoted_to_draft") return "status-indexed";
  if (status === "ignored") return "status-failed";
  return "status-queued";
}

export function FeedbackTable({ items, selectedId, onSelect }: Props) {
  return (
    <table className="doc-table">
      <caption className="sr-only">Feedback review queue</caption>
      <thead>
        <tr>
          <th scope="col">Rating</th>
          <th scope="col">Reason</th>
          <th scope="col">Question</th>
          <th scope="col">Status</th>
          <th scope="col" />
        </tr>
      </thead>
      <tbody>
        {items.map((feedback) => (
          <tr key={feedback.id} className={feedback.id === selectedId ? "selected" : undefined}>
            <td>{feedback.rating === 1 ? "👍" : "👎"}</td>
            <td>{feedback.reason ?? "—"}</td>
            <td>{feedback.question ?? "—"}</td>
            <td>
              <span className={`badge ${statusClass(feedback.status)}`}>{feedback.status}</span>
            </td>
            <td>
              <button type="button" onClick={() => onSelect(feedback)}>
                {feedback.id === selectedId ? "Selected" : "Review"}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

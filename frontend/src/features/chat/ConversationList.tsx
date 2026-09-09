import type { ConversationSummary } from "./types";

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="conversation-list" aria-label="Conversations">
      <button type="button" className="new-conversation" onClick={onNew}>
        + New conversation
      </button>
      <ul>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              className={conversation.id === activeId ? "active" : undefined}
              onClick={() => onSelect(conversation.id)}
            >
              {conversation.title}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

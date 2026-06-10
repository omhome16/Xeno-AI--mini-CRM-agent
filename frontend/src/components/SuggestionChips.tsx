import type { Suggestion } from '../api';

interface Props {
  suggestions: Suggestion[];
  onSelect: (suggestion: Suggestion) => void;
}

const categoryColors: Record<string, string> = {
  audience: '#3b82f6',
  channel: '#8b5cf6',
  offer: '#f59e0b',
  message: '#22c55e',
  action: '#ec4899',
};

const categoryIcons: Record<string, string> = {
  audience: '👥',
  channel: '📡',
  offer: '🏷️',
  message: '✉️',
  action: '⚡',
};

export default function SuggestionChips({ suggestions, onSelect }: Props) {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="suggestion-chips">
      {suggestions.map((s, i) => (
        <button
          key={`${s.value}-${i}`}
          className="suggestion-chip"
          style={{
            '--chip-color': categoryColors[s.category] || '#6b7280',
          } as React.CSSProperties}
          onClick={() => onSelect(s)}
        >
          <span className="chip-icon">{categoryIcons[s.category] || '💡'}</span>
          <span className="chip-label">{s.label}</span>
        </button>
      ))}
    </div>
  );
}

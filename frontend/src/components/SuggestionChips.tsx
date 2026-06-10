import type { Suggestion } from '../api';
import { Users, Radio, Tag, MessageSquare, Zap, HelpCircle } from 'lucide-react';

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

const getCategoryIcon = (category: string) => {
  const size = 13;
  switch (category) {
    case 'audience':
      return <Users size={size} />;
    case 'channel':
      return <Radio size={size} />;
    case 'offer':
      return <Tag size={size} />;
    case 'message':
      return <MessageSquare size={size} />;
    case 'action':
      return <Zap size={size} />;
    default:
      return <HelpCircle size={size} />;
  }
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
          <span className="chip-icon" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            {getCategoryIcon(s.category)}
          </span>
          <span className="chip-label">{s.label}</span>
        </button>
      ))}
    </div>
  );
}

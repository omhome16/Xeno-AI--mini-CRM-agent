import { Target, MessageSquare, Radio, Gift, Sparkles, ChevronRight } from 'lucide-react';
import type { CampaignBrief } from '../api';

interface Props {
  brief: CampaignBrief;
  readyToPlan: boolean;
  onPlanClick: () => void;
}

const channelEmoji: Record<string, string> = {
  whatsapp: '💬',
  sms: '📱',
  email: '📧',
  rcs: '🎨',
};

export default function CampaignBriefCard({ brief, readyToPlan, onPlanClick }: Props) {
  const fields = [
    { key: 'goal', label: 'Goal', icon: <Sparkles size={14} />, value: brief.goal },
    { key: 'audience', label: 'Audience', icon: <Target size={14} />, value: brief.audience },
    { key: 'channel', label: 'Channel', icon: <Radio size={14} />, value: brief.channel ? `${channelEmoji[brief.channel] || '📡'} ${brief.channel.toUpperCase()}` : undefined },
    { key: 'message_idea', label: 'Message', icon: <MessageSquare size={14} />, value: brief.message_idea },
    { key: 'offer', label: 'Offer', icon: <Gift size={14} />, value: brief.offer },
  ];

  const filledCount = fields.filter(f => f.value).length;
  const totalFields = fields.length;
  const progress = (filledCount / totalFields) * 100;

  if (filledCount === 0) return null;

  return (
    <div className="campaign-brief-card glass">
      <div className="brief-header">
        <div className="brief-title">
          <Sparkles size={16} className="brief-icon" />
          <span>Campaign Brief</span>
        </div>
        <div className="brief-progress">
          <div className="brief-progress-bar">
            <div className="brief-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="brief-progress-text">{filledCount}/{totalFields}</span>
        </div>
      </div>

      <div className="brief-fields">
        {fields.map(f => (
          <div key={f.key} className={`brief-field ${f.value ? 'filled' : 'empty'}`}>
            <div className="brief-field-icon">{f.icon}</div>
            <div className="brief-field-content">
              <div className="brief-field-label">{f.label}</div>
              <div className="brief-field-value">
                {f.value || <span className="brief-pending">Pending...</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {readyToPlan && (
        <button
          className="btn-plan-campaign"
          onClick={onPlanClick}
        >
          <span>Plan This Campaign</span>
          <ChevronRight size={16} />
        </button>
      )}
    </div>
  );
}

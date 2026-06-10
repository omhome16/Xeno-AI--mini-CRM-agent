import { Users, MessageSquare, Radio, Database, ChevronDown, ChevronUp, Rocket, ArrowLeft, ClipboardList } from 'lucide-react';
import { useState } from 'react';
import CustomerPreviewTable from './CustomerPreviewTable';


interface Props {
  audienceCount: number;
  audiencePreview: Record<string, any>[];
  audienceSql: string;
  messageTemplate: string;
  channel: string;
  segmentName: string;
  campaignName?: string;
  onLaunch: () => void;
  onBack: () => void;
  loading?: boolean;
}

export default function CampaignPlanCard({
  audienceCount,
  audiencePreview,
  audienceSql,
  messageTemplate,
  channel,
  segmentName,
  onLaunch,
  onBack,
  loading,
}: Props) {
  const [showSql, setShowSql] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  return (
    <div className="campaign-plan-card glass">
      <div className="plan-header">
        <h3 className="plan-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ClipboardList size={18} />
          <span>Campaign Plan</span>
        </h3>
        <p className="plan-subtitle">Review everything before launching</p>
      </div>

      {/* Audience Section */}
      <div className="plan-section">
        <div className="plan-section-header">
          <Users size={16} />
          <span>Audience</span>
          <span className="plan-badge">{audienceCount.toLocaleString()} customers</span>
        </div>
        <div className="plan-section-body">
          <div className="plan-detail">
            <span className="plan-detail-label">Segment</span>
            <span className="plan-detail-value">{segmentName}</span>
          </div>

          <button className="plan-toggle" onClick={() => setShowSql(s => !s)}>
            <Database size={13} />
            <span>{showSql ? 'Hide' : 'Show'} SQL Query</span>
            {showSql ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showSql && (
            <pre className="plan-sql">{audienceSql}</pre>
          )}

          <button className="plan-toggle" onClick={() => setShowPreview(s => !s)}>
            <Users size={13} />
            <span>{showPreview ? 'Hide' : 'Show'} Customer Preview ({Math.min(audiencePreview.length, 10)} of {audienceCount})</span>
            {showPreview ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showPreview && audiencePreview.length > 0 && (
            <CustomerPreviewTable preview={audiencePreview} totalCount={audienceCount} />
          )}
        </div>
      </div>

      {/* Message Section */}
      <div className="plan-section">
        <div className="plan-section-header">
          <MessageSquare size={16} />
          <span>Message</span>
          <span className="plan-badge">{messageTemplate.length} chars</span>
        </div>
        <div className="plan-section-body">
          <div className="plan-message-preview">{messageTemplate}</div>
        </div>
      </div>

      {/* Channel Section */}
      <div className="plan-section">
        <div className="plan-section-header">
          <Radio size={16} />
          <span>Channel</span>
          <span className="plan-badge channel-badge">{(channel || 'whatsapp').toUpperCase()}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="plan-actions">
        <button className="btn-back-brainstorm" onClick={onBack} disabled={loading}>
          <ArrowLeft size={16} />
          <span>Back to Brainstorm</span>
        </button>
        <button className="btn-launch-campaign" onClick={onLaunch} disabled={loading}>
          {loading ? (
            <>
              <div className="spinner-small" />
              <span>Launching...</span>
            </>
          ) : (
            <>
              <Rocket size={16} />
              <span>Launch Campaign</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

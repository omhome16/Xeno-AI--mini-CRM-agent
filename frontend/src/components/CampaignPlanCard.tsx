import { Users, MessageSquare, Radio, Database, ChevronDown, ChevronUp, Rocket, ArrowLeft, ClipboardList, Edit, Sparkles } from 'lucide-react';
import { useState, useEffect } from 'react';
import CustomerPreviewTable from './CustomerPreviewTable';
import { improveMessage } from '../api';


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
  onUpdateMessage: (newMessage: string) => void;
  audienceDescription?: string;
  offerDetails?: string;
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
  onUpdateMessage,
  audienceDescription,
  offerDetails,
  loading,
}: Props) {
  const [showSql, setShowSql] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedMessage, setEditedMessage] = useState(messageTemplate);
  const [showImprove, setShowImprove] = useState(false);
  const [improveInstruction, setImproveInstruction] = useState('');
  const [improving, setImproving] = useState(false);
  const [improveError, setImproveError] = useState('');

  useEffect(() => {
    setEditedMessage(messageTemplate);
  }, [messageTemplate]);

  const handleSaveEdit = () => {
    onUpdateMessage(editedMessage);
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditedMessage(messageTemplate);
    setIsEditing(false);
  };

  const handleImproveMessage = async () => {
    if (!improveInstruction.trim() || improving) return;
    setImproving(true);
    setImproveError('');
    try {
      const result = await improveMessage(
        messageTemplate,
        improveInstruction,
        channel,
        audienceDescription,
        offerDetails
      );
      onUpdateMessage(result.improved_message);
      setImproveInstruction('');
      setShowImprove(false);
    } catch (err: any) {
      setImproveError(err.message || 'Failed to improve message.');
    } finally {
      setImproving(false);
    }
  };

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
          <span className="plan-badge" style={{ marginLeft: '8px' }}>{messageTemplate.length} chars</span>
          <div className="plan-message-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            {!isEditing && !loading && (
              <>
                <button className="plan-action-btn" onClick={() => { setIsEditing(true); setShowImprove(false); }}>
                  <Edit size={12} />
                  <span>Edit</span>
                </button>
                <button className="plan-action-btn" onClick={() => setShowImprove(s => !s)}>
                  <Sparkles size={12} />
                  <span>Improve with AI</span>
                </button>
              </>
            )}
          </div>
        </div>
        <div className="plan-section-body">
          {isEditing ? (
            <div className="plan-message-edit-wrap">
              <textarea
                className="plan-message-textarea"
                value={editedMessage}
                onChange={e => setEditedMessage(e.target.value)}
                placeholder="Draft your message template here..."
                disabled={loading}
              />
              <div className="plan-message-edit-actions" style={{ display: 'flex', gap: '8px', marginTop: '8px', justifyContent: 'flex-end' }}>
                <button className="plan-action-btn btn-cancel" onClick={handleCancelEdit} disabled={loading}>
                  Cancel
                </button>
                <button className="plan-action-btn btn-save" style={{ background: 'var(--orange-500)', borderColor: 'var(--orange-400)', color: 'white' }} onClick={handleSaveEdit} disabled={loading}>
                  Save Changes
                </button>
              </div>
            </div>
          ) : (
            <div className="plan-message-preview">{messageTemplate}</div>
          )}

          {showImprove && !isEditing && (
            <div className="plan-message-improve-wrap" style={{ marginTop: '6px', padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  className="plan-improve-input"
                  value={improveInstruction}
                  onChange={e => setImproveInstruction(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleImproveMessage();
                    }
                  }}
                  placeholder="Tell AI what to improve... (e.g. 'make it shorter', 'make it urgent')"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid rgba(255,255,255,0.1)',
                    background: 'rgba(0,0,0,0.2)',
                    color: 'var(--text-primary)',
                    fontSize: '12.5px',
                    outline: 'none',
                  }}
                  disabled={improving || loading}
                />
                <button
                  className="plan-action-btn"
                  style={{ background: 'var(--purple-600)', borderColor: 'var(--purple-500)', color: 'white' }}
                  onClick={handleImproveMessage}
                  disabled={improving || loading || !improveInstruction.trim()}
                >
                  {improving ? 'Improving...' : 'Improve'}
                </button>
              </div>
              {improveError && (
                <div className="improve-error" style={{ color: '#ef4444', fontSize: '11px', marginTop: '6px' }}>
                  {improveError}
                </div>
              )}
            </div>
          )}
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

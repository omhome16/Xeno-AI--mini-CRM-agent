import { useState } from 'react';
import { Users, MessageSquare, Rocket, Check, X, Pencil, RefreshCw } from 'lucide-react';
import CustomerPreviewTable from './CustomerPreviewTable';

interface InterruptCardProps {
  data: Record<string, unknown>;
  onRespond: (response: Record<string, unknown>) => void;
}

function SegmentReviewCard({ data, onRespond }: InterruptCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');

  const preview = (data.audience_preview as Record<string, unknown>[]) || [];

  return (
    <div className="interrupt-card">
      <div className="card-header">
        <div className="card-icon segment"><Users size={18} /></div>
        <h3>Review Audience Segment</h3>
      </div>
      <div className="card-body">
        <p style={{ marginBottom: 12, color: 'var(--text-secondary)' }}>
          Found <strong>{data.audience_count as number}</strong> customers matching your criteria
        </p>

        {typeof data.audience_sql === 'string' && data.audience_sql && (
          <div style={{
            fontSize: 11.5,
            fontFamily: "'SFMono-Regular', 'Consolas', monospace",
            background: 'rgba(0,0,0,0.03)',
            padding: '8px 12px',
            borderRadius: 8,
            marginBottom: 12,
            color: 'var(--text-muted)',
            wordBreak: 'break-all',
            lineHeight: 1.5,
          }}>
            {data.audience_sql as string}
          </div>
        )}

        {preview.length > 0 && (
          <CustomerPreviewTable preview={preview} totalCount={data.audience_count as number} />
        )}

        {isEditing && (
          <textarea
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            placeholder="Describe a different audience..."
            autoFocus
          />
        )}
      </div>
      <div className="card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => onRespond({ action: 'approve' })}>
          <Check size={14} /> Approve
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => {
            if (isEditing && editValue.trim()) {
              onRespond({ action: 'edit', new_description: editValue });
            } else {
              setIsEditing(true);
            }
          }}
        >
          <Pencil size={14} /> {isEditing ? 'Submit Edit' : 'Edit'}
        </button>
      </div>
    </div>
  );
}

function MessageReviewCard({ data, onRespond }: InterruptCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [messageText, setMessageText] = useState(data.message_template as string || '');

  return (
    <div className="interrupt-card">
      <div className="card-header">
        <div className="card-icon message"><MessageSquare size={18} /></div>
        <h3>Review Message</h3>
      </div>
      <div className="card-body">
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, fontSize: 13, color: 'var(--text-muted)' }}>
          <span>Channel: <strong>{(data.channel as string || '').toUpperCase()}</strong></span>
          <span>&middot;</span>
          <span>{data.char_count as number} chars</span>
        </div>

        {isEditing ? (
          <textarea
            value={messageText}
            onChange={e => setMessageText(e.target.value)}
            style={{ minHeight: 120 }}
            autoFocus
          />
        ) : (
          <div className="message-preview">{messageText}</div>
        )}
      </div>
      <div className="card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => {
          if (isEditing) {
            onRespond({ action: 'edit', new_message: messageText });
          } else {
            onRespond({ action: 'approve' });
          }
        }}>
          <Check size={14} /> {isEditing ? 'Save & Continue' : 'Approve'}
        </button>
        <button className="btn btn-secondary btn-sm" onClick={() => setIsEditing(!isEditing)}>
          <Pencil size={14} /> {isEditing ? 'Cancel' : 'Edit'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => onRespond({ action: 'rewrite' })}>
          <RefreshCw size={14} /> Regenerate
        </button>
      </div>
    </div>
  );
}

function CampaignConfirmCard({ data, onRespond }: InterruptCardProps) {
  return (
    <div className="interrupt-card">
      <div className="card-header">
        <div className="card-icon confirm"><Rocket size={18} /></div>
        <h3>Confirm Campaign</h3>
      </div>
      <div className="card-body">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 20px', marginBottom: 16, fontSize: 14 }}>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 600 }}>CAMPAIGN</span>
            <div style={{ fontWeight: 600 }}>{data.campaign_name as string}</div>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 600 }}>CHANNEL</span>
            <div style={{ fontWeight: 600 }}>{(data.channel as string || '').toUpperCase()}</div>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 600 }}>AUDIENCE</span>
            <div style={{ fontWeight: 600 }}>{data.audience_count as number} customers</div>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 600 }}>SEGMENT</span>
            <div style={{ fontWeight: 600 }}>{data.segment_name as string}</div>
          </div>
        </div>

        {typeof data.message_preview === 'string' && data.message_preview && (
          <div className="message-preview" style={{ fontSize: 13 }}>
            {data.message_preview as string}
          </div>
        )}
      </div>
      <div className="card-actions">
        <button className="btn btn-success btn-sm" onClick={() => onRespond({ action: 'approve' })}>
          <Rocket size={14} /> Send Campaign
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => onRespond({ action: 'cancel' })}>
          <X size={14} /> Cancel
        </button>
      </div>
    </div>
  );
}

export default function InterruptCard({ data, onRespond }: InterruptCardProps) {
  const type = data.type as string;

  if (type === 'segment_review') return <SegmentReviewCard data={data} onRespond={onRespond} />;
  if (type === 'message_review') return <MessageReviewCard data={data} onRespond={onRespond} />;
  if (type === 'campaign_confirm') return <CampaignConfirmCard data={data} onRespond={onRespond} />;

  // Fallback
  return (
    <div className="interrupt-card">
      <div className="card-header"><h3>Action Required</h3></div>
      <div className="card-body">
        <pre style={{ fontSize: 12, overflow: 'auto' }}>{JSON.stringify(data, null, 2)}</pre>
      </div>
      <div className="card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => onRespond({ action: 'approve' })}>
          Continue
        </button>
      </div>
    </div>
  );
}

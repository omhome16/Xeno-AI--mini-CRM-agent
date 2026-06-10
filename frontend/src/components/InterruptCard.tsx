import { useState } from 'react';
import { Users, MessageSquare, Rocket, Check, X, Pencil, RefreshCw } from 'lucide-react';

interface InterruptCardProps {
  data: Record<string, unknown>;
  onRespond: (response: Record<string, unknown>) => void;
}

function SegmentReviewCard({ data, onRespond }: InterruptCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');

  return (
    <div className="interrupt-card">
      <div className="card-header">
        <div className="card-icon segment"><Users size={18} /></div>
        <h3>Review Audience Segment</h3>
      </div>
      <div className="card-body">
        <p style={{ marginBottom: 12, color: '#525252' }}>
          Found <strong>{data.audience_count as number}</strong> customers matching your criteria
        </p>

        {Array.isArray(data.audience_preview) && (data.audience_preview as Record<string, unknown>[]).length > 0 && (
          <table className="preview-table">
            <thead>
              <tr><th>Name</th><th>City</th><th>Spent</th><th>Orders</th></tr>
            </thead>
            <tbody>
              {(data.audience_preview as Record<string, unknown>[]).slice(0, 5).map((c, i) => (
                <tr key={i}>
                  <td>{c.name as string}</td>
                  <td>{c.city as string || '—'}</td>
                  <td>₹{Number(c.total_spent || 0).toLocaleString('en-IN')}</td>
                  <td>{c.total_orders as number || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, fontSize: 13, color: '#737373' }}>
          <span>Channel: <strong>{(data.channel as string || '').toUpperCase()}</strong></span>
          <span>•</span>
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
            <span style={{ color: '#737373', fontSize: 12, fontWeight: 600 }}>CAMPAIGN</span>
            <div style={{ fontWeight: 600 }}>{data.campaign_name as string}</div>
          </div>
          <div>
            <span style={{ color: '#737373', fontSize: 12, fontWeight: 600 }}>CHANNEL</span>
            <div style={{ fontWeight: 600 }}>{(data.channel as string || '').toUpperCase()}</div>
          </div>
          <div>
            <span style={{ color: '#737373', fontSize: 12, fontWeight: 600 }}>AUDIENCE</span>
            <div style={{ fontWeight: 600 }}>{data.audience_count as number} customers</div>
          </div>
          <div>
            <span style={{ color: '#737373', fontSize: 12, fontWeight: 600 }}>SEGMENT</span>
            <div style={{ fontWeight: 600 }}>{data.segment_name as string}</div>
          </div>
        </div>

        {data.message_preview && (
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

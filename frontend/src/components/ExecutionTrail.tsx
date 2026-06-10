import { CheckCircle, XCircle, Loader, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

export interface TrailStep {
  id: string;
  label: string;
  message: string;
  status: 'pending' | 'running' | 'done' | 'error';
  detail?: string;
}

interface Props {
  steps: TrailStep[];
  campaignResult?: {
    campaign_id: string;
    campaign_name: string;
    total_audience: number;
    communications_created: number;
  };
  error?: string;
  onDone: () => void;
}

export default function ExecutionTrail({ steps, campaignResult, error, onDone }: Props) {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  return (
    <div className="execution-trail glass">
      <div className="trail-header">
        <h3 className="trail-title">🚀 Campaign Execution</h3>
        <p className="trail-subtitle">Running end-to-end — no interruptions</p>
      </div>

      <div className="trail-steps">
        {steps.map((step, i) => (
          <div key={step.id} className={`trail-step trail-step-${step.status}`}>
            <div className="trail-connector">
              <div className={`trail-dot trail-dot-${step.status}`}>
                {step.status === 'running' && <Loader size={14} className="spinning" />}
                {step.status === 'done' && <CheckCircle size={14} />}
                {step.status === 'error' && <XCircle size={14} />}
                {step.status === 'pending' && <div className="trail-dot-empty" />}
              </div>
              {i < steps.length - 1 && <div className={`trail-line trail-line-${step.status}`} />}
            </div>
            <div className="trail-content">
              <div
                className="trail-label"
                onClick={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
              >
                <span>{step.label}</span>
                {step.detail && (
                  expandedStep === step.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                )}
              </div>
              <div className="trail-message">{step.message}</div>
              {expandedStep === step.id && step.detail && (
                <pre className="trail-detail">{step.detail}</pre>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="trail-error">
          <XCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {campaignResult && (
        <div className="trail-success">
          <div className="trail-success-icon">🎉</div>
          <h4>Campaign Launched!</h4>
          <div className="trail-success-stats">
            <div className="trail-stat">
              <div className="trail-stat-value">{campaignResult.total_audience.toLocaleString()}</div>
              <div className="trail-stat-label">Customers</div>
            </div>
            <div className="trail-stat">
              <div className="trail-stat-value">{campaignResult.communications_created.toLocaleString()}</div>
              <div className="trail-stat-label">Messages Queued</div>
            </div>
          </div>
          <button className="btn-new-campaign" onClick={onDone}>
            Start New Campaign
          </button>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { Database, Upload, AlertCircle, CheckCircle2, FileText, RefreshCw, Trash2 } from 'lucide-react';
import { ingestCustomers, ingestOrders } from '../api';

export default function DataIngestionPage() {
  const [activeTab, setActiveTab] = useState<'customers' | 'orders'>('customers');
  const [csvText, setCsvText] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [result, setResult] = useState<{
    status: 'success' | 'error' | 'partial_success';
    count: number;
    message: string;
    errors?: string[];
  } | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setSelectedFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      if (text) {
        setCsvText(text);
      }
    };
    reader.readAsText(file);
  };

  const handleIngest = async () => {
    if (!csvText.trim()) {
      alert('Please upload a CSV file first.');
      return;
    }
    
    setIngesting(true);
    setResult(null);
    
    try {
      let res;
      if (activeTab === 'customers') {
        res = await ingestCustomers(csvText);
      } else {
        res = await ingestOrders(csvText);
      }
      
      setResult({
        status: res.status as 'success' | 'partial_success',
        count: res.count,
        message: res.message,
        errors: res.errors
      });
    } catch (err: any) {
      console.error('Ingestion failed:', err);
      setResult({
        status: 'error',
        count: 0,
        message: err.message || 'Data Ingestion failed. Verify your CSV format.'
      });
    } finally {
      setIngesting(false);
    }
  };

  const clearFile = () => {
    setSelectedFileName('');
    setCsvText('');
    setResult(null);
  };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="glass" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)' }}>
          <Database size={22} className="text-orange-500" />
          <span>Data Ingestion Engine</span>
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Organize and upload customer contact books and order transaction logs.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '2px' }}>
        <button
          onClick={() => { setActiveTab('customers'); setCsvText(''); setSelectedFileName(''); setResult(null); }}
          className={`nav-item ${activeTab === 'customers' ? 'active' : ''}`}
          style={{ padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
        >
          Customer Book Ingestion
        </button>
        <button
          onClick={() => { setActiveTab('orders'); setCsvText(''); setSelectedFileName(''); setResult(null); }}
          className={`nav-item ${activeTab === 'orders' ? 'active' : ''}`}
          style={{ padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
        >
          Order Transaction Ingestion
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Input Panel */}
        <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} className="text-orange-400" />
            <span>CSV Source File</span>
          </h4>

          {!selectedFileName ? (
            <label
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '220px',
                padding: '24px',
                borderRadius: '12px',
                border: '2px dashed rgba(255, 255, 255, 0.15)',
                background: 'rgba(255, 255, 255, 0.05)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              className="upload-dropzone"
            >
              <Upload size={32} style={{ color: 'var(--orange-400)', marginBottom: '12px', opacity: 0.8 }} />
              <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Click to upload a CSV file</span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', textAlign: 'center' }}>
                {activeTab === 'customers'
                  ? 'Required: name, external_id (Recommended)'
                  : 'Required: customer_external_id, total_amount'
                }
              </span>
              <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: 'none' }} />
            </label>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '220px',
                padding: '24px',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                background: 'rgba(255, 255, 255, 0.1)',
              }}
            >
              <CheckCircle2 size={36} color="#10b981" style={{ marginBottom: '12px' }} />
              <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', wordBreak: 'break-all' }}>
                {selectedFileName}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                CSV file loaded and parsed successfully
              </span>
              <button
                onClick={clearFile}
                style={{
                  marginTop: '16px',
                  fontSize: '11px',
                  color: '#ef4444',
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.15)',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Trash2 size={12} /> Remove File
              </button>
            </div>
          )}

          <button
            onClick={handleIngest}
            disabled={ingesting || !csvText.trim()}
            className="btn btn-primary"
            style={{ width: '100%', background: 'var(--orange-500)', border: 'none', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
          >
            {ingesting ? <RefreshCw size={16} className="spinning" /> : <Database size={16} />}
            <span>{ingesting ? 'Processing Ingestion...' : `Ingest ${activeTab}`}</span>
          </button>
        </div>

        {/* Info & Results Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Format Helper Card */}
          <div className="glass" style={{ padding: '20px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
              <AlertCircle size={16} className="text-orange-400" />
              <span>Formatting Guidelines</span>
            </h4>
            
            {activeTab === 'customers' ? (
              <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px', color: 'var(--text-secondary)' }}>
                <p>Ingesting customers registers them in the database for targeting campaigns.</p>
                <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <li><strong>name</strong> (Required): Shopper's full name.</li>
                  <li><strong>external_id</strong> (Recommended): Unique brand customer identifier used to map order history.</li>
                  <li><strong>city</strong> (Optional): Normalized to Bangalore, Delhi, Mumbai, etc.</li>
                  <li><strong>tags</strong> (Optional): Comma-separated (e.g. <code>vip,lapsed</code>).</li>
                </ul>
              </div>
            ) : (
              <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px', color: 'var(--text-secondary)' }}>
                <p>Ingesting orders recomputes customer lifetime value aggregates automatically.</p>
                <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <li><strong>customer_external_id</strong> (Required): Maps the purchase to a customer's <code>external_id</code>.</li>
                  <li><strong>total_amount</strong> (Required): Total price in INR (e.g. <code>4500.00</code>).</li>
                  <li><strong>order_date</strong> (Required): Date of order (e.g. <code>YYYY-MM-DD</code>).</li>
                  <li><strong>category / product_name</strong> (Optional): Categories/products purchased.</li>
                </ul>
              </div>
            )}
          </div>

          {/* Results Summary Card */}
          {result && (
            <div className="glass" style={{ padding: '20px', border: result.status === 'success' ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
                {result.status === 'success' ? (
                  <CheckCircle2 className="text-success" size={20} style={{ color: '#10b981' }} />
                ) : (
                  <AlertCircle className="text-error" size={20} style={{ color: '#ef4444' }} />
                )}
                <h4 style={{ fontSize: '14.5px', fontWeight: 700, textTransform: 'capitalize' }}>
                  Ingestion {result.status.replace('_', ' ')}
                </h4>
              </div>

              <p style={{ fontSize: '13.5px', color: 'var(--text-primary)', marginBottom: '8px' }}>
                {result.message}
              </p>

              {result.errors && result.errors.length > 0 && (
                <div style={{ marginTop: '12px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>ERRORS ENCOUNTERED:</span>
                  <div style={{ maxHeight: '120px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {result.errors.map((err, idx) => (
                      <div key={idx} style={{ fontSize: '11px', color: '#ef4444', fontFamily: 'monospace', background: 'rgba(239,68,68,0.06)', padding: '4px 8px', borderRadius: '4px' }}>
                        {err}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

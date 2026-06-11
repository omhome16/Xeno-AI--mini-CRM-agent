import { useState } from 'react';
import { Database, Upload, AlertCircle, CheckCircle2, Copy, FileText, RefreshCw } from 'lucide-react';
import { ingestCustomers, ingestOrders } from '../api';

export default function DataIngestionPage() {
  const [activeTab, setActiveTab] = useState<'customers' | 'orders'>('customers');
  const [csvText, setCsvText] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [result, setResult] = useState<{
    status: 'success' | 'error' | 'partial_success';
    count: number;
    message: string;
    errors?: string[];
  } | null>(null);

  const sampleCustomerCSV = 
`name,city,tags,external_id,email,phone
Aditya Verma,Mumbai,vip,cust_001,aditya@example.com,+91-9999911111
Sneha Patil,Mumbai,lapsed,cust_002,sneha@example.com,+91-9999922222
Rohan Joshi,Delhi,vip,cust_003,rohan@example.com,+91-9999933333
Priya Sharma,Bangalore,new,cust_004,priya@example.com,+91-9999944444`;

  const sampleOrderCSV = 
`customer_external_id,total_amount,order_date,items_count,category,product_name
cust_001,4500.00,2026-06-01 10:30:00,2,Silk Sarees,Pure Kanjeevaram Saree
cust_001,1200.00,2026-06-05 14:15:00,1,General,Matching Blouse Piece
cust_003,8500.00,2026-05-20 18:00:00,1,Silk Sarees,Banarasi Georgette Saree
cust_004,250.00,2026-06-10 12:00:00,1,Accessories,Decorative Bindis`;

  const handleCopyTemplate = () => {
    const text = activeTab === 'customers' ? sampleCustomerCSV : sampleOrderCSV;
    setCsvText(text);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
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
      alert('Please paste or upload some CSV data first.');
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
          onClick={() => { setActiveTab('customers'); setCsvText(''); setResult(null); }}
          className={`nav-item ${activeTab === 'customers' ? 'active' : ''}`}
          style={{ padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
        >
          Customer Book Ingestion
        </button>
        <button
          onClick={() => { setActiveTab('orders'); setCsvText(''); setResult(null); }}
          className={`nav-item ${activeTab === 'orders' ? 'active' : ''}`}
          style={{ padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', outline: 'none' }}
        >
          Order Transaction Ingestion
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Input Panel */}
        <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={16} className="text-orange-400" />
              <span>CSV Payload</span>
            </h4>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="plan-action-btn"
                onClick={handleCopyTemplate}
                style={{ fontSize: '11px', display: 'flex', gap: '4px', alignItems: 'center' }}
              >
                <Copy size={11} /> Load Template
              </button>
              <label className="plan-action-btn" style={{ fontSize: '11px', cursor: 'pointer', display: 'flex', gap: '4px', alignItems: 'center' }}>
                <Upload size={11} />
                <span>Upload File</span>
                <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: 'none' }} />
              </label>
            </div>
          </div>

          <textarea
            placeholder={
              activeTab === 'customers'
                ? "name,city,tags,external_id,email,phone\nJohn Doe,Delhi,vip,cust_999,john@example.com,+91-9876543210"
                : "customer_external_id,total_amount,order_date,items_count,category,product_name\ncust_999,4500.00,2026-06-11 12:00:00,1,Clothing,Pure Silk Saree"
            }
            value={csvText}
            onChange={e => setCsvText(e.target.value)}
            style={{ width: '100%', minHeight: '260px', padding: '12px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical', fontFamily: 'monospace', fontSize: '12.5px', lineHeight: '1.5' }}
          />

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

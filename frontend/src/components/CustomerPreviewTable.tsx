import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface CustomerPreviewTableProps {
  preview: Record<string, unknown>[];
  totalCount: number;
}

export default function CustomerPreviewTable({ preview, totalCount }: CustomerPreviewTableProps) {
  const [showAll, setShowAll] = useState(false);

  if (!preview || preview.length === 0) return null;

  // 1. Determine columns based on the keys of the first item
  const allKeys = Object.keys(preview[0]);
  
  // Filter out internal/ugly columns (like UUIDs, timestamps) if there are other columns
  const excludedKeys = ['id', 'customer_id', 'external_id', 'whatsapp_id', 'updated_at'];
  let displayKeys = allKeys.filter(k => !excludedKeys.includes(k));
  
  if (displayKeys.length === 0) {
    // If everything got filtered out, just show all keys
    displayKeys = allKeys;
  }

  // Helper to format header text
  const formatHeader = (key: string) => {
    return key
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Helper to format cell values
  const formatValue = (key: string, value: unknown) => {
    if (value === null || value === undefined) return '\u2014';
    
    // Format currencies
    const lowerKey = key.toLowerCase();
    const isCurrency = lowerKey.includes('spent') || 
                       lowerKey.includes('amount') || 
                       lowerKey.includes('value') || 
                       lowerKey.includes('price') || 
                       lowerKey.includes('revenue');
                       
    if (typeof value === 'number') {
      if (isCurrency) {
        return '\u20B9' + Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });
      }
      return value.toLocaleString('en-IN');
    }

    // Format tags array
    if (Array.isArray(value)) {
      return (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {value.map((t: unknown, i) => (
            <span key={i} className="badge" style={{ 
              background: 'rgba(255, 255, 255, 0.12)', 
              color: 'var(--text-on-glass)',
              fontSize: '10px',
              padding: '2px 6px',
              border: '1px solid rgba(255, 255, 255, 0.15)'
            }}>
              {String(t)}
            </span>
          ))}
        </div>
      );
    }

    // Format Date strings (simple check for ISO string or date-like string)
    if (typeof value === 'string' && (lowerKey.endsWith('_at') || lowerKey.endsWith('_date'))) {
      try {
        const d = new Date(value);
        if (!isNaN(d.getTime())) {
          return d.toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
          });
        }
      } catch {
        // Fall through
      }
    }

    return String(value);
  };

  const displayCount = showAll ? preview.length : 5;
  const hasMore = preview.length > 5;

  return (
    <div className="preview-table-container" style={{ margin: '14px 0', width: '100%' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'baseline', 
        marginBottom: 8,
        fontSize: '12.5px',
        color: 'var(--text-muted)'
      }}>
        <span>Showing {Math.min(preview.length, displayCount)} of {preview.length} loaded records</span>
        {totalCount > preview.length && (
          <span>Total matching in database: <strong>{totalCount}</strong></span>
        )}
      </div>

      <div className="glass-subtle" style={{ overflowX: 'auto', borderRadius: '12px', border: '1px solid var(--glass-border)', background: 'var(--glass-bg-strong)', backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)' }}>
        <table className="preview-table" style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '13px' }}>
          <thead>
            <tr style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
              {displayKeys.map(k => (
                <th key={k} style={{ 
                  textAlign: 'left', 
                  padding: '12px 16px', 
                  color: 'var(--text-muted)', 
                  fontWeight: 700,
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  borderBottom: '1px solid var(--glass-border)'
                }}>
                  {formatHeader(k)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.slice(0, displayCount).map((row, rowIndex) => (
              <tr key={rowIndex}>
                {displayKeys.map(k => (
                  <td key={k} style={{ 
                    padding: '12px 16px', 
                    borderTop: rowIndex > 0 ? '1px solid var(--glass-border-subtle)' : 'none',
                    color: 'var(--text-on-glass)',
                    lineHeight: '1.5'
                  }}>
                    {formatValue(k, row[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <button
          className="btn btn-secondary btn-sm"
          style={{ 
            width: '100%', 
            justifyContent: 'center', 
            marginTop: 8,
            background: 'rgba(255, 255, 255, 0.08)',
            borderColor: 'rgba(255, 255, 255, 0.15)'
          }}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {showAll ? `Show less` : `View all ${preview.length} results`}
        </button>
      )}
    </div>
  );
}

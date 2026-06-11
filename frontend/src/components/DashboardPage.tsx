import { useState, useEffect } from 'react';
import { BarChart3, Users, ShoppingCart, TrendingUp, Send, Eye, MousePointerClick } from 'lucide-react';
import { fetchCustomerStats, fetchCampaigns, type CustomerStats, type Campaign } from '../api';

export default function DashboardPage() {
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedCampaignId, setExpandedCampaignId] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [s, c] = await Promise.all([
          fetchCustomerStats(),
          fetchCampaigns(),
        ]);
        setStats(s);
        setCampaigns(c.campaigns || []);
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const toggleCampaign = (id: string) => {
    setExpandedCampaignId(prev => prev === id ? null : id);
  };

  if (loading) {
    return (
      <div className="empty-state">
        <div className="loading-dots"><span /><span /><span /></div>
        <h3>Loading dashboard...</h3>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card glass">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="stat-label">Total Customers</div>
              <div className="stat-value">{stats?.total_customers?.toLocaleString() || 0}</div>
            </div>
            <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: 8, borderRadius: 8 }}>
              <Users size={20} color="#3b82f6" />
            </div>
          </div>
        </div>

        <div className="stat-card glass">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="stat-label">Total Orders</div>
              <div className="stat-value">{stats?.total_orders?.toLocaleString() || 0}</div>
            </div>
            <div style={{ background: 'rgba(249, 115, 22, 0.1)', padding: 8, borderRadius: 8 }}>
              <ShoppingCart size={20} color="#f97316" />
            </div>
          </div>
        </div>

        <div className="stat-card glass">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="stat-label">Total Revenue</div>
              <div className="stat-value">₹{(stats?.total_revenue || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
            </div>
            <div style={{ background: 'rgba(34, 197, 94, 0.1)', padding: 8, borderRadius: 8 }}>
              <TrendingUp size={20} color="#22c55e" />
            </div>
          </div>
        </div>

        <div className="stat-card glass">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="stat-label">Campaigns</div>
              <div className="stat-value">{campaigns.length}</div>
            </div>
            <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: 8, borderRadius: 8 }}>
              <BarChart3 size={20} color="#8b5cf6" />
            </div>
          </div>
        </div>
      </div>

      {/* City Distribution */}
      {stats?.city_distribution && Object.keys(stats.city_distribution).length > 0 && (
        <div className="glass" style={{ padding: 20, marginBottom: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Customer Distribution by City</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(stats.city_distribution)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 12)
              .map(([city, count]) => (
                <div key={city} className="glass-subtle" style={{ padding: '8px 14px', display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{city}</span>
                  <span style={{ color: '#a3a3a3', fontSize: 12 }}>{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Campaigns List */}
      <div>
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Recent Campaigns</h3>
        {campaigns.length === 0 ? (
          <div className="glass empty-state" style={{ padding: 40 }}>
            <BarChart3 size={48} strokeWidth={1} />
            <h3>No campaigns yet</h3>
            <p>Start a conversation with the AI agent to create your first campaign</p>
          </div>
        ) : (
          <div className="campaign-list">
            {campaigns.map(c => (
              <div
                key={c.id}
                className={`campaign-card glass ${expandedCampaignId === c.id ? 'expanded' : ''}`}
                onClick={() => toggleCampaign(c.id)}
                style={{ cursor: 'pointer', transition: 'all 0.3s ease' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <div className="campaign-info">
                    <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>{c.name}</span>
                      <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 'normal', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.08)' }}>
                        {expandedCampaignId === c.id ? 'Hide Details' : 'View Details'}
                      </span>
                    </h4>
                    <div className="campaign-meta">
                      <span className={`badge badge-${c.status}`}>{c.status}</span>
                      <span>{c.channel.toUpperCase()}</span>
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="campaign-stats">
                    <div className="mini-stat">
                      <div className="mini-value" style={{ color: '#3b82f6' }}>
                        <Send size={14} style={{ marginRight: 2 }} />{c.total_sent}
                      </div>
                      <div className="mini-label">Sent</div>
                    </div>
                    <div className="mini-stat">
                      <div className="mini-value" style={{ color: '#f97316' }}>
                        <Eye size={14} style={{ marginRight: 2 }} />{c.total_opened}
                      </div>
                      <div className="mini-label">Opened</div>
                    </div>
                    <div className="mini-stat">
                      <div className="mini-value" style={{ color: '#22c55e' }}>
                        <MousePointerClick size={14} style={{ marginRight: 2 }} />{c.total_clicked}
                      </div>
                      <div className="mini-label">Clicked</div>
                    </div>

                    {/* Funnel Bar */}
                    <div style={{ width: 120 }}>
                      <div className="funnel-bar">
                        <div
                          className="fill delivered"
                          style={{ width: `${c.total_sent ? (c.total_delivered / c.total_sent * 100) : 0}%` }}
                        />
                      </div>
                      <div className="funnel-bar">
                        <div
                          className="fill opened"
                          style={{ width: `${c.total_delivered ? (c.total_opened / c.total_delivered * 100) : 0}%` }}
                        />
                      </div>
                      <div className="funnel-bar">
                        <div
                          className="fill clicked"
                          style={{ width: `${c.total_delivered ? (c.total_clicked / c.total_delivered * 100) : 0}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Details Section */}
                {expandedCampaignId === c.id && (
                  <div
                    className="campaign-details-expanded"
                    style={{
                      marginTop: '20px',
                      paddingTop: '20px',
                      borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                      width: '100%',
                      textAlign: 'left',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px'
                    }}
                    onClick={(e) => e.stopPropagation()} // Prevent collapse when clicking details content
                  >
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                      {/* Audience info card */}
                      <div className="glass-subtle" style={{ padding: '16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.12)', background: 'rgba(255, 255, 255, 0.35)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '8px' }}>
                          Target Audience Segment
                        </div>
                        <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', fontWeight: '600', lineHeight: '1.5' }}>
                          {c.segment_description || 'No description available'}
                        </div>
                      </div>

                      {/* Parameters card */}
                      <div className="glass-subtle" style={{ padding: '16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.12)', background: 'rgba(255, 255, 255, 0.35)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '8px' }}>
                          Campaign Parameters
                        </div>
                        <div style={{ fontSize: '12.5px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ color: 'var(--text-muted)' }}>Audience Size:</span>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.total_audience.toLocaleString()} customers</span>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ color: 'var(--text-muted)' }}>Channel:</span>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{(c.channel || 'WhatsApp').toUpperCase()}</span>
                          </div>
                          {c.filter_criteria?.filters && c.filter_criteria.filters.length > 0 && (
                            <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                              <span style={{ color: 'var(--text-muted)', fontSize: '11px', display: 'block', marginBottom: '4px' }}>Filters Applied:</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {c.filter_criteria.filters.map((f: any, idx: number) => (
                                  <span key={idx} className="glass-subtle" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>
                                    {f.field} {f.op} {String(f.value)}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Message content card */}
                    <div className="glass-subtle" style={{ padding: '16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.12)', background: 'rgba(255, 255, 255, 0.35)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '8px' }}>
                        Message Copy Template
                      </div>
                      <pre style={{
                        padding: '14px 16px',
                        borderRadius: '8px',
                        background: 'rgba(255, 255, 255, 0.55)',
                        border: '1px solid rgba(255, 255, 255, 0.25)',
                        borderLeft: '3px solid var(--orange-400)',
                        fontSize: '13px',
                        lineHeight: '1.6',
                        color: 'var(--text-primary)',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'inherit',
                        margin: 0
                      }}>
                        {c.message_template}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Store, Plus, Trash2, Save, Loader2, Link, Phone, FileText, ShoppingBag, MapPin } from 'lucide-react';
import { fetchBrandProfile, saveBrandProfile, type BrandProfile, type ProductItem, type OutletItem } from '../api';

export default function BrandProfilePage() {
  const [profile, setProfile] = useState<BrandProfile>({
    brand_name: '',
    niche: '',
    product_catalog: [],
    outlets: [],
    campaign_urls: [],
    support_phone: '',
    brand_tone: 'Friendly & Conversational',
    custom_context: ''
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [newUrl, setNewUrl] = useState('');

  // Local inputs for catalog items
  const [newProduct, setNewProduct] = useState<Partial<ProductItem>>({ name: '', price: 0, category: '', description: '' });
  const [newOutlet, setNewOutlet] = useState<Partial<OutletItem>>({ name: '', city: '', address: '' });

  useEffect(() => {
    async function loadProfile() {
      try {
        const data = await fetchBrandProfile();
        setProfile(data);
      } catch (err) {
        console.error('Failed to load brand profile:', err);
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, []);

  const handleSave = async () => {
    if (!profile.brand_name.trim()) {
      alert('Brand name is required');
      return;
    }
    setSaving(true);
    setSaveStatus('idle');
    try {
      await saveBrandProfile(profile);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch (err) {
      console.error('Failed to save brand profile:', err);
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const addProduct = () => {
    if (!newProduct.name?.trim() || !newProduct.price) return;
    setProfile(prev => ({
      ...prev,
      product_catalog: [...prev.product_catalog, {
        name: newProduct.name!.trim(),
        price: Number(newProduct.price),
        category: newProduct.category?.trim() || 'General',
        description: newProduct.description?.trim() || ''
      }]
    }));
    setNewProduct({ name: '', price: 0, category: '', description: '' });
  };

  const removeProduct = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      product_catalog: prev.product_catalog.filter((_, i) => i !== idx)
    }));
  };

  const addOutlet = () => {
    if (!newOutlet.name?.trim() || !newOutlet.city?.trim()) return;
    setProfile(prev => ({
      ...prev,
      outlets: [...prev.outlets, {
        name: newOutlet.name!.trim(),
        city: newOutlet.city!.trim(),
        address: newOutlet.address?.trim() || ''
      }]
    }));
    setNewOutlet({ name: '', city: '', address: '' });
  };

  const removeOutlet = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      outlets: prev.outlets.filter((_, i) => i !== idx)
    }));
  };

  const addUrl = () => {
    if (!newUrl.trim()) return;
    try {
      new URL(newUrl.trim()); // basic validation
      setProfile(prev => ({
        ...prev,
        campaign_urls: [...prev.campaign_urls, newUrl.trim()]
      }));
      setNewUrl('');
    } catch {
      alert('Please enter a valid URL (e.g. https://example.com)');
    }
  };

  const removeUrl = (idx: number) => {
    setProfile(prev => ({
      ...prev,
      campaign_urls: prev.campaign_urls.filter((_, i) => i !== idx)
    }));
  };

  if (loading) {
    return (
      <div className="empty-state">
        <div className="loading-dots"><span /><span /><span /></div>
        <h3>Loading Brand Profile...</h3>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="glass" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)' }}>
            <Store size={22} className="text-orange-500" />
            <span>Brand Profile & Context Hub</span>
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Define your company, catalog, stores, and marketing assets. The AI strategist uses this to construct custom campaign recommendations and templates.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--orange-500)', border: 'none' }}
        >
          {saving ? <Loader2 size={16} className="spinning" /> : <Save size={16} />}
          <span>{saving ? 'Saving...' : 'Save Profile'}</span>
        </button>
      </div>

      {saveStatus === 'success' && (
        <div className="glass-subtle" style={{ padding: '12px 20px', background: 'rgba(52, 211, 153, 0.15)', border: '1px solid rgba(52, 211, 153, 0.3)', color: '#047857', borderRadius: '8px', fontSize: '13.5px', fontWeight: 600 }}>
          ✓ Brand Profile saved successfully! The AI agent will now use this context immediately.
        </div>
      )}

      {saveStatus === 'error' && (
        <div className="glass-subtle" style={{ padding: '12px 20px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#b91c1c', borderRadius: '8px', fontSize: '13.5px', fontWeight: 600 }}>
          ✗ Failed to save brand profile. Please check connection and try again.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Left Column - Core Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Identity Card */}
          <div className="glass" style={{ padding: '20px' }}>
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, marginBottom: '16px' }}>
              <FileText size={16} className="text-orange-400" />
              <span>Identity & Tone</span>
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>Brand Name *</label>
                <input
                  type="text"
                  placeholder="e.g. Mugdha Silk Sarees"
                  value={profile.brand_name}
                  onChange={e => setProfile(prev => ({ ...prev, brand_name: e.target.value }))}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>Niche / Industry</label>
                <input
                  type="text"
                  placeholder="e.g. Apparel / Fashion Retail"
                  value={profile.niche}
                  onChange={e => setProfile(prev => ({ ...prev, niche: e.target.value }))}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>Brand Tone of Voice</label>
                <input
                  type="text"
                  placeholder="e.g. Warm, Premium, and Welcoming"
                  value={profile.brand_tone || ''}
                  onChange={e => setProfile(prev => ({ ...prev, brand_tone: e.target.value }))}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>Customer Support Phone</label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <Phone size={14} style={{ color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    placeholder="e.g. +91-9876543210"
                    value={profile.support_phone || ''}
                    onChange={e => setProfile(prev => ({ ...prev, support_phone: e.target.value }))}
                    style={{ flex: 1, padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Links & CTA assets */}
          <div className="glass" style={{ padding: '20px' }}>
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, marginBottom: '16px' }}>
              <Link size={16} className="text-orange-400" />
              <span>Promotional URLs & CTA Links</span>
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  placeholder="Paste URL (e.g., https://mugdha.co/sale)"
                  value={newUrl}
                  onChange={e => setNewUrl(e.target.value)}
                  style={{ flex: 1, padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
                />
                <button className="btn btn-sm" onClick={addUrl} style={{ background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.25)', color: 'var(--text-primary)' }}>
                  <Plus size={16} />
                </button>
              </div>

              {profile.campaign_urls.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
                  {profile.campaign_urls.map((url, idx) => (
                    <div key={idx} className="glass-subtle" style={{ padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.2)' }}>
                      <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }}>
                        {url}
                      </span>
                      <button onClick={() => removeUrl(idx)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column - Inventory & Stores */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Custom Guidelines */}
          <div className="glass" style={{ padding: '20px' }}>
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, marginBottom: '16px' }}>
              <FileText size={16} className="text-orange-400" />
              <span>Guidelines & Custom Context</span>
            </h4>
            <textarea
              placeholder="e.g. Always write in premium, classy tone. Propose matching pure Kanjeevaram sarees. Focus calls to action on booking a physical store visit."
              value={profile.custom_context || ''}
              onChange={e => setProfile(prev => ({ ...prev, custom_context: e.target.value }))}
              style={{ width: '100%', minHeight: '100px', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>

          {/* Store Outlets */}
          <div className="glass" style={{ padding: '20px' }}>
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, marginBottom: '16px' }}>
              <MapPin size={16} className="text-orange-400" />
              <span>Retail Stores / Outlets</span>
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px' }}>
                <input
                  type="text"
                  placeholder="Store Name (e.g. CP Delhi)"
                  value={newOutlet.name || ''}
                  onChange={e => setNewOutlet(prev => ({ ...prev, name: e.target.value }))}
                  style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', fontSize: '12.5px', outline: 'none' }}
                />
                <input
                  type="text"
                  placeholder="City (e.g. Delhi)"
                  value={newOutlet.city || ''}
                  onChange={e => setNewOutlet(prev => ({ ...prev, city: e.target.value }))}
                  style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', fontSize: '12.5px', outline: 'none' }}
                />
                <button className="btn btn-sm" onClick={addOutlet} style={{ background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.25)', color: 'var(--text-primary)' }}>
                  <Plus size={16} />
                </button>
              </div>

              {profile.outlets.length > 0 && (
                <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
                  {profile.outlets.map((o, idx) => (
                    <div key={idx} className="glass-subtle" style={{ padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.2)' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{o.name}</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{o.city}</span>
                      </div>
                      <button onClick={() => removeOutlet(idx)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Product Catalog */}
      <div className="glass" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <ShoppingBag size={18} className="text-orange-500" />
          <span>Product Catalog & Pricing</span>
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: '12px', alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>Product Name</label>
              <input
                type="text"
                placeholder="e.g. Pure Kanjeevaram Saree"
                value={newProduct.name || ''}
                onChange={e => setNewProduct(prev => ({ ...prev, name: e.target.value }))}
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>Price (₹)</label>
              <input
                type="number"
                placeholder="e.g. 15000"
                value={newProduct.price || ''}
                onChange={e => setNewProduct(prev => ({ ...prev, price: Number(e.target.value) }))}
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>Category</label>
              <input
                type="text"
                placeholder="e.g. Silk Sarees"
                value={newProduct.category || ''}
                onChange={e => setNewProduct(prev => ({ ...prev, category: e.target.value }))}
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.45)', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
            <button className="btn btn-primary" onClick={addProduct} style={{ height: '40px', padding: '0 16px', background: 'var(--orange-500)', border: 'none' }}>
              <Plus size={18} /> Add Product
            </button>
          </div>

          {profile.product_catalog.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', border: '1px dashed rgba(255,255,255,0.15)', borderRadius: '8px', color: 'var(--text-muted)', fontSize: '13px' }}>
              No products added to catalog yet. Add products to let the AI strategist suggest product-focused campaigns!
            </div>
          ) : (
            <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.1)', textAlign: 'left' }}>
                    <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>Product Name</th>
                    <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>Category</th>
                    <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>Price</th>
                    <th style={{ padding: '12px 16px', width: '60px' }} />
                  </tr>
                </thead>
                <tbody>
                  {profile.product_catalog.map((product, idx) => (
                    <tr key={idx} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>{product.name}</td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                        <span style={{ fontSize: '11px', background: 'rgba(255,255,255,0.15)', padding: '2px 8px', borderRadius: '4px' }}>
                          {product.category || 'General'}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-primary)' }}>₹{product.price.toLocaleString()}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <button onClick={() => removeProduct(idx)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

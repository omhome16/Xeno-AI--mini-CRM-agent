const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Types ──

export interface CampaignBrief {
  goal?: string;
  audience?: string;
  channel?: string;
  message_idea?: string;
  offer?: string;
}

export interface Suggestion {
  label: string;
  value: string;
  category: 'audience' | 'channel' | 'offer' | 'message' | 'action';
}

export interface Customer {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  city: string | null;
  tags: string[];
  total_orders: number;
  total_spent: number;
  avg_order_value: number;
  last_order_at: string | null;
  created_at: string;
}

export interface CustomerStats {
  total_customers: number;
  total_orders: number;
  total_revenue: number;
  avg_orders_per_customer: number;
  avg_spend_per_customer: number;
  city_distribution: Record<string, number>;
  tag_distribution: Record<string, number>;
}

export interface Campaign {
  id: string;
  name: string;
  channel: string;
  status: string;
  message_template: string;
  total_audience: number;
  total_sent: number;
  total_delivered: number;
  total_failed: number;
  total_opened: number;
  total_clicked: number;
  total_conversions?: number;
  total_attributed_revenue?: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  segment_description?: string;
  filter_criteria?: any;
}

export interface CampaignDetail {
  campaign: Campaign;
  funnel: Record<string, number>;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  failure_reasons: Record<string, number>;
}

// ── Chat API (Campaign Studio) ──

export async function startChat(
  message: string,
  mode: string = 'brainstorm',
  history: { role: string; content: string }[] = [],
  brief: CampaignBrief = {},
  conversation_id?: string,
): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, mode, history, brief, conversation_id }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function planCampaign(
  brief: CampaignBrief,
  history: { role: string; content: string }[] = [],
): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brief, history }),
  });
  if (!res.ok) throw new Error(`Plan failed: ${res.status}`);
  return res.json();
}

export async function improveMessage(
  messageTemplate: string,
  instruction: string,
  channel: string,
  audienceDescription?: string,
  offerDetails?: string,
): Promise<{ improved_message: string }> {
  const res = await fetch(`${API_BASE}/api/chat/improve-message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message_template: messageTemplate,
      instruction,
      channel,
      audience_description: audienceDescription || '',
      offer_details: offerDetails || '',
    }),
  });
  if (!res.ok) throw new Error(`Improve message failed: ${res.status}`);
  return res.json();
}

export async function executeCampaign(
  brief: CampaignBrief,
  audienceDescription: string,
  channel: string,
  messageDescription: string = '',
  offerDetails: string = '',
  messageTemplate?: string,
): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      brief,
      audience_description: audienceDescription,
      channel,
      message_description: messageDescription,
      offer_details: offerDetails,
      message_template: messageTemplate,
    }),
  });
  if (!res.ok) throw new Error(`Execute failed: ${res.status}`);
  return res.json();
}

export async function resumeChat(
  conversationId: string,
  response: Record<string, unknown>,
): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, response }),
  });
  if (!res.ok) throw new Error(`Resume failed: ${res.status}`);
  return res.json();
}

export function connectSSE(
  conversationId: string,
  onEvent: (event: { type: string; data: any }) => void,
): EventSource {
  const es = new EventSource(`${API_BASE}/api/chat/stream/${conversationId}`);
  let done = false;

  const eventTypes = [
    'step_start', 'step_complete', 'interrupt',
    'result', 'error', 'campaign_update', 'heartbeat',
  ];

  eventTypes.forEach(type => {
    es.addEventListener(type, (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data);
        if (type === 'result' || type === 'error') done = true;
        onEvent({ type, data: parsed });
      } catch {
        onEvent({ type, data: e.data });
      }
      if (type === 'result' || type === 'error') {
        es.close();
      }
    });
  });

  es.onerror = () => {
    if (!done) {
      onEvent({ type: 'error', data: { message: 'Connection lost' } });
    }
    es.close();
  };

  return es;
}

// ── Customers API ──

export async function fetchCustomers(page = 1, limit = 20, search = ''): Promise<{
  customers: Customer[];
  total: number;
  page: number;
  limit: number;
}> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) params.set('search', search);
  const res = await fetch(`${API_BASE}/api/customers?${params}`);
  return res.json();
}

export async function fetchCustomerStats(): Promise<CustomerStats> {
  const res = await fetch(`${API_BASE}/api/customers/stats`);
  return res.json();
}

// ── Campaigns API ──

export async function fetchCampaigns(): Promise<{ campaigns: Campaign[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/campaigns`);
  return res.json();
}

export async function fetchCampaignDetail(id: string): Promise<CampaignDetail> {
  const res = await fetch(`${API_BASE}/api/campaigns/${id}`);
  return res.json();
}

// ── Brand Profile API ──

export interface ProductItem {
  name: string;
  price: number;
  category?: string;
  description?: string;
}

export interface OutletItem {
  name: string;
  city: string;
  address?: string;
}

export interface BrandProfile {
  brand_name: string;
  niche: string;
  product_catalog: ProductItem[];
  outlets: OutletItem[];
  campaign_urls: string[];
  support_phone?: string;
  brand_tone?: string;
  custom_context?: string;
}

export async function fetchBrandProfile(): Promise<BrandProfile> {
  const res = await fetch(`${API_BASE}/brand`);
  if (!res.ok) throw new Error('Failed to fetch brand profile');
  return res.json();
}

export async function saveBrandProfile(profile: BrandProfile): Promise<{ status: string; data: BrandProfile }> {
  const res = await fetch(`${API_BASE}/brand`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error('Failed to save brand profile');
  return res.json();
}

// ── Ingestion API ──

export async function ingestCustomers(csvText: string): Promise<{ status: string; count: number; message: string; errors?: string[] }> {
  const res = await fetch(`${API_BASE}/api/ingest/customers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to ingest customers' }));
    throw new Error(errData.detail || 'Failed to ingest customers');
  }
  return res.json();
}

export async function ingestOrders(csvText: string): Promise<{ status: string; count: number; message: string; errors?: string[] }> {
  const res = await fetch(`${API_BASE}/api/ingest/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to ingest orders' }));
    throw new Error(errData.detail || 'Failed to ingest orders');
  }
  return res.json();
}

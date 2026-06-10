const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Chat API ──

export async function startChat(message: string, mode: string): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, mode }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function resumeChat(conversationId: string, response: Record<string, unknown>): Promise<{ conversation_id: string }> {
  const res = await fetch(`${API_BASE}/api/chat/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, response }),
  });
  if (!res.ok) throw new Error(`Resume failed: ${res.status}`);
  return res.json();
}

export function connectSSE(conversationId: string, onEvent: (event: { type: string; data: unknown }) => void): EventSource {
  const es = new EventSource(`${API_BASE}/api/chat/stream/${conversationId}`);
  let done = false;

  const eventTypes = ['step_start', 'step_complete', 'interrupt', 'result', 'error', 'campaign_update', 'heartbeat'];
  eventTypes.forEach(type => {
    es.addEventListener(type, (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data);
        if (type === 'result' || type === 'error') done = true;
        onEvent({ type, data: parsed });
      } catch {
        onEvent({ type, data: e.data });
      }
      // Close after terminal events
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

// ── Types ──

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
  total_audience: number;
  total_sent: number;
  total_delivered: number;
  total_failed: number;
  total_opened: number;
  total_clicked: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface CampaignDetail {
  campaign: Campaign;
  funnel: Record<string, number>;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  failure_reasons: Record<string, number>;
}

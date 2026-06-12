import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Send, Bot, Brain, ChevronRight, ChevronLeft, Sparkles, X, Check, Play } from 'lucide-react';
import {
  planCampaign,
  executeCampaign,
  connectSSE,
  startChat,
  fetchAudienceRecommendations,
  fetchStrategyRecommendation,
  fetchMessageRecommendations,
  fetchSegmentCount,
  fetchCampaignMetadata,
  type AudienceRecommendation,
  type StrategyRecommendation,
  type MessageRecommendation,
} from '../api';
import CustomerPreviewTable from './CustomerPreviewTable';
import ExecutionTrail, { type TrailStep } from './ExecutionTrail';

type Step = 1 | 2 | 3 | 4;

interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const formatTagName = (tag: string) => {
  return tag
    .replace(/_/g, ' ')
    .split(' ')
    .map(w => {
      const lower = w.toLowerCase();
      if (lower === 'sms') return 'SMS';
      if (lower === 'whatsapp') return 'WhatsApp';
      if (lower === 'vip') return 'VIP';
      if (lower === 'rcs') return 'RCS';
      if (lower === 'email') return 'Email';
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    })
    .join(' ');
};

export default function ChatPage({ isActive = true }: { isActive?: boolean }) {
  // ── Step State ──
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // ── Form State ──
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [minSpent, setMinSpent] = useState<string>('');
  const [maxSpent, setMaxSpent] = useState<string>('');
  const [minOrders, setMinOrders] = useState<string>('');
  const [maxOrders, setMaxOrders] = useState<string>('');
  const [selectedGoal, setSelectedGoal] = useState<string>('');
  const [selectedChannel, setSelectedChannel] = useState<string>('whatsapp');
  const [messageTemplate, setMessageTemplate] = useState<string>('');

  // ── Database-Driven Metadata State ──
  const [availableCities, setAvailableCities] = useState<{ city: string; count: number }[]>([]);
  const [availableTags, setAvailableTags] = useState<{ tag: string; count: number }[]>([]);
  const [maxSpentLimit, setMaxSpentLimit] = useState<number>(100000);
  const [maxOrdersLimit, setMaxOrdersLimit] = useState<number>(20);

  // ── Recommendations & Count State ──
  const [audienceRecs, setAudienceRecs] = useState<AudienceRecommendation[]>([]);
  const [strategyRec, setStrategyRec] = useState<StrategyRecommendation | null>(null);
  const [messageRecs, setMessageRecs] = useState<MessageRecommendation[]>([]);
  const [audienceCount, setAudienceCount] = useState<number>(0);
  const [audienceSql, setAudienceSql] = useState<string>('');
  const [audiencePreview, setAudiencePreview] = useState<Record<string, any>[]>([]);

  // ── Loading States ──
  const [loadingAudience, setLoadingAudience] = useState(false);
  const [loadingStrategy, setLoadingStrategy] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(false);
  const [loadingCount, setLoadingCount] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [loadingExecute, setLoadingExecute] = useState(false);

  // ── Execution States ──
  const [executing, setExecuting] = useState(false);
  const [trailSteps, setTrailSteps] = useState<TrailStep[]>([]);
  const [campaignResult, setCampaignResult] = useState<any>(null);
  const [execError, setExecError] = useState<string | undefined>();

  // ── Floating Copilot State ──
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hi! I am your AI Copilot. I can answer your query, advise you, or create and run your campaign start to end for you.'
    }
  ]);
  const [copilotInput, setCopilotInput] = useState('');
  const [loadingCopilot, setLoadingCopilot] = useState(false);

  const copilotEndRef = useRef<HTMLDivElement>(null);

  // Scroll copilot messages
  useEffect(() => {
    copilotEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [copilotMessages, copilotOpen]);

  // Load initial metadata and limits
  useEffect(() => {
    const initMetadata = async () => {
      try {
        const meta = await fetchCampaignMetadata([]);
        setAvailableCities(meta.cities);
        setAvailableTags(meta.tags);
        if (meta.max_spent > 0) setMaxSpentLimit(meta.max_spent);
        if (meta.max_orders > 0) setMaxOrdersLimit(meta.max_orders);
      } catch (err) {
        console.error('Failed to fetch initial metadata', err);
      }
    };
    initMetadata();
  }, []);

  // Update tag counts dynamically when selectedCities changes
  useEffect(() => {
    const loadTagMetadata = async () => {
      try {
        const meta = await fetchCampaignMetadata(selectedCities);
        setAvailableTags(meta.tags);
      } catch (err) {
        console.error('Failed to update tag metadata', err);
      }
    };
    loadTagMetadata();
  }, [selectedCities]);

  // Step 1: Load audience recommendations
  useEffect(() => {
    const loadAudienceRecs = async () => {
      setLoadingAudience(true);
      try {
        const recs = await fetchAudienceRecommendations();
        setAudienceRecs(recs);
      } catch (err) {
        console.error('Failed to load audience suggestions', err);
      } finally {
        setLoadingAudience(false);
      }
    };
    loadAudienceRecs();
  }, []);

  // Step 2: Load strategy recommendation on transition or filters change
  useEffect(() => {
    if (currentStep !== 2) return;
    const loadStrategyRec = async () => {
      setLoadingStrategy(true);
      try {
        const filters = {
          cities: selectedCities,
          tags: selectedTags,
          min_spent: minSpent === '' ? null : Number(minSpent),
          max_spent: maxSpent === '' ? null : Number(maxSpent),
          min_orders: minOrders === '' ? null : Number(minOrders),
          max_orders: maxOrders === '' ? null : Number(maxOrders)
        };
        const rec = await fetchStrategyRecommendation(filters);
        setStrategyRec(rec);
      } catch (err) {
        console.error('Failed to load strategy recommendation', err);
      } finally {
        setLoadingStrategy(false);
      }
    };
    loadStrategyRec();
  }, [currentStep, selectedCities, selectedTags, minSpent, maxSpent, minOrders, maxOrders]);

  // Step 3: Load message recommendations
  useEffect(() => {
    if (currentStep !== 3) return;
    const loadMessageRecs = async () => {
      setLoadingMessage(true);
      try {
        const desc = getAudienceDescription();
        const recs = await fetchMessageRecommendations(desc, selectedGoal || 'Promote a sale', selectedChannel);
        setMessageRecs(recs);
        // Autofill first copy variation if empty
        if (recs.length > 0) {
          setMessageTemplate(recs[0].content);
        }
      } catch (err) {
        console.error('Failed to load message copy variations', err);
      } finally {
        setLoadingMessage(false);
      }
    };
    loadMessageRecs();
  }, [currentStep, selectedGoal, selectedChannel]);

  // Debounced Segment Count loader
  useEffect(() => {
    const loadCount = async () => {
      setLoadingCount(true);
      try {
        const filters = {
          cities: selectedCities,
          tags: selectedTags,
          min_spent: minSpent === '' ? null : Number(minSpent),
          max_spent: maxSpent === '' ? null : Number(maxSpent),
          min_orders: minOrders === '' ? null : Number(minOrders),
          max_orders: maxOrders === '' ? null : Number(maxOrders)
        };
        const res = await fetchSegmentCount(filters);
        setAudienceCount(res.count);
      } catch (err) {
        console.error('Failed to load count', err);
      } finally {
        setLoadingCount(false);
      }
    };

    const timer = setTimeout(loadCount, 300);
    return () => clearTimeout(timer);
  }, [selectedCities, selectedTags, minSpent, maxSpent, minOrders, maxOrders]);

  // ── Audience description helper ──
  const getAudienceDescription = () => {
    let parts: string[] = [];
    if (selectedTags.length > 0) {
      parts.push(selectedTags.map(t => formatTagName(t)).join(', '));
    } else {
      parts.push('Customers');
    }
    if (selectedCities.length > 0) {
      parts.push(`in ${selectedCities.join(', ')}`);
    }
    if (minSpent || maxSpent) {
      if (minSpent && maxSpent) {
        parts.push(`who spent between ₹${Number(minSpent).toLocaleString()} and ₹${Number(maxSpent).toLocaleString()}`);
      } else if (minSpent) {
        parts.push(`who spent at least ₹${Number(minSpent).toLocaleString()}`);
      } else if (maxSpent) {
        parts.push(`who spent at most ₹${Number(maxSpent).toLocaleString()}`);
      }
    }
    if (minOrders || maxOrders) {
      if (minOrders && maxOrders) {
        parts.push(`with between ${minOrders} and ${maxOrders} orders`);
      } else if (minOrders) {
        parts.push(`with at least ${minOrders} orders`);
      } else if (maxOrders) {
        parts.push(`with at most ${maxOrders} orders`);
      }
    }
    return parts.join(' ');
  };

  // Toggle items in arrays
  const toggleCity = (city: string) => {
    setSelectedCities(prev =>
      prev.includes(city) ? prev.filter(c => c !== city) : [...prev, city]
    );
  };

  const toggleTag = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const applyAudienceSuggestion = (rec: AudienceRecommendation) => {
    setSelectedCities(rec.filters.cities || []);
    setSelectedTags(rec.filters.tags || []);
    setMinSpent(rec.filters.min_spent !== null && rec.filters.min_spent !== undefined ? String(rec.filters.min_spent) : '');
    setMaxSpent(rec.filters.max_spent !== null && rec.filters.max_spent !== undefined ? String(rec.filters.max_spent) : '');
    setMinOrders(rec.filters.min_orders !== null && rec.filters.min_orders !== undefined ? String(rec.filters.min_orders) : '');
    setMaxOrders(rec.filters.max_orders !== null && rec.filters.max_orders !== undefined ? String(rec.filters.max_orders) : '');
  };

  // Safeguards for sliders
  const handleMinSpentChange = (val: string) => {
    if (val === '0') {
      setMinSpent('');
      return;
    }
    setMinSpent(val);
    if (maxSpent && Number(val) > Number(maxSpent)) {
      setMaxSpent(val);
    }
  };

  const handleMaxSpentChange = (val: string) => {
    if (val === '0' || Number(val) >= maxSpentLimit) {
      setMaxSpent('');
      return;
    }
    setMaxSpent(val);
    if (minSpent && Number(val) < Number(minSpent)) {
      setMinSpent(val);
    }
  };

  const handleMinOrdersChange = (val: string) => {
    if (val === '0') {
      setMinOrders('');
      return;
    }
    setMinOrders(val);
    if (maxOrders && Number(val) > Number(maxOrders)) {
      setMaxOrders(val);
    }
  };

  const handleMaxOrdersChange = (val: string) => {
    if (val === '0' || Number(val) >= maxOrdersLimit) {
      setMaxOrders('');
      return;
    }
    setMaxOrders(val);
    if (minOrders && Number(val) < Number(minOrders)) {
      setMinOrders(val);
    }
  };

  const applyStrategySuggestion = () => {
    if (strategyRec) {
      setSelectedGoal(strategyRec.goal);
      setSelectedChannel(strategyRec.channel);
    }
  };

  // Transitions to Step 4 (requires running planCampaign graph tool)
  const handleTransitionToReview = async () => {
    setLoadingPlan(true);
    try {
      const brief = {
        goal: selectedGoal || 'Campaign Promotion',
        audience: getAudienceDescription(),
        channel: selectedChannel,
        message_idea: messageTemplate,
        offer: ''
      };
      
      const history = copilotMessages
        .filter(m => m.id !== 'welcome')
        .map(m => ({ role: m.role, content: m.content }));

      const { conversation_id } = await planCampaign(brief, history);
      
      connectSSE(conversation_id, (event) => {
        if (event.type === 'result') {
          const state = event.data?.state || {};
          if (state.audience_sql) {
            setAudienceSql(state.audience_sql);
            setAudiencePreview(state.audience_preview || []);
            setCurrentStep(4);
          }
          setLoadingPlan(false);
        } else if (event.type === 'error') {
          setLoadingPlan(false);
        }
      });
    } catch (err) {
      console.error('Plan generation failed', err);
      setLoadingPlan(false);
    }
  };

  // Launch approved campaign
  const handleLaunchCampaign = async (overrideParams?: {
    cities?: string[];
    tags?: string[];
    minSpent?: string;
    maxSpent?: string;
    minOrders?: string;
    maxOrders?: string;
    goal?: string;
    channel?: string;
    messageTemplate?: string;
  }) => {
    setExecuting(true);
    setLoadingExecute(true);
    setCampaignResult(null);
    setExecError(undefined);
    setTrailSteps([
      { id: '1', label: 'Building Audience', message: 'Creating saved segment...', status: 'running' },
      { id: '2', label: 'Drafting Message', message: 'Generating copy...', status: 'pending' },
      { id: '3', label: 'Creating Campaign', message: 'Setting up records...', status: 'pending' },
    ]);

    const cities = overrideParams?.cities !== undefined ? overrideParams.cities : selectedCities;
    const tags = overrideParams?.tags !== undefined ? overrideParams.tags : selectedTags;
    const spentMin = overrideParams?.minSpent !== undefined ? overrideParams.minSpent : minSpent;
    const spentMax = overrideParams?.maxSpent !== undefined ? overrideParams.maxSpent : maxSpent;
    const ordersMin = overrideParams?.minOrders !== undefined ? overrideParams.minOrders : minOrders;
    const ordersMax = overrideParams?.maxOrders !== undefined ? overrideParams.maxOrders : maxOrders;
    const goal = overrideParams?.goal !== undefined ? overrideParams.goal : selectedGoal;
    const channel = overrideParams?.channel !== undefined ? overrideParams.channel : selectedChannel;
    const msgTemplate = overrideParams?.messageTemplate !== undefined ? overrideParams.messageTemplate : messageTemplate;

    const getDesc = () => {
      let parts: string[] = [];
      if (tags.length > 0) {
        parts.push(tags.map(t => formatTagName(t)).join(', '));
      } else {
        parts.push('Customers');
      }
      if (cities.length > 0) {
        parts.push(`in ${cities.join(', ')}`);
      }
      if (spentMin || spentMax) {
        if (spentMin && spentMax) {
          parts.push(`who spent between ₹${Number(spentMin).toLocaleString()} and ₹${Number(spentMax).toLocaleString()}`);
        } else if (spentMin) {
          parts.push(`who spent at least ₹${Number(spentMin).toLocaleString()}`);
        } else if (spentMax) {
          parts.push(`who spent at most ₹${Number(spentMax).toLocaleString()}`);
        }
      }
      if (ordersMin || ordersMax) {
        if (ordersMin && ordersMax) {
          parts.push(`with between ${ordersMin} and ${ordersMax} orders`);
        } else if (ordersMin) {
          parts.push(`with at least ${ordersMin} orders`);
        } else if (ordersMax) {
          parts.push(`with at most ${ordersMax} orders`);
        }
      }
      return parts.join(' ');
    };

    const audienceDescription = getDesc();

    try {
      const brief = {
        goal: goal,
        audience: audienceDescription,
        channel: channel,
        message_idea: msgTemplate
      };

      const { conversation_id } = await executeCampaign(
        brief,
        audienceDescription,
        channel,
        msgTemplate,
        '',
        msgTemplate
      );

      connectSSE(conversation_id, (event) => {
        if (event.type === 'step_start' || event.type === 'step_complete') {
          const stepMsg = event.data?.message || event.data?.step || '';
          const stepLabel = event.data?.step || '';
          const isComplete = event.type === 'step_complete';

          setTrailSteps(prev => {
            const updated = [...prev];
            const lowerLabel = stepLabel.toLowerCase();

            if (lowerLabel.includes('sql') || lowerLabel.includes('found') || lowerLabel.includes('segment') || lowerLabel.includes('audience')) {
              if (isComplete) {
                updated[0] = { ...updated[0], status: 'done', message: 'Audience segment created.' };
                updated[1] = { ...updated[1], status: 'running', message: 'Generating copy...' };
              } else {
                updated[0] = { ...updated[0], status: 'running', message: stepMsg };
              }
            } else if (lowerLabel.includes('draft') || lowerLabel.includes('message')) {
              if (isComplete) {
                updated[0] = { ...updated[0], status: 'done' };
                updated[1] = { ...updated[1], status: 'done', message: 'Message drafted.' };
                updated[2] = { ...updated[2], status: 'running', message: 'Setting up records...' };
              } else {
                updated[0] = { ...updated[0], status: 'done' };
                updated[1] = { ...updated[1], status: 'running', message: stepMsg };
              }
            } else if (lowerLabel.includes('creat') || lowerLabel.includes('campaign') || lowerLabel.includes('launch') || lowerLabel.includes('execute')) {
              if (isComplete) {
                updated[0] = { ...updated[0], status: 'done' };
                updated[1] = { ...updated[1], status: 'done' };
                updated[2] = { ...updated[2], status: 'done', message: 'Campaign launched successfully.' };
              } else {
                updated[0] = { ...updated[0], status: 'done' };
                updated[1] = { ...updated[1], status: 'done' };
                updated[2] = { ...updated[2], status: 'running', message: stepMsg };
              }
            }
            return updated;
          });
        } else if (event.type === 'result') {
          const state = event.data?.state || {};
          setTrailSteps(prev => prev.map(s => ({ ...s, status: 'done' as const })));
          if (state.campaign_id) {
            setCampaignResult({
              campaign_id: state.campaign_id,
              campaign_name: state.campaign_name || 'Campaign',
              total_audience: state.total_audience || 0,
              communications_created: state.communications_created || 0,
            });
          }
          setLoadingExecute(false);
        } else if (event.type === 'error') {
          setExecError(event.data?.message || 'Execution failed');
          setTrailSteps(prev => prev.map(s => s.status === 'running' || s.status === 'pending' ? { ...s, status: 'error' as const } : s));
          setLoadingExecute(false);
        }
      });
    } catch {
      setExecError('Failed to connect to execution engine');
      setLoadingExecute(false);
    }
  };

  // Copilot Message Send
  const handleSendCopilot = async () => {
    const text = copilotInput.trim();
    if (!text || loadingCopilot) return;

    setCopilotInput('');
    setCopilotMessages(prev => [...prev, { id: `user-${Date.now()}`, role: 'user', content: text }]);
    setLoadingCopilot(true);

    try {
      const history = copilotMessages
        .filter(m => m.id !== 'welcome')
        .map(m => ({ role: m.role, content: m.content }));
      
      const brief = {
        cities: selectedCities,
        tags: selectedTags,
        min_spent: minSpent === '' ? null : Number(minSpent),
        max_spent: maxSpent === '' ? null : Number(maxSpent),
        min_orders: minOrders === '' ? null : Number(minOrders),
        max_orders: maxOrders === '' ? null : Number(maxOrders),
        goal: selectedGoal,
        channel: selectedChannel
      };

      const { conversation_id } = await startChat(text, 'copilot', history, brief, conversationId || undefined);
      setConversationId(conversation_id);

      connectSSE(conversation_id, (event) => {
        if (event.type === 'result') {
          const state = event.data?.state || {};
          const reply = state.ai_response || 'Updated.';
          setCopilotMessages(prev => [...prev, { id: `copilot-${Date.now()}`, role: 'assistant', content: reply }]);

          // Sync field updates back to react state
          const updates = state.field_updates || {};
          if (updates.cities) setSelectedCities(updates.cities);
          if (updates.tags) setSelectedTags(updates.tags);
          if (updates.min_spent !== undefined) setMinSpent(updates.min_spent !== null ? String(updates.min_spent) : '');
          if (updates.max_spent !== undefined) setMaxSpent(updates.max_spent !== null ? String(updates.max_spent) : '');
          if (updates.min_orders !== undefined) setMinOrders(updates.min_orders !== null ? String(updates.min_orders) : '');
          if (updates.max_orders !== undefined) setMaxOrders(updates.max_orders !== null ? String(updates.max_orders) : '');
          if (updates.goal) setSelectedGoal(updates.goal);
          if (updates.channel) setSelectedChannel(updates.channel);

          if (state.trigger_launch) {
            handleLaunchCampaign({
              cities: updates.cities,
              tags: updates.tags,
              minSpent: updates.min_spent !== undefined ? (updates.min_spent !== null ? String(updates.min_spent) : '') : undefined,
              maxSpent: updates.max_spent !== undefined ? (updates.max_spent !== null ? String(updates.max_spent) : '') : undefined,
              minOrders: updates.min_orders !== undefined ? (updates.min_orders !== null ? String(updates.min_orders) : '') : undefined,
              maxOrders: updates.max_orders !== undefined ? (updates.max_orders !== null ? String(updates.max_orders) : '') : undefined,
              goal: updates.goal,
              channel: updates.channel,
              messageTemplate: updates.message_template || messageTemplate
            });
          }

          setLoadingCopilot(false);
        } else if (event.type === 'error') {
          const errMsg = event.data?.message || 'Error communicating with copilot.';
          setCopilotMessages(prev => [...prev, { id: `copilot-${Date.now()}`, role: 'assistant', content: `Error: ${errMsg}` }]);
          setLoadingCopilot(false);
        }
      });
    } catch (err) {
      console.error(err);
      setLoadingCopilot(false);
    }
  };

  const handleReset = () => {
    setCurrentStep(1);
    setSelectedCities([]);
    setSelectedTags([]);
    setMinSpent('');
    setMaxSpent('');
    setMinOrders('');
    setMaxOrders('');
    setSelectedGoal('');
    setSelectedChannel('whatsapp');
    setMessageTemplate('');
    setExecuting(false);
    setCampaignResult(null);
    setExecError(undefined);
  };

  const [portalNode, setPortalNode] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const el = document.getElementById('header-copilot-portal');
    setPortalNode(el);
  }, [isActive]);
  const copilotPortalContent = portalNode ? createPortal(
    <div
      className="header-copilot-container"
      style={{
        width: '100%',
        maxWidth: '420px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        position: 'relative',
        pointerEvents: 'auto'
      }}
    >
      {/* Floating Chat Input Bar */}
      <div
        className="header-copilot-bar"
        onClick={() => !copilotOpen && setCopilotOpen(true)}
        style={{
          background: 'rgba(255, 255, 255, 0.35)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid var(--glass-border)',
          borderRadius: '99px',
          padding: '4px 6px 4px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: 'var(--glass-shadow-sm)',
          cursor: copilotOpen ? 'default' : 'pointer',
          width: '100%',
          transition: 'all 0.3s ease'
        }}
      >
        <Bot size={18} style={{ color: 'var(--orange-500)', flexShrink: 0 }} />
        <input
          type="text"
          value={copilotInput}
          onChange={e => setCopilotInput(e.target.value)}
          onFocus={() => setCopilotOpen(true)}
          onKeyDown={e => {
            if (e.key === 'Enter') handleSendCopilot();
          }}
          placeholder="Ask Copilot / brainstorm..."
          disabled={loadingCopilot}
          style={{
            flexGrow: 1,
            background: 'none',
            border: 'none',
            color: 'var(--text-primary)',
            padding: '6px 0',
            fontSize: '0.88rem',
            outline: 'none',
            minWidth: '0'
          }}
        />
        <button
          className="copilot-send-btn"
          disabled={!copilotInput.trim() || loadingCopilot}
          onClick={handleSendCopilot}
          style={{
            background: 'var(--orange-500)',
            color: '#fff',
            border: 'none',
            width: '30px',
            height: '30px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            flexShrink: 0
          }}
        >
          <Send size={13} />
        </button>
      </div>

      {/* Floating Popover History Window */}
      {copilotOpen && (
        <div
          className="header-copilot-popover"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: '0',
            width: '420px',
            height: '380px',
            borderRadius: '16px',
            background: 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid var(--glass-border)',
            boxShadow: '0 12px 40px rgba(26, 16, 8, 0.15)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'slideUp 0.3s ease',
            zIndex: 1100
          }}
        >
          {/* Popover Header */}
          <div
            className="copilot-header"
            style={{
              padding: '0.75rem 1rem',
              background: 'rgba(249, 115, 22, 0.08)',
              borderBottom: '1px solid var(--glass-border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <span className="copilot-header-title" style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
              <Bot size={16} style={{ color: 'var(--orange-500)' }} /> Campaign Copilot
            </span>
            <button
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              onClick={() => setCopilotOpen(false)}
            >
              <X size={14} />
            </button>
          </div>

          {/* Popover Messages */}
          <div
            className="copilot-messages"
            style={{
              flexGrow: 1,
              padding: '0.75rem',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.6rem'
            }}
          >
            {copilotMessages.map(msg => (
              <div
                key={msg.id}
                className={`copilot-msg copilot-msg-${msg.role}`}
                style={{
                  maxWidth: '85%',
                  padding: '0.6rem 0.8rem',
                  borderRadius: '12px',
                  fontSize: '0.82rem',
                  lineHeight: '1.4',
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  background: msg.role === 'user' ? 'var(--orange-500)' : 'rgba(255, 255, 255, 0.5)',
                  color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                  border: msg.role === 'user' ? 'none' : '1px solid var(--glass-border-subtle)',
                  borderBottomRightRadius: msg.role === 'user' ? '2px' : '12px',
                  borderBottomLeftRadius: msg.role === 'user' ? '12px' : '2px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                }}
              >
                {msg.content}
              </div>
            ))}
            {loadingCopilot && (
              <div
                className="copilot-msg copilot-msg-assistant"
                style={{
                  alignSelf: 'flex-start',
                  background: 'rgba(255, 255, 255, 0.4)',
                  color: 'var(--text-muted)',
                  padding: '0.6rem 0.8rem',
                  borderRadius: '12px',
                  borderBottomLeftRadius: '2px',
                  border: '1px solid var(--glass-border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.82rem'
                }}
              >
                <div className="thinking-dots"><span /><span /><span /></div> Thinking...
              </div>
            )}
            <div ref={copilotEndRef} />
          </div>
        </div>
      )}
    </div>,
    portalNode
  ) : null;

  return (
    <div className="campaign-studio" style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Dynamic CSS Inject */}
      <style>{`
        .wizard-graph-flow {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 1rem;
          background: rgba(255, 255, 255, 0.45);
          backdrop-filter: blur(14px);
          border: 1px solid rgba(255, 255, 255, 0.28);
          border-radius: 12px;
          padding: 0.6rem 1.5rem;
        }
        .wizard-node {
          display: flex;
          flex-direction: column;
          align-items: center;
          position: relative;
          z-index: 2;
          cursor: pointer;
          transition: all 0.3s ease;
        }
        .wizard-node-circle {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.3);
          border: 2px solid rgba(255, 255, 255, 0.28);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 0.8rem;
          color: var(--text-secondary);
          transition: all 0.3s ease;
        }
        .wizard-node.active .wizard-node-circle {
          border-color: var(--orange-500);
          color: #fff;
          box-shadow: 0 0 15px rgba(249, 115, 22, 0.4);
          background: radial-gradient(circle, var(--orange-400) 0%, var(--orange-600) 100%);
          transform: scale(1.1);
        }
        .wizard-node.completed .wizard-node-circle {
          border-color: #10b981;
          color: #fff;
          background: #10b981;
        }
        .wizard-node-label {
          margin-top: 0.35rem;
          font-size: 0.78rem;
          font-weight: 500;
          color: var(--text-muted);
        }
        .wizard-node.active .wizard-node-label {
          color: var(--text-primary);
          font-weight: 600;
        }
        .wizard-node.completed .wizard-node-label {
          color: #10b981;
        }
        .wizard-line {
          flex-grow: 1;
          height: 3px;
          background: rgba(255, 255, 255, 0.28);
          margin: 0 1rem;
          position: relative;
          top: -11px;
          z-index: 1;
        }
        .wizard-line.completed {
          background: #10b981;
        }
        .wizard-canvas {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 1.5rem;
          flex: 1;
          min-height: 0;
        }
        .wizard-left-panel {
          background: rgba(255, 255, 255, 0.3);
          border: 1px solid rgba(255, 255, 255, 0.28);
          border-radius: 16px;
          padding: 1.5rem;
          backdrop-filter: blur(14px);
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          box-shadow: var(--glass-shadow);
          max-height: 100%;
          overflow-y: auto;
        }
        .wizard-left-panel::-webkit-scrollbar {
          width: 6px;
        }
        .wizard-left-panel::-webkit-scrollbar-track {
          background: transparent;
        }
        .wizard-left-panel::-webkit-scrollbar-thumb {
          background: rgba(249, 115, 22, 0.2);
          border-radius: 4px;
        }
        .wizard-left-panel::-webkit-scrollbar-thumb:hover {
          background: rgba(249, 115, 22, 0.4);
        }
        .wizard-right-panel {
          background: rgba(255, 255, 255, 0.2);
          border: 1px solid rgba(249, 115, 22, 0.2);
          border-radius: 16px;
          padding: 1.5rem;
          backdrop-filter: blur(14px);
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
          box-shadow: inset 0 0 20px rgba(249, 115, 22, 0.03);
          max-height: 100%;
          overflow-y: auto;
        }
        .wizard-right-panel::-webkit-scrollbar {
          width: 6px;
        }
        .wizard-right-panel::-webkit-scrollbar-track {
          background: transparent;
        }
        .wizard-right-panel::-webkit-scrollbar-thumb {
          background: rgba(249, 115, 22, 0.2);
          border-radius: 4px;
        }
        .wizard-right-panel::-webkit-scrollbar-thumb:hover {
          background: rgba(249, 115, 22, 0.4);
        }
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--glass-border-subtle);
          padding-bottom: 0.75rem;
          margin-bottom: 1.2rem;
        }
        .panel-header .panel-title {
          border-bottom: none;
          padding-bottom: 0;
        }
        .panel-header .matching-badge-container {
          margin: 0;
          padding: 0.35rem 0.75rem;
          border-radius: 8px;
        }
        .panel-header .matching-text {
          font-size: 0.8rem;
          font-weight: 500;
        }
        .panel-title {
          font-size: 1.1rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--text-primary);
          border-bottom: 1px solid var(--glass-border-subtle);
          padding-bottom: 0.75rem;
          margin: 0;
        }
        .ai-recommendation-title {
          color: var(--orange-600);
        }
        .wizard-form-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .wizard-label {
          font-size: 0.85rem;
          font-weight: 500;
          color: var(--text-primary);
        }
        .tag-selector-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }
        .tag-checkbox-btn {
          padding: 0.45rem 0.9rem;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.25);
          border: 1px solid var(--glass-border-subtle);
          color: var(--text-primary);
          font-size: 0.85rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .tag-checkbox-btn:hover {
          background: rgba(255, 255, 255, 0.45);
        }
        .tag-checkbox-btn.selected {
          background: var(--orange-100);
          border-color: var(--orange-500);
          color: var(--orange-700);
          box-shadow: 0 0 10px rgba(249, 115, 22, 0.15);
          font-weight: 600;
        }
        .slider-container {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .slider-val-box {
          display: flex;
          justify-content: space-between;
          font-size: 0.8rem;
          color: var(--text-secondary);
        }
        .slider-val-box span.active {
          color: var(--text-primary);
          font-weight: 600;
        }
        .ai-rec-card {
          background: rgba(255, 255, 255, 0.2);
          border: 1px solid var(--glass-border-subtle);
          border-radius: 12px;
          padding: 1.1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          transition: all 0.3s ease;
        }
        .ai-rec-card:hover {
          border-color: rgba(249, 115, 22, 0.3);
          transform: translateY(-2px);
          background: rgba(255, 255, 255, 0.35);
        }
        .ai-rec-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .ai-rec-name {
          font-weight: 600;
          font-size: 0.95rem;
          color: var(--text-primary);
        }
        .ai-rec-count-badge {
          font-size: 0.75rem;
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid #10b981;
          color: #047857;
          padding: 0.15rem 0.5rem;
          border-radius: 12px;
          font-weight: 600;
        }
        .ai-rec-reason {
          font-size: 0.8rem;
          color: var(--text-secondary);
          line-height: 1.4;
          margin: 0;
        }
        .ai-rec-analytics {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.8rem;
          color: var(--text-secondary);
          background: rgba(255, 255, 255, 0.25);
          padding: 0.4rem 0.6rem;
          border-radius: 6px;
          border: 1px solid var(--glass-border-subtle);
          margin: 0.25rem 0;
        }
        .ai-rec-analytics .divider {
          color: var(--glass-border);
        }
        .ai-rec-apply-btn {
          align-self: flex-start;
          font-size: 0.8rem;
          padding: 0.35rem 0.75rem;
          border-radius: 6px;
          background: var(--orange-500);
          color: #fff;
          border: none;
          cursor: pointer;
          font-weight: 500;
          transition: all 0.2s ease;
        }
        .ai-rec-apply-btn:hover {
          background: var(--orange-600);
          box-shadow: 0 0 10px rgba(249, 115, 22, 0.4);
        }
        .matching-badge-container {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          background: rgba(16, 185, 129, 0.08);
          border: 1px solid rgba(16, 185, 129, 0.2);
          border-radius: 10px;
          padding: 0.75rem 1rem;
          margin-bottom: 1rem;
        }
        .matching-pulse-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #10b981;
          box-shadow: 0 0 8px #10b981;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0% { transform: scale(0.95); opacity: 0.5; }
          50% { transform: scale(1.05); opacity: 1; }
          100% { transform: scale(0.95); opacity: 0.5; }
        }
        .matching-text {
          font-size: 0.9rem;
          color: var(--text-primary);
        }
        .msg-var-selector {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .msg-var-card {
          background: rgba(255, 255, 255, 0.2);
          border: 1px solid var(--glass-border-subtle);
          border-radius: 12px;
          padding: 1.1rem;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .msg-var-card:hover {
          background: rgba(255, 255, 255, 0.35);
        }
        .msg-var-card.active {
          border-color: var(--orange-500);
          background: var(--orange-50);
          box-shadow: 0 0 15px rgba(249, 115, 22, 0.1);
        }
        .msg-var-header {
          display: flex;
          justify-content: space-between;
          font-size: 0.9rem;
          font-weight: 600;
        }
        .msg-var-type {
          color: var(--orange-600);
        }
        .msg-var-content {
          font-size: 0.85rem;
          color: var(--text-primary);
          white-space: pre-wrap;
          background: rgba(255, 255, 255, 0.3);
          border: 1px solid var(--glass-border-subtle);
          padding: 0.75rem;
          border-radius: 8px;
        }
        .msg-var-reason {
          font-size: 0.75rem;
          color: var(--text-secondary);
          font-style: italic;
        }
        .goal-deck {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0.75rem;
        }
        .goal-card {
          padding: 1.2rem;
          border-radius: 12px;
          border: 1px solid var(--glass-border-subtle);
          background: rgba(255, 255, 255, 0.2);
          color: var(--text-secondary);
          cursor: pointer;
          font-weight: 500;
          font-size: 0.9rem;
          text-align: center;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 80px;
        }
        .goal-card:hover {
          background: rgba(255, 255, 255, 0.35);
        }
        .goal-card.active {
          border-color: var(--orange-500);
          background: var(--orange-100);
          color: var(--orange-700);
          font-weight: 600;
          box-shadow: 0 0 15px rgba(249, 115, 22, 0.15);
        }
        .wizard-footer {
          display: flex;
          justify-content: space-between;
          margin-top: 1rem;
          border-top: 1px solid var(--glass-border-subtle);
          padding-top: 1rem;
          flex-shrink: 0;
        }
        .wizard-btn {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.6rem 1.2rem;
          border-radius: 8px;
          font-weight: 600;
          font-size: 0.9rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .wizard-btn-prev {
          background: rgba(255, 255, 255, 0.3);
          border: 1px solid var(--glass-border);
          color: var(--text-primary);
        }
        .wizard-btn-prev:hover {
          background: rgba(255, 255, 255, 0.45);
        }
        .wizard-btn-next {
          background: var(--orange-500);
          border: none;
          color: #fff;
        }
        .wizard-btn-next:hover {
          background: var(--orange-600);
          box-shadow: 0 0 15px rgba(249, 115, 22, 0.4);
        }
        .review-panel {
          grid-column: span 2;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          max-height: 100%;
          overflow-y: auto;
          padding-right: 0.5rem;
        }
        .review-panel::-webkit-scrollbar {
          width: 6px;
        }
        .review-panel::-webkit-scrollbar-track {
          background: transparent;
        }
        .review-panel::-webkit-scrollbar-thumb {
          background: rgba(249, 115, 22, 0.2);
          border-radius: 4px;
        }
        .review-panel::-webkit-scrollbar-thumb:hover {
          background: rgba(249, 115, 22, 0.4);
        }
        .review-card {
          background: rgba(255, 255, 255, 0.3);
          border: 1px solid var(--glass-border);
          border-radius: 16px;
          padding: 1.5rem;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
        }
        .review-item {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }
        .review-label {
          font-size: 0.8rem;
          color: var(--text-secondary);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .review-value {
          font-size: 1rem;
          color: var(--text-primary);
          font-weight: 500;
        }
        .review-sql-box {
          grid-column: span 2;
          background: rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          padding: 1rem;
          font-family: monospace;
          font-size: 0.85rem;
          color: var(--orange-700);
          max-height: 120px;
          overflow-y: auto;
          white-space: pre-wrap;
          border: 1px solid var(--glass-border-subtle);
        }
        .review-msg-box {
          grid-column: span 2;
          background: rgba(249, 115, 22, 0.05);
          border: 1px solid rgba(249, 115, 22, 0.1);
          border-radius: 12px;
          padding: 1.2rem;
          font-size: 0.95rem;
          color: var(--text-primary);
          white-space: pre-wrap;
          line-height: 1.5;
        }
        .thinking-dots {
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        .thinking-dots span {
          width: 6px;
          height: 6px;
          background-color: var(--orange-500);
          border-radius: 50%;
          animation: thinking-bounce 1.4s infinite ease-in-out both;
        }
        .thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
        .thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes thinking-bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1.0); }
        }
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>

      {/* Top Visual Graph Progress Flow */}
      <div className="wizard-graph-flow">
        <div className={`wizard-node ${currentStep === 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}`} onClick={() => !executing && setCurrentStep(1)}>
          <div className="wizard-node-circle">{currentStep > 1 ? <Check size={13} /> : '1'}</div>
          <span className="wizard-node-label">Segment Builder</span>
        </div>
        <div className={`wizard-line ${currentStep > 1 ? 'completed' : ''}`} />
        
        <div className={`wizard-node ${currentStep === 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}`} onClick={() => !executing && currentStep >= 2 && setCurrentStep(2)}>
          <div className="wizard-node-circle">{currentStep > 2 ? <Check size={13} /> : '2'}</div>
          <span className="wizard-node-label">Goal & Channel</span>
        </div>
        <div className={`wizard-line ${currentStep > 2 ? 'completed' : ''}`} />

        <div className={`wizard-node ${currentStep === 3 ? 'active' : ''} ${currentStep > 3 ? 'completed' : ''}`} onClick={() => !executing && currentStep >= 3 && setCurrentStep(3)}>
          <div className="wizard-node-circle">{currentStep > 3 ? <Check size={13} /> : '3'}</div>
          <span className="wizard-node-label">Copywriter</span>
        </div>
        <div className={`wizard-line ${currentStep > 3 ? 'completed' : ''}`} />

        <div className={`wizard-node ${currentStep === 4 ? 'active' : ''}`} onClick={() => !executing && currentStep >= 4 && setCurrentStep(4)}>
          <div className="wizard-node-circle">4</div>
          <span className="wizard-node-label">Launch Review</span>
        </div>
      </div>

      {/* Execution view takes over when launching */}
      {executing ? (
        <div className="execution-area" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <ExecutionTrail
            steps={trailSteps}
            campaignResult={campaignResult}
            error={execError}
            onDone={handleReset}
          />
        </div>
      ) : (
        <>
          {/* Main Wizard Canvas */}
          <div className="wizard-canvas">
            
            {/* Step 1: Segment & Audience Builder */}
            {currentStep === 1 && (
              <>
                <div className="wizard-left-panel">
                  <div className="panel-header">
                    <h3 className="panel-title"><Sparkles size={16} /> Define Segment Filters</h3>
                    {/* Dynamic customers count badge */}
                    <div className="matching-badge-container">
                      <div className="matching-pulse-dot" />
                      <span className="matching-text">
                        {loadingCount ? 'Recalculating...' : `Found ${audienceCount.toLocaleString()} matching customers`}
                      </span>
                    </div>
                  </div>
                  
                  {/* Cities Select */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Cities</label>
                    <div className="tag-selector-grid">
                      {availableCities.map(({ city, count }) => (
                        <button
                          key={city}
                          onClick={() => toggleCity(city)}
                          className={`tag-checkbox-btn ${selectedCities.includes(city) ? 'selected' : ''}`}
                        >
                          {city} ({count})
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Tags Checkbox selector */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Audience Tags</label>
                    <div className="tag-selector-grid">
                      {availableTags.map(({ tag, count }) => (
                        <button
                          key={tag}
                          onClick={() => toggleTag(tag)}
                          className={`tag-checkbox-btn ${selectedTags.includes(tag) ? 'selected' : ''}`}
                        >
                          {formatTagName(tag)} ({count})
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Spend limits */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                    {/* Min Spent slider */}
                    <div className="wizard-form-group slider-container">
                      <div className="slider-val-box">
                        <span className="wizard-label">Min Spend</span>
                        <span className={minSpent ? 'active' : ''}>
                          {minSpent ? `₹${Number(minSpent).toLocaleString()}` : '₹0'}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max={maxSpentLimit}
                        step={Math.max(1, Math.round(maxSpentLimit / 100))}
                        value={minSpent || '0'}
                        onChange={e => handleMinSpentChange(e.target.value)}
                        style={{ accentColor: 'var(--orange-500)' }}
                      />
                    </div>

                    {/* Max Spent slider */}
                    <div className="wizard-form-group slider-container">
                      <div className="slider-val-box">
                        <span className="wizard-label">Max Spend</span>
                        <span className={maxSpent ? 'active' : ''}>
                          {maxSpent ? `₹${Number(maxSpent).toLocaleString()}` : `₹${maxSpentLimit.toLocaleString()}`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max={maxSpentLimit}
                        step={Math.max(1, Math.round(maxSpentLimit / 100))}
                        value={maxSpent || String(maxSpentLimit)}
                        onChange={e => handleMaxSpentChange(e.target.value)}
                        style={{ accentColor: 'var(--orange-500)' }}
                      />
                    </div>
                  </div>

                  {/* Orders limits */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                    {/* Min Orders slider */}
                    <div className="wizard-form-group slider-container">
                      <div className="slider-val-box">
                        <span className="wizard-label">Min Orders</span>
                        <span className={minOrders ? 'active' : ''}>
                          {minOrders ? `${minOrders}` : '0'}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max={maxOrdersLimit}
                        step="1"
                        value={minOrders || '0'}
                        onChange={e => handleMinOrdersChange(e.target.value)}
                        style={{ accentColor: 'var(--orange-500)' }}
                      />
                    </div>

                    {/* Max Orders slider */}
                    <div className="wizard-form-group slider-container">
                      <div className="slider-val-box">
                        <span className="wizard-label">Max Orders</span>
                        <span className={maxOrders ? 'active' : ''}>
                          {maxOrders ? `${maxOrders}` : `${maxOrdersLimit}`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max={maxOrdersLimit}
                        step="1"
                        value={maxOrders || String(maxOrdersLimit)}
                        onChange={e => handleMaxOrdersChange(e.target.value)}
                        style={{ accentColor: 'var(--orange-500)' }}
                      />
                    </div>
                  </div>


                </div>

                <div className="wizard-right-panel">
                  <h3 className="panel-title ai-recommendation-title"><Brain size={16} /> AI Segment Recommendations</h3>
                  
                  {loadingAudience ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '2rem 0', alignItems: 'center' }}>
                      <div className="thinking-dots"><span /><span /><span /></div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Analyzing database statistics...</span>
                    </div>
                  ) : audienceRecs.length > 0 ? (
                    audienceRecs.map((rec, i) => (
                      <div key={i} className="ai-rec-card">
                        <div className="ai-rec-header">
                          <span className="ai-rec-name">{rec.name}</span>
                          <span className="ai-rec-count-badge">~{rec.count} matches</span>
                        </div>
                        <p className="ai-rec-reason">{rec.reason}</p>
                        
                        {/* Segment Analytics */}
                        <div className="ai-rec-analytics">
                          <span>Avg Spent: <strong>₹{Math.round(rec.avg_spent || 0).toLocaleString()}</strong></span>
                          <span className="divider">|</span>
                          <span>Avg Orders: <strong>{(rec.avg_orders || 0).toFixed(1)}</strong></span>
                        </div>

                        <button
                          className="ai-rec-apply-btn"
                          onClick={() => applyAudienceSuggestion(rec)}
                        >
                          Apply AI Segment
                        </button>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
                      No segment recommendations available. Adjust data ingestion.
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Step 2: Goal & Channel */}
            {currentStep === 2 && (
              <>
                <div className="wizard-left-panel">
                  <h3 className="panel-title"><Sparkles size={16} /> Campaign Strategy</h3>

                  {/* Goal Cards Grid */}
                  <div className="wizard-form-group">
                    <label className="wizard-label" style={{ marginBottom: '0.5rem' }}>Select Campaign Goal</label>
                    <div className="goal-deck">
                      {[
                        { title: 'Re-engage lapsed customers', val: 'Re-engage lapsed customers' },
                        { title: 'Promote a sale', val: 'Promote a sale' },
                        { title: 'Welcome new signups', val: 'Welcome new signups' },
                        { title: 'VIP exclusive offer', val: 'VIP exclusive offer' }
                      ].map(goal => (
                        <div
                          key={goal.val}
                          className={`goal-card ${selectedGoal === goal.val ? 'active' : ''}`}
                          onClick={() => setSelectedGoal(goal.val)}
                        >
                          {goal.title}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Channel Dropdown */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Communication Channel</label>
                    <select
                      value={selectedChannel}
                      onChange={e => setSelectedChannel(e.target.value)}
                      className="tag-checkbox-btn"
                      style={{ width: '100%', outline: 'none', background: 'rgba(255,255,255,0.4)', border: '1px solid var(--glass-border-subtle)', color: 'var(--text-primary)', padding: '0.6rem' }}
                    >
                      <option value="whatsapp">WhatsApp</option>
                      <option value="email">Email</option>
                      <option value="sms">SMS</option>
                      <option value="rcs">RCS</option>
                    </select>
                  </div>
                </div>

                <div className="wizard-right-panel">
                  <h3 className="panel-title ai-recommendation-title"><Brain size={16} /> AI Strategy Recommendation</h3>

                  {loadingStrategy ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '2rem 0', alignItems: 'center' }}>
                      <div className="thinking-dots"><span /><span /><span /></div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Evaluating filters for channel matching...</span>
                    </div>
                  ) : strategyRec ? (
                    <div className="ai-rec-card" style={{ border: '1px solid rgba(249, 115, 22, 0.25)', background: 'rgba(255,255,255,0.25)' }}>
                      <div className="ai-rec-header" style={{ borderBottom: '1px solid var(--glass-border-subtle)', paddingBottom: '0.5rem' }}>
                        <span className="ai-rec-name" style={{ color: 'var(--orange-600)' }}>Recommended Plan</span>
                      </div>
                      <div style={{ margin: '0.5rem 0', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                        <div><strong>Goal:</strong> {strategyRec.goal}</div>
                        <div style={{ marginTop: '0.2rem' }}><strong>Channel:</strong> {strategyRec.channel.toUpperCase()}</div>
                      </div>
                      <p className="ai-rec-reason" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{strategyRec.reason}</p>
                      <button
                        className="ai-rec-apply-btn"
                        onClick={applyStrategySuggestion}
                        style={{ marginTop: '0.5rem' }}
                      >
                        Apply AI Strategy
                      </button>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
                      Set segment filters to generate strategy recommendations.
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Step 3: Message Copywriter */}
            {currentStep === 3 && (
              <>
                <div className="wizard-left-panel">
                  <h3 className="panel-title"><Sparkles size={16} /> Message Editor</h3>

                  {/* Rich template area */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Draft Message Copy</label>
                    <textarea
                      value={messageTemplate}
                      onChange={e => setMessageTemplate(e.target.value)}
                      className="chat-input"
                      rows={10}
                      style={{ background: 'rgba(255,255,255,0.25)', width: '100%', border: '1px solid var(--glass-border-subtle)', color: 'var(--text-primary)', padding: '0.8rem', outline: 'none', borderRadius: '8px', fontSize: '0.9rem', lineHeight: '1.5', fontFamily: 'inherit' }}
                      placeholder="Your campaign copy..."
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      <span>Placeholders available: <code>{"{{name}}"}</code>, <code>{"{{city}}"}</code></span>
                      <span>{messageTemplate.length} characters</span>
                    </div>
                  </div>
                </div>

                <div className="wizard-right-panel">
                  <h3 className="panel-title ai-recommendation-title"><Brain size={16} /> AI Message Copy Variants</h3>

                  {loadingMessage ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '2rem 0', alignItems: 'center' }}>
                      <div className="thinking-dots"><span /><span /><span /></div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Drafting channel-appropriate copy...</span>
                    </div>
                  ) : messageRecs.length > 0 ? (
                    <div className="msg-var-selector">
                      {messageRecs.map((rec, i) => (
                        <div
                          key={i}
                          className={`msg-var-card ${messageTemplate === rec.content ? 'active' : ''}`}
                          onClick={() => setMessageTemplate(rec.content)}
                        >
                          <div className="msg-var-header">
                            <span className="msg-var-type">{rec.type} Variation</span>
                            {messageTemplate === rec.content && <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.75rem' }}><Check size={12} /> Active</span>}
                          </div>
                          <div className="msg-var-content">{rec.content}</div>
                          <p className="msg-var-reason">Reason: {rec.reason}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
                      No copy variants generated. Complete previous stages.
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Step 4: Launch Review */}
            {currentStep === 4 && (
              <div className="review-panel">
                <h3 className="panel-title"><Sparkles size={16} /> Campaign Plan Final Review</h3>
                
                <div className="review-card">
                  <div className="review-item">
                    <span className="review-label">Audience Segment</span>
                    <span className="review-value" style={{ color: 'var(--orange-600)' }}>{getAudienceDescription()}</span>
                  </div>
                  
                  <div className="review-item">
                    <span className="review-label">Audience Count</span>
                    <span className="review-value" style={{ color: '#10b981' }}>{audienceCount.toLocaleString()} Customers</span>
                  </div>

                  <div className="review-item">
                    <span className="review-label">Goal Target</span>
                    <span className="review-value">{selectedGoal || 'General Promotion'}</span>
                  </div>

                  <div className="review-item">
                    <span className="review-label">Channel</span>
                    <span className="review-value" style={{ textTransform: 'uppercase' }}>{selectedChannel}</span>
                  </div>

                  <div className="review-sql-box">
                    <strong>Generated Database SQL:</strong><br />
                    {audienceSql}
                  </div>

                  <div className="review-msg-box">
                    <strong>Approved Copy Body:</strong><br />
                    {messageTemplate}
                  </div>
                </div>

                {/* Direct display of preview list */}
                {audiencePreview.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem', fontWeight: 600 }}>Target Audience Preview</h4>
                    <CustomerPreviewTable preview={audiencePreview} totalCount={audienceCount} />
                  </div>
                )}
              </div>
            )}

          </div>

          {/* Bottom Navigation Controls */}
          <div className="wizard-footer">
            {currentStep > 1 ? (
              <button
                className="wizard-btn wizard-btn-prev"
                onClick={() => setCurrentStep(prev => (prev - 1) as Step)}
              >
                <ChevronLeft size={16} /> Back
              </button>
            ) : (
              <div />
            )}

            {currentStep < 4 ? (
              <button
                className="wizard-btn wizard-btn-next"
                disabled={loadingPlan || (currentStep === 1 && audienceCount === 0)}
                onClick={() => {
                  if (currentStep === 3) {
                    handleTransitionToReview();
                  } else {
                    setCurrentStep(prev => (prev + 1) as Step);
                  }
                }}
              >
                {loadingPlan ? (
                  <>Evaluating segment graph...</>
                ) : (
                  <>Next <ChevronRight size={16} /></>
                )}
              </button>
            ) : (
              <button
                className="wizard-btn wizard-btn-next"
                style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 0 15px rgba(16,185,129,0.3)' }}
                disabled={loadingExecute || audienceCount === 0}
                onClick={() => handleLaunchCampaign()}
              >
                <Play size={16} /> Launch Campaign End-to-End
              </button>
            )}
          </div>
        </>
      )}

      {copilotPortalContent}
    </div>
  );
}

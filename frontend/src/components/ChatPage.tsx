import { useState, useRef, useEffect } from 'react';
import { Send, Bot, Brain, ChevronRight, ChevronLeft, Sparkles, X, MessageSquare, Check, Play } from 'lucide-react';
import {
  planCampaign,
  executeCampaign,
  connectSSE,
  startChat,
  fetchAudienceRecommendations,
  fetchStrategyRecommendation,
  fetchMessageRecommendations,
  fetchSegmentCount,
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

export default function ChatPage() {
  // ── Step State ──
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // ── Form State ──
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [minSpent, setMinSpent] = useState<string>('');
  const [minOrders, setMinOrders] = useState<string>('');
  const [selectedGoal, setSelectedGoal] = useState<string>('');
  const [selectedChannel, setSelectedChannel] = useState<string>('whatsapp');
  const [messageTemplate, setMessageTemplate] = useState<string>('');

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
      content: 'Hi! I am your AI Copilot. You can ask me questions about this campaign, or ask me to change filters (e.g., "change city to Delhi" or "set tags to VIP").'
    }
  ]);
  const [copilotInput, setCopilotInput] = useState('');
  const [loadingCopilot, setLoadingCopilot] = useState(false);

  const copilotEndRef = useRef<HTMLDivElement>(null);

  // ── Predefined list options ──
  const availableCities = ['Delhi', 'Mumbai', 'Bangalore', 'Pune'];
  const availableTags = ['vip', 'active', 'lapsed', 'new'];

  // Scroll copilot messages
  useEffect(() => {
    copilotEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [copilotMessages, copilotOpen]);

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
          min_orders: minOrders === '' ? null : Number(minOrders)
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
  }, [currentStep, selectedCities, selectedTags, minSpent, minOrders]);

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
          min_orders: minOrders === '' ? null : Number(minOrders)
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
  }, [selectedCities, selectedTags, minSpent, minOrders]);

  // ── Audience description helper ──
  const getAudienceDescription = () => {
    let parts: string[] = [];
    if (selectedTags.length > 0) {
      parts.push(selectedTags.join(', ').toUpperCase());
    } else {
      parts.push('Customers');
    }
    if (selectedCities.length > 0) {
      parts.push(`in ${selectedCities.join(', ')}`);
    }
    if (minSpent) {
      parts.push(`who spent at least ₹${Number(minSpent).toLocaleString()}`);
    }
    if (minOrders) {
      parts.push(`with at least ${minOrders} orders`);
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
    setMinSpent(rec.filters.min_spent !== null ? String(rec.filters.min_spent) : '');
    setMinOrders(rec.filters.min_orders !== null ? String(rec.filters.min_orders) : '');
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
  const handleLaunchCampaign = async () => {
    setExecuting(true);
    setLoadingExecute(true);
    setCampaignResult(null);
    setExecError(undefined);
    setTrailSteps([
      { id: '1', label: 'Building Audience', message: 'Creating saved segment...', status: 'running' },
      { id: '2', label: 'Drafting Message', message: 'Generating copy...', status: 'pending' },
      { id: '3', label: 'Creating Campaign', message: 'Setting up records...', status: 'pending' },
    ]);

    try {
      const brief = {
        goal: selectedGoal,
        audience: getAudienceDescription(),
        channel: selectedChannel,
        message_idea: messageTemplate
      };

      const { conversation_id } = await executeCampaign(
        brief,
        getAudienceDescription(),
        selectedChannel,
        messageTemplate,
        '',
        messageTemplate
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
        min_orders: minOrders === '' ? null : Number(minOrders),
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
          if (updates.min_orders !== undefined) setMinOrders(updates.min_orders !== null ? String(updates.min_orders) : '');
          if (updates.goal) setSelectedGoal(updates.goal);
          if (updates.channel) setSelectedChannel(updates.channel);

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
    setMinOrders('');
    setSelectedGoal('');
    setSelectedChannel('whatsapp');
    setMessageTemplate('');
    setExecuting(false);
    setCampaignResult(null);
    setExecError(undefined);
  };

  return (
    <div className="campaign-studio" style={{ paddingBottom: '5rem' }}>
      {/* Dynamic CSS Inject */}
      <style>{`
        .wizard-graph-flow {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 2rem;
          background: rgba(20, 20, 20, 0.6);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          padding: 1.5rem 2rem;
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
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: #1e1e24;
          border: 2px solid rgba(255, 255, 255, 0.2);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
          transition: all 0.3s ease;
        }
        .wizard-node.active .wizard-node-circle {
          border-color: #6366f1;
          color: #fff;
          box-shadow: 0 0 15px rgba(99, 102, 241, 0.5);
          background: radial-gradient(circle, #6366f1 0%, #312e81 100%);
          transform: scale(1.1);
        }
        .wizard-node.completed .wizard-node-circle {
          border-color: #10b981;
          color: #fff;
          background: #10b981;
        }
        .wizard-node-label {
          margin-top: 0.5rem;
          font-size: 0.85rem;
          font-weight: 500;
          color: rgba(255, 255, 255, 0.5);
        }
        .wizard-node.active .wizard-node-label {
          color: #fff;
        }
        .wizard-node.completed .wizard-node-label {
          color: #10b981;
        }
        .wizard-line {
          flex-grow: 1;
          height: 3px;
          background: rgba(255, 255, 255, 0.1);
          margin: 0 1rem;
          position: relative;
          top: -16px;
          z-index: 1;
        }
        .wizard-line.completed {
          background: #10b981;
        }
        .wizard-canvas {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 1.5rem;
          min-height: 480px;
        }
        .wizard-left-panel {
          background: rgba(20, 20, 25, 0.5);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 1.5rem;
          backdrop-filter: blur(16px);
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .wizard-right-panel {
          background: rgba(15, 23, 42, 0.4);
          border: 1px solid rgba(99, 102, 241, 0.15);
          border-radius: 16px;
          padding: 1.5rem;
          backdrop-filter: blur(16px);
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
          box-shadow: inset 0 0 20px rgba(99, 102, 241, 0.05);
        }
        .panel-title {
          font-size: 1.1rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #fff;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding-bottom: 0.75rem;
          margin: 0;
        }
        .ai-recommendation-title {
          color: #818cf8;
        }
        .wizard-form-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .wizard-label {
          font-size: 0.85rem;
          font-weight: 500;
          color: rgba(255, 255, 255, 0.7);
        }
        .tag-selector-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }
        .tag-checkbox-btn {
          padding: 0.45rem 0.9rem;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
          color: rgba(255, 255, 255, 0.8);
          font-size: 0.85rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .tag-checkbox-btn.selected {
          background: rgba(99, 102, 241, 0.15);
          border-color: #6366f1;
          color: #fff;
          box-shadow: 0 0 10px rgba(99, 102, 241, 0.2);
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
          color: rgba(255, 255, 255, 0.5);
        }
        .slider-val-box span.active {
          color: #fff;
          font-weight: 600;
        }
        .ai-rec-card {
          background: rgba(30, 41, 59, 0.4);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 12px;
          padding: 1.1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          transition: all 0.3s ease;
        }
        .ai-rec-card:hover {
          border-color: rgba(99, 102, 241, 0.3);
          transform: translateY(-2px);
          background: rgba(30, 41, 59, 0.6);
        }
        .ai-rec-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .ai-rec-name {
          font-weight: 600;
          font-size: 0.95rem;
          color: #fff;
        }
        .ai-rec-count-badge {
          font-size: 0.75rem;
          background: rgba(16, 185, 129, 0.15);
          border: 1px solid #10b981;
          color: #10b981;
          padding: 0.15rem 0.5rem;
          border-radius: 12px;
          font-weight: 600;
        }
        .ai-rec-reason {
          font-size: 0.8rem;
          color: rgba(255, 255, 255, 0.6);
          line-height: 1.4;
          margin: 0;
        }
        .ai-rec-apply-btn {
          align-self: flex-start;
          font-size: 0.8rem;
          padding: 0.35rem 0.75rem;
          border-radius: 6px;
          background: #6366f1;
          color: #fff;
          border: none;
          cursor: pointer;
          font-weight: 500;
          transition: all 0.2s ease;
        }
        .ai-rec-apply-btn:hover {
          background: #4f46e5;
          box-shadow: 0 0 10px rgba(99, 102, 241, 0.4);
        }
        .matching-badge-container {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          background: rgba(16, 185, 129, 0.08);
          border: 1px solid rgba(16, 185, 129, 0.2);
          border-radius: 10px;
          padding: 0.75rem 1rem;
          margin-top: auto;
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
          color: rgba(255, 255, 255, 0.8);
        }
        .floating-copilot-btn {
          position: fixed;
          bottom: 2rem;
          right: 2rem;
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
          color: #fff;
          border: none;
          box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          z-index: 1000;
          transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .floating-copilot-btn:hover {
          transform: scale(1.08) rotate(5deg);
        }
        .floating-copilot-chat {
          position: fixed;
          bottom: 6rem;
          right: 2rem;
          width: 380px;
          height: 500px;
          border-radius: 16px;
          background: rgba(15, 23, 42, 0.95);
          border: 1px solid rgba(99, 102, 241, 0.3);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          backdrop-filter: blur(20px);
          z-index: 1000;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideUp 0.3s ease;
        }
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .copilot-header {
          padding: 1rem;
          background: rgba(99, 102, 241, 0.15);
          border-bottom: 1px solid rgba(99, 102, 241, 0.2);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .copilot-header-title {
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #fff;
        }
        .copilot-messages {
          flex-grow: 1;
          padding: 1rem;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .copilot-msg {
          max-width: 85%;
          padding: 0.7rem 0.9rem;
          border-radius: 12px;
          font-size: 0.85rem;
          line-height: 1.4;
        }
        .copilot-msg-user {
          background: #6366f1;
          color: #fff;
          align-self: flex-end;
          border-bottom-right-radius: 2px;
        }
        .copilot-msg-assistant {
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.9);
          align-self: flex-start;
          border-bottom-left-radius: 2px;
        }
        .copilot-input-bar {
          padding: 0.75rem;
          background: rgba(0, 0, 0, 0.3);
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          gap: 0.5rem;
        }
        .copilot-input {
          flex-grow: 1;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #fff;
          padding: 0.5rem 0.75rem;
          font-size: 0.85rem;
          outline: none;
        }
        .copilot-input:focus {
          border-color: #6366f1;
        }
        .copilot-send-btn {
          background: #6366f1;
          color: #fff;
          border: none;
          width: 34px;
          height: 34px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .copilot-send-btn:hover {
          background: #4f46e5;
        }
        .msg-var-selector {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .msg-var-card {
          background: rgba(30, 41, 59, 0.4);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 12px;
          padding: 1.1rem;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .msg-var-card.active {
          border-color: #6366f1;
          background: rgba(99, 102, 241, 0.08);
          box-shadow: 0 0 15px rgba(99, 102, 241, 0.1);
        }
        .msg-var-header {
          display: flex;
          justify-content: space-between;
          font-size: 0.9rem;
          font-weight: 600;
        }
        .msg-var-type {
          color: #818cf8;
        }
        .msg-var-content {
          font-size: 0.8rem;
          color: rgba(255, 255, 255, 0.85);
          white-space: pre-wrap;
          background: rgba(0, 0, 0, 0.2);
          padding: 0.75rem;
          border-radius: 8px;
        }
        .msg-var-reason {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
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
          border: 1px solid rgba(255, 255, 255, 0.08);
          background: rgba(255, 255, 255, 0.02);
          color: rgba(255, 255, 255, 0.7);
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
        .goal-card.active {
          border-color: #6366f1;
          background: rgba(99, 102, 241, 0.1);
          color: #fff;
          box-shadow: 0 0 15px rgba(99, 102, 241, 0.15);
        }
        .wizard-footer {
          display: flex;
          justify-content: space-between;
          margin-top: 2rem;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          padding-top: 1.5rem;
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
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.8);
        }
        .wizard-btn-prev:hover {
          background: rgba(255, 255, 255, 0.1);
        }
        .wizard-btn-next {
          background: #6366f1;
          border: none;
          color: #fff;
        }
        .wizard-btn-next:hover {
          background: #4f46e5;
          box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
        }
        .review-panel {
          grid-column: span 2;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .review-card {
          background: rgba(20, 20, 25, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.08);
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
          color: rgba(255, 255, 255, 0.4);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .review-value {
          font-size: 1rem;
          color: #fff;
          font-weight: 500;
        }
        .review-sql-box {
          grid-column: span 2;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          padding: 1rem;
          font-family: monospace;
          font-size: 0.85rem;
          color: #38bdf8;
          max-height: 120px;
          overflow-y: auto;
          white-space: pre-wrap;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .review-msg-box {
          grid-column: span 2;
          background: rgba(99, 102, 241, 0.05);
          border: 1px solid rgba(99, 102, 241, 0.1);
          border-radius: 12px;
          padding: 1.2rem;
          font-size: 0.95rem;
          color: rgba(255, 255, 255, 0.9);
          white-space: pre-wrap;
          line-height: 1.5;
        }
      `}</style>

      {/* Top Visual Graph Progress Flow */}
      <div className="wizard-graph-flow">
        <div className={`wizard-node ${currentStep === 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}`} onClick={() => !executing && setCurrentStep(1)}>
          <div className="wizard-node-circle">{currentStep > 1 ? <Check size={16} /> : '1'}</div>
          <span className="wizard-node-label">Segment Builder</span>
        </div>
        <div className={`wizard-line ${currentStep > 1 ? 'completed' : ''}`} />
        
        <div className={`wizard-node ${currentStep === 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}`} onClick={() => !executing && currentStep >= 2 && setCurrentStep(2)}>
          <div className="wizard-node-circle">{currentStep > 2 ? <Check size={16} /> : '2'}</div>
          <span className="wizard-node-label">Goal & Channel</span>
        </div>
        <div className={`wizard-line ${currentStep > 2 ? 'completed' : ''}`} />

        <div className={`wizard-node ${currentStep === 3 ? 'active' : ''} ${currentStep > 3 ? 'completed' : ''}`} onClick={() => !executing && currentStep >= 3 && setCurrentStep(3)}>
          <div className="wizard-node-circle">{currentStep > 3 ? <Check size={16} /> : '3'}</div>
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
                  <h3 className="panel-title"><Sparkles size={16} /> Define Segment Filters</h3>
                  
                  {/* Cities Select */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Cities</label>
                    <div className="tag-selector-grid">
                      {availableCities.map(city => (
                        <button
                          key={city}
                          onClick={() => toggleCity(city)}
                          className={`tag-checkbox-btn ${selectedCities.includes(city) ? 'selected' : ''}`}
                        >
                          {city}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Tags Checkbox selector */}
                  <div className="wizard-form-group">
                    <label className="wizard-label">Audience Tags</label>
                    <div className="tag-selector-grid">
                      {availableTags.map(tag => (
                        <button
                          key={tag}
                          onClick={() => toggleTag(tag)}
                          className={`tag-checkbox-btn ${selectedTags.includes(tag) ? 'selected' : ''}`}
                        >
                          {tag.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Min Spent slider */}
                  <div className="wizard-form-group slider-container">
                    <div className="slider-val-box">
                      <span className="wizard-label">Min Total Spent</span>
                      <span className={minSpent ? 'active' : ''}>
                        {minSpent ? `₹${Number(minSpent).toLocaleString()}+` : 'Any'}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100000"
                      step="5000"
                      value={minSpent || '0'}
                      onChange={e => setMinSpent(e.target.value === '0' ? '' : e.target.value)}
                      style={{ accentColor: '#6366f1' }}
                    />
                  </div>

                  {/* Min Orders slider */}
                  <div className="wizard-form-group slider-container">
                    <div className="slider-val-box">
                      <span className="wizard-label">Min Total Orders</span>
                      <span className={minOrders ? 'active' : ''}>
                        {minOrders ? `${minOrders}+ orders` : 'Any'}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="20"
                      step="1"
                      value={minOrders || '0'}
                      onChange={e => setMinOrders(e.target.value === '0' ? '' : e.target.value)}
                      style={{ accentColor: '#6366f1' }}
                    />
                  </div>

                  {/* Dynamic customers count badge */}
                  <div className="matching-badge-container">
                    <div className="matching-pulse-dot" />
                    <span className="matching-text">
                      {loadingCount ? 'Recalculating...' : `Found ${audienceCount.toLocaleString()} matching customers in segment`}
                    </span>
                  </div>
                </div>

                <div className="wizard-right-panel">
                  <h3 className="panel-title ai-recommendation-title"><Brain size={16} /> AI Segment Recommendations</h3>
                  
                  {loadingAudience ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '2rem 0', alignItems: 'center' }}>
                      <div className="thinking-dots"><span /><span /><span /></div>
                      <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)' }}>Analyzing database statistics...</span>
                    </div>
                  ) : audienceRecs.length > 0 ? (
                    audienceRecs.map((rec, i) => (
                      <div key={i} className="ai-rec-card">
                        <div className="ai-rec-header">
                          <span className="ai-rec-name">{rec.name}</span>
                          <span className="ai-rec-count-badge">~{rec.count} matches</span>
                        </div>
                        <p className="ai-rec-reason">{rec.reason}</p>
                        <button
                          className="ai-rec-apply-btn"
                          onClick={() => applyAudienceSuggestion(rec)}
                        >
                          Apply AI Segment
                        </button>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
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
                      style={{ width: '100%', outline: 'none', background: 'rgba(15,15,20,0.8)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '0.6rem' }}
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
                      <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)' }}>Evaluating filters for channel matching...</span>
                    </div>
                  ) : strategyRec ? (
                    <div className="ai-rec-card" style={{ border: '1px solid rgba(99,102,241,0.25)', background: 'rgba(15,23,42,0.6)' }}>
                      <div className="ai-rec-header" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.5rem' }}>
                        <span className="ai-rec-name" style={{ color: '#818cf8' }}>Recommended Plan</span>
                      </div>
                      <div style={{ margin: '0.5rem 0', fontSize: '0.85rem' }}>
                        <div><strong>Goal:</strong> {strategyRec.goal}</div>
                        <div style={{ marginTop: '0.2rem' }}><strong>Channel:</strong> {strategyRec.channel.toUpperCase()}</div>
                      </div>
                      <p className="ai-rec-reason" style={{ fontSize: '0.85rem' }}>{strategyRec.reason}</p>
                      <button
                        className="ai-rec-apply-btn"
                        onClick={applyStrategySuggestion}
                        style={{ marginTop: '0.5rem' }}
                      >
                        Apply AI Strategy
                      </button>
                    </div>
                  ) : (
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
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
                      style={{ background: 'rgba(10,10,15,0.5)', width: '100%', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '0.8rem', outline: 'none', borderRadius: '8px', fontSize: '0.9rem', lineHeight: '1.5', fontFamily: 'inherit' }}
                      placeholder="Your campaign copy..."
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', marginTop: '0.25rem' }}>
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
                      <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)' }}>Drafting channel-appropriate copy...</span>
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
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
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
                    <span className="review-value" style={{ color: '#818cf8' }}>{getAudienceDescription()}</span>
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
                onClick={handleLaunchCampaign}
              >
                <Play size={16} /> Launch Campaign End-to-End
              </button>
            )}
          </div>
        </>
      )}

      {/* Floating AI Copilot Chat Toggle Button */}
      <button
        className="floating-copilot-btn"
        onClick={() => setCopilotOpen(prev => !prev)}
      >
        {copilotOpen ? <X size={22} /> : <MessageSquare size={22} />}
      </button>

      {/* Floating Drawer / Chat Box */}
      {copilotOpen && (
        <div className="floating-copilot-chat">
          <div className="copilot-header">
            <span className="copilot-header-title"><Bot size={18} style={{ color: '#818cf8' }} /> Campaign Copilot</span>
            <button style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer' }} onClick={() => setCopilotOpen(false)}><X size={16} /></button>
          </div>
          
          <div className="copilot-messages">
            {copilotMessages.map(msg => (
              <div key={msg.id} className={`copilot-msg copilot-msg-${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {loadingCopilot && (
              <div className="copilot-msg copilot-msg-assistant" style={{ opacity: 0.7 }}>
                Thinking...
              </div>
            )}
            <div ref={copilotEndRef} />
          </div>

          <div className="copilot-input-bar">
            <input
              type="text"
              value={copilotInput}
              onChange={e => setCopilotInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') handleSendCopilot();
              }}
              placeholder="Ask me to change fields or ask a doubt..."
              disabled={loadingCopilot}
              className="copilot-input"
            />
            <button
              className="copilot-send-btn"
              disabled={!copilotInput.trim() || loadingCopilot}
              onClick={handleSendCopilot}
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User } from 'lucide-react';
import {
  startChat,
  planCampaign,
  executeCampaign,
  connectSSE,
  type CampaignBrief,
  type Suggestion,
} from '../api';
import CampaignBriefCard from './CampaignBriefCard';
import SuggestionChips from './SuggestionChips';
import CampaignPlanCard from './CampaignPlanCard';
import ExecutionTrail, { type TrailStep } from './ExecutionTrail';
import CustomerPreviewTable from './CustomerPreviewTable';

type Phase = 'brainstorm' | 'planning' | 'plan_review' | 'executing' | 'done';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  suggestions?: Suggestion[];
  customerPreview?: Record<string, any>[];
  customerCount?: number;
}

function formatMessageContent(content: string) {
  if (!content) return '';
  const parts = content.split('**');
  return parts.map((part, index) => {
    if (index % 2 === 1) {
      return <strong key={index}>{part}</strong>;
    }
    return part;
  });
}

export default function ChatPage() {
  // ── Phase state ──
  const [phase, setPhase] = useState<Phase>('brainstorm');

  // ── Brainstorm state ──
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    content: "Hi! I'm your AI Campaign Strategist. Tell me about the campaign you want to create — who do you want to reach, what do you want to say, and how? Let's brainstorm together!",
    suggestions: [
      { label: 'Re-engage lapsed customers', value: 'I want to re-engage customers who haven\'t purchased recently', category: 'audience' },
      { label: 'Promote a sale', value: 'I want to promote a sale to my customers', category: 'message' },
      { label: 'Welcome new signups', value: 'I want to welcome new customers who just signed up', category: 'audience' },
      { label: 'VIP exclusive offer', value: 'I want to send an exclusive offer to VIP customers', category: 'offer' },
    ],
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [brief, setBrief] = useState<CampaignBrief>({});
  const [readyToPlan, setReadyToPlan] = useState(false);

  // ── Plan state ──
  const [planData, setPlanData] = useState<{
    audienceCount: number;
    audiencePreview: Record<string, any>[];
    audienceSql: string;
    messageTemplate: string;
    channel: string;
    segmentName: string;
  } | null>(null);

  // ── Execute state ──
  const [trailSteps, setTrailSteps] = useState<TrailStep[]>([]);
  const [campaignResult, setCampaignResult] = useState<any>(null);
  const [execError, setExecError] = useState<string | undefined>();

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, phase]);

  // Focus input
  useEffect(() => {
    if (phase === 'brainstorm' && !loading) {
      inputRef.current?.focus();
    }
  }, [phase, loading]);

  // Auto-adjust textarea height based on typing input
  useEffect(() => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  // ── Build history for API calls ──
  const getHistory = useCallback(() => {
    return messages
      .filter(m => m.role !== 'system' && m.id !== 'welcome')
      .map(m => ({ role: m.role, content: m.content }));
  }, [messages]);

  // ── Handle SSE events from brainstorm/query ──
  const handleChatSSE = useCallback((event: { type: string; data: any }) => {
    if (event.type === 'step_complete') {
      const { step, data } = event.data;

      if (step === 'respond_brainstorm' && data) {
        const aiResponse = data.ai_response || 'Let me help you plan a campaign!';
        const suggestions = data.suggestions || [];
        const newBrief = data.brief || {};
        const isReady = data.ready_to_plan || false;

        setBrief(newBrief);
        setReadyToPlan(isReady);

        setMessages(prev => {
          if (prev.some(m => m.content === aiResponse)) return prev;
          return [...prev, {
            id: `ai-${Date.now()}`,
            role: 'assistant',
            content: aiResponse,
            suggestions,
          }];
        });
        setLoading(false);
      } else if (step === 'respond_general' && data) {
        const aiResponse = data.ai_response || 'I\'m here to help!';
        setMessages(prev => {
          if (prev.some(m => m.content === aiResponse)) return prev;
          return [...prev, {
            id: `ai-${Date.now()}`,
            role: 'assistant',
            content: aiResponse,
          }];
        });
        setLoading(false);
      } else if (step === 'build_segment' && data) {
        // Query result
        if (data.error) {
          const errMsg = `Error: ${data.error}`;
          setMessages(prev => {
            if (prev.some(m => m.content === errMsg)) return prev;
            return [...prev, {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: errMsg,
            }];
          });
        } else {
          const count = data.audience_count || 0;
          const preview = data.audience_preview || [];
          const countMsg = `Found **${count.toLocaleString()} customers** matching your query.`;
          setMessages(prev => {
            if (prev.some(m => m.content === countMsg)) return prev;
            return [...prev, {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: countMsg,
              customerPreview: preview,
              customerCount: count,
            }];
          });
        }
        setLoading(false);
      }
    } else if (event.type === 'result') {
      const state = event.data?.state || {};

      // If this was a query/general and we haven't processed it via step_complete
      if (state.ai_response) {
        setMessages(prev => {
          if (prev.some(m => m.content === state.ai_response)) return prev;
          return [...prev, {
            id: `ai-${Date.now()}`,
            role: 'assistant',
            content: state.ai_response,
            suggestions: state.suggestions || [],
          }];
        });

        if (state.brief) setBrief(state.brief);
        if (state.ready_to_plan) setReadyToPlan(true);
      }

      // Handle query_customers result
      if (state.action === 'query_customers' && state.audience_count && !state.ai_response) {
        const queryMsg = `Found **${(state.audience_count || 0).toLocaleString()} customers** matching your query.`;
        setMessages(prev => {
          if (prev.some(m => m.content === queryMsg)) return prev;
          return [...prev, {
            id: `ai-${Date.now()}`,
            role: 'assistant',
            content: queryMsg,
            customerPreview: state.audience_preview || [],
            customerCount: state.audience_count,
          }];
        });
      }

      setLoading(false);
    } else if (event.type === 'error') {
      const errMsg = `Warning: ${event.data?.message || 'Something went wrong. Try again.'}`;
      setMessages(prev => {
        if (prev.some(m => m.content === errMsg)) return prev;
        return [...prev, {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: errMsg,
        }];
      });
      setLoading(false);
    }
  }, []);

  // ── Send a brainstorm message ──
  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    setInput('');
    setMessages(prev => [...prev, {
      id: `user-${Date.now()}`,
      role: 'user',
      content: msg,
    }]);
    setLoading(true);

    try {
      const { conversation_id } = await startChat(msg, 'brainstorm', getHistory(), brief);
      connectSSE(conversation_id, handleChatSSE);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Warning: Failed to connect to the AI agent. Is the backend running?',
      }]);
      setLoading(false);
    }
  };

  // ── Handle suggestion chip click ──
  const handleSuggestionClick = (suggestion: Suggestion) => {
    if (suggestion.category === 'action' && suggestion.value === 'plan_campaign') {
      handlePlanCampaign();
    } else {
      handleSend(suggestion.value);
    }
  };

  // ── Plan the campaign ──
  const handlePlanCampaign = async () => {
    setPhase('planning');
    setLoading(true);
    setPlanData(null);

    try {
      const { conversation_id } = await planCampaign(brief, getHistory());
      connectSSE(conversation_id, (event) => {
        if (event.type === 'result') {
          const state = event.data?.state || {};
          if (state.audience_count) {
            setPlanData({
              audienceCount: state.audience_count,
              audiencePreview: state.audience_preview || [],
              audienceSql: state.audience_sql || '',
              messageTemplate: state.message_template || '',
              channel: state.channel || brief.channel || 'whatsapp',
              segmentName: state.segment_name || 'Campaign Segment',
            });
            setPhase('plan_review');
          } else {
            setMessages(prev => [...prev, {
              id: `err-${Date.now()}`,
              role: 'assistant',
              content: 'Warning: Could not build a plan. Try refining your audience description.',
            }]);
            setPhase('brainstorm');
          }
          setLoading(false);
        } else if (event.type === 'error') {
          setMessages(prev => [...prev, {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: `Warning: ${event.data?.message || 'Planning failed. Try again.'}`,
          }]);
          setPhase('brainstorm');
          setLoading(false);
        }
      });
    } catch {
      setPhase('brainstorm');
      setLoading(false);
    }
  };

  // ── Launch the campaign ──
  const handleLaunchCampaign = async () => {
    setPhase('executing');
    setLoading(true);
    setCampaignResult(null);
    setExecError(undefined);
    setTrailSteps([
      { id: '1', label: 'Building Audience', message: 'Querying database...', status: 'running' },
      { id: '2', label: 'Drafting Message', message: 'Generating copy...', status: 'pending' },
      { id: '3', label: 'Creating Campaign', message: 'Setting up records...', status: 'pending' },
    ]);

    try {
      const { conversation_id } = await executeCampaign(
        brief,
        brief.audience || 'all customers',
        brief.channel || 'whatsapp',
        brief.message_idea || '',
        brief.offer || '',
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
                updated[2] = { ...updated[2], status: 'done', message: 'Campaign created and launched.' };
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
          setLoading(false);
        } else if (event.type === 'error') {
          setExecError(event.data?.message || 'Execution failed');
          setTrailSteps(prev => {
            const updated = [...prev];
            return updated.map(s => s.status === 'running' || s.status === 'pending' ? { ...s, status: 'error' as const } : s);
          });
          setLoading(false);
        }
      });
    } catch {
      setExecError('Failed to connect to the execution engine');
      setLoading(false);
    }
  };

  // ── Back to brainstorm ──
  const handleBackToBrainstorm = () => {
    setPhase('brainstorm');
    setPlanData(null);
  };

  // ── Start new campaign ──
  const handleNewCampaign = () => {
    setPhase('brainstorm');
    setBrief({});
    setReadyToPlan(false);
    setPlanData(null);
    setCampaignResult(null);
    setExecError(undefined);
    setTrailSteps([]);
    setMessages([{
      id: 'welcome-new',
      role: 'assistant',
      content: "Ready for another campaign! What are you thinking?",
      suggestions: [
        { label: 'Re-engage lapsed customers', value: 'I want to re-engage customers who haven\'t purchased recently', category: 'audience' },
        { label: 'Promote a sale', value: 'I want to promote a sale to my customers', category: 'message' },
        { label: 'VIP exclusive offer', value: 'I want to send an exclusive offer to VIP customers', category: 'offer' },
      ],
    }]);
  };



  // ── Render based on phase ──
  return (
    <div className="campaign-studio">
      {/* Phase indicator */}
      <div className="phase-indicator">
        <div className={`phase-step ${phase === 'brainstorm' ? 'active' : 'completed'}`}>
          <span className="phase-dot">1</span>
          <span className="phase-label">Brainstorm</span>
        </div>
        <div className="phase-connector" />
        <div className={`phase-step ${phase === 'planning' || phase === 'plan_review' ? 'active' : (phase === 'executing' || phase === 'done' ? 'completed' : '')}`}>
          <span className="phase-dot">2</span>
          <span className="phase-label">Plan</span>
        </div>
        <div className="phase-connector" />
        <div className={`phase-step ${phase === 'executing' || phase === 'done' ? 'active' : ''}`}>
          <span className="phase-dot">3</span>
          <span className="phase-label">Execute</span>
        </div>
      </div>

      {/* Main content area */}
      <div className="studio-content">
        {/* Brainstorm Phase */}
        {(phase === 'brainstorm' || phase === 'planning') && (
          <div className="brainstorm-layout">
            <div className="chat-area">
              <div className="chat-messages">
                {messages.map(msg => (
                  <div key={msg.id} className={`chat-msg chat-msg-${msg.role}`}>
                    <div className="msg-avatar">
                      {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    <div className="msg-body">
                      <div className="msg-content">{formatMessageContent(msg.content)}</div>
                      {msg.customerPreview && (
                        <CustomerPreviewTable preview={msg.customerPreview} totalCount={msg.customerCount || 0} />
                      )}
                      {msg.suggestions && msg.suggestions.length > 0 && (
                        <SuggestionChips
                          suggestions={msg.suggestions}
                          onSelect={handleSuggestionClick}
                        />
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="chat-msg chat-msg-assistant">
                    <div className="msg-avatar"><Bot size={16} /></div>
                    <div className="msg-body">
                      <div className="msg-content thinking">
                        <div className="thinking-dots"><span /><span /><span /></div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input bar */}
              <div className="chat-input-bar glass">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder={loading ? 'AI is thinking...' : 'Describe your campaign idea...'}
                  disabled={loading || phase === 'planning'}
                  className="chat-input"
                  rows={1}
                />
                <button
                  className="chat-send-btn"
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading || phase === 'planning'}
                >
                  <Send size={18} />
                </button>
              </div>
            </div>

            {/* Brief sidebar */}
            <div className="brief-sidebar">
              <CampaignBriefCard
                brief={brief}
                readyToPlan={readyToPlan}
                onPlanClick={handlePlanCampaign}
              />
            </div>
          </div>
        )}

        {/* Plan Review Phase */}
        {phase === 'plan_review' && planData && (
          <div className="plan-review-area">
            <CampaignPlanCard
              {...planData}
              onLaunch={handleLaunchCampaign}
              onBack={handleBackToBrainstorm}
              loading={loading}
            />
          </div>
        )}

        {/* Execution Phase */}
        {phase === 'executing' && (
          <div className="execution-area">
            <ExecutionTrail
              steps={trailSteps}
              campaignResult={campaignResult}
              error={execError}
              onDone={handleNewCampaign}
            />
          </div>
        )}
      </div>
    </div>
  );
}

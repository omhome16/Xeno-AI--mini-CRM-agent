import { useState, useRef, useEffect, useCallback } from 'react';
import { ArrowUp, Sparkles, Zap, Check } from 'lucide-react';
import { startChat, resumeChat, connectSSE } from '../api';
import InterruptCard from './InterruptCard';
import CustomerPreviewTable from './CustomerPreviewTable';

interface Message {
  id: string;
  type: 'user' | 'agent' | 'system' | 'interrupt' | 'step';
  content: string;
  data?: unknown;
  timestamp: Date;
}

interface ChatPageProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export default function ChatPage({ messages, setMessages }: ChatPageProps) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<'guided' | 'autopilot'>('guided');
  const [isProcessing, setIsProcessing] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);
  useEffect(() => { return () => { eventSource?.close(); }; }, [eventSource]);

  const addMessage = useCallback((msg: Omit<Message, 'id' | 'timestamp'>) => {
    setMessages(prev => [...prev, {
      ...msg,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    }]);
  }, [setMessages]);

  const handleSSEEvent = useCallback((event: { type: string; data: unknown }) => {
    const d = event.data as Record<string, unknown>;
    switch (event.type) {
      case 'step_start':
        addMessage({ type: 'step', content: (d.message as string) || (d.step as string) || 'Processing...' });
        break;
      case 'step_complete': {
        // Show node completions as subtle step indicators, not agent bubbles
        const stepName = (d.step as string) || '';
        // Map raw node names to human-readable labels
        const labels: Record<string, string> = {
          parse_intent: 'Intent parsed',
          build_segment: 'Segment built',
          review_segment: 'Segment reviewed',
          draft_message: 'Message drafted',
          review_message: 'Message reviewed',
          confirm_campaign: 'Campaign confirmed',
          execute_campaign: 'Campaign executed',
        };
        addMessage({ type: 'step', content: labels[stepName] || stepName || 'Step completed' });
        break;
      }
      case 'interrupt':
        setIsProcessing(false);
        addMessage({ type: 'interrupt', content: '', data: d });
        break;
      case 'result': {
        setIsProcessing(false);
        // Build a human-readable summary from the state
        const state = (d.state || d) as Record<string, unknown>;
        let summary = '';
        if (state.audience_count) {
          summary = `Found ${state.audience_count} customers`;
          if (state.segment_name) summary += ` in segment "${state.segment_name}"`;
          summary += '.';
        } else if (state.campaign_id) {
          summary = `Campaign created successfully. ${state.communications_created || 0} messages queued for delivery.`;
        } else {
          summary = 'Done.';
        }
        addMessage({ type: 'agent', content: summary, data: state });
        break;
      }
      case 'error':
        setIsProcessing(false);
        addMessage({ type: 'system', content: (d.message as string) || 'An error occurred' });
        break;
      case 'campaign_update':
        addMessage({ type: 'agent', content: `Campaign: ${d.sent || 0}/${d.total || 0} sent (${d.progress_pct || 0}%)`, data: d });
        break;
    }
  }, [addMessage]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isProcessing) return;
    setInput('');
    setIsProcessing(true);
    addMessage({ type: 'user', content: msg });
    try {
      const historyParam = messages
        .filter(m => m.type === 'user' || m.type === 'agent')
        .map(m => ({
          role: m.type === 'user' ? 'user' : 'assistant',
          content: m.content
        }));

      const result = await startChat(msg, mode, historyParam);
      setConversationId(result.conversation_id);
      const es = connectSSE(result.conversation_id, handleSSEEvent);
      setEventSource(prev => { prev?.close(); return es; });
    } catch (err) {
      setIsProcessing(false);
      addMessage({ type: 'system', content: `Failed to connect: ${err instanceof Error ? err.message : 'Unknown error'}` });
    }
  };

  const handleResume = async (response: Record<string, unknown>) => {
    if (!conversationId) return;
    setIsProcessing(true);
    addMessage({
      type: 'user',
      content: response.action === 'approve' ? 'Approved' :
               response.action === 'cancel' ? 'Cancelled' :
               `${response.action as string || 'Response sent'}`,
    });
    try {
      await resumeChat(conversationId, response);
      const es = connectSSE(conversationId, handleSSEEvent);
      setEventSource(prev => { prev?.close(); return es; });
    } catch (err) {
      setIsProcessing(false);
      addMessage({ type: 'system', content: `Resume failed: ${err instanceof Error ? err.message : 'Unknown error'}` });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">
              <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
                <path d="M36 4L43 28.5L68 36L43 43.5L36 68L29 43.5L4 36L29 28.5L36 4Z"
                  stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
                <path d="M36 16L40 30L54 36L40 42L36 56L32 42L18 36L32 30L36 16Z"
                  stroke="currentColor" strokeWidth="0.8" strokeLinejoin="round" fill="none" opacity="0.4" />
              </svg>
            </div>
            <h3>Start a conversation</h3>
            <p>
              Describe a campaign in plain English. The agent will build your audience, 
              draft the message, and send — with your approval at each step.
            </p>
          </div>
        )}

        {messages.map(msg => {
          if (msg.type === 'interrupt') {
            return <InterruptCard key={msg.id} data={msg.data as Record<string, unknown>} onRespond={handleResume} />;
          }
          if (msg.type === 'step') {
            const isLastStep = messages.filter(m => m.type === 'step').pop()?.id === msg.id;
            const showSpinner = isLastStep && isProcessing;
            return (
              <div key={msg.id} className="step-indicator">
                {showSpinner ? (
                  <div className="spinner" />
                ) : (
                  <div className="step-check"><Check size={10} /></div>
                )}
                {msg.content}
              </div>
            );
          }

          if (msg.type === 'agent') {
            const hasPreview = msg.data && typeof msg.data === 'object' && 'audience_preview' in (msg.data as any);
            const data = msg.data as any;
            return (
              <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', gap: 10, alignSelf: 'flex-start', maxWidth: '88%', width: '100%' }}>
                <div className="chat-bubble agent" style={{ maxWidth: '85%' }}>
                  {msg.content}
                </div>
                {hasPreview && data.audience_preview && data.audience_preview.length > 0 && (
                  <div className="interrupt-card" style={{ maxWidth: '100%', width: '100%', margin: '0 0 10px 0', animation: 'none' }}>
                    <div className="card-header">
                      <div className="card-icon segment" style={{ background: 'rgba(96, 165, 250, 0.12)', color: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32, borderRadius: 8 }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                      </div>
                      <h3 style={{ fontSize: 14, fontWeight: 700 }}>Query Results</h3>
                    </div>
                    <div className="card-body" style={{ margin: 0 }}>
                      {data.audience_sql && (
                        <div style={{
                          fontSize: 11,
                          fontFamily: "'SFMono-Regular', 'Consolas', monospace",
                          background: 'rgba(0,0,0,0.03)',
                          padding: '6px 10px',
                          borderRadius: 6,
                          marginBottom: 10,
                          color: 'var(--text-muted)',
                          wordBreak: 'break-all',
                          lineHeight: 1.4,
                        }}>
                          {data.audience_sql}
                        </div>
                      )}
                      <CustomerPreviewTable preview={data.audience_preview} totalCount={data.audience_count || 0} />
                    </div>
                  </div>
                )}
              </div>
            );
          }

          return (
            <div key={msg.id} className={`chat-bubble ${msg.type}`}>
              {msg.content}
            </div>
          );
        })}

        {isProcessing && (messages.length === 0 || messages[messages.length - 1]?.type !== 'step') && (
          <div className="chat-bubble agent" style={{ alignSelf: 'flex-start' }}>
            <div className="loading-dots"><span /><span /><span /></div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div className="mode-toggle">
            <button className={mode === 'guided' ? 'active' : ''} onClick={() => setMode('guided')}>
              <Sparkles size={12} /> Guided
            </button>
            <button className={mode === 'autopilot' ? 'active' : ''} onClick={() => setMode('autopilot')}>
              <Zap size={12} /> Autopilot
            </button>
          </div>
        </div>

        <div className="chat-input-container">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Send a 10% discount to VIP customers in Mumbai via WhatsApp..."
            disabled={isProcessing}
            rows={1}
          />
          <button className="send-btn" onClick={handleSend} disabled={!input.trim() || isProcessing}>
            <ArrowUp />
          </button>
        </div>
      </div>
    </div>
  );
}

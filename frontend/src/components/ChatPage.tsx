import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, Zap } from 'lucide-react';
import { startChat, resumeChat, connectSSE } from '../api';
import InterruptCard from './InterruptCard';

interface Message {
  id: string;
  type: 'user' | 'agent' | 'system' | 'interrupt' | 'step';
  content: string;
  data?: unknown;
  timestamp: Date;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
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

  useEffect(() => {
    return () => { eventSource?.close(); };
  }, [eventSource]);

  const addMessage = useCallback((msg: Omit<Message, 'id' | 'timestamp'>) => {
    setMessages(prev => [...prev, {
      ...msg,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    }]);
  }, []);

  const handleSSEEvent = useCallback((event: { type: string; data: unknown }) => {
    const d = event.data as Record<string, unknown>;

    switch (event.type) {
      case 'step_start':
        addMessage({ type: 'step', content: d.message as string || d.step as string || 'Processing...' });
        break;

      case 'step_complete':
        addMessage({
          type: 'agent',
          content: `✓ ${d.step as string || 'Step completed'}`,
          data: d.data,
        });
        break;

      case 'interrupt':
        setIsProcessing(false);
        addMessage({ type: 'interrupt', content: '', data: d });
        break;

      case 'result':
        setIsProcessing(false);
        addMessage({
          type: 'agent',
          content: '✅ Workflow complete!',
          data: d.state,
        });
        break;

      case 'error':
        setIsProcessing(false);
        addMessage({
          type: 'system',
          content: `⚠️ ${d.message as string || 'An error occurred'}`,
        });
        break;

      case 'campaign_update':
        addMessage({
          type: 'agent',
          content: `📊 Campaign: ${d.sent || 0}/${d.total || 0} sent (${d.progress_pct || 0}%)`,
          data: d,
        });
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
      const result = await startChat(msg, mode);
      setConversationId(result.conversation_id);

      // Connect SSE
      const es = connectSSE(result.conversation_id, handleSSEEvent);
      setEventSource(prev => { prev?.close(); return es; });
    } catch (err) {
      setIsProcessing(false);
      addMessage({
        type: 'system',
        content: `⚠️ Failed to connect: ${err instanceof Error ? err.message : 'Unknown error'}`,
      });
    }
  };

  const handleResume = async (response: Record<string, unknown>) => {
    if (!conversationId) return;

    setIsProcessing(true);
    addMessage({
      type: 'user',
      content: response.action === 'approve' ? '✅ Approved' :
               response.action === 'cancel' ? '❌ Cancelled' :
               `✏️ ${response.action as string || 'Response sent'}`,
    });

    try {
      await resumeChat(conversationId, response);
      // Reconnect SSE for the resumed workflow
      const es = connectSSE(conversationId, handleSSEEvent);
      setEventSource(prev => { prev?.close(); return es; });
    } catch (err) {
      setIsProcessing(false);
      addMessage({
        type: 'system',
        content: `⚠️ Resume failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
      });
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
      {/* Chat Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <Sparkles size={64} strokeWidth={1} />
            <h3>Start a conversation</h3>
            <p>
              Tell the AI what you want to do. Try: "Send a 10% discount to 
              customers who haven't purchased in 90 days via WhatsApp"
            </p>
          </div>
        )}

        {messages.map(msg => {
          if (msg.type === 'interrupt') {
            return (
              <InterruptCard
                key={msg.id}
                data={msg.data as Record<string, unknown>}
                onRespond={handleResume}
              />
            );
          }

          if (msg.type === 'step') {
            return (
              <div key={msg.id} className="step-indicator">
                <div className="spinner" />
                {msg.content}
              </div>
            );
          }

          return (
            <div key={msg.id} className={`chat-bubble ${msg.type}`}>
              {msg.content}
            </div>
          );
        })}

        {isProcessing && messages[messages.length - 1]?.type !== 'step' && (
          <div className="chat-bubble agent">
            <div className="loading-dots">
              <span /><span /><span />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div className="mode-toggle">
            <button
              className={mode === 'guided' ? 'active' : ''}
              onClick={() => setMode('guided')}
              title="Review each step before proceeding"
            >
              <Sparkles size={14} style={{ marginRight: 4 }} />
              Guided
            </button>
            <button
              className={mode === 'autopilot' ? 'active' : ''}
              onClick={() => setMode('autopilot')}
              title="AI handles everything, confirm before sending"
            >
              <Zap size={14} style={{ marginRight: 4 }} />
              Autopilot
            </button>
          </div>
        </div>

        <div className="chat-input-wrapper">
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
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={!input.trim() || isProcessing}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

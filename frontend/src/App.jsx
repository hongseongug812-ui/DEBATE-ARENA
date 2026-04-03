import { useState, useRef, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import InputBar from './components/InputBar';
import { RoundDivider, MessageBubble, TypingIndicator } from './components/ChatMessage';
import './styles/globals.css';
import './styles/App.css';

const API_BASE = '/api';

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDebating, setIsDebating] = useState(false);
  const [debateDone, setDebateDone] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentRound, setCurrentRound] = useState(0);
  const [currentTopic, setCurrentTopic] = useState('');
  const [messages, setMessages] = useState([]);
  const [agentStates, setAgentStates] = useState({
    optimist: 'idle',
    critic: 'idle',
    realist: 'idle',
    businessman: 'idle',
    veteran: 'idle',
    judge: 'idle',
  });
  const [streamingAgent, setStreamingAgent] = useState(null);
  const [error, setError] = useState(null);

  const chatRef = useRef(null);
  const streamingMsgRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, streamingAgent]);

  const resetAgentStates = useCallback(() => {
    setAgentStates({
      optimist: 'idle',
      critic: 'idle',
      realist: 'idle',
      businessman: 'idle',
      veteran: 'idle',
      judge: 'idle',
    });
    setStreamingAgent(null);
    setCurrentRound(0);
  }, []);

  const runSSE = useCallback(async (body, appendMessages) => {
    setIsDebating(true);
    setDebateDone(false);
    setError(null);
    resetAgentStates();

    if (!appendMessages) setMessages([]);

    try {
      const response = await fetch(`${API_BASE}/debate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error(`서버 오류: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6).trim();
            if (eventType && eventData) {
              try {
                handleSSEEvent(eventType, JSON.parse(eventData));
              } catch (e) {
                console.error('SSE parse error:', e);
              }
              eventType = '';
              eventData = '';
            }
          }
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsDebating(false);
      setDebateDone(true);
      resetAgentStates();
    }
  }, [resetAgentStates]);

  const startDebate = useCallback((topic) => {
    setCurrentTopic(topic);
    setSessionId(null);
    runSSE({ topic }, false);
  }, [runSSE]);

  const sendFeedback = useCallback((feedback) => {
    setMessages((prev) => [
      ...prev,
      { type: 'feedback', text: feedback },
    ]);
    runSSE({ topic: currentTopic, session_id: sessionId, feedback }, true);
  }, [runSSE, currentTopic, sessionId]);

  const handleSSEEvent = useCallback((event, data) => {
    switch (event) {
      case 'debate_start':
        if (data.session_id) setSessionId(data.session_id);
        break;

      case 'round_start':
        setCurrentRound(data.round);
        setMessages((prev) => [
          ...prev,
          { type: 'round', round: data.round, title: data.title },
        ]);
        break;

      case 'agent_thinking': {
        setMessages((prev) => {
          const exists = prev.some(
            (m) => m.agentId === data.agent_id && m.round === data.round
          );
          if (exists) return prev;
          return [...prev, { type: 'thinking', agentId: data.agent_id, round: data.round }];
        });
        break;
      }

      case 'agent_start': {
        setMessages((prev) => {
          const idx = prev.findIndex(
            (m) => m.agentId === data.agent_id && m.round === data.round
          );
          const next = [...prev];
          if (idx !== -1) {
            next[idx] = { type: 'message', agentId: data.agent_id, text: '', round: data.round };
          } else {
            next.push({ type: 'message', agentId: data.agent_id, text: '', round: data.round });
          }
          return next;
        });
        setStreamingAgent(data.agent_id);
        setAgentStates((prev) => {
          const next = { ...prev };
          Object.keys(next).forEach((id) => {
            next[id] = id === data.agent_id ? 'talking' : 'idle';
          });
          return next;
        });
        break;
      }

      case 'agent_chunk': {
        const { agent_id, chunk } = data;
        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].type === 'message' && updated[i].agentId === agent_id) {
              updated[i] = { ...updated[i], text: updated[i].text + chunk };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'agent_end':
        setStreamingAgent(null);
        setAgentStates((prev) => ({ ...prev, [data.agent_id]: 'idle' }));
        streamingMsgRef.current = null;
        break;

      case 'round_end':
        setAgentStates((prev) => {
          const next = { ...prev };
          Object.keys(next).forEach((id) => { next[id] = 'idle'; });
          return next;
        });
        break;

      case 'convergence_reached':
        setMessages((prev) => [
          ...prev,
          { type: 'convergence', round: data.round },
        ]);
        break;

      case 'debate_end':
        if (data.session_id) setSessionId(data.session_id);
        resetAgentStates();
        break;

      default:
        break;
    }
  }, [resetAgentStates]);

  return (
    <div className="app">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        agentStates={agentStates}
        currentRound={currentRound}
        isDebating={isDebating}
      />

      <main className="main">
        <header className="main-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button className="mobile-menu-btn" onClick={() => setSidebarOpen(true)}>☰</button>
            <span className="main-header-title">
              {isDebating ? '토론 진행 중' : debateDone ? '토론 완료' : '새 토론'}
            </span>
          </div>
          {currentTopic && (
            <span className="main-header-topic" title={currentTopic}>{currentTopic}</span>
          )}
        </header>

        <div className="chat-area" ref={chatRef}>
          {messages.length === 0 && !isDebating ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">⚔</div>
              <div className="chat-empty-title">DEBATE ARENA</div>
              <div className="chat-empty-desc">
                고민이나 질문을 입력하면<br />
                5명의 AI 에이전트가 실시간으로 토론하고<br />
                심판이 최종 결론을 내려드립니다
              </div>
            </div>
          ) : (
            messages.map((msg, i) => {
              if (msg.type === 'round') {
                return <RoundDivider key={`round-${i}`} round={msg.round} title={msg.title} />;
              }
              if (msg.type === 'thinking') {
                return <TypingIndicator key={`think-${msg.agentId}-${msg.round}`} agentId={msg.agentId} />;
              }
              if (msg.type === 'convergence') {
                return (
                  <div key={`conv-${i}`} className="message-round-divider">
                    <span className="message-round-label" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                      ✓ 핵심 쟁점에 대해 충분히 논의됨 — 심판 결론으로 이동
                    </span>
                  </div>
                );
              }
              if (msg.type === 'feedback') {
                return (
                  <div key={`fb-${i}`} className="feedback-bubble">
                    <span className="feedback-label">내 피드백</span>
                    <span className="feedback-text">{msg.text}</span>
                  </div>
                );
              }
              return (
                <MessageBubble
                  key={`msg-${i}`}
                  agentId={msg.agentId}
                  text={msg.text}
                  round={msg.round}
                  isStreaming={streamingAgent === msg.agentId && i === messages.length - 1}
                />
              );
            })
          )}

          {error && (
            <div style={{
              margin: '16px 0', padding: '12px 16px',
              background: 'var(--critic-bg)', border: '1px solid var(--critic)',
              borderRadius: 'var(--radius-md)', color: '#fca5a5', fontSize: 13,
            }}>
              ⚠ {error}
            </div>
          )}
        </div>

        <InputBar
          onSubmit={startDebate}
          onFeedback={sendFeedback}
          isDebating={isDebating}
          debateDone={debateDone}
          sessionId={sessionId}
        />
      </main>
    </div>
  );
}

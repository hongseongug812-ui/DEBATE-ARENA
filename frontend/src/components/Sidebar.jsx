import PixelCharacter from './PixelCharacter';

const AGENT_INFO = {
  ceo:    { name: '대표',        role: 'CEO — 비전과 결단',         color: '#dc2626' },
  cfo:    { name: 'CFO',         role: 'CFO — 재무와 숫자',         color: '#16a34a' },
  cto:    { name: 'CTO',         role: 'CTO — 기술 실현 가능성',    color: '#2563eb' },
  cmo:    { name: 'CMO',         role: 'CMO — 마케팅과 고객',       color: '#db2777' },
  bd:     { name: 'BD팀장',      role: 'BD — 파트너십과 투자',      color: '#7c3aed' },
  legal:  { name: '법무팀장',    role: 'Legal — 리스크와 규정',     color: '#b45309' },
  ux:     { name: 'UX디자이너',  role: 'UX — 사용자 경험',          color: '#0891b2' },
  data:   { name: '데이터분석가', role: 'Data — 숫자로 검증',       color: '#0d9488' },
  junior: { name: 'MZ신입',      role: 'Junior — Z세대 트렌드',     color: '#d97706' },
  chair:  { name: '의장',        role: 'Chair — 최종 결론',         color: '#6b7280' },
};

const STATE_LABELS = {
  idle: '대기',
  talking: '발언 중',
  reacting: '반응',
};

export default function Sidebar({
  isOpen,
  onClose,
  agentStates,
  currentRound,
  isDebating,
}) {
  return (
    <>
      {isOpen && (
        <div className="sidebar-backdrop" onClick={onClose} />
      )}
      <aside className="sidebar" data-open={isOpen}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-dot" style={{
              background: isDebating ? '#dc2626' : 'var(--accent)',
              boxShadow: isDebating
                ? '0 0 8px #dc2626'
                : '0 0 8px var(--accent)',
            }} />
            <h1>DEBATE ARENA</h1>
          </div>
          <p className="sidebar-subtitle">AI 멀티에이전트 토론 플랫폼</p>
        </div>

        {/* Agent Roster */}
        <div className="agent-roster">
          {Object.entries(AGENT_INFO).map(([id, info]) => {
            const state = agentStates[id] || 'idle';
            const isActive = state !== 'idle';

            return (
              <div
                key={id}
                className="agent-card"
                data-active={isActive}
                style={{
                  '--agent-color': info.color,
                }}
              >
                <div className="agent-card-avatar">
                  <PixelCharacter agentId={id} state={state} size={3} />
                </div>
                <div className="agent-card-info">
                  <div className="agent-card-name" style={{ color: info.color }}>
                    {info.name}
                  </div>
                  <div className="agent-card-role">{info.role}</div>
                </div>
                <div
                  className="agent-card-status"
                  data-state={state}
                  style={{ color: isActive ? info.color : undefined }}
                >
                  {STATE_LABELS[state] || state}
                </div>
              </div>
            );
          })}
        </div>

        {/* Round Indicator */}
        <div className="round-indicator">
          <div className="round-indicator-label">
            {isDebating ? `ROUND ${currentRound}` : 'READY'}
          </div>
          <div className="round-dots">
            {Array.from({ length: Math.max(currentRound + 1, 3) }, (_, i) => i + 1).map((r) => (
              <div
                key={r}
                className="round-dot"
                data-active={currentRound === r}
                data-complete={currentRound > r}
              />
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}

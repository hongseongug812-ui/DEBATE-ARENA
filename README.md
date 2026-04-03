# 🎮 Debate Arena — AI 멀티에이전트 토론 플랫폼

사용자가 고민이나 질문을 입력하면, 서로 다른 페르소나를 가진 AI 에이전트들이  
실시간으로 토론을 벌이고 심판 에이전트가 최종 결론을 도출하는 웹 서비스입니다.

## 구조

```
debate-arena/
├── backend/                 # FastAPI 백엔드
│   ├── main.py              # SSE 스트리밍 토론 엔진
│   ├── agents.py            # 에이전트 페르소나 & 프롬프트
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # React + Vite 프론트엔드
│   ├── src/
│   │   ├── components/
│   │   │   ├── PixelCharacter.jsx   # 픽셀 아트 캐릭터 (Canvas)
│   │   │   ├── Sidebar.jsx          # 사이드바 (에이전트 로스터)
│   │   │   ├── ChatMessage.jsx      # 채팅 메시지 버블
│   │   │   └── InputBar.jsx         # 입력 바
│   │   ├── styles/
│   │   │   ├── globals.css          # 디자인 시스템 변수
│   │   │   └── App.css              # 레이아웃 & 반응형
│   │   ├── App.jsx                  # 메인 앱 (SSE 핸들링)
│   │   └── main.jsx                 # 엔트리포인트
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

## 실행 방법

### 1. 백엔드

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력

python main.py
# → http://localhost:8000
```

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

Vite 프록시 설정으로 `/api/*` 요청은 자동으로 백엔드(8000)로 전달됩니다.

## 기술 스택

| 영역 | 기술 | 이유 |
|------|------|------|
| 프론트엔드 | React + Vite | 빠른 HMR, 가벼운 빌드 |
| 픽셀 애니메이션 | Canvas API | 외부 의존성 없이 도트 캐릭터 구현 |
| 백엔드 | FastAPI + Python | 비동기 SSE 처리에 최적 |
| AI | Anthropic Claude Sonnet 4 | 에이전트별 비용 최적화 |
| 실시간 통신 | SSE (Server-Sent Events) | 단방향, 간단, WebSocket 불필요 |

## 에이전트 구성

| 에이전트 | 역할 |
|----------|------|
| 🟢 낙관론자 (Optimist) | 가능성과 기회에 집중, 긍정적 논거 |
| 🔴 비판론자 (Critic) | 리스크와 문제점 분석, 반례 제시 |
| 🔵 현실주의자 (Realist) | 데이터 기반 현실적 판단 |
| 🟡 심판 (Judge) | 전체 토론 분석 후 최종 결론 |

## 토론 라운드

1. **Round 1** — 각자 독립적인 초기 의견 제시
2. **Round 2** — 상대 발언을 읽고 반박 또는 보완
3. **Round 3** — 심판이 전체 토론 분석 후 최적 결론 도출

## 배포

- 프론트엔드: `npm run build` → Vercel / Netlify
- 백엔드: Render / Railway / AWS Lambda (with Mangum)

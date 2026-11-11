# KiwiSci Dashboard UI — React + TypeScript + FastAPI

Interfaz de control y supervisión multiagente para investigación científica, conectada a un backend FastAPI.

## Stack

- **React 19** + **TypeScript** (strict mode)
- **Vite 6** (build + dev server)
- **Zustand** (state management con persistencia en localStorage)
- **TanStack React Query v5** (data fetching, caching, background refetching)
- **Tailwind CSS 3** (utility-first styling con tema cyber-dark personalizado)
- **D3.js** (física de grafos interactiva)
- **Recharts** (gráficos estadísticos)
- **Lucide React** (iconografía)

## Estructura del proyecto

```
ui/
├── src/
│   ├── types/          # Interfaces TypeScript + DTOs API
│   │   ├── swarm.ts    # Tipos dominio (AgentNode, PipelineJob, etc.)
│   │   └── api.ts      # Request/Response DTOs para FastAPI
│   ├── services/       # Capa de comunicación con backend
│   │   ├── api.ts      # Client REST con fetch wrapper + typed responses
│   │   ├── websocket.ts# WebSocket singleton con auto-reconnect
│   │   └── polling.ts  # Polling service (fallback/hybrid)
│   ├── store/          # Estado global con Zustand
│   │   ├── dashboard.ts # Store principal (pipelines, agents, logs, cost)
│   │   └── config.ts    # Config persistente
│   ├── hooks/          # Custom React hooks
│   │   ├── useApi.ts       # Hooks de React Query (queries + mutations)
│   │   ├── useWebSocket.ts # Hook para eventos en tiempo real
│   │   └── useGraphPhysics.ts # Hook para simulación D3 force-directed
│   ├── utils/          # Funciones auxiliares
│   ├── components/     # Componentes React
│   │   ├── common/         # Badge, Card, ProgressBar, Modal
│   │   ├── header/         # Logo, CostDisplay, SwarmStatus, NewResearchModal
│   │   ├── sidebar/        # PipelineList con filtros
│   │   ├── pipeline-graph/ # AgentGraph (canvas D3 animado)
│   │   ├── terminal/       # AgentTerminal (logs CoT en vivo)
│   │   ├── inspector/      # StepInspector (pasos + razonamiento)
│   │   ├── results/        # ResultsPanel (PDF preview + métricas)
│   │   └── DashboardLayout.tsx  # Integración de todas las secciones
│   ├── App.tsx           # Root app con QueryClientProvider
│   ├── main.tsx          # Entry point React
│   ├── index.css         # Tailwind + utilidades custom
│   └── vite-env.d.ts     # Env type declarations
├── public/
├── package.json
├── vite.config.ts        # Vite config con aliases + proxy /api → FastAPI
├── tsconfig.json         # TS config (monorepo-style)
├── tailwind.config.js    # Tema cyber-dark + animaciones custom
├── postcss.config.js
├── .env.example
└── README.md
```

## API Endpoints (FastAPI backend esperado)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/pipelines` | Lista todas las pipelines |
| POST | `/api/v1/pipelines` | Crea nueva investigación |
| GET | `/api/v1/pipelines/{id}` | Detalles de una pipeline |
| PATCH | `/api/v1/pipelines/{id}/status` | Pausa/reanuda pipeline |
| DELETE | `/api/v1/pipelines/{id}` | Elimina pipeline |
| GET | `/api/v1/pipelines/{id}/steps` | Pasos de una pipeline |
| POST | `/api/v1/pipelines/reexecute` | Re-ejecuta un paso |
| GET | `/api/v1/swarm/health` | Estado del swarm de agentes |
| GET | `/api/v1/swarm/agents` | Estados individuales |
| POST | `/api/v1/swarm/{agent}/restart` | Reinicia agente |
| GET | `/api/v1/costs` | Snapshot de costos |
| GET | `/api/v1/costs/history` | Historial de costos |
| GET | `/api/v1/results/{id}/paper` | Paper compilado |
| GET | `/api/v1/results/{id}/artifacts` | Artefactos generados |
| GET | `/api/v1/search/papers` | Búsqueda RAG |

### WebSocket Events

| Tipo | Payload | Descripción |
|------|---------|-------------|
| `pipeline_update` | `{ pipelineId, progress, status, activeAgents }` | Actualización de progreso |
| `step_update` | `{ pipelineId, stepNum, agent, status }` | Cambio de paso |
| `log_entry` | `{ agent, text, type, timestamp }` | Nuevo log en terminal |
| `agent_status_change` | `{ agentId, newStatus }` | Cambio de estado de agente |
| `cost_update` | `{ tokensSinceLastUpdate, costUsd }` | Actualización de costo |

## Desarrollo rápido

```bash
cd ui
npm install
cp .env.example .env.local
npm run dev    # → http://localhost:3000
```

El proxy de Vite redirige `/api/*` al backend FastAPI en `http://localhost:8000`.

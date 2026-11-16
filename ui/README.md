# KiwiSci Dashboard UI — React + TypeScript + FastAPI

Interfaz web para lanzar, supervisar y revisar investigaciones del sistema multiagente Kiwis. Habla con el backend
FastAPI (`kiwis serve`) por REST y WebSocket.

## Stack

React 19 · TypeScript (strict) · Vite 6 · React Router 6 · TanStack Query 5 · Zustand · Tailwind CSS 3 · Recharts · Lucide

## Páginas

| Ruta | Página | Para qué sirve |
|------|--------|----------------|
| `/` | Inicio | Formulario de consulta: tema, hipótesis opcional, tipo, dominio y parámetros avanzados (modelo, profundidad, presupuesto). Avisa si falta el backend o las API keys. |
| `/pipelines` | Investigaciones | Todas las ejecuciones con filtros, búsqueda, totales de tokens/coste, estado del enjambre y acciones (pausar, reanudar, eliminar). |
| `/pipelines/:id` | Monitor | Seguimiento en vivo: grafo de agentes, terminal de logs, inspector de pasos (re-ejecución), pausar/reanudar/detener. |
| `/pipelines/:id/results` | Resultados | Artículo y PDF, hipótesis/literatura/diseño/análisis, puntuaciones de la revisión por pares, artefactos (vista previa y descarga). |
| `/library` | Biblioteca | Búsqueda de artículos en arXiv; permite lanzar una investigación a partir de un resultado. |
| `/settings` | Ajustes | Estado de la conexión, proveedores LLM disponibles, modelo por agente y preferencias por defecto. |

## Arquitectura de datos

- **React Query** es la fuente de verdad de los datos del servidor (`src/hooks/useApi.ts`).
- **`useLiveSync`** (montado una vez en `AppShell`) conecta el WebSocket `/ws/events` e invalida las consultas afectadas
  según los eventos (`pipeline_update`, `step_update`, `log_entry`, `agent_status_change`, `cost_update`). El polling cada
  10 s queda solo como respaldo.
- **Zustand** (`src/store/`) guarda solo estado de interfaz: logs en vivo por pipeline, pestañas, avisos y preferencias.
- `src/services/api.ts` desenvuelve el sobre `{ success, data }` y lanza `ApiError` con `status`/`code`/`message`.

## Desarrollo

```bash
# Backend (en la raíz del repo)
pip install -e ".[api]"
kiwis serve -c kiwis_config.yaml          # → http://localhost:8000

# Frontend
cd ui
npm install
cp .env.example .env.local                # opcional: cambia VITE_API_BASE_URL / VITE_WS_URL
npm run dev                               # → http://localhost:3000
npm run build                             # typecheck + build de producción
```

Sin API keys los agentes funcionan en modo placeholder (contenido de ejemplo vacío); la página de inicio y los ajustes lo indican.
Define `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` en el entorno del servidor, o activa Ollama en `kiwis_config.yaml`.

## Notas

- Los tokens y costes son **estimaciones** (≈4 caracteres por token y precios aproximados).
- El backend guarda las investigaciones en memoria: al reiniciar `kiwis serve` desaparecen de la lista (los ficheros de cada
  una quedan en `output/jobs/<id>/`).

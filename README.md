# IG Message Variation Service 🔄

Microservicio de generación de variaciones de texto para mensajes de Instagram.  
Usa **IA** (Groq, Gemini, OpenAI) para reescribir un mensaje base en múltiples variaciones naturales que no parezcan enviadas por un bot.

## ⚡ Features

- 🤖 **Reescritura inteligente** con Llama 3.3 70B (via Groq), Gemini Flash, o GPT-4o-mini
- 📝 **Placeholders dinámicos** — `{nombre}`, `{detalle}`, `{oferta}` se preservan automáticamente
- 🎨 **Control de tono** — casual, profesional, amigable, directo, entusiasta
- 🏢 **Contexto de negocio** — personaliza las variaciones según tu tipo de negocio
- 📦 **Cache inteligente** — SQLite con transformaciones ligeras para reciclar variaciones y ahorrar tokens
- 🔑 **Autenticación API Key** — protege tus endpoints
- 🔄 **Fallback automático** — si un provider falla, usa el siguiente (Groq → Gemini → OpenAI)
- 🐳 **Docker ready** — un solo `docker compose up`
- 📄 **Swagger UI** — documentación interactiva en `/docs`

## 🏗️ Arquitectura

```
Chrome Extension ──POST /api/v1/variations──▶ FastAPI
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                                  Groq       Gemini      OpenAI
                               (primary)   (fallback)  (fallback)
                                    │
                                    ▼
                              SQLite Cache
                          (con transformaciones)
```

## 🚀 Setup Rápido

### Opción 1: Docker Compose (Recomendado para VPS)

```bash
# 1. Clonar y configurar
git clone <repo-url>
cd AgentMessageIgLeads
cp .env.example .env
# Editar .env: poner tu API_KEY y GROQ_API_KEY

# 2. Levantar
docker compose up -d

# 3. Verificar
curl http://localhost:8000/api/v1/health
```

### Opción 2: Desarrollo Local

```bash
# 1. Instalar dependencias
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configurar
cp .env.example .env
# Editar .env con tus API keys

# 3. Arrancar
uvicorn app.main:app --reload --port 8000
```

## 🔑 Providers de IA

El servicio usa una **cadena de providers con fallback automático**. Si el primary falla (rate limit, error), pasa al siguiente:

| Orden | Provider | Modelo | Costo | Cómo activar |
|-------|----------|--------|-------|--------------|
| 1️⃣ | **Groq** | Llama 3.3 70B | **Gratis** (30 req/min) | `GROQ_API_KEY=...` |
| 2️⃣ | **Google Gemini** | Gemini 2.0 Flash | **Gratis** (15 req/min) | `GEMINI_API_KEY=...` |
| 3️⃣ | **OpenAI** | GPT-4o-mini | ~$0.001/request | `OPENAI_API_KEY=...` |

> Solo necesitas configurar la API key en `.env` para activar un provider. Si la key está vacía, el provider se omite.

**Obtener API keys:**
- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey
- OpenAI: https://platform.openai.com/api-keys

## 📡 API Reference

### `POST /api/v1/variations`
Genera variaciones de un mensaje base.

**Headers:**
```
X-API-Key: tu-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
    "message": "Hola {nombre}, vi tu perfil y me llamó la atención {detalle}. Estoy trabajando en {oferta} y creo que podría interesarte.",
    "num_variations": 10,
    "tone": "profesional",
    "context": "Agencia de marketing digital especializada en ayudar a negocios a conseguir más clientes mediante Instagram y publicidad online.",
    "rules": ["Usar tuteo", "No mencionar precios"]
}
```

**Response:**
```json
{
    "status": "success",
    "variations": [
        "Hey {nombre}, estuve revisando tu contenido y {detalle} me pareció muy interesante. Estoy desarrollando {oferta}, pienso que podría serte útil.",
        "Qué tal {nombre}, noté tu perfil y me impresionó {detalle}. Me especializo en {oferta} y considero que te podría servir.",
        "..."
    ],
    "total": 10,
    "from_cache": 0,
    "from_generation": 10,
    "provider": "groq/llama-3.3-70b-versatile",
    "generation_time_seconds": 2.3,
    "message": "Generación exitosa: 0 del cache + 10 generadas por IA"
}
```

**Campos del request:**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `message` | string | requerido | Mensaje base (10-2000 chars) con placeholders |
| `num_variations` | int | 20 | Variaciones a generar (1-100) |
| `tone` | string | "profesional" | profesional, casual, amigable, directo, entusiasta |
| `context` | string | null | Contexto del negocio para variaciones más relevantes |
| `rules` | string[] | [] | Reglas adicionales para la generación |

### `GET /api/v1/health`
Health check — muestra estado de todos los providers (sin autenticación).

### `GET /api/v1/providers`
Info de la cadena de providers configurados (requiere API key).

### `DELETE /api/v1/cache`
Limpiar cache de variaciones (requiere API key).

## 🔌 Consumo desde Chrome Extension

```javascript
async function generateVariations(message, numVariations = 20) {
    const response = await fetch('http://tu-vps:8000/api/v1/variations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'tu-api-key'
        },
        body: JSON.stringify({
            message: message,
            num_variations: numVariations,
            tone: 'profesional',
            context: 'Agencia de marketing digital para negocios en Instagram',
            rules: ['Usar tuteo']
        })
    });

    const data = await response.json();
    return data.variations;
}

// Uso
const variations = await generateVariations(
    'Hola {nombre}, vi tu perfil y me llamó la atención {detalle}.'
);

// Seleccionar una al azar
const randomMessage = variations[Math.floor(Math.random() * variations.length)];

// Reemplazar placeholders con datos reales
const finalMessage = randomMessage
    .replace('{nombre}', 'María')
    .replace('{detalle}', 'tu trabajo en diseño');
```

## 📁 Estructura del Proyecto

```
AgentMessageIgLeads/
├── app/
│   ├── main.py                     # FastAPI app + CORS
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── models/
│   │   ├── enums.py                # Tone, GenerationStatus
│   │   └── schemas.py              # Request/Response models
│   ├── services/
│   │   ├── variation_service.py    # Orquestador + provider chain
│   │   ├── prompt_builder.py       # Prompts de ventas/leads
│   │   ├── cache_service.py        # SQLite cache + transformador
│   │   └── providers/
│   │       ├── base.py             # ABC provider
│   │       ├── groq_provider.py    # OpenAI-compatible (Groq, OpenAI)
│   │       └── gemini_provider.py  # Google Gemini API
│   ├── api/v1/
│   │   └── variations.py          # Endpoints
│   └── middleware/
│       └── auth.py                # API key validation
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 📜 Licencia

MIT

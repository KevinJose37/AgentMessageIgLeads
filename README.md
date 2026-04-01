# IG Message Variation Service 🔄

Microservicio de generación de variaciones de texto para mensajes de Instagram.  
Usa **Mistral 7B** (via [Ollama](https://ollama.com)) para reescribir un mensaje base en múltiples variaciones naturales que no parezcan enviadas por un bot.

## ⚡ Features

- 🤖 **Reescritura inteligente** con Mistral 7B Instruct (local, sin API externa)
- 📝 **Placeholders dinámicos** — `{nombre}`, `{detalle}`, `{oferta}` se preservan automáticamente
- 🎨 **Control de tono** — casual, profesional, amigable, directo, entusiasta
- 📦 **Cache inteligente** — SQLite con transformaciones ligeras para reciclar variaciones
- 🔑 **Autenticación API Key** — protege tus endpoints
- 🐳 **Docker ready** — un solo `docker compose up`
- 📄 **Swagger UI** — documentación interactiva en `/docs`

## 🏗️ Arquitectura

```
Chrome Extension ──POST /api/v1/variations──▶ FastAPI ──▶ Ollama (Mistral 7B)
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
# Editar .env con tu API_KEY

# 2. Levantar servicios
docker compose up -d

# 3. Descargar el modelo Mistral (solo la primera vez)
docker exec -it ollama ollama pull mistral

# 4. Verificar
curl http://localhost:8000/api/v1/health
```

### Opción 2: Desarrollo Local

```bash
# 1. Instalar Ollama
# Windows: https://ollama.com/download
# Linux: curl -fsSL https://ollama.com/install.sh | sh

# 2. Descargar Mistral
ollama pull mistral

# 3. Instalar dependencias Python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Configurar
cp .env.example .env
# Editar .env con tu API_KEY

# 5. Arrancar
uvicorn app.main:app --reload --port 8000
```

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
    "tone": "casual",
    "rules": ["Usar tuteo", "No mencionar precios"]
}
```

**Response:**
```json
{
    "status": "success",
    "variations": [
        "Hey {nombre}, estuve viendo tu perfil y {detalle} me pareció genial. Ando con {oferta} y creo que te puede servir.",
        "Qué tal {nombre}, noté tu perfil y me impresionó {detalle}. Estoy enfocado en {oferta}, y pienso que te podría gustar.",
        "..."
    ],
    "total": 10,
    "from_cache": 0,
    "from_generation": 10,
    "provider": "ollama/mistral",
    "generation_time_seconds": 45.2,
    "message": "Generación exitosa: 0 del cache + 10 generadas por IA"
}
```

**Campos del request:**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `message` | string | requerido | Mensaje base (10-2000 chars) |
| `num_variations` | int | 20 | Variaciones a generar (1-100) |
| `tone` | string | "casual" | casual, profesional, amigable, directo, entusiasta |
| `rules` | string[] | [] | Reglas adicionales |

### `GET /api/v1/health`
Health check (sin autenticación).

### `GET /api/v1/providers`
Info del provider activo (requiere API key).

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
            tone: 'casual',
            rules: ['Usar tuteo']
        })
    });

    const data = await response.json();
    return data.variations; // Array de strings
}

// Uso
const variations = await generateVariations(
    'Hola {nombre}, vi tu perfil y me llamó la atención {detalle}.'
);

// Seleccionar una al azar para enviar
const randomMessage = variations[Math.floor(Math.random() * variations.length)];

// Reemplazar placeholders
const finalMessage = randomMessage
    .replace('{nombre}', 'María')
    .replace('{detalle}', 'tu trabajo en diseño');
```

## ⚠️ Notas de Rendimiento

| Métrica | Valor estimado |
|---------|---------------|
| Modelo | Mistral 7B Q4 (CPU) |
| RAM del modelo | ~4.5 GB |
| Velocidad | ~3-8 tok/s |
| 10 variaciones | ~30-90 segundos |
| 20 variaciones | ~1-3 minutos |
| 50 variaciones | ~3-8 minutos |

> **Tip**: El cache reduce drásticamente los tiempos. La primera generación es lenta,
> pero las siguientes solicitudes con el mismo mensaje son instantáneas (con transformaciones
> ligeras para que sigan siendo únicas).

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
│   │   ├── variation_service.py    # Orquestador principal
│   │   ├── prompt_builder.py       # Construcción de prompts
│   │   ├── cache_service.py        # SQLite cache + transformador
│   │   └── providers/
│   │       ├── base.py             # ABC provider
│   │       └── ollama_provider.py  # Ollama REST client
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

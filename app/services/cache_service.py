import hashlib
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight text transformer for cached variation recycling
# ---------------------------------------------------------------------------
class TextTransformer:
    """
    Applies light, rule-based transformations to cached variations
    so they feel fresh without requiring another AI inference call.
    """

    # Spanish greeting variants (position-aware — only applied at start)
    GREETINGS = [
        "Hola", "Hey", "Qué tal", "Buenas", "Saludos",
        "Qué onda", "Buen día",
    ]

    # Curated synonym map for common IG outreach vocabulary
    SYNONYMS: dict[str, list[str]] = {
        "interesante": ["llamativo", "atractivo", "genial", "increíble"],
        "ayudar": ["apoyar", "colaborar", "servir"],
        "ayudarte": ["apoyarte", "servirte", "echarte una mano"],
        "trabajando": ["desarrollando", "enfocado en", "especializándome en"],
        "servicio": ["propuesta", "solución", "proyecto"],
        "creo": ["pienso", "considero", "siento"],
        "podría": ["puede", "lograría", "tiene el potencial de"],
        "interesarte": ["gustarte", "llamarte la atención", "ser de tu interés"],
        "perfil": ["cuenta", "página", "contenido"],
        "llamó la atención": ["pareció interesante", "me gustó", "me impresionó"],
        "vi": ["revisé", "noté", "estuve viendo", "encontré"],
        "me encantaría": ["me gustaría", "quisiera", "sería genial"],
        "genial": ["excelente", "increíble", "fantástico"],
        "bueno": ["genial", "excelente", "ideal"],
        "importante": ["clave", "fundamental", "esencial", "relevante"],
        "oportunidad": ["posibilidad", "chance", "opción"],
        "negocio": ["emprendimiento", "proyecto", "empresa"],
        "resultados": ["logros", "avances", "frutos"],
        "contacto": ["comunicación", "conversación"],
        "hablar": ["platicar", "conversar", "charlar"],
        "momento": ["rato", "instante", "minuto"],
        "información": ["info", "detalles", "datos"],
        "excelente": ["increíble", "fantástico", "espectacular"],
        "problema": ["situación", "reto", "desafío"],
        "mensaje": ["texto", "nota"],
        "gracias": ["te agradezco", "mil gracias", "muchas gracias"],
    }

    # Connectors that can be swapped
    CONNECTORS: dict[str, list[str]] = {
        " y ": [" además ", " también ", " e incluso "],
        " pero ": [" sin embargo ", " aunque "],
        " porque ": [" ya que ", " dado que ", " pues "],
        " entonces ": [" así que ", " por eso "],
    }

    @classmethod
    def transform(cls, text: str, intensity: float = 0.35) -> str:
        """
        Apply light transformations to make a cached variation feel unique.

        Args:
            text: Original cached variation.
            intensity: 0.0–1.0, probability of each transform being applied.

        Returns:
            Transformed text.
        """
        result = text

        # --- 1. Greeting swap (only if text starts with a known greeting) ---
        for greeting in cls.GREETINGS:
            if result.lower().startswith(greeting.lower()):
                replacement = random.choice(
                    [g for g in cls.GREETINGS if g.lower() != greeting.lower()]
                )
                result = replacement + result[len(greeting):]
                break

        # --- 2. Synonym replacement (2-3 random swaps) ---
        swap_count = 0
        max_swaps = random.randint(2, 3)
        shuffled_synonyms = list(cls.SYNONYMS.items())
        random.shuffle(shuffled_synonyms)

        for word, alternatives in shuffled_synonyms:
            if swap_count >= max_swaps:
                break
            if word.lower() in result.lower() and random.random() < intensity:
                replacement = random.choice(alternatives)
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result = pattern.sub(replacement, result, count=1)
                swap_count += 1

        # --- 3. Connector swap ---
        if random.random() < intensity * 0.5:
            shuffled_connectors = list(cls.CONNECTORS.items())
            random.shuffle(shuffled_connectors)
            for conn, alts in shuffled_connectors:
                if conn in result:
                    result = result.replace(conn, random.choice(alts), 1)
                    break

        # --- 4. Punctuation variation ---
        if random.random() < intensity * 0.4:
            if result.rstrip().endswith("!"):
                result = result.rstrip()[:-1] + "."
            elif result.rstrip().endswith(".") and random.random() < 0.3:
                result = result.rstrip()[:-1] + "!"

        return result


# ---------------------------------------------------------------------------
# SQLite-backed cache service
# ---------------------------------------------------------------------------
class CacheService:
    """
    Caches AI-generated variations in SQLite.
    On cache hit, variations are retrieved and lightly transformed
    to feel fresh without needing another inference call.
    """

    def __init__(self, db_path: str, ttl_hours: int = 168):
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self.transformer = TextTransformer()
        self._init_db()

    def _init_db(self):
        """Create the cache table if it doesn't exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS variation_cache (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_hash    TEXT    NOT NULL,
                    tone        TEXT    NOT NULL,
                    variation   TEXT    NOT NULL,
                    created_at  TEXT    DEFAULT (datetime('now')),
                    UNIQUE(msg_hash, tone, variation)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_lookup
                ON variation_cache(msg_hash, tone)
                """
            )
            conn.commit()

    # -- hashing --

    @staticmethod
    def _hash_message(message: str) -> str:
        normalized = re.sub(r"\s+", " ", message.strip().lower())
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    # -- read --

    def get_cached_variations(
        self, message: str, tone: str, num_requested: int
    ) -> list[str]:
        """
        Retrieve cached variations, apply light transforms, return up to
        *num_requested* items.
        """
        msg_hash = self._hash_message(message)
        cutoff = (datetime.utcnow() - timedelta(hours=self.ttl_hours)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT variation FROM variation_cache "
                "WHERE msg_hash = ? AND tone = ? AND created_at > ? "
                "ORDER BY RANDOM()",
                (msg_hash, tone, cutoff),
            ).fetchall()

        if not rows:
            return []

        cached = [r[0] for r in rows]

        # Transform each for diversity
        result: list[str] = []
        for var in cached[:num_requested]:
            transformed = self.transformer.transform(var, intensity=0.35)
            result.append(transformed)

        logger.info(
            "Cache hit: %d stored, returning %d (transformed)",
            len(cached),
            len(result),
        )
        return result

    # -- write --

    def store_variations(self, message: str, tone: str, variations: list[str]):
        """Store newly generated variations in cache."""
        msg_hash = self._hash_message(message)

        with sqlite3.connect(self.db_path) as conn:
            for var in variations:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO variation_cache "
                        "(msg_hash, tone, variation) VALUES (?, ?, ?)",
                        (msg_hash, tone, var),
                    )
                except sqlite3.IntegrityError:
                    pass
            conn.commit()

        logger.info("Cached %d new variations", len(variations))

    # -- stats & maintenance --

    def get_cache_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM variation_cache").fetchone()[0]

    def clear_cache(self) -> int:
        """Clear all cache entries. Returns number of rows deleted."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM variation_cache").fetchone()[0]
            conn.execute("DELETE FROM variation_cache")
            conn.commit()
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of rows deleted."""
        cutoff = (datetime.utcnow() - timedelta(hours=self.ttl_hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM variation_cache WHERE created_at < ?", (cutoff,)
            )
            conn.commit()
            return cursor.rowcount

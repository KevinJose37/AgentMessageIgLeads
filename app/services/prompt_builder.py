import re


class PromptBuilder:
    """
    Builds optimized prompts for message rewriting.
    Focused on sales outreach and lead generation for Instagram DMs.
    """

    SYSTEM_PROMPT = (
        "Eres un especialista en ventas, generación de leads y comunicación "
        "persuasiva a través de mensajes directos en Instagram. "
        "Tienes amplia experiencia en outreach B2B y B2C, y tu fortaleza es "
        "crear mensajes que capten la atención de potenciales clientes de forma "
        "natural, profesional y no invasiva.\n\n"
        "Tu estilo de comunicación es formal-neutro: profesional pero cercano, "
        "sin ser frío ni excesivamente informal. Escribes como un profesional "
        "real que se comunica con prospectos — nunca como un bot o un mensaje masivo.\n\n"
        "REGLA FUNDAMENTAL: Respondes ÚNICAMENTE con un JSON array de strings. "
        "Sin explicaciones, sin markdown, sin texto adicional antes o después del JSON."
    )

    TONE_DESCRIPTIONS = {
        "casual": "Relajado pero profesional, como un colega que recomienda algo",
        "profesional": "Formal-neutro, transmite seriedad y credibilidad",
        "amigable": "Cálido y cercano, genera confianza desde el primer mensaje",
        "directo": "Conciso y al grano, respeta el tiempo del prospecto",
        "entusiasta": "Positivo y con energía, muestra pasión por lo que ofrece",
    }

    @staticmethod
    def build_variation_prompt(
        message: str,
        num_variations: int,
        tone: str,
        rules: list[str] | None = None,
        context: str | None = None,
    ) -> tuple[str, str]:
        """
        Build system + user prompts for variation generation.

        Args:
            message: Base message template with optional placeholders.
            num_variations: Number of unique variations to generate.
            tone: Desired communication tone.
            rules: Optional additional rules from the user.
            context: Optional business context for better variations.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Detect placeholders like {nombre}, {detalle}, {oferta}
        placeholders = re.findall(r"\{(\w+)\}", message)
        placeholder_rule = ""
        if placeholders:
            placeholder_list = ", ".join([f"{{{p}}}" for p in placeholders])
            placeholder_rule = (
                f"- CRÍTICO: Conserva EXACTAMENTE estos placeholders sin "
                f"modificar ni traducir: {placeholder_list}\n"
            )

        # Business context
        context_section = ""
        if context:
            context_section = (
                f"\nCONTEXTO DEL NEGOCIO:\n{context}\n"
                f"Usa este contexto para que las variaciones sean coherentes "
                f"con el negocio y su propuesta de valor.\n"
            )

        # Additional user rules
        rules_text = ""
        if rules:
            rules_text = "\nREGLAS DEL USUARIO:\n" + "\n".join(
                [f"- {r}" for r in rules]
            )

        tone_desc = PromptBuilder.TONE_DESCRIPTIONS.get(tone, tone)

        user_prompt = f"""Reescribe el siguiente mensaje de outreach generando exactamente {num_variations} versiones ÚNICAS.

OBJETIVO: Cada versión debe parecer escrita por una persona real que contacta a un prospecto por Instagram. El mensaje debe captar la atención, generar interés y abrir la puerta a una conversación.
{context_section}
REGLAS DE REESCRITURA:
- No cambies la intención ni el significado del mensaje original
- Mantén longitud similar (±20% de caracteres)
- Cada versión DEBE tener estructura y palabras notablemente diferentes
- Usa lenguaje natural — como lo escribiría un profesional real, no un bot
- NO repitas las mismas frases o patrones entre versiones
- NO uses emojis excesivos (máximo 1 por mensaje, y solo en algunas versiones)
- Varía los saludos iniciales (Hola, Hey, Qué tal, Buenos días, etc.)
- Varía las formas de cerrar o invitar a la conversación
- Evita frases genéricas de spam como "increíble oportunidad" o "no te lo pierdas"
{placeholder_rule}- TONO: {tone_desc}
{rules_text}

MENSAJE BASE:
"{message}"

RESPUESTA: JSON array de {num_variations} strings. SOLO el array, nada más.
Ejemplo: ["versión 1", "versión 2"]"""

        return PromptBuilder.SYSTEM_PROMPT, user_prompt

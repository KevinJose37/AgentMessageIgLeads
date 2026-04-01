import re


class PromptBuilder:
    """
    Builds optimized prompts for Instagram DM outreach rewriting.
    Focused on generating SHORT, VARIED, HUMAN messages that avoid
    detection patterns and don't sound like a bot or agency.
    """

    SYSTEM_PROMPT = (
        "Eres una persona real que contacta prospectos por Instagram DM. "
        "NO eres un copywriter, NO eres una agencia, NO escribes emails.\n\n"
        "Escribes como una persona normal que manda mensajes cortos por Instagram: "
        "directo, informal pero profesional, a veces imperfecto, siempre humano.\n\n"
        "REGLA ABSOLUTA: Respondes ÚNICAMENTE con un JSON array de strings. "
        "Sin explicaciones, sin markdown, sin texto adicional."
    )

    TONE_DESCRIPTIONS = {
        "casual": "Relajado, como hablarle a un conocido por DM",
        "profesional": "Profesional pero cercano, sin sonar a email corporativo",
        "amigable": "Cálido, genera confianza desde el primer mensaje",
        "directo": "Al grano, sin rodeos, respeta el tiempo",
        "entusiasta": "Positivo con energía, pero sin exagerar",
    }

    # Message archetypes to force diversity
    MESSAGE_ARCHETYPES = """
TIPOS DE MENSAJE (mezcla estos estilos entre las variaciones):
1. CURIOSIDAD — genera intriga sin vender ("Vi algo en tu perfil que me llamó la atención...")
2. PREGUNTA DIRECTA — abre conversación ("¿Tú manejas el marketing de tu negocio o alguien más lo hace?")
3. OBSERVACIÓN — comenta algo específico ("Tu contenido tiene buen engagement, ¿has probado escalar con ads?")
4. CONVERSACIONAL — casual, como amigo ("Hey, una pregunta rápida...")
5. SOFT PITCH — menciona valor sin vender ("Estoy ayudando a negocios como el tuyo con algo, si te interesa te cuento")
6. INCOMPLETO/ABIERTO — deja con curiosidad, pero indicando el contexto ("Vi tu perfil y se me ocurrió algo relacionado al {contexto}, ¿tienes un minuto?")\
"""

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

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Detect placeholders like {nombre}, {detalle}, {oferta}
        placeholders = re.findall(r"\{(\w+)\}", message)
        placeholder_rule = ""
        if placeholders:
            placeholder_list = ", ".join([f"{{{p}}}" for p in placeholders])
            placeholder_rule = (
                f"- CRITICO: Conserva estos placeholders EXACTOS sin modificar: "
                f"{placeholder_list}\n"
            )

        # Business context
        context_section = ""
        if context:
            context_section = (
                f"\nCONTEXTO DEL NEGOCIO (usa esto para dar coherencia, "
                f"pero NO lo menciones textualmente):\n{context}\n"
            )

        # Additional user rules
        rules_text = ""
        if rules:
            rules_text = "\nREGLAS DEL USUARIO:\n" + "\n".join(
                [f"- {r}" for r in rules]
            )

        tone_desc = PromptBuilder.TONE_DESCRIPTIONS.get(tone, tone)

        user_prompt = f"""Reescribe el siguiente mensaje de Instagram DM en {num_variations} versiones COMPLETAMENTE diferentes.

CONTEXTO: Esto es un DM de Instagram, NO un email. Los mensajes deben ser CORTOS y directos.
{context_section}
{PromptBuilder.MESSAGE_ARCHETYPES}

REGLAS DE REESCRITURA:
- Longitud: entre 8 y 25 palabras por mensaje (MÁXIMO 2 líneas)
- NO todas las versiones deben ser ventas directas
- Algunas deben ser SOLO preguntas
- Algunas deben ser curiosas o abiertas (dejar con intriga)
- Algunas pueden OMITIR saludo e ir directo al punto
- Algunas pueden empezar con una pregunta o idea
- Varía COMPLETAMENTE la estructura entre versiones
- PROHIBIDO repetir el patrón: saludo + observación + pitch + CTA
- Usa lenguaje natural, incluso ligeramente imperfecto (como humano real escribiendo rápido)
- EVITA tono corporativo, de agencia o de email marketing
- EVITA frases genéricas como "increíble oportunidad", "no te lo pierdas", "me encantaría conectar"
- Máximo 1 emoji en ALGUNAS versiones (no en todas)
- Algunos mensajes pueden ser incompletos o terminar con "..."
{placeholder_rule}- TONO: {tone_desc}
{rules_text}

MENSAJE BASE (extrae la intención, NO copies la estructura):
"{message}"

RESPUESTA: JSON array de {num_variations} strings cortos. SOLO el array.
["msg1", "msg2", ...]"""

        return PromptBuilder.SYSTEM_PROMPT, user_prompt

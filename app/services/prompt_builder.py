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

    # Message archetypes to inspire diversity
    MESSAGE_ARCHETYPES = """
ESTILOS SUGERIDOS PARA DAR VARIEDAD (puedes usarlos sutilmente, pero sin perder el mensaje original):
- Curiosidad (genera intriga sutil)
- Pregunta directa (abre conversación)
- Observación corta
- Conversacional casual
- Indirecto o incompleto (deja con ganas de responder)\
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

        user_prompt = f"""Genera {num_variations} variaciones del siguiente mensaje de Instagram DM.

CONTEXTO: Esto es un DM de Instagram, NO un email. Los mensajes deben ser CORTOS, directos y naturales.
{context_section}
{PromptBuilder.MESSAGE_ARCHETYPES}

REGLAS DE ESCRITURA:
- IMPORTANTE: Las REGLAS DEL USUARIO (si existen) tienen PRECEDENCIA ABSOLUTA sobre todo lo demás. ¡Cúmplelas al pie de la letra!
- Debes mantener el MENSAJE BASE como el núcleo principal, NO inventes temas que el original no menciona y NO pierdas su significado.
- Varía el fraseo para que no sean idénticas, pero respetando la intención exacta del mensaje base.
- Usa lenguaje conversacional (informal, como escribiendo rápido en el celular).
- EVITA tono de vendedor corporativo, lenguaje de "entrenador de negocios" o email marketing.
- Máximo 1 emoji en ALGUNAS versiones (no en todas).
{placeholder_rule}- TONO SUGERIDO: {tone_desc}
{rules_text}

MENSAJE BASE (mantén su enfoque, contexto e intención principal):
"{message}"

RESPUESTA: JSON array de {num_variations} strings cortos. SOLO el array, sin explicaciones.
["msg1", "msg2", ...]"""

        return PromptBuilder.SYSTEM_PROMPT, user_prompt


class CommentPromptBuilder:
    """
    Builds prompts for generating natural Instagram post comments.
    The goal is engagement and conversation, NOT selling.
    """

    SYSTEM_PROMPT = (
        "Eres una persona real interactuando en Instagram, comentando "
        "publicaciones de otros usuarios.\n\n"
        "NO eres un bot, NO eres una marca, NO eres una empresa. "
        "Eres un usuario normal dejando comentarios naturales en posts.\n\n"
        "Tu objetivo es escribir comentarios que:\n"
        "- Se sientan humanos, espontaneos y reales\n"
        "- Aporten algo al post (opinion, reaccion, pregunta o reflexion)\n"
        "- Generen interaccion sin parecer forzado\n\n"
        "REGLA ABSOLUTA: Respondes UNICAMENTE con un JSON array de strings. "
        "Sin explicaciones, sin markdown, sin texto adicional."
    )

    TONE_DESCRIPTIONS = {
        "casual": "Relajado, como un amigo comentando",
        "profesional": "Respetuoso y con criterio, sin sonar a marca",
        "amigable": "Calido y genuino, genera conexion",
        "directo": "Breve y al punto, comentario rapido",
        "entusiasta": "Positivo y con energia real (no fake)",
    }

    COMMENT_ARCHETYPES = """
TIPOS DE COMENTARIO (mezcla estos estilos):
1. REACCION GENUINA — respuesta emocional real al contenido ("Esto me paso igual la semana pasada, es tal cual")
2. PREGUNTA CURIOSA — pregunta algo especifico del post ("Como llegaste a esa conclusion? Me interesa el proceso")
3. OPINION/INSIGHT — agrega valor con un punto de vista ("Yo agregaria que tambien funciona si...")
4. ANECDOTA CORTA — comparte algo personal relacionado ("Me recuerda a cuando yo empece con esto...")
5. REFLEXION — comenta algo que te hizo pensar ("Esto cambia la perspectiva de como se ve normalmente")
6. FELICITACION NATURAL — si es un logro, felicita sin ser generico ("El esfuerzo se nota, sobre todo en [detalle especifico]")
"""

    @staticmethod
    def build_comment_prompt(
        post_content: str,
        tone: str,
        rules: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Build system + user prompts for single comment generation.

        Args:
            post_content: The text content of the Instagram post.
            tone: Desired tone.
            rules: Optional additional rules.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Additional rules
        rules_text = ""
        if rules:
            rules_text = "\nREGLAS DEL USUARIO:\n" + "\n".join(
                [f"- {r}" for r in rules]
            )

        tone_desc = CommentPromptBuilder.TONE_DESCRIPTIONS.get(tone, tone)

        user_prompt = f"""Lee el siguiente post de Instagram y genera 1 comentario natural y genuino.

Elige UNO de estos estilos segun lo que encaje mejor con el post:
{CommentPromptBuilder.COMMENT_ARCHETYPES}

ADAPTACION AL CONTEXTO DEL POST:
- Si el post es emocional -> responde con empatia real
- Si es informativo -> comenta una opinion o insight
- Si es un logro -> felicita de forma natural y especifica
- Si es pregunta -> responde o aporta tu experiencia
- Si es polemico -> opina con respeto
- Si es humor -> sigue el tono o reacciona naturalmente

REGLAS CRITICAS:
- Longitud: 5 a 20 palabras (como un comentario real de Instagram)
- NO escribir como marketing o ventas
- NO promocionar nada
- NO sonar corporativo ni tecnico
- NO usar frases genericas: "gran post", "excelente contenido", "muy interesante", "buen post"
- NO exagerar entusiasmo artificial
- Puede usar 0 o 1 emoji (opcional)
- TONO: {tone_desc}
{rules_text}

POST DE INSTAGRAM:
\"\"\"{post_content}\"\"\"

RESPUESTA: JSON array con exactamente 1 string. SOLO el array.
["tu comentario aqui"]"""

        return CommentPromptBuilder.SYSTEM_PROMPT, user_prompt



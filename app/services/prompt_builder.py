import re


class PromptBuilder:
    """Builds optimized prompts for message rewriting with Mistral 7B."""

    SYSTEM_PROMPT = (
        "Eres un experto en comunicación y copywriting en español latinoamericano. "
        "Tu trabajo es reescribir mensajes para que suenen naturales, humanos y "
        "diferentes entre sí. Respondes ÚNICAMENTE con JSON válido."
    )

    TONE_DESCRIPTIONS = {
        "casual": "Casual y relajado, como un mensaje entre conocidos",
        "profesional": "Profesional pero accesible, sin ser demasiado formal",
        "amigable": "Cálido y amigable, genera confianza inmediata",
        "directo": "Directo y al grano, sin rodeos ni relleno",
        "entusiasta": "Entusiasta y positivo, con energía contagiosa",
    }

    @staticmethod
    def build_variation_prompt(
        message: str,
        num_variations: int,
        tone: str,
        rules: list[str] | None = None,
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
                f"- OBLIGATORIO: Conserva EXACTAMENTE estos placeholders sin "
                f"modificar: {placeholder_list}\n"
            )

        # Additional user rules
        rules_text = ""
        if rules:
            rules_text = "\nREGLAS ADICIONALES DEL USUARIO:\n" + "\n".join(
                [f"- {r}" for r in rules]
            )

        tone_desc = PromptBuilder.TONE_DESCRIPTIONS.get(tone, tone)

        user_prompt = f"""Reescribe el siguiente mensaje generando exactamente {num_variations} versiones ÚNICAS y diferentes entre sí.

REGLAS ESTRICTAS:
- No cambies la intención ni el significado del mensaje
- Mantén una longitud similar (±20% de caracteres)
- Usa lenguaje natural y humano, como si lo escribiera una persona real
- Cada versión DEBE ser notablemente diferente en estructura y palabras
- NO uses frases que suenen a bot, spam o mensaje masivo
- NO uses emojis excesivos (máximo 1-2 por mensaje, y no en todos)
- Varía la estructura de las oraciones (orden, conectores, inicio)
- Varía los saludos y cierres entre versiones
{placeholder_rule}- TONO: {tone_desc}
{rules_text}

MENSAJE BASE:
"{message}"

FORMATO DE RESPUESTA: Responde ÚNICAMENTE con un JSON array de strings. Sin explicaciones, sin markdown, sin texto adicional.
Ejemplo de formato: ["variación 1", "variación 2", "variación 3"]"""

        return PromptBuilder.SYSTEM_PROMPT, user_prompt

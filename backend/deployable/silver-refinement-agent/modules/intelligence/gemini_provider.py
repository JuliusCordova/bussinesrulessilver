from __future__ import annotations

import os


class GeminiProvider:
    def __init__(self) -> None:
        self.project_id = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GEMINI_LOCATION", "us-central1")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def generate(self, prompt: str) -> str:
        if not self.project_id:
            raise RuntimeError("PROJECT_ID no está configurado para Vertex AI.")

        from google import genai
        from google.genai.types import GenerateContentConfig, HttpOptions

        client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
            http_options=HttpOptions(api_version="v1"),
        )
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1200,
                system_instruction=(
                    "Eres el asistente empresarial de Enterprise DataOps Platform. "
                    "Responde únicamente con la evidencia suministrada. No inventes hechos, "
                    "no ejecutes acciones y señala explícitamente la incertidumbre o fuentes faltantes. "
                    "Prioriza una explicación clara, causa, impacto y próximos pasos seguros."
                ),
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini devolvió una respuesta vacía.")
        return text

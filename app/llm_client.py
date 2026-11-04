import json
import re
import time
from typing import Dict, Any
import httpx
from app.config import settings
from app.schemas import LLMCardDraft


class GeminiClient:
    """Клиент для работы с Google Gemini через официальный REST API."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = 45.0

    def generate_draft(self, system_prompt: str, user_prompt: str) -> LLMCardDraft:
        """Отправляет запрос к Gemini API с автоматическим повтором при сбоях сети."""
        if not self.api_key or self.api_key.startswith("your_"):
            raise RuntimeError(
                "Не настроен GEMINI_API_KEY. "
                "Пожалуйста, укажите валидный API-ключ Gemini в файле .env."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload)

                if resp.status_code == 400:
                    raise RuntimeError(f"Gemini API 400 Bad Request: {resp.text}")
                elif resp.status_code == 403:
                    raise RuntimeError("Gemini API 403 Forbidden: недействительный API-ключ")
                elif resp.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise RuntimeError("Gemini API 429: превышен лимит запросов в минуту (quota exceeded)")
                elif resp.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Gemini API {resp.status_code} Service Error: {resp.text}")

                data = resp.json()
                raw_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed_json = self._clean_and_parse_json(raw_content)
                return LLMCardDraft.model_validate(parsed_json)
            except Exception as e:
                is_transient = any(err in str(e).lower() for err in ["proxyerror", "502", "503", "connect", "timeout"])
                if attempt < max_retries - 1 and is_transient:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if "Gemini API" in str(e):
                    raise
                raise RuntimeError(f"Ошибка вызова Gemini API: {e}")

        raise RuntimeError("Не удалось получить ответ от Gemini API: исчерпаны все попытки подключения.")

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """Очищает текст от возможных markdown-оберток (```json) и парсит JSON."""
        clean = text.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
            if match:
                clean = match.group(1).strip()
        return json.loads(clean)


# Алиас для обратной совместимости
UniversalLLMClient = GeminiClient

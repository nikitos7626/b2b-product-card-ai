import json
import re
import time
from typing import Dict, Any, Optional
import httpx
from app.config import settings
from app.schemas import LLMCardDraft


class UniversalLLMClient:
    """Универсальный клиент с поддержкой Google Gemini и OpenAI-совместимых LLM API."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.gemini_key = settings.gemini_api_key or os_key_fallback()
        self.gemini_model = settings.gemini_model
        
        self.openai_key = settings.openai_api_key
        self.openai_base_url = settings.openai_base_url.rstrip("/")
        self.openai_model = settings.openai_model
        
        self.timeout = 45.0

    def generate_draft(self, system_prompt: str, user_prompt: str) -> LLMCardDraft:
        """Отправляет запрос к LLM (Gemini или OpenAI) и возвращает структурированный черновик."""
        
        # 1. Проверяем Google Gemini
        if self._is_gemini_active():
            return self._call_gemini(system_prompt, user_prompt)
            
        # 2. Проверяем OpenAI-совместимый API
        if self._is_openai_active():
            return self._call_openai(system_prompt, user_prompt)
            
        raise RuntimeError(
            "Не настроен ни один провайдер LLM. "
            "Пожалуйста, укажите GEMINI_API_KEY или OPENAI_API_KEY в файле .env."
        )

    def _is_gemini_active(self) -> bool:
        """Проверяет, активен ли Gemini."""
        if self.gemini_key and not self.gemini_key.startswith("your_"):
            return True
        # Если ключ передан в openai_api_key, но формат гугловский (AQ. или AIza)
        if self.openai_key and (self.openai_key.startswith("AQ.") or self.openai_key.startswith("AIza")):
            self.gemini_key = self.openai_key
            return True
        return False

    def _is_openai_active(self) -> bool:
        """Проверяет, активен ли OpenAI."""
        return bool(self.openai_key and not self.openai_key.startswith("your_"))

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> LLMCardDraft:
        """Вызов Google Gemini через официальный REST API с автоматическими повторами при сбоях сети."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
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

    def _call_openai(self, system_prompt: str, user_prompt: str) -> LLMCardDraft:
        """Вызов OpenAI-совместимого API с автоматическими повторами."""
        url = f"{self.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=headers)

                if response.status_code == 401:
                    raise RuntimeError("Ошибка авторизации LLM API (401 Unauthorized)")
                elif response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise RuntimeError("Превышен лимит запросов к LLM API (429 Rate Limit Exceeded)")
                elif response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Сбой LLM API (код {response.status_code}): {response.text}")
                elif response.status_code >= 400:
                    raise RuntimeError(f"Сбой LLM API (код {response.status_code}): {response.text}")

                data = response.json()
                raw_content = data["choices"][0]["message"]["content"]
                parsed_json = self._clean_and_parse_json(raw_content)
                return LLMCardDraft.model_validate(parsed_json)
            except Exception as e:
                is_transient = any(err in str(e).lower() for err in ["proxyerror", "502", "503", "connect", "timeout"])
                if attempt < max_retries - 1 and is_transient:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if "LLM API" in str(e):
                    raise
                raise RuntimeError(f"Ошибка при обработке ответа LLM: {e}")

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """Очищает текст от возможных markdown-оберток (```json) и парсит JSON."""
        clean = text.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
            if match:
                clean = match.group(1).strip()
        return json.loads(clean)


def os_key_fallback() -> str:
    import os
    return os.getenv("GEMINI_API_KEY", "")

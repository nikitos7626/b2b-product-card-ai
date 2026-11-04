import json
import re
from typing import Dict, Any, Optional
import httpx
from app.config import settings
from app.schemas import LLMCardDraft


class UniversalLLMClient:
    """Универсальный клиент для работы с OpenAI-совместимыми LLM API через httpx.
    Поддерживает: OpenAI (gpt-4o-mini, gpt-4o), OpenRouter, Groq, DeepSeek, Ollama, vLLM.
    """

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.timeout = 45.0

    def generate_draft(self, system_prompt: str, user_prompt: str) -> LLMCardDraft:
        """Отправляет запрос к LLM API и возвращает структурированный черновик."""
        
        # Если API-ключ не задан в .env, генерируем детерминированный оффлайн-черновик
        if not self.api_key or self.api_key.startswith("your_api_key") or self.api_key == "none":
            return self._generate_offline_mock(user_prompt)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code == 401:
                raise RuntimeError("Ошибка авторизации LLM API (401 Unauthorized): проверьте OPENAI_API_KEY в .env")
            elif response.status_code == 429:
                raise RuntimeError("Превышен лимит запросов к LLM API (429 Rate Limit Exceeded)")
            elif response.status_code >= 400:
                raise RuntimeError(f"Сбой LLM API (код {response.status_code}): {response.text}")

            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
            parsed_json = self._clean_and_parse_json(raw_content)
            return LLMCardDraft.model_validate(parsed_json)

        except httpx.ConnectTimeout:
            raise RuntimeError(f"Таймаут подключения к LLM API ({self.base_url})")
        except httpx.ReadTimeout:
            raise RuntimeError(f"Таймаут ожидания ответа модели ({self.timeout}с)")
        except httpx.ConnectError as e:
            raise RuntimeError(f"Сетевая ошибка подключения к LLM API ({self.base_url}): {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка при обработке ответа LLM: {e}")

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """Очищает текст от возможных markdown-оберток (```json) и парсит JSON."""
        clean = text.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
            if match:
                clean = match.group(1).strip()
        return json.loads(clean)

    def _generate_offline_mock(self, user_prompt: str) -> LLMCardDraft:
        """Оффлайн-генератор черновика (используется для тестов или когда ключ еще не заполнен)."""
        is_pd100 = "пд100" in user_prompt.lower() or "овен" in user_prompt.lower()

        if is_pd100:
            return LLMCardDraft(
                seo_title="Преобразователь давления ОВЕН ПД100-ДИ 0-1,6 МПа 4-20 мА",
                seo_description=(
                    "Микропроцессорный преобразователь давления ОВЕН серии ПД100-ДИ предназначен для "
                    "высокоточного непрерывного измерения избыточного давления жидких и газообразных сред, "
                    "неагрессивных к нержавеющей стали AISI 316L, с последующим преобразованием в унифицированный "
                    "аналоговый сигнал постоянного тока 4-20 мА. Прибор оснащен стандартным штуцером с метрической "
                    "резьбой M20×1,5 для непосредственного монтажа в технологические трубопроводы и аппараты. "
                    "Широкий диапазон рабочего питания 12–36 В постоянного тока и основная приведенная погрешность "
                    "не более 0,5 % обеспечивают стабильное функционирование датчика в автоматизированных системах "
                    "управления технологическими процессами (АСУ ТП), котельных установках, насосных станциях, "
                    "тепловых распределительных пунктах и объектах водоснабжения. Прочная конструкция с металлической "
                    "мембраной гарантирует надежную долговременную работу прибора в тяжелых промышленных условиях."
                ),
                key_specs=[
                    {"parameter": "Тип прибора", "value": "Преобразователь давления избыточного"},
                    {"parameter": "Производитель", "value": "ОВЕН"},
                    {"parameter": "Модель", "value": "ПД100-ДИ1,6-111-0,5"},
                    {"parameter": "Диапазон измерений", "value": "0...1,6 МПа"},
                    {"parameter": "Выходной сигнал", "value": "4...20 мА"},
                    {"parameter": "Приведенная погрешность", "value": "±0,5 %"},
                    {"parameter": "Напряжение питания", "value": "12...36 В DC"},
                    {"parameter": "Присоединительная резьба", "value": "M20×1,5"},
                    {"parameter": "Температура рабочей среды", "value": "данных нет"},
                    {"parameter": "Степень защиты корпуса (IP)", "value": "данных нет"}
                ],
                search_queries=[
                    "преобразователь давления овен пд100 ди купить",
                    "датчик давления овен 4 20 ма 1 6 мпа",
                    "овен пд100 ди характеристики паспорт",
                    "датчик давления m20x1 5 овен"
                ],
                commercial_block={
                    "target_audience": "Инженеры АСУ ТП, службы главного энергетика, тепловые сети, водоканалы и промышленные предприятия.",
                    "tasks_solved": "Непрерывный дистанционный контроль давления в контурах циркуляции, передача данных в ПЛК и автоматическая защита насосного оборудования."
                },
                llm_missing_fields=["Температура рабочей среды", "Степень пылевлагозащиты корпуса (IP)", "Исполнение по взрывозащите"]
            )
        else:
            return LLMCardDraft(
                seo_title="Манометр показывающий DM 02 Манотомь 0-1,6 МПа G1/2 100 мм",
                seo_description=(
                    "Показывающий манометр DM 02 производства завода «Манотомь» предназначен для точного измерения "
                    "избыточного давления жидких и газообразных некристаллизующихся сред, неагрессивных к медным сплавам. "
                    "Прибор выполнен в прочном стандартном корпусе диаметром 100 мм со штуцером с трубной резьбой G1/2, "
                    "что обеспечивает удобное подключение к технологическим линиям. Стандартный диапазон измерений от 0 до 1,6 МПа "
                    "и класс точности 1,5 позволяют применять манометр в системах отопления, горячего и холодного водоснабжения, "
                    "насосных станциях и котельных установках. Четкая аналоговая круговая шкала гарантирует быстрое и однозначное "
                    "считывание текущих показателей дежурным оперативным персоналом. Механический принцип действия прибора позволяет "
                    "осуществлять непрерывный визуальный контроль параметров без необходимости подключения электропитания, что снижает "
                    "затраты на монтаж и обеспечивает максимальную автономность измерительного узла."
                ),
                key_specs=[
                    {"parameter": "Тип прибора", "value": "Манометр показывающий"},
                    {"parameter": "Производитель", "value": "Манотомь"},
                    {"parameter": "Модель", "value": "DM 02"},
                    {"parameter": "Диапазон измерений", "value": "0–1,6 МПа"},
                    {"parameter": "Класс точности", "value": "1,5"},
                    {"parameter": "Присоединительная резьба", "value": "G1/2"},
                    {"parameter": "Диаметр корпуса", "value": "100 мм"},
                    {"parameter": "Температура измеряемой среды", "value": "данных нет"},
                    {"parameter": "Степень защиты корпуса (IP)", "value": "данных нет"}
                ],
                search_queries=[
                    "манометр показывающий dm 02 манотомь купить",
                    "манометр 0 1.6 мпа g1 2 диаметр 100",
                    "манометр dm 02 технические характеристики",
                    "манометр манотомь dm 02 с поверкой"
                ],
                commercial_block={
                    "target_audience": "Службы ЖКХ, эксплуатирующие организации теплопунктов, монтажные компании систем отопления и водоснабжения.",
                    "tasks_solved": "Надежный автономный визуальный контроль избыточного давления в трубопроводах без подвода внешнего электропитания."
                },
                llm_missing_fields=["Температура измеряемой среды", "Степень защиты корпуса IP", "Материал штуцера и корпуса"]
            )

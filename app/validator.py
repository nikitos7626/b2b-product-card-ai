import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from app.schemas import KeySpecItem, DataQualityReport
from app.config import settings


class TaxonomyAndGroundingValidator:
    """Детерминированный валидатор фактов, защиты от галлюцинаций и проверки полноты характеристик."""

    def __init__(self, taxonomy_path: Path = None):
        self.taxonomy_path = taxonomy_path or (settings.data_dir / "categories_taxonomy.json")
        self.categories: List[Dict[str, Any]] = []
        self._load_taxonomy()

    def _load_taxonomy(self):
        """Загружает базу 238 категорий КИПиА в память."""
        if self.taxonomy_path.exists():
            try:
                with open(self.taxonomy_path, "r", encoding="utf-8") as f:
                    self.categories = json.load(f)
            except Exception:
                self.categories = []

    def match_category(self, name: str, description: str = "") -> Dict[str, Any]:
        """Определяет категорию товара по наименованию и тексту описания."""
        text = f"{name} {description}".lower()

        # 1. Точные ключевые совпадения
        keywords_map = [
            (["манометр", "вакуумметр", "напоромер", "тягомер", "дифманометр"], "CAT_176", "Манометры показывающие"),
            (["датчик давления", "преобразователь давления", "пд100"], "CAT_033", "Преобразователи (датчики) давления"),
            (["термопреобразовател", "термометр сопротивления", "тсп", "тсм", "pt100"], "CAT_027", "Термопреобразователи сопротивления (ТСМ, ТСП)"),
            (["термопар", "термоэлектрическ", "тха", "тжк"], "CAT_028", "Термоэлектрические преобразователи (термопары)"),
            (["термометр"], "CAT_174", "Термометры биметаллические"),
            (["расходомер", "счетчик воды", "счетчик тепла", "ротаметр"], "CAT_195", "Ультразвуковые расходомеры"),
            (["уровнемер", "датчик уровня", "сигнализатор уровня"], "CAT_036", "Датчики уровня"),
            (["газоанализатор", "сигнализатор загазованности"], "CAT_196", "Газоанализаторы переносные"),
            (["регулятор", "контроллер", "плк", "трм"], "CAT_010", "Измерители-регуляторы")
        ]

        for keys, cat_id, default_name in keywords_map:
            if any(k in text for k in keys):
                # Ищем запись в загруженной базе
                for item in self.categories:
                    if item.get("category_id") == cat_id:
                        return item
                return {
                    "category_id": cat_id,
                    "category_name": default_name,
                    "required_specs": "Диапазон измерений; Класс точности; Присоединение",
                    "critical_missing_checks": "Температура среды; Степень защиты IP"
                }

        # Дефолтная категория
        return {
            "category_id": "CAT_GENERAL",
            "category_name": "Общепромышленные приборы КИПиА",
            "required_specs": "Диапазон измерений; Класс точности / погрешность; Напряжение питания",
            "critical_missing_checks": "Температурный диапазон; Степень защиты корпуса (IP)"
        }

    def analyze_data_quality(
        self,
        name: str,
        manufacturer: str,
        specs: Dict[str, Any],
        description: str,
        category_info: Dict[str, Any]
    ) -> DataQualityReport:
        """Анализирует входные данные на отсутствие критических полей и наличие сомнительных значений."""
        missing: List[str] = []
        clarifications: List[str] = []

        all_input_text = f"{name} {manufacturer} {description}".lower()
        specs_lower = {k.lower(): str(v).strip() for k, v in specs.items()}

        # 1. Проверка по обязательным полям категории
        required_raw = category_info.get("required_specs", "")
        required_list = [r.strip() for r in required_raw.split(";") if r.strip()]

        SYNONYM_STEMS = {
            "присоединен": ["резьб", "штуцер", "присоединен", "монтаж", "порт"],
            "резьб": ["присоединен", "штуцер", "резьб"],
            "диапазон": ["шкал", "предел", "диапазон"],
            "температур": ["t°", "t ", "темп"],
            "корпус": ["диаметр", "габарит", "размер", "корпус"],
            "погрешност": ["точност", "класс"],
            "питани": ["напряжен", "питани", "вольт", "в dc", "в ac"],
            "выход": ["сигнал", "выход", "интерфейс"]
        }

        def matches_any_synonym(target_text: str, candidate_text: str) -> bool:
            """Проверяет точные совпадения и совпадения по стемам синонимов."""
            t_words = target_text.lower().split()
            c_text = candidate_text.lower()
            if any(w in c_text for w in t_words if len(w) > 3):
                return True
            for stem, synonyms in SYNONYM_STEMS.items():
                if any(syn in target_text.lower() for syn in synonyms):
                    if any(syn in c_text for syn in synonyms):
                        return True
            return False

        all_specs_keys = " ".join(specs_lower.keys())

        for req in required_list:
            clean_req = re.sub(r"\s*\(.*?\)", "", req).strip()
            found = matches_any_synonym(clean_req, all_specs_keys) or matches_any_synonym(clean_req, all_input_text)
            if not found:
                missing.append(clean_req)

        # 2. Проверка критических условий эксплуатации
        critical_raw = category_info.get("critical_missing_checks", "")
        critical_list = [c.strip() for c in critical_raw.split(";") if c.strip()]
        for crit in critical_list:
            clean_crit = re.sub(r"\s*\(.*?\)", "", crit).strip()
            found = matches_any_synonym(clean_crit, all_specs_keys) or matches_any_synonym(clean_crit, all_input_text)
            if not found:
                missing.append(clean_crit)

        # 3. Проверка полей, требующих уточнения (нет единиц, размытые значения)
        DIMENSIONLESS_FIELDS = {
            "класс точности", "точность", "степень защиты", "ip", 
            "климатическое исполнение", "гост", "количество", "число"
        }

        for k, v in specs.items():
            k_lower = k.lower().strip()
            val_str = str(v).strip()
            
            # Пропускаем безразмерные метрологические величины
            if any(dim in k_lower for dim in DIMENSIONLESS_FIELDS):
                continue

            # Число без единиц измерения (например "16", "100", "0.5")
            if re.match(r"^[-+]?\d+([.,]\d+)?$", val_str):
                clarifications.append(f"Поле «{k}» имеет значение «{val_str}» без указания единицы измерения (МПа, мм, бар и т.д.)")
            # Размытые значения
            if val_str.lower() in ["стандартное", "обычное", "по гост", "нормальное"]:
                clarifications.append(f"Поле «{k}» имеет размытое значение «{val_str}», требуется конкретный типоразмер или стандарт")

        status = "requires_clarification" if (missing or clarifications) else "complete"

        recs = []
        if missing:
            recs.append("Запросить у поставщика/завода недостающие параметры паспорта.")
        if clarifications:
            recs.append("Уточнить единицы измерения числовых параметров для корректного подбора.")
        if not recs:
            recs.append("Входные технические данные достаточны для публикации карточки.")

        return DataQualityReport(
            status=status,
            detected_category=category_info.get("category_name", "Общепромышленные приборы КИПиА"),
            missing_fields=missing,
            clarification_needed=clarifications,
            recommendations=" ".join(recs)
        )

    def verify_grounding(
        self,
        key_specs: List[KeySpecItem],
        input_payload: Dict[str, Any]
    ) -> List[KeySpecItem]:
        """Проверяет каждое значение в характеристиках на отсутствие выдуманных данных.
        Если значение отсутствует во входных данных и не равно 'данных нет', оно помечается.
        """
        all_text = " ".join([
            str(input_payload.get("name", "")),
            str(input_payload.get("manufacturer", "")),
            str(input_payload.get("description", "")),
            " ".join(f"{k} {v}" for k, v in input_payload.get("specs", {}).items())
        ]).lower()

        # Очистка для сопоставления
        normalized_corpus = re.sub(r"[^\w\d\s.,-]", " ", all_text)

        verified_specs: List[KeySpecItem] = []
        for item in key_specs:
            val = item.value.strip()
            # Допустимое отсутствие
            if val.lower() in ["данных нет", "не указано", "нет данных", "н/д"]:
                verified_specs.append(KeySpecItem(parameter=item.parameter, value="данных нет"))
                continue

            # Извлекаем числа из значения (например "0-1,6 МПа" -> ["0", "1", "6"])
            numbers_in_val = re.findall(r"\d+", val)
            if numbers_in_val:
                # Проверяем, что хотя бы ключевые числа присутствуют в исходном корпусе
                found_numbers = all(num in normalized_corpus for num in numbers_in_val)
                if not found_numbers:
                    verified_specs.append(KeySpecItem(
                        parameter=item.parameter,
                        value=f"{val} [⚠️ требует проверки источника]"
                    ))
                    continue

            verified_specs.append(item)

        return verified_specs

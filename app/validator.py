import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from app.schemas import KeySpecItem, DataQualityReport
from app.config import settings


def normalize_spec_value(val: str) -> str:
    """Детерминированная нормализация технических значений приборов КИПиА."""
    if not val:
        return "данных нет"
    
    v = str(val).strip()
    if v.lower() in ["данных нет", "нет данных", "не указано", "н/д", "none", "null", "-", "—"]:
        return "данных нет"
    
    # 1. Резьбы (G1/2, M20x1.5)
    # G1/2", g 1/2, g1/2 -> G1/2
    v = re.sub(r"\bg\s*(\d+/\d+)\b[\"']?", r"G\1", v, flags=re.IGNORECASE)
    # M20x1.5, м20*1,5 -> M20×1,5
    v = re.sub(r"[mм]\s*(\d+)\s*[*xх×]\s*(\d+([.,]\d+)?)", lambda m: f"M{m.group(1)}×{m.group(2).replace('.', ',')}", v, flags=re.IGNORECASE)
    
    # 2. Выходные электрические сигналы
    v = re.sub(r"\b4\s*[-–—.]+\s*20\s*(?:ма|ma)\b", "4...20 мА", v, flags=re.IGNORECASE)
    v = re.sub(r"\b0\s*[-–—.]+\s*20\s*(?:ма|ma)\b", "0...20 мА", v, flags=re.IGNORECASE)
    v = re.sub(r"\b0\s*[-–—.]+\s*10\s*(?:в|v)\b", "0...10 В", v, flags=re.IGNORECASE)

    # 3. Давление: МПа, кПа, бар
    v = re.sub(r"(\d+)\s*[-–—]\s*(\d+([.,]\d+)?)\s*мпа", lambda m: f"{m.group(1)}–{m.group(2).replace('.', ',')} МПа", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+)\s*[-–—]\s*(\d+([.,]\d+)?)\s*кпа", lambda m: f"{m.group(1)}–{m.group(2).replace('.', ',')} кПа", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+([.,]\d+)?)\s*мпа", lambda m: f"{m.group(1).replace('.', ',')} МПа", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+([.,]\d+)?)\s*кпа", lambda m: f"{m.group(1).replace('.', ',')} кПа", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+([.,]\d+)?)\s*бар\b", lambda m: f"{m.group(1).replace('.', ',')} бар", v, flags=re.IGNORECASE)

    # 4. Линейные размеры (мм)
    v = re.sub(r"(\d+)\s*мм\.?", r"\1 мм", v, flags=re.IGNORECASE)

    # 5. Температура (°C)
    v = re.sub(r"([-+]?\d+)\s*[-–—.]+\s*([-+]?\d+)\s*(?:°\s*[cс]|град(?:ус(?:ов|а)?)?(?:\s*цельси(?:я|е)?)?)", r"\1...\2 °C", v, flags=re.IGNORECASE)
    v = re.sub(r"([-+]?\d+)\s*(?:°\s*[cс]|град(?:ус(?:ов|а)?)?(?:\s*цельси(?:я|е)?)?)", r"\1 °C", v, flags=re.IGNORECASE)

    # 6. Питание (В DC / В AC)
    v = re.sub(r"(\d+)\s*[-–—.]+\s*(\d+)\s*(?:в|v)\s*(?:dc|пост(?:оянного)?(?:\s*тока)?)", r"\1...\2 В DC", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+)\s*(?:в|v)\s*(?:dc|пост(?:оянного)?(?:\s*тока)?)", r"\1 В DC", v, flags=re.IGNORECASE)
    v = re.sub(r"(\d+)\s*(?:в|v)\s*(?:ac|перем(?:енного)?(?:\s*тока)?)", r"\1 В AC", v, flags=re.IGNORECASE)

    # 7. Погрешность (+-0.5%, +/- 0.5 %)
    v = re.sub(r"(?:\+\s*/\s*-|\+-\s*|±\s*)(\d+([.,]\d+)?)\s*%", lambda m: f"±{m.group(1).replace('.', ',')} %", v)

    # 8. Запятая в десятичных дробях для одиночных чисел (1.5 -> 1,5)
    if re.match(r"^[-+]?\d+\.\d+$", v):
        v = v.replace(".", ",")

    return v.strip()


def normalize_spec_key(key: str) -> str:
    """Приводит наименования параметров к отраслевому стандарту с заглавной буквы."""
    if not key:
        return ""
    k = key.strip()
    KEY_SYNONYMS = {
        "диапазон": "Диапазон измерений",
        "диапазон измерений": "Диапазон измерений",
        "предел измерений": "Диапазон измерений",
        "шкала": "Диапазон измерений",
        "присоединение": "Присоединительная резьба",
        "резьба": "Присоединительная резьба",
        "штуцер": "Присоединительная резьба",
        "класс точности": "Класс точности",
        "погрешность": "Основная погрешность",
        "приведенная погрешность": "Основная приведенная погрешность",
        "основная приведенная погрешность": "Основная приведенная погрешность",
        "выход": "Выходной сигнал",
        "выходной сигнал": "Выходной сигнал",
        "питание": "Напряжение питания",
        "напряжение питания": "Напряжение питания",
        "диаметр": "Диаметр корпуса",
        "диаметр корпуса": "Диаметр корпуса",
        "степень защиты": "Степень защиты",
        "температура среды": "Температура измеряемой среды",
        "температура измеряемой среды": "Температура измеряемой среды"
    }
    k_lower = k.lower()
    if k_lower in KEY_SYNONYMS:
        return KEY_SYNONYMS[k_lower]
    return k[0].upper() + k[1:] if len(k) > 1 else k.upper()


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

    def match_category(self, name: str, description: Optional[str] = "") -> Dict[str, Any]:
        """Определяет категорию товара по наименованию и тексту описания."""
        text = f"{name or ''} {description or ''}".lower()

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
        manufacturer: Optional[str] = "",
        specs: Optional[Dict[str, Any]] = None,
        description: Optional[str] = "",
        category_info: Optional[Dict[str, Any]] = None
    ) -> DataQualityReport:
        """Анализирует входные данные на отсутствие критических полей и наличие сомнительных значений."""
        missing: List[str] = []
        clarifications: List[str] = []

        all_input_text = f"{name or ''} {manufacturer or ''} {description or ''}".lower()
        specs_lower = {k.lower(): str(v).strip() for k, v in (specs or {}).items()}

        # 1. Проверка по обязательным полям категории
        required_raw = (category_info or {}).get("required_specs", "")
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
            norm_key = normalize_spec_key(item.parameter)
            val = item.value.strip()
            
            # Допустимое отсутствие
            if val.lower() in ["данных нет", "не указано", "нет данных", "н/д"]:
                verified_specs.append(KeySpecItem(parameter=norm_key, value="данных нет"))
                continue

            # Нормализация технического значения (единицы, резьбы, тире, дроби)
            norm_val = normalize_spec_value(val)

            # Извлекаем числа из значения (например "0-1,6 МПа" -> ["0", "1", "6"])
            numbers_in_val = re.findall(r"\d+", val)
            if numbers_in_val:
                # Проверяем, что хотя бы ключевые числа присутствуют в исходном корпусе
                found_numbers = all(num in normalized_corpus for num in numbers_in_val)
                if not found_numbers:
                    verified_specs.append(KeySpecItem(
                        parameter=norm_key,
                        value=f"{norm_val} [⚠️ требует проверки источника]"
                    ))
                    continue

            verified_specs.append(KeySpecItem(parameter=norm_key, value=norm_val))

        return verified_specs

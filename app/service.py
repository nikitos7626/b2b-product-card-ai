import re
from typing import Dict, Any, List, Optional
from app.schemas import ProductInput, DraftCardResponse, KeySpecItem, DataQualityReport
from app.prompt import SYSTEM_PROMPT, build_user_prompt
from app.validator import TaxonomyAndGroundingValidator
from app.llm_client import UniversalLLMClient


class ProductCardService:
    """Сервис генерации черновика карточки товара B2B."""

    def __init__(self):
        self.validator = TaxonomyAndGroundingValidator()
        self.llm_client = UniversalLLMClient()

    def generate_product_card(self, product: ProductInput) -> DraftCardResponse:
        """Полный конвейер генерации и валидации черновика карточки."""
        
        # 1. Определение категории прибора в таксономии
        category_info = self.validator.match_category(product.name, product.description)
        
        # 2. Анализ полноты входных данных
        data_quality = self.validator.analyze_data_quality(
            name=product.name,
            manufacturer=product.manufacturer or "",
            specs=product.specs or {},
            description=product.description or "",
            category_info=category_info
        )

        # 3. Формирование промпта
        user_prompt = build_user_prompt(
            name=product.name,
            manufacturer=product.manufacturer or "",
            specs=product.specs or {},
            description=product.description or "",
            detected_category=category_info.get("category_name", ""),
            required_specs_hint=category_info.get("required_specs", "")
        )

        # 4. Вызов LLM
        llm_draft = self.llm_client.generate_draft(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        # 5. Проверка длины заголовка (гарантия <= 70 символов)
        seo_title = llm_draft.seo_title.strip()
        if len(seo_title) > 70:
            seo_title = seo_title[:67].rstrip(" ,-—") + "..."

        # 5b. Контроль длины SEO-описания (гарантия 800 - 1200 символов)
        seo_description = llm_draft.seo_description.strip()
        if len(seo_description) < 800:
            extension = (
                f" Эксплуатация прибора должна осуществляться в соответствии с паспортом изделия, "
                f"техническим регламентом и правилами безопасности на промышленных объектах КИПиА."
            )
            if len(seo_description) + len(extension) <= 1200:
                seo_description = seo_description.rstrip(". ") + "." + extension
        elif len(seo_description) > 1200:
            truncated = seo_description[:1190]
            last_dot = max(truncated.rfind(". "), truncated.rfind(".\n"))
            if last_dot > 800:
                seo_description = truncated[:last_dot + 1]
            else:
                seo_description = truncated.rstrip(" ,-—") + "..."

        # 6. Проверка фактов и защита от галлюцинаций (Grounding Verifier)
        input_payload = {
            "name": product.name,
            "manufacturer": product.manufacturer,
            "specs": product.specs,
            "description": product.description
        }
        verified_specs = self.validator.verify_grounding(llm_draft.key_specs, input_payload)

        # 7. Фильтруем отсутствующие поля:
        # Характеристики, которые уже извлечены в таблицу с реальным значением (не "данных нет"), НЕ считаются отсутствующими!
        extracted_valid_keys = [
            s.parameter.lower().strip()
            for s in verified_specs
            if s.value.strip().lower() not in ["данных нет", "нет данных", "н/д", "не указано"]
        ]

        # Любой параметр из verified_specs, у которого значение "данных нет"
        specs_with_no_data = [
            s.parameter.strip()
            for s in verified_specs
            if s.value.strip().lower() in ["данных нет", "нет данных", "н/д", "не указано"]
        ]

        synonym_stems = ["присоединен", "резьб", "штуцер", "диапазон", "шкал", "предел", "температур", "корпус", "диаметр", "погрешност", "точност", "питани", "выход"]

        candidate_missing = data_quality.missing_fields + llm_draft.llm_missing_fields + specs_with_no_data
        clean_missing: List[str] = []
        seen_missing = set()

        for m in candidate_missing:
            m_clean = re.sub(r"\s*\(.*?\)", "", m).strip()
            m_lower = m_clean.lower()
            if not m_clean or m_lower in seen_missing:
                continue

            # Проверяем, есть ли уже этот параметр среди успешно извлеченных
            is_extracted = False
            for val_key in extracted_valid_keys:
                if m_lower in val_key or val_key in m_lower:
                    is_extracted = True
                    break
                for stem in synonym_stems:
                    if stem in m_lower and stem in val_key:
                        is_extracted = True
                        break
                if is_extracted:
                    break

            if not is_extracted:
                seen_missing.add(m_lower)
                clean_missing.append(m_clean)

        data_quality.missing_fields = clean_missing
        if clean_missing or data_quality.clarification_needed:
            data_quality.status = "requires_clarification"
        else:
            data_quality.status = "complete"
            data_quality.recommendations = "Входные технические данные достаточны для публикации карточки."

        # 8. Формирование готового Markdown-представления
        markdown_text = self._build_markdown_view(
            title=seo_title,
            description=seo_description,
            specs=verified_specs,
            queries=llm_draft.search_queries,
            commercial=llm_draft.commercial_block,
            quality=data_quality
        )

        # 9. Формирование микроразметки Schema.org Product (по стандартам /seo-ecommerce)
        schema_org_data = self._build_schema_org(
            title=seo_title,
            description=seo_description,
            manufacturer=product.manufacturer or "",
            category=data_quality.detected_category,
            specs=verified_specs
        )

        return DraftCardResponse(
            seo_title=seo_title,
            seo_title_length=len(seo_title),
            seo_description=seo_description,
            seo_description_length=len(seo_description),
            key_specs=verified_specs,
            search_queries=llm_draft.search_queries,
            commercial_block=llm_draft.commercial_block,
            data_quality=data_quality,
            markdown_card=markdown_text,
            schema_org=schema_org_data
        )

    def _build_markdown_view(
        self,
        title: str,
        description: str,
        specs: List[KeySpecItem],
        queries: List[str],
        commercial: Any,
        quality: DataQualityReport
    ) -> str:
        """Генерирует чистый структурированный Markdown черновика для копирования."""
        lines = [
            f"# {title}",
            "",
            "## Описание товара",
            description,
            "",
            "## Ключевые технические характеристики",
            "| Параметр | Значение |",
            "| :--- | :--- |"
        ]
        for s in specs:
            lines.append(f"| {s.parameter} | {s.value} |")

        lines.extend([
            "",
            "## Поисковые запросы для оптимизации страницы",
        ])
        for q in queries:
            lines.append(f"- `{q}`")

        lines.extend([
            "",
            "## Коммерческий блок для менеджера по продажам",
            f"**Целевая аудитория:** {commercial.target_audience}",
            "",
            f"**Решаемые задачи:** {commercial.tasks_solved}",
            ""
        ])

        if quality.missing_fields or quality.clarification_needed:
            lines.append("## ⚠️ Требует внимания контент-менеджера")
            if quality.missing_fields:
                lines.append("**Отсутствующие критические поля:**")
                for m in quality.missing_fields:
                    lines.append(f"- {m}")
            if quality.clarification_needed:
                lines.append("**Поля, требующие уточнения:**")
                for c in quality.clarification_needed:
                    lines.append(f"- {c}")
            lines.append(f"\n*Рекомендация:* {quality.recommendations}")

        return "\n".join(lines)

    def _build_schema_org(
        self,
        title: str,
        description: str,
        manufacturer: Optional[str],
        category: str,
        specs: List[KeySpecItem]
    ) -> Dict[str, Any]:
        """
        Генерирует микроразметку Schema.org Product (JSON-LD) по спецификации /seo-ecommerce.
        Включает базовые атрибуты Google Merchant и массив характеристик additionalProperty.
        """
        additional_props = [
            {
                "@type": "PropertyValue",
                "name": s.parameter,
                "value": s.value
            }
            for s in specs
            if s.value and s.value.strip().lower() not in ["данных нет", "нет данных", "не указано", "н/д"]
        ]

        schema: Dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": title,
            "description": description[:300] + ("..." if len(description) > 300 else ""),
            "category": category,
            "brand": {
                "@type": "Brand",
                "name": manufacturer or "Не указан"
            },
            "offers": {
                "@type": "Offer",
                "priceCurrency": "RUB",
                "availability": "https://schema.org/InStock",
                "itemCondition": "https://schema.org/NewCondition"
            }
        }
        if additional_props:
            schema["additionalProperty"] = additional_props

        return schema


card_service = ProductCardService()

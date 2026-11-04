from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ProductInput(BaseModel):
    """Входные данные о контрольно-измерительном приборе."""
    name: str = Field(..., description="Название товара (например, Манометр показывающий DM 02)")
    manufacturer: Optional[str] = Field(default="", description="Производитель прибора")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Краткие характеристики в виде словаря")
    description: Optional[str] = Field(default="", description="Текстовое описание или фрагмент паспорта")

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Название товара не может быть пустым.")
        return clean


class KeySpecItem(BaseModel):
    """Единичная характеристика прибора."""
    parameter: str = Field(..., description="Наименование параметра")
    value: str = Field(..., description="Значение параметра")


class CommercialBlock(BaseModel):
    """Коммерческий блок для менеджера по продажам."""
    target_audience: str = Field(..., description="Кому подходит прибор")
    tasks_solved: str = Field(..., description="Какие задачи решает")

    @field_validator("target_audience", "tasks_solved", mode="before")
    @classmethod
    def list_to_string(cls, v: Any) -> str:
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return str(v)


class DataQualityReport(BaseModel):
    """Отчет о полноте данных и необходимости уточнений."""
    status: str = Field(default="complete", description="'complete' или 'requires_clarification'")
    detected_category: str = Field(default="Общепромышленные приборы КИПиА", description="Определенная категория товара")
    missing_fields: List[str] = Field(default_factory=list, description="Критические поля, отсутствующие во входе")
    clarification_needed: List[str] = Field(default_factory=list, description="Поля, требующие уточнения (без единиц и т.д.)")
    recommendations: str = Field(default="", description="Рекомендации контент-менеджеру или отделу закупок")


class LLMCardDraft(BaseModel):
    """Структурированный ответ от LLM."""
    seo_title: str = Field(..., description="SEO-заголовок до 70 символов")
    seo_description: str = Field(..., description="SEO-описание от 800 до 1200 символов")
    key_specs: List[KeySpecItem] = Field(..., description="Список характеристик")
    search_queries: List[str] = Field(..., description="3-5 поисковых запросов")
    commercial_block: CommercialBlock = Field(..., description="Информация для менеджера")
    llm_missing_fields: List[str] = Field(default_factory=list, description="Замеченные пропуски")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_response(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Если модель вернула key_specs как словарь {"диапазон": "0-10", ...}
        specs_raw = data.get("key_specs")
        if isinstance(specs_raw, dict):
            converted = []
            for k, v in specs_raw.items():
                converted.append({"parameter": str(k).strip(), "value": str(v).strip()})
            data["key_specs"] = converted

        # Если модель назвала поле search_keywords вместо search_queries
        if "search_queries" not in data and "search_keywords" in data:
            data["search_queries"] = data["search_keywords"]

        return data


class DraftCardResponse(BaseModel):
    """Итоговый черновик карточки товара, возвращаемый клиенту."""
    seo_title: str
    seo_title_length: int
    seo_description: str
    seo_description_length: int
    key_specs: List[KeySpecItem]
    search_queries: List[str]
    commercial_block: CommercialBlock
    data_quality: DataQualityReport
    markdown_card: str
    schema_org: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Микроразметка Schema.org Product (JSON-LD)")

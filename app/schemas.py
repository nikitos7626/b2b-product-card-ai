from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


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
    parameter: str = Field(..., description="Наименование параметра (например, Диапазон измерений)")
    value: str = Field(..., description="Значение параметра строго из исходных данных либо 'данных нет'")


class CommercialBlock(BaseModel):
    """Коммерческий блок для менеджера по продажам."""
    target_audience: str = Field(..., description="Кому подходит прибор: отрасли, службы, предприятия")
    tasks_solved: str = Field(..., description="Какие инженерные и эксплуатационные задачи решает прибор")


class DataQualityReport(BaseModel):
    """Отчет о полноте данных и необходимости уточнений."""
    status: str = Field(default="complete", description="'complete' или 'requires_clarification'")
    detected_category: str = Field(default="Общепромышленные приборы КИПиА", description="Определенная категория товара")
    missing_fields: List[str] = Field(default_factory=list, description="Критические поля, отсутствующие во входе")
    clarification_needed: List[str] = Field(default_factory=list, description="Поля, требующие уточнения (без единиц и т.д.)")
    recommendations: str = Field(default="", description="Рекомендации контент-менеджеру или отделу закупок")


class LLMCardDraft(BaseModel):
    """Структурированный ответ от LLM."""
    seo_title: str = Field(..., description="SEO-заголовок строго до 70 символов")
    seo_description: str = Field(..., description="Техническое SEO-описание объемом от 800 до 1200 символов")
    key_specs: List[KeySpecItem] = Field(..., description="Список характеристик. Значения строго из текста или 'данных нет'")
    search_queries: List[str] = Field(..., description="3-5 релевантных поисковых запросов для страницы")
    commercial_block: CommercialBlock = Field(..., description="Информация для менеджера по продажам")
    llm_missing_fields: List[str] = Field(default_factory=list, description="Замеченные LLM пропуски данных")


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

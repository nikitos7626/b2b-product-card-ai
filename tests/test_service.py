import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ProductInput, KeySpecItem
from app.service import card_service
from app.validator import TaxonomyAndGroundingValidator, normalize_spec_value, normalize_spec_key


@pytest.fixture
def client():
    return TestClient(app)


def test_empty_name_validation():
    """Проверка, что пустое название товара вызывает ошибку валидации."""
    with pytest.raises(ValueError):
        ProductInput(name="   ", manufacturer="Манотомь")


def test_category_matching_manometer():
    """Проверка корректного определения категории манометра."""
    val = TaxonomyAndGroundingValidator()
    cat = val.match_category("Манометр показывающий DM 02", "Прибор для измерения давления")
    assert "Манометры" in cat["category_name"]


def test_category_matching_pressure_transmitter():
    """Проверка корректного определения категории датчика давления."""
    val = TaxonomyAndGroundingValidator()
    cat = val.match_category("Преобразователь давления ОВЕН ПД100-ДИ", "токовый выход 4-20 мА")
    assert "давления" in cat["category_name"].lower()


def test_data_quality_detects_missing_and_clarifications():
    """Проверка выявления отсутствующих полей и числовых значений без единиц измерения."""
    val = TaxonomyAndGroundingValidator()
    cat = val.match_category("Манометр показывающий DM 02")
    
    # Передаем значение без единицы измерения (давление: 16)
    report = val.analyze_data_quality(
        name="Манометр показывающий DM 02",
        manufacturer="Манотомь",
        specs={"давление": "16", "диаметр": "100"},
        description="",
        category_info=cat
    )

    assert report.status == "requires_clarification"
    assert any("без указания единицы" in c for c in report.clarification_needed)


def test_grounding_verifier_flags_hallucinations():
    """Проверка, что выдуманные моделью цифры маркируются предупреждением."""
    val = TaxonomyAndGroundingValidator()
    input_payload = {
        "name": "Манометр DM 02",
        "manufacturer": "Манотомь",
        "specs": {"диапазон": "0-1,6 МПа"},
        "description": "корпус 100 мм"
    }

    test_specs = [
        KeySpecItem(parameter="Диапазон", value="0-1,6 МПа"),  # есть во входе
        KeySpecItem(parameter="Температура", value="данных нет"),  # допустимо
        KeySpecItem(parameter="Питание", value="24 В DC")  # выдуманное число 24
    ]

    verified = val.verify_grounding(test_specs, input_payload)
    assert "1,6 МПа" in verified[0].value
    assert verified[1].value == "данных нет"
    assert "требует проверки источника" in verified[2].value


def test_full_pipeline_generation():
    """Сквозная проверка генерации черновика карточки товара."""
    inp = ProductInput(
        name="Манометр показывающий DM 02",
        manufacturer="Манотомь",
        specs={
            "диапазон измерений": "0–1,6 МПа",
            "класс точности": "1,5",
            "присоединение": "G1/2",
            "диаметр корпуса": "100 мм"
        },
        description="Прибор предназначен для измерения избыточного давления."
    )

    res = card_service.generate_product_card(inp)
    
    # 1. Заголовок <= 70 символов
    assert res.seo_title_length <= 70
    assert len(res.seo_title) <= 70
    
    # 2. Описание от 800 до 1200 символов
    assert 800 <= res.seo_description_length <= 1200
    
    # 3. 3-5 поисковых запросов
    assert 3 <= len(res.search_queries) <= 5
    
    # 4. Наличие коммерческого блока и Markdown
    assert len(res.commercial_block.target_audience) > 10
    assert "# " in res.markdown_card


def test_api_health_endpoint(client):
    """Проверка эндпоинта /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["categories_loaded"] >= 200


def test_api_examples_endpoint(client):
    """Проверка эндпоинта получения примеров товаров."""
    res1 = client.get("/api/examples/1")
    assert res1.status_code == 200
    assert "DM 02" in res1.json()["name"]

    res2 = client.get("/api/examples/2")
    assert res2.status_code == 200
    assert "ПД100" in res2.json()["name"]


def test_api_generate_endpoint(client):
    """Проверка POST /api/generate."""
    payload = {
        "name": "Преобразователь давления ОВЕН ПД100-ДИ1,6-111-0,5",
        "manufacturer": "ОВЕН",
        "specs": {
            "диапазон измерений": "0...1,6 МПа",
            "выходной сигнал": "4...20 мА"
        },
        "description": "Датчик избыточного давления."
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "seo_title" in data
    assert data["seo_title_length"] <= 70
    assert len(data["key_specs"]) > 0


def test_specs_value_and_key_normalization():
    """Тестирование детерминированной нормализации единиц измерения и ключей КИПиА."""
    # Значения
    assert normalize_spec_value("0-1.6мпа") == "0–1,6 МПа"
    assert normalize_spec_value("g 1/2") == "G1/2"
    assert normalize_spec_value("g1/2\"") == "G1/2"
    assert normalize_spec_value("м20*1.5") == "M20×1,5"
    assert normalize_spec_value("4-20ма") == "4...20 мА"
    assert normalize_spec_value("24в dc") == "24 В DC"
    assert normalize_spec_value("+-0.5%") == "±0,5 %"
    assert normalize_spec_value("100мм") == "100 мм"
    assert normalize_spec_value("-50...+180 градусов цельсия") == "-50...+180 °C"
    assert normalize_spec_value("none") == "данных нет"
    assert normalize_spec_value("-") == "данных нет"

    # Ключи
    assert normalize_spec_key("диапазон") == "Диапазон измерений"
    assert normalize_spec_key("присоединение") == "Присоединительная резьба"
    assert normalize_spec_key("питание") == "Напряжение питания"
    assert normalize_spec_key("диаметр") == "Диаметр корпуса"


def test_grounding_normalizes_dirty_specs():
    """Проверка, что грязные спецификации нормализуются при валидации."""
    val = TaxonomyAndGroundingValidator()
    input_payload = {
        "name": "Манометр DM 02",
        "manufacturer": "Манотомь",
        "specs": {"диапазон": "0-1.6мпа", "штуцер": "g 1/2"},
        "description": "корпус 100мм"
    }

    test_specs = [
        KeySpecItem(parameter="диапазон", value="0-1.6мпа"),
        KeySpecItem(parameter="присоединение", value="g 1/2"),
        KeySpecItem(parameter="диаметр", value="100мм"),
        KeySpecItem(parameter="температура", value="none")
    ]

    verified = val.verify_grounding(test_specs, input_payload)
    
    assert verified[0].parameter == "Диапазон измерений"
    assert verified[0].value == "0–1,6 МПа"
    
    assert verified[1].parameter == "Присоединительная резьба"
    assert verified[1].value == "G1/2"
    
    assert verified[2].parameter == "Диаметр корпуса"
    assert verified[2].value == "100 мм"
    
    assert verified[3].value == "данных нет"

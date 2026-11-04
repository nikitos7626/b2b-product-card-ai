import json
from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.schemas import ProductInput, DraftCardResponse
from app.service import card_service

router = APIRouter(prefix="/api", tags=["Product Cards"])


@router.post(
    "/generate",
    response_model=DraftCardResponse,
    summary="Сгенерировать черновик карточки товара",
    response_description="Готовый черновик с SEO-заголовком, описанием, таблицей характеристик и отчетом о качестве данных"
)
def generate_card(product: ProductInput) -> DraftCardResponse:
    """
    Принимает входные данные прибора (название, производитель, характеристики, паспорт)
    и возвращает валидированный черновик карточки.

    Примечание: функция синхронная (def, а не async def), так как обращение к LLM и валидатору
    выполняется синхронно. FastAPI автоматически выполняет синхронные роуты в пуле потоков
    (threadpool), предотвращая блокировку главного цикла событий (event loop).
    """
    try:
        return card_service.generate_product_card(product)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректные входные данные: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации карточки: {str(e)}"
        )


@router.get(
    "/examples/{example_id}",
    summary="Получить тестовый пример товара (1 или 2)",
    response_description="Предзаполненный JSON с реальными параметрами прибора"
)
def get_example_product(example_id: int):
    """Возвращает предзаполненный JSON с данными по тестовым приборам."""
    filename = f"product_{example_id}.json"
    file_path = settings.data_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Пример {filename} не найден.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import ProductInput, DraftCardResponse
from app.service import card_service

app = FastAPI(
    title="AI-помощник подготовки карточек товаров B2B",
    description="Сервис генерации черновиков карточек контрольно-измерительных приборов для B2B интернет-магазина",
    version="1.0.0"
)

# Монтирование статических файлов
static_dir = settings.base_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", summary="Главная страница с веб-формой")
async def read_index():
    """Отдает веб-интерфейс для контент-менеджера."""
    index_file = settings.base_dir / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Веб-интерфейс доступен в /static/index.html"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Заглушка для favicon, чтобы браузер не спамил 404 в логах."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/health", summary="Проверка работоспособности сервиса")
async def health_check():
    """Легковесный health-check."""
    return {
        "status": "ok",
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "categories_loaded": len(card_service.validator.categories)
    }


@app.get("/api/examples/{example_id}", summary="Получить тестовый пример товара (1 или 2)")
async def get_example_product(example_id: int):
    """Возвращает предзаполненный JSON с данными по тестовым приборам."""
    filename = f"product_{example_id}.json"
    file_path = settings.data_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Пример {filename} не найден.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post(
    "/api/generate",
    response_model=DraftCardResponse,
    summary="Сгенерировать черновик карточки товара",
    response_description="Готовый черновик с SEO-заголовком, описанием, таблицей характеристик и отчетом о качестве данных"
)
async def generate_card(product: ProductInput):
    """
    Принимает JSON с информацией о приборе (название, производитель, характеристики, описание)
    и возвращает сгенерированный и валидированный черновик карточки.
    """
    try:
        draft = card_service.generate_product_card(product)
        return draft
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


if __name__ == "__main__":
    import uvicorn
    print(f"Запуск сервиса на http://{settings.app_host}:{settings.app_port}")
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)

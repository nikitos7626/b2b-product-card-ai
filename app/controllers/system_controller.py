from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse
from app.config import settings
from app.service import card_service

router = APIRouter(tags=["System"])


@router.get("/", summary="Главная страница с веб-формой")
def read_index():
    """Отдает статический веб-интерфейс для контент-менеджера."""
    index_file = settings.base_dir / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Веб-интерфейс доступен в /static/index.html"}


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Заглушка для favicon, предотвращающая 404 в логах сервера."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/health", summary="Проверка работоспособности сервиса")
def health_check():
    """Легковесный health-check состояния сервиса и загруженных категорий."""
    return {
        "status": "ok",
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "categories_loaded": len(card_service.validator.categories)
    }

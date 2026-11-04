from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.controllers import card_router, system_router


def create_app() -> FastAPI:
    """
    Фабрика создания приложения FastAPI.
    Отвечает исключительно за инициализацию приложения, подключение
    контроллеров (роутеров) и монтирование статических ресурсов.
    """
    application = FastAPI(
        title="AI-помощник подготовки карточек товаров B2B",
        description="Сервис генерации черновиков карточек контрольно-измерительных приборов для B2B интернет-магазина",
        version="1.0.0"
    )

    # Монтирование статических файлов (css, js, assets)
    static_dir = settings.base_dir / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Регистрация модульных контроллеров
    application.include_router(system_router)
    application.include_router(card_router)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    print(f"Запуск сервиса на http://{settings.app_host}:{settings.app_port}")
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)

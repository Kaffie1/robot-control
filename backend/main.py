from .api import create_app
from .config import APP_HOST, APP_PORT

app = create_app()


def main() -> None:
    import uvicorn

    print(f"Robot Upgrade Web 已启动: http://{APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="info", access_log=False)


if __name__ == "__main__":
    main()

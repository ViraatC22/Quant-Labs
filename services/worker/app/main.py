import os
import signal
import time


def main() -> None:
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"worker started; redis_url={redis_url}")

    while running:
        time.sleep(5)

    print("worker stopped")


if __name__ == "__main__":
    main()

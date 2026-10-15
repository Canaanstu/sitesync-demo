import time
from .sync import enqueue_due

if __name__ == '__main__':
    while True:
        try:
            enqueue_due()
        except Exception:
            print('Scheduler could not enqueue work. Check Redis and database connectivity.', flush=True)
        time.sleep(60)

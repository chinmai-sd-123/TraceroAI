from uuid import UUID
import time
import redis
from app.core.config import get_settings
from app.services.deep_eval_queue import QUEUE_NAME
from app.services.deep_evaluation import run_deep_evaluation


def main() -> None:
    """Worker that listens to the deep_eval queue and processes trace_ids."""
    settings = get_settings()
    if not settings.redis_url:
        raise SystemExit("Traceroai Redis URL is not configured. Please set the REDIS_URL environment variable.")
    

    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    print(f"[worker] waiting for jobs on queue '{QUEUE_NAME}'...")

    while True:
        try:
            item = client.brpop(QUEUE_NAME, timeout=2)  # Wait for a job with a timeout
        except redis.exceptions.ConnectionError as e:
            print(f"[worker] Redis connection error: {e}. Retrying :{e}", flush=True)
            time.sleep(1)
            continue

        if item is None:
            continue  # No job received, loop again

        _, trace_id = item
        print(f"[worker] processing trace_id: {trace_id}", flush=True)
        try:
            run_deep_evaluation(UUID(trace_id))
        except Exception as e:
            print(f"[worker] error processing trace_id {trace_id}: {e}", flush=True)

if __name__ == "__main__":
    main()
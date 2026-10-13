from concurrent.futures import ThreadPoolExecutor, as_completed

def parallel(fn, items, workers: int):
    """Yield fn(item) results as they finish."""
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(fn, item) for item in items]
    try:
        for future in as_completed(futures):
            yield future.result()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
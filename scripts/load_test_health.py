"""
Простой нагрузочный прогон HTTP (для отчёта по практике / раздел 5.4.5).

Пример:
    uv run python scripts/load_test_health.py --url http://localhost:8000/health -n 500 -c 20

Перед запуском поднимите API Gateway (порт 8000 по умолчанию).
"""
from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import time
from typing import Any

import httpx


async def _one(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> tuple[bool, float]:
    t0 = time.perf_counter()
    async with sem:
        try:
            r = await client.get(url)
            ok = 200 <= r.status_code < 300
        except Exception:
            ok = False
    dt = time.perf_counter() - t0
    return ok, dt


async def run_load(url: str, total: int, concurrency: int, timeout: float) -> dict[str, Any]:
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=concurrency + 10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        t_wall0 = time.perf_counter()
        tasks = [_one(client, url, sem) for _ in range(total)]
        results = await asyncio.gather(*tasks)
        wall = time.perf_counter() - t_wall0

    oks = [ok for ok, _ in results]
    latencies = [dt for _, dt in results]
    success = sum(1 for ok in oks if ok)
    failed = total - success
    rps = total / wall if wall > 0 else 0.0
    if latencies:
        sl = sorted(latencies)
        p95_idx = min(len(sl) - 1, max(0, math.ceil(0.95 * len(sl)) - 1))
        p95_s = sl[p95_idx]
    else:
        p95_s = 0.0
    return {
        "url": url,
        "requests": total,
        "concurrency": concurrency,
        "success": success,
        "failed": failed,
        "wall_seconds": wall,
        "rps": rps,
        "latency_mean_ms": statistics.mean(latencies) * 1000 if latencies else 0.0,
        "latency_p95_ms": p95_s * 1000,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Нагрузочный прогон GET (по умолчанию /health шлюза)")
    p.add_argument("--url", default="http://localhost:8000/health", help="URL для GET")
    p.add_argument("-n", type=int, default=300, help="Число запросов")
    p.add_argument("-c", type=int, default=15, help="Параллельность (одновременных запросов)")
    p.add_argument("--timeout", type=float, default=10.0, help="Таймаут одного запроса, с")
    args = p.parse_args()

    if args.n < 1 or args.c < 1:
        raise SystemExit("Ожидаются -n >= 1 и -c >= 1")

    stats = asyncio.run(run_load(args.url, args.n, args.c, args.timeout))
    err_pct = 100.0 * stats["failed"] / stats["requests"] if stats["requests"] else 0.0

    print("=== Нагрузочный прогон ===")
    print(f"URL:              {stats['url']}")
    print(f"Запросов (n):     {stats['requests']}")
    print(f"Параллельность:   {stats['concurrency']}")
    print(f"Успешно:          {stats['success']}")
    print(f"Ошибок:           {stats['failed']}  ({err_pct:.2f} %)")
    print(f"Время (wall):     {stats['wall_seconds']:.3f} s")
    print(f"RPS:              {stats['rps']:.1f}")
    print(f"Latency mean:     {stats['latency_mean_ms']:.1f} ms")
    print(f"Latency p95:      {stats['latency_p95_ms']:.1f} ms")
    print("==========================")


if __name__ == "__main__":
    main()

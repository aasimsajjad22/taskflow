import asyncio
import time

import httpx

urls = [
    f"http://localhost:8000/fake/{n}/?delay=1" for n in ["weather", "holidays", "exchange-rates"]
]

start = time.perf_counter()
with httpx.Client() as client:
    data = [client.get(url).json()["service"] for url in urls]

print("httpx sync:", data, round(time.perf_counter() - start, 2), "s")


async def fetch_all():
    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(*(client.get(url) for url in urls))

        return [r.json()["service"] for r in responses]


start = time.perf_counter()
data = asyncio.run(fetch_all())
print("httpx async + gather:", data, round(time.perf_counter() - start, 2), "s")

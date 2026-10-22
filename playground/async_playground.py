import asyncio
import time

# def make_drink_sync(name):
#     time.sleep(1)
#     return f"{name} ready"
#
# start = time.perf_counter()
# results = [make_drink_sync(n) for n in ["tea", "juice", "coffee"]]
#
# print("sync:", results, round(time.perf_counter() - start, 2), "s")


# ASYNC: "async def" makes a COROUTINE: a function that can pause at "await".
async def make_drink_async(name):
    # await asyncio.sleep(): pause HERE and let the event loop run other coroutines.
    await asyncio.sleep(1)
    return f"{name} ready"


# gather(): start several coroutines together and wait until ALL are done.
async def main():
    return await asyncio.gather(
        make_drink_async("tea"), make_drink_async("coffee"), make_drink_async("juice")
    )


# asyncio.run(): create an event loop, run main() in it, then close the loop.
start = time.perf_counter()
results = asyncio.run(main())
print("async + gather:", results, round(time.perf_counter() - start, 2), "s")


# A COMMON MISTAKE: async functions, but awaited one after another.
async def main_one_by_one():
    out = []
    for n in ["tea", "coffee", "juice"]:
        out.append(await make_drink_async(n))
    return out


start = time.perf_counter()
asyncio.run(main_one_by_one())
print("async but awaited one by one:", round(time.perf_counter() - start, 2), "s")

#
# # ANOTHER COMMON MISTAKE: calling an async function without "await" doesn't run it.
# coroutine = make_drink_async("x")
# print("calling without await gives:", type(coroutine).__name__)
# coroutine.close()

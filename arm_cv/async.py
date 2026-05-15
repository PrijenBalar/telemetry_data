import asyncio
import aiohttp

BASE_URL = "http://192.168.4.1"

async def move_stepper(session, num, angle):
    url = f"{BASE_URL}/stepper?num={num}&angle={angle}"
    try:
        async with session.get(url, timeout=10) as resp:
            text = await resp.text()
            print(text, f"stepper {num} angle {angle}")
    except Exception as e:
        print("Error:", e)

async def main():
    async with aiohttp.ClientSession() as session:
        for i in range(100):

            # Move both steppers at the SAME TIME
            await asyncio.gather(
                move_stepper(session, 3, -15),
                move_stepper(session, 2, -15)
            )

            await asyncio.sleep(2)

            await asyncio.gather(
                move_stepper(session, 3, 0),
                move_stepper(session, 2, 0)
            )

            await asyncio.sleep(2)

    print("Motion finished")

# ===================== RUN =====================
asyncio.run(main())

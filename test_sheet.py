import asyncio
import httpx

SHEET_ID = "17cgprZE6fp7PpNCve3zHlLWXWdiN07ZsK2ZiiKiv8XI"

async def test():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Catalogo"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        print(r.text[:800])

asyncio.run(test())
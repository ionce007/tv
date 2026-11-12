   
import asyncio
from pytdxdata import TdxData
from pytdxdata.models import KlinePeriod

async def main():
    async with TdxData() as td:
        for start in [6400, 7200, 8000, 8800, 9600]:
            bars = await td.get_bars('sh000001', KlinePeriod.DAY, start=start, count=800)
            if bars:
                print(f'start={start}: {bars[0].year}-{bars[0].month:02d}-{bars[0].day:02d} ~ {bars[-1].year}-{bars[-1].month:02d}-{bars[-1].day:02d} ({len(bars)}根)')
            else:
                print(f'start={start}: 空')
                break

asyncio.run(main())

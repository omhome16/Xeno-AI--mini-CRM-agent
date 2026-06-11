import asyncio
import time
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        print("Testing API speeds...")
        
        # Test /brand
        start = time.perf_counter()
        res_brand = await client.get("http://127.0.0.1:8000/brand")
        brand_time = time.perf_counter() - start
        print(f"/brand status: {res_brand.status_code} | time: {brand_time:.4f}s")
        
        # Test /api/customers/stats
        start = time.perf_counter()
        res_stats = await client.get("http://127.0.0.1:8000/api/customers/stats")
        stats_time = time.perf_counter() - start
        print(f"/api/customers/stats status: {res_stats.status_code} | time: {stats_time:.4f}s")
        
        # Test /api/campaigns
        start = time.perf_counter()
        res_camp = await client.get("http://127.0.0.1:8000/api/campaigns")
        camp_time = time.perf_counter() - start
        print(f"/api/campaigns status: {res_camp.status_code} | time: {camp_time:.4f}s")

if __name__ == "__main__":
    asyncio.run(main())

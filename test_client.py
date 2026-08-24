import asyncio
import httpx
from src.core.database import engine
from src.models.tenant import Tenant
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def setup_test_tenant():
    """Create a dummy tenant so we have an API key to use."""
    async with AsyncSession(engine) as session:
        # Check if exists
        result = await session.execute(select(Tenant).where(Tenant.api_key == "test_key_123"))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                name="Test Organization",
                api_key="test_key_123",
                budget_limit_usd=10.0,
                tier="pro"
            )
            session.add(tenant)
            await session.commit()
            print("✅ Created Test Tenant with API Key: 'test_key_123'")
        else:
            print("✅ Test Tenant already exists.")

async def send_chat_request():
    """Send a request to our FastAPI Gateway."""
    url = "http://127.0.0.1:8000/v1/chat/completions"
    headers = {
        "X-API-Key": "test_key_123",
        "Content-Type": "application/json"
    }
    # Notice we don't strictly need to specify a model; the Gateway router will pick one!
    # But you can pass a specific model to override it. 
    # If your OpenAI account is out of quota, you can switch to Gemini by uncommenting the line below!
    payload = {
        # "model": "gpt-4o-mini",          # Requires OPENAI_API_KEY with active billing
        "model": "gemini/gemini-3.6-flash", # Requires GEMINI_API_KEY
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ]
    }
    
    print("\n🚀 Sending request to Gateway...")
    async with httpx.AsyncClient() as client:
        # LiteLLM needs an API key in the environment to forward to providers!
        # Make sure OPENAI_API_KEY is set in your .env if using OpenAI models.
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        
        if response.status_code == 200:
            data = response.json()
            print("\n🟢 Gateway Response:")
            print(data["choices"][0]["message"]["content"])
        else:
            print(f"\n🔴 Error {response.status_code}: {response.text}")

async def main():
    await setup_test_tenant()
    await send_chat_request()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from app.services.medical.service import MedicalAgentService

async def test_no_date():
    service = MedicalAgentService()
    await service.initialize()
    
    # Simulate a query without a date
    response = await service.handle_chat("test_user_1", "幫我查一下數據")
    print("Response text:", response["text"])
    print("Intent:", response["intent"])

if __name__ == "__main__":
    asyncio.run(test_no_date())

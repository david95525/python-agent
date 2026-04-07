import asyncio
from app.services.medical.service import MedicalAgentService

async def test_modern_interrupt():
    service = MedicalAgentService()
    await service.initialize()
    
    user_id = "modern_test_user"
    
    # 第一輪：不帶日期
    print("\n--- 第一輪：不帶日期的請求 ---")
    response1 = await service.handle_chat(user_id, "幫我查一下數據")
    print("AI 回覆:", response1["text"])
    print("意圖:", response1["intent"])
    
    if response1["intent"] == "interrupt":
        # 第二輪：提供日期
        print("\n--- 第二輪：提供日期 ---")
        response2 = await service.handle_chat(user_id, "昨天")
        print("AI 回覆:", response2["text"])
        print("意圖:", response2["intent"])

if __name__ == "__main__":
    asyncio.run(test_modern_interrupt())

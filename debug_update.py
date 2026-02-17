import telegram
from telegram import Update, Message, Chat, User
import asyncio
import sys

print(f"Telegram version: {telegram.__version__}")
print(f"Update location: {Update}")

async def main():
    try:
        # Construct a dummy update
        u = Update(update_id=1, message=Message(message_id=1, date=None, chat=Chat(id=1, type="private"), from_user=User(id=1, first_name="test", is_bot=False)))
        print(f"Effective user: {u.effective_user}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

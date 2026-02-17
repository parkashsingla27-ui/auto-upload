# ===== CONFIG — loaded from .env file =====
from dotenv import load_dotenv
load_dotenv()

import os, moviepy as mp, json, warnings
warnings.filterwarnings("ignore", message=".*FFMPEG_AudioReader.*")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
USER_TOKENS_FILE = "user_tokens.json"

YOUTUBE_CREDENTIALS = {
    "client_id": os.environ["YOUTUBE_CLIENT_ID"],
    "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
    "token_uri": "https://oauth2.googleapis.com/token"
}

from gtts import gTTS
from langdetect import detect

from moviepy import AudioFileClip, ImageClip, CompositeVideoClip

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

STATE = {}
os.makedirs("backgrounds", exist_ok=True)



def load_user_tokens():
    if os.path.exists(USER_TOKENS_FILE):
        with open(USER_TOKENS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_token(user_id, token):
    tokens = load_user_tokens()
    tokens[str(user_id)] = token
    with open(USER_TOKENS_FILE, "w") as f:
        json.dump(tokens, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    STATE[update.effective_chat.id] = {"images": []}
    await update.message.reply_text("📌 Send topic")

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        token = context.args[0]
        save_user_token(user_id, token)
        await update.message.reply_text("✅ Token saved successfully!")
        # Try to delete the message containing the token for security
        try:
            await update.message.delete()
        except:
            pass
    except IndexError:
        await update.message.reply_text("⚠️ Usage: /set_token <your_refresh_token>")

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handles /set token <token>
    try:
        if context.args[0].lower() == "token":
            # Treat as set_token, using the second argument as the token
            # We mock the context.args for the set_token function or just call save logic directly
            try:
                token = context.args[1]
                save_user_token(update.effective_user.id, token)
                await update.message.reply_text("✅ Token saved successfully!")
                try:
                    await update.message.delete()
                except:
                    pass
            except IndexError:
                 await update.message.reply_text("⚠️ Usage: /set token <your_refresh_token>")
        else:
            await update.message.reply_text("⚠️ Unknown setting. Did you mean '/set token'?")
    except IndexError:
        await update.message.reply_text("⚠️ Usage: /set token <your_refresh_token>")



async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    text = update.message.text

    if chat not in STATE:
        return

    state = STATE[chat]

    if "topic" not in state:
        state["topic"] = text
        await update.message.reply_text("✍️ Send prompt")
        return

    if "prompt" not in state:
        state["prompt"] = text
        await update.message.reply_text("🖼 Send 4+ images")
        return


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    if chat not in STATE:
        return

    state = STATE[chat]

    file = await update.message.photo[-1].get_file()
    path = f"backgrounds/bg{len(state['images'])}.jpg"
    await file.download_to_drive(path)

    state["images"].append(path)

    await update.message.reply_text(f"📸 Image {len(state['images'])} saved")

    if len(state["images"]) >= 4:
        await update.message.reply_text("🎬 Creating video…")

        try:
            link = create_video_and_upload(
                state["topic"],
                state["prompt"],
                state["images"],
                update.effective_user.id
            )
            await update.message.reply_text(f"✅ Uploaded!\n{link}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        STATE.pop(chat)


def create_video_and_upload(topic, prompt, images, user_id):
    lang = "hi" if detect(prompt) in ["hi", "mr"] else "en"

    gTTS(prompt, lang=lang).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")

    duration = max(audio.duration, 15)

    clips = []
    t = 0
    i = 0

    while t < duration:
        clip = (
            ImageClip(images[i % len(images)])
            .with_duration(3)
            .resized((1080, 1920))
        )
        clips.append(clip)
        t += 3
        i += 1

    bg = mp.concatenate_videoclips(clips).subclipped(0, duration)

    final = CompositeVideoClip([bg]).with_audio(audio)

    final.write_videofile(
        "output.mp4",
        fps=30,
        codec="libx264",
        audio_codec="aac"
    )

    return upload_to_youtube(topic, prompt, user_id)


def upload_to_youtube(topic, desc, user_id):
    tokens = load_user_tokens()
    refresh_token = tokens.get(str(user_id))
    
    if not refresh_token:
        raise Exception("Refresh token not found. Use /set_token <token> first.")

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri=YOUTUBE_CREDENTIALS["token_uri"],
        client_id=YOUTUBE_CREDENTIALS["client_id"],
        client_secret=YOUTUBE_CREDENTIALS["client_secret"]
    )

    yt = build("youtube", "v3", credentials=creds)

    req = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": topic,
                "description": desc,
                "categoryId": "22"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload("output.mp4")
    )

    res = req.execute()
    return f"https://youtube.com/watch?v={res['id']}"


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_token", set_token))
    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()

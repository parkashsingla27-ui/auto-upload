# ===== CONFIG — loaded from .env file =====
from dotenv import load_dotenv
load_dotenv()

import os, moviepy as mp, json, warnings, datetime
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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

STATE = {}
os.makedirs("backgrounds", exist_ok=True)
os.makedirs("videos", exist_ok=True)


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
    await update.message.reply_text(
        "👋 Welcome! I can create videos from text and images, and upload them to YouTube.\n\n"
        "Use /menu to see options or just send a topic to start."
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Create Video", callback_data="start_flow")],
        [InlineKeyboardButton("🔑 Set Token", callback_data="set_token_info")],
        [InlineKeyboardButton("📜 Show All Commands", callback_data="show_commands")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 **Main Menu**:", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == "start_flow":
        STATE[chat_id] = {"images": []}
        await query.message.reply_text("📌 Send topic")
        
    elif query.data == "set_token_info":
        await query.message.reply_text("To set your YouTube refresh token, use:\n`/set token <your_token>`", parse_mode="Markdown")
        
    elif query.data == "show_commands":
        help_text = (
            "**🤖 Available Commands:**\n\n"
            "/start - Start the bot\n"
            "/menu - Show main menu\n"
            "/set - Set configurations (e.g., /set token <token>)\n"
            "/set_token - Alias for setting token\n"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown")
        
    elif query.data == "upload_now":
        if chat_id in STATE and "video_path" in STATE[chat_id]:
            await query.message.edit_text("🚀 Uploading now...")
            try:
                link = upload_to_youtube(
                    STATE[chat_id]["video_path"],
                    STATE[chat_id]["topic"],
                    STATE[chat_id]["prompt"],
                    update.effective_user.id
                )
                await query.message.reply_text(f"✅ Uploaded!\n{link}")
            except Exception as e:
                await query.message.reply_text(f"❌ Error: {str(e)}")
            
            # Cleanup
            cleanup_chat(chat_id)
        else:
            await query.message.reply_text("❌ Session expired or video not found.")

    elif query.data == "schedule":
        if chat_id in STATE and "video_path" in STATE[chat_id]:
            STATE[chat_id]["status"] = "scheduling"
            await query.message.edit_text(
                "📅 **Scheduling**\n\n"
                "Please enter the time in **HH:MM** format (24-hour).\n"
                "Example: `14:30` for 2:30 PM today.\n"
                "Or `+X` for X minutes from now (e.g., `+10`).",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text("❌ Session expired.")

def cleanup_chat(chat_id):
    if chat_id in STATE:
        # Optional: Delete files (images, video) to save space
        # For now, keeping them as per original logic implies we overwrite or just keep
        STATE.pop(chat_id)

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        token = context.args[0]
        save_user_token(user_id, token)
        await update.message.reply_text("✅ Token saved successfully!")
        try:
            await update.message.delete()
        except:
            pass
    except IndexError:
        await update.message.reply_text("⚠️ Usage: /set_token <your_refresh_token>")

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.args[0].lower() == "token":
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
    
    # Handle Scheduling Input
    if state.get("status") == "scheduling":
        try:
            delay_seconds = 0
            human_time = ""
            
            if text.startswith("+"):
                # Relative time in minutes
                mins = int(text.replace("+", ""))
                delay_seconds = mins * 60
                run_time = datetime.datetime.now() + datetime.timedelta(minutes=mins)
                human_time = f"in {mins} minutes"
            else:
                # Absolute time HH:MM
                now = datetime.datetime.now()
                target_time = datetime.datetime.strptime(text, "%H:%M").time()
                run_time = datetime.datetime.combine(now.date(), target_time)
                
                if run_time < now:
                    # If time passed today, assume tomorrow
                    run_time += datetime.timedelta(days=1)
                
                delay_seconds = (run_time - now).total_seconds()
                human_time = f"at {run_time.strftime('%Y-%m-%d %H:%M')}"

            context.job_queue.run_once(
                scheduled_upload_job,
                delay_seconds,
                chat_id=chat,
                data={
                    "chat_id": chat,
                    "video_path": state["video_path"],
                    "topic": state["topic"],
                    "prompt": state["prompt"],
                    "user_id": update.effective_user.id
                }
            )
            
            await update.message.reply_text(f"✅ Video scheduled to upload {human_time}!")
            cleanup_chat(chat)
            
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use HH:MM or +X (e.g., 14:30 or +10). try again.")
        return

    if "topic" not in state:
        state["topic"] = text
        await update.message.reply_text("✍️ Send prompt")
        return

    if "prompt" not in state:
        state["prompt"] = text
        await update.message.reply_text("🖼 Send 4+ images")
        return


async def scheduled_upload_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    
    try:
        await context.bot.send_message(chat_id, "⏰ Running scheduled upload...")
        link = upload_to_youtube(
            job_data["video_path"],
            job_data["topic"],
            job_data["prompt"],
            job_data["user_id"]
        )
        await context.bot.send_message(chat_id, f"✅ Scheduled Upload Complete!\n{link}")
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Scheduled Upload Failed: {str(e)}")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    if chat not in STATE:
        return

    state = STATE[chat]
    # If we are in scheduling mode, ignore photos or reset? 
    # Let's assume photos only valid during image collection.
    if state.get("status") == "scheduling":
        return

    file = await update.message.photo[-1].get_file()
    path = f"backgrounds/{chat}_bg{len(state['images'])}.jpg"
    await file.download_to_drive(path)

    state["images"].append(path)

    await update.message.reply_text(f"📸 Image {len(state['images'])} saved")

    if len(state["images"]) >= 4:
        await update.message.reply_text("🎬 Creating video, please wait...")

        try:
            video_path = create_video(
                state["topic"],
                state["prompt"],
                state["images"],
                chat
            )
            state["video_path"] = video_path
            
            # Show Options
            keyboard = [
                [InlineKeyboardButton("🚀 Upload Now", callback_data="upload_now")],
                [InlineKeyboardButton("📅 Schedule", callback_data="schedule")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "✅ Video created! What would you like to do?",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error creating video: {str(e)}")
            STATE.pop(chat)


def create_video(topic, prompt, images, chat_id):
    lang = "hi" if detect(prompt) in ["hi", "mr"] else "en"

    voice_path = f"voice_{chat_id}.mp3"
    gTTS(prompt, lang=lang).save(voice_path)
    audio = AudioFileClip(voice_path)

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
    
    output_filename = f"videos/output_{chat_id}_{int(datetime.datetime.now().timestamp())}.mp4"

    final.write_videofile(
        output_filename,
        fps=30,
        codec="libx264",
        audio_codec="aac"
    )
    
    # Clean up voice file
    try:
        os.remove(voice_path)
        audio.close() # Close to release file lock
    except:
        pass

    return output_filename


def upload_to_youtube(video_path, topic, desc, user_id):
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
        media_body=MediaFileUpload(video_path)
    )

    res = req.execute()
    return f"https://youtube.com/watch?v={res['id']}"


def main():
    # Start a simple health check server for Railway/Render
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
        def log_message(self, *args):
            pass  # suppress logs

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Health check on port {port}")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("set_token", set_token))
    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()

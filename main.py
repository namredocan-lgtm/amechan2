# Minimal web server for Render keep-alive
import threading
from flask import Flask
import discord
import asyncio
import os
import dotenv
from discord.ext import commands
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError
from dotenv import load_dotenv
load_dotenv()
# === CONFIG ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CAI_TOKEN = os.getenv("CAI_TOKEN")
CHARACTER_ID = os.getenv("CHARACTER_ID", "yR-BB03I0cV75kPajA7xmOpkngAAxMcwAslUGv0eAdE")

# === Discord Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True  # needed for reading messages
bot = commands.Bot(command_prefix='!', intents=intents)

# === Character.AI Setup ===
cai_client = None
chat = None
allowed_channel_id = None  # Store the allowed channel ID

@bot.event
async def on_ready():
    global cai_client, chat
    if not CAI_TOKEN:
        print("❌ CAI_TOKEN not found in environment variables")
        return

    cai_client = await get_client(token=CAI_TOKEN)
    me = await cai_client.account.fetch_me()
    chat, greeting_message = await cai_client.chat.create_chat(CHARACTER_ID)

    print(f"✅ Logged in as {bot.user}")
    print(f"🤖 Connected to Character.AI as @{me.username}")
    print(f"💬 Greeting: {greeting_message.get_primary_candidate().text}")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    global allowed_channel_id
    allowed_channel_id = ctx.channel.id
    await ctx.send(f"✅ Bot has been set up to work only in this channel: {ctx.channel.mention}")
    print(f"🔧 Bot restricted to channel: {ctx.channel.name} ({ctx.channel.id})")

@bot.command(name="status")
async def status_command(ctx):
    global allowed_channel_id
    
    if allowed_channel_id:
        channel = bot.get_channel(allowed_channel_id)
        channel_info = channel.mention if channel else f"Channel ID: {allowed_channel_id}"
        status_msg = f"🔒 Bot is restricted to: {channel_info}"
    else:
        status_msg = "🌐 Bot works in all channels (no restriction set)"
    
    await ctx.send(status_msg)

@bot.event
async def on_message(message):
    global chat, allowed_channel_id
    
    if message.author == bot.user:
        return  # ignore the bot's own messages
    
    # Process commands first
    await bot.process_commands(message)
    
    # If it's a command, don't process as AI chat
    if message.content.startswith(bot.command_prefix):
        return
    
    # Check if bot should only respond in the configured channel
    if allowed_channel_id and message.channel.id != allowed_channel_id:
        # If bot is mentioned in other channels, still respond
        if bot.user in message.mentions:
            try:
                # Remove the mention from the message content
                content = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
                if not content:  # If message only contains mention
                    content = "Hello!"
                
                # Send user message to Character.AI
                response = await cai_client.chat.send_message(
                    CHARACTER_ID, chat.chat_id, content
                )
                # Reply with mention
                await message.reply(response.get_primary_candidate().text)
            except SessionClosedError:
                await message.channel.send("⚠️ Session closed. Please restart the bot.")
        return  # Don't process further if not in allowed channel

    try:
        # Send user message to Character.AI (auto-chat in allowed channel)
        response = await cai_client.chat.send_message(
            CHARACTER_ID, chat.chat_id, message.content
        )
        # Reply ONLY with the text (no author name)
        await message.channel.send(response.get_primary_candidate().text)

    except SessionClosedError:
        await message.channel.send("⚠️ Session closed. Please restart the bot.")

@bot.event
async def on_disconnect():
    if cai_client:
        await cai_client.close_session()

# === Minimal Flask web server for Render keep-alive ===
def run_web():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Bot is running!"

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not found in environment variables")
    print("Please add your Discord bot token to the Secrets tab")
else:
    # Start the web server in a separate thread
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN)
import discord
import os
import random
import asyncio
import yt_dlp
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

# --- PHẦN 1: WEB SERVER ẢO (Để UptimeRobot ping) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot đang chạy ngon lành trên Render!"

def run_web():
    # Render yêu cầu chạy ở port mặc định hoặc 10000
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- PHẦN 2: DISCORD BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')
LOFI_URL = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Cấu hình nhạc
YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True', 'quiet': True}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

@bot.event
async def on_ready():
    print(f'{bot.user} đã online!')

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice: return await ctx.send("Vào voice đi bạn ơi!")
    if not ctx.voice_client: await ctx.author.voice.channel.connect()
    
    await ctx.send(f"🔎 Đang tìm: {query}...")
    
    # Xử lý lấy link nhạc
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            url = info['url']
            title = info['title']
            
            vc = ctx.voice_client
            if vc.is_playing(): vc.stop()
            
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            await ctx.send(f"🎶 Đang phát: **{title}**")
        except Exception as e:
            await ctx.send("Lỗi rồi: " + str(e))

@bot.command()
async def stop(ctx):
    if ctx.voice_client: ctx.voice_client.stop()

# --- CHẠY ---
if __name__ == "__main__":
    keep_alive() # Bật web server trước
    if TOKEN:
        bot.run(TOKEN)

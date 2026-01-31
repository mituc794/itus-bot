import discord
import os
import asyncio
import yt_dlp
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- PHẦN 1: WEB SERVER (Giữ bot sống trên Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot SoundCloud đang chạy ổn định!"

def run_web():
    # Render yêu cầu chạy ở port 10000
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- PHẦN 2: CẤU HÌNH BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')

# Cấp quyền
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Cấu hình yt-dlp (Thêm User-Agent để tránh bị chặn)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'default_search': 'scsearch', # Mặc định tìm trên SoundCloud
    'source_address': '0.0.0.0',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
}

# Cấu hình FFmpeg (QUAN TRỌNG: Fix lỗi ngắt kết nối 4006 và allowed_extensions)
FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
        '-protocol_whitelist file,http,https,tcp,tls,crypto '
        '-allowed_extensions ALL' 
    ),
    'options': '-vn'
}

# --- PHẦN 3: LOGIC BOT ---

@bot.event
async def on_ready():
    print(f'✅ Bot đã online: {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="SoundCloud"))

@bot.command()
async def play(ctx, *, query):
    """Phát nhạc từ SoundCloud (Fix lỗi disconnect)"""
    
    # 1. Kiểm tra và vào phòng Voice
    if not ctx.author.voice:
        return await ctx.send("❌ Bạn phải vào phòng Voice trước đã!")
    
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
    
    await ctx.send(f"☁️ Đang tìm trên SoundCloud: **{query}**...")
    
    try:
        # 2. Xử lý tìm kiếm (Link hoặc Từ khóa)
        # Nếu không phải link http thì thêm scsearch: vào đầu
        search_query = query if query.startswith('http') else f"scsearch:{query}"

        # Chạy yt-dlp trong luồng riêng (Non-blocking)
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(search_query, download=False))

        # Lấy thông tin bài hát đầu tiên
        if 'entries' in data:
            data = data['entries'][0]
            
        song_url = data['url']
        title = data.get('title', 'Nhạc SoundCloud')
        artist = data.get('uploader', 'Unknown')

        vc = ctx.voice_client
        
        # 3. Phát nhạc
        if vc.is_playing():
            vc.stop()
            
        # Truyền options đã fix lỗi vào đây
        vc.play(discord.FFmpegPCMAudio(song_url, **FFMPEG_OPTIONS))
        
        await ctx.send(f"🎶 Đang phát: **{title}** - {artist}")
        
    except Exception as e:
        print(f"Lỗi Play: {e}")
        await ctx.send("❌ Lỗi: Không thể phát bài này (Thử bài khác xem sao).")

@bot.command()
async def stop(ctx):
    """Dừng nhạc và thoát"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Bye bye!")

@bot.command()
async def skip(ctx):
    """Bỏ qua bài hiện tại"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Next!")

# --- PHẦN 4: KHỞI CHẠY ---
if __name__ == "__main__":
    keep_alive() # Bật Web Server
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Lỗi: Chưa có DISCORD_TOKEN trong Environment Variables")

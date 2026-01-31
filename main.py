import discord
import os
import asyncio
import yt_dlp
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- PHẦN 1: WEB SERVER ẢO (Giữ bot sống trên Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord (SoundCloud Edition) đang chạy!"

def run_web():
    # Render yêu cầu chạy ở port 10000
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- PHẦN 2: CẤU HÌNH BOT ---
TOKEN = os.getenv('DISCORD_TOKEN')

# Cấp quyền cho bot
intents = discord.Intents.default()
intents.message_content = True # Để đọc tin nhắn
intents.voice_states = True    # Để quản lý voice

bot = commands.Bot(command_prefix='!', intents=intents)

# Cấu hình yt-dlp chuyên cho SoundCloud (scsearch)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'default_search': 'scsearch', # Mặc định tìm trên SoundCloud
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# Cấu hình FFmpeg để stream mượt, tự kết nối lại nếu rớt mạng
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn' # Không lấy hình ảnh
}

# --- PHẦN 3: CÁC SỰ KIỆN VÀ LỆNH ---

@bot.event
async def on_ready():
    print(f'✅ Bot đã online: {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="SoundCloud"))

@bot.command()
async def play(ctx, *, query):
    """Phát nhạc từ SoundCloud. Ví dụ: !play đen vâu"""
    
    # 1. Kiểm tra Voice
    if not ctx.author.voice:
        return await ctx.send("❌ Bạn phải vào phòng Voice trước đã!")
    
    # 2. Kết nối Bot vào phòng
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
    
    await ctx.send(f"☁️ Đang tìm trên SoundCloud: **{query}**...")
    
    # 3. Tìm và phát nhạc
    try:
        # Nếu query là link (http...) thì để nguyên, nếu là từ khóa thì thêm scsearch:
        search_query = query if query.startswith('http') else f"scsearch:{query}"

        # Chạy yt-dlp trong luồng riêng để không làm đơ bot
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(search_query, download=False))

        # Xử lý kết quả tìm kiếm (SoundCloud thường trả về danh sách 'entries')
        if 'entries' in data:
            data = data['entries'][0]
            
        song_url = data['url']
        title = data.get('title', 'Nhạc SoundCloud')
        artist = data.get('uploader', 'Unknown')

        vc = ctx.voice_client
        
        # Nếu đang hát bài khác thì dừng
        if vc.is_playing():
            vc.stop()
            
        # Phát nhạc
        vc.play(discord.FFmpegPCMAudio(song_url, **FFMPEG_OPTIONS))
        
        await ctx.send(f"🎶 Đang phát: **{title}** - {artist}")
        
    except Exception as e:
        print(f"Lỗi: {e}")
        await ctx.send("❌ Không tìm thấy bài hát hoặc lỗi kết nối SoundCloud.")

@bot.command()
async def stop(ctx):
    """Dừng nhạc và mời bot ra ngoài"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Bye bye! Hẹn gặp lại.")
    else:
        await ctx.send("Bot có ở trong phòng đâu mà đuổi?")

@bot.command()
async def skip(ctx):
    """Bỏ qua bài hiện tại (Nếu đang dùng chế độ playlist - Code này hiện tại chỉ stop)"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Đã bỏ qua bài hát.")

# --- PHẦN 4: CHẠY ---
if __name__ == "__main__":
    keep_alive() # Khởi động Web Server
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Lỗi: Chưa tìm thấy biến môi trường DISCORD_TOKEN")

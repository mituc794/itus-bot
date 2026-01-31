import discord
import os
import asyncio
import yt_dlp
import random
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

# --- WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Study (Full Version) Online!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- CẤU HÌNH ---
TOKEN = os.getenv('DISCORD_TOKEN')

LOFI_PLAYLIST = [
    "https://soundcloud.com/relaxdaily/sets/deep-focus-music-studying-concentration-work",
]

QUOTES = [
    # --- HỆ CODER (Dành cho dân IT) ---
    "Code chạy rồi thì ĐỪNG CÓ SỬA NỮA! 🛑",
    "Một ngày code, 23 giờ fix bug. Cố lên! 🐛",
    "Đừng deploy vào thứ 6, và đừng lười vào thứ 2! 📅",
    "Feature này không lỗi, đó là tính năng ẩn đấy! 😎",
    "Ngồi thẳng lưng lên! Còng lưng là lương không tăng đâu! a🦴",
    "Bạn có chắc là đã lưu file chưa? Ctrl+S cái nữa cho chắc! 💾",
    "Cao thủ không bằng tranh thủ. Code lẹ đi ngủ nào! 💤",

    # --- HỆ "TƯ BẢN" (Động lực bằng tiền) ---
    "Kiến thức hôm nay là 'Sổ đỏ' ngày mai! 🏠",
    "Làm việc đi, Tư bản không nuôi người lười đâu! 💸",
    "Đừng để số dư tài khoản buồn, hãy làm cho nó vui! 💰",
    "Khổ trước sướng sau, thế mới giàu! 🚀",
    "Ngủ giờ này thì chỉ có mơ thấy tiền, chứ không kiếm được tiền đâu! 😴",

    # --- HỆ "CÀ KHỊA" (Tỉnh ngủ ngay) ---
    "Deadline dí tới mông rồi kìa, chạy lẹ đi! 🔥",
    "Việc hôm nay chớ để ngày mai, vì ngày mai... lười y hệt hôm nay! 🐸",
    "Thất bại là mẹ thành công, nhưng thất học là mẹ của nghèo khổ! 📚",
    "Áp lực tạo kim cương, nhưng đừng tự tạo nghiệp là được! 💎",
    "Đừng nhìn màn hình nữa, nhìn vào tương lai tăm tối nếu không học kìa! 🌑",

    # --- HỆ "CHILL" (Nhắc nhở nhẹ nhàng) ---
    "Uống ngụm nước đi, não cần nước để tưới mát! 💧",
    "Hít thở sâu nào... Rồi code tiếp! 🍃",
    "Mắt mỏi chưa? Nhìn ra xa 20 giây đi bạn ơi! 👀",
    "Thương bản thân thì học cho xong đi rồi ngủ ngon! ❤️"
]

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True 

# Tắt help mặc định để dùng help tự chế
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

queues = {}
pomo_sessions = {}
DEFAULT_VOLUME = 0.5

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True', 
    'extract_flat': 'in_playlist',
    'quiet': True,
    'default_search': 'scsearch', 
    'source_address': '0.0.0.0',
    'http_headers': {'User-Agent': 'Mozilla/5.0...'}
}
YTDL_SINGLE_OPTIONS = YTDL_OPTIONS.copy()
YTDL_SINGLE_OPTIONS['noplaylist'] = True
YTDL_SINGLE_OPTIONS['extract_flat'] = False

FFMPEG_OPTIONS = {
    'before_options': ('-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -protocol_whitelist file,http,https,tcp,tls,crypto -allowed_extensions ALL'),
    'options': '-vn'
}

# --- LỆNH HELP (MỚI THÊM) ---

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🤖 HƯỚNG DẪN SỬ DỤNG BOT",
        description="Bot hỗ trợ học tập: Nhạc SoundCloud + Pomodoro + Động lực",
        color=0x00ff00 # Màu xanh lá
    )
    
    # Cột 1: Nhạc
    embed.add_field(
        name="🎵 Âm Nhạc (SoundCloud)",
        value=(
            "`!play <tên/link>`: Phát nhạc (Hỗ trợ Playlist)\n"
            "`!skip`: Qua bài\n"
            "`!stop`: Dừng nhạc & Xóa hàng chờ\n"
            "`!volume <0-100>`: Chỉnh âm lượng\n"
            "`!queue`: Xem danh sách chờ"
        ),
        inline=False
    )
    
    # Cột 2: Học tập
    embed.add_field(
        name="🍅 Pomodoro (Học/Nghỉ)",
        value=(
            "`!pomo`: Bắt đầu (25p Học / 5p Nghỉ)\n"
            "`!pomo <học> <nghỉ>`: Tùy chỉnh (VD: !pomo 50 10)\n"
            "`!stop_pomo`: Dừng tính giờ"
        ),
        inline=False
    )
    
    # Cột 3: Tính năng ẩn
    embed.add_field(
        name="✨ Tính Năng Tự Động",
        value=(
            "- **Autoplay:** Hết nhạc tự động bật Lofi Radio.\n"
            "- **Động lực:** Nhắc nhở, gửi quote mỗi 45 phút.\n"
            "- **Clean Chat:** Tự xóa tin nhắn rác sau 5s."
        ),
        inline=False
    )
    
    embed.set_footer(text="Code by You | Chúc bạn học tốt! 🚀")
    await ctx.send(embed=embed)

# --- LOGIC NHẠC ---

def check_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        query = queues[guild_id].pop(0)
        coro = play_source(ctx, query)
        asyncio.run_coroutine_threadsafe(coro, bot.loop)
    else:
        random_playlist = random.choice(LOFI_PLAYLIST)
        coro = play_source(ctx, random_playlist, is_autoplay=True)
        asyncio.run_coroutine_threadsafe(coro, bot.loop)

async def play_source(ctx, query, is_autoplay=False):
    try:
        search_query = query if query.startswith('http') else f"scsearch:{query}"
        loop = asyncio.get_event_loop()
        
        # Tải thông tin
        data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(search_query, download=False))
        song_info = None
        
        if 'entries' in data:
            entries = list(data['entries'])
            if is_autoplay:
                entry = random.choice(entries)
                song_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_SINGLE_OPTIONS).extract_info(entry['url'], download=False))
            else:
                if query.startswith('http'): 
                    first_entry = entries[0]
                    song_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_SINGLE_OPTIONS).extract_info(first_entry['url'], download=False))
                    added_count = 0
                    for entry in entries[1:]:
                        if entry.get('url'):
                            queues[ctx.guild.id].append(entry['url'])
                            added_count += 1
                    if added_count > 0:
                        await ctx.send(f"✅ Đã thêm **{added_count}** bài từ Playlist vào hàng chờ!", delete_after=5)
                else:
                    first_entry = entries[0]
                    song_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_SINGLE_OPTIONS).extract_info(first_entry['url'], download=False))
        else:
            song_info = data

        if not song_info: return
        song_url = song_info['url']
        title = song_info.get('title', 'Nhạc Chill')
        
        vc = ctx.voice_client
        if not vc: return

        source = discord.FFmpegPCMAudio(song_url, **FFMPEG_OPTIONS)
        transformed_source = discord.PCMVolumeTransformer(source, volume=DEFAULT_VOLUME)
        
        vc.play(transformed_source, after=lambda e: check_queue(ctx))
        
        if not is_autoplay:
            await ctx.send(f"🎶 Đang phát: **{title}**")
            
    except Exception as e:
        print(f"Lỗi Play: {e}")
        check_queue(ctx)

# --- LOGIC POMODORO ---

async def run_pomodoro(ctx, work, break_time):
    guild_id = ctx.guild.id
    while pomo_sessions.get(guild_id, False):
        await ctx.send(f"🍅 **BẮT ĐẦU HỌC! ({work}p)**\nCất điện thoại đi nhé!")
        for _ in range(work * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)
        
        if not pomo_sessions.get(guild_id, False): return
        await ctx.send(f"☕ **GIẢI LAO! ({break_time}p)**\nĐứng dậy vươn vai nào!")
        for _ in range(break_time * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)

@bot.command()
async def pomo(ctx, work: int = 25, break_time: int = 5):
    guild_id = ctx.guild.id
    if pomo_sessions.get(guild_id, False):
        return await ctx.send("⚠️ Đang chạy rồi! Gõ `!stop_pomo` để tắt.", delete_after=5)
    pomo_sessions[guild_id] = True
    await ctx.send(f"✅ **Pomodoro Start:** {work}p Học / {break_time}p Nghỉ.")
    bot.loop.create_task(run_pomodoro(ctx, work, break_time))

@bot.command()
async def stop_pomo(ctx):
    pomo_sessions[ctx.guild.id] = False
    await ctx.send("🛑 Đã dừng Pomodoro.", delete_after=5)

# --- CÁC LỆNH KHÁC ---

@bot.event
async def on_ready():
    print(f'✅ Bot Online: {bot.user}')
    if not send_motivation.is_running():
        send_motivation.start()

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice: 
        return await ctx.send("❌ Vào voice đi!", delete_after=5)
    if not ctx.voice_client: 
        await ctx.author.voice.channel.connect()
    
    if ctx.guild.id not in queues: queues[ctx.guild.id] = []
    
    vc = ctx.voice_client
    if vc.is_playing():
        queues[ctx.guild.id].append(query)
        await ctx.send(f"✅ Đã thêm queue: **{query}**", delete_after=5)
    else:
        await play_source(ctx, query)

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skip!", delete_after=5)

@bot.command()
async def stop(ctx):
    if ctx.guild.id in queues: queues[ctx.guild.id].clear()
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Bye!", delete_after=5)

@bot.command()
async def queue(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        # Chỉ hiển thị 10 bài đầu tiên để đỡ spam
        list_nhac = "\n".join([f"{i+1}. {bai}" for i, bai in enumerate(queues[ctx.guild.id][:10])])
        if len(queues[ctx.guild.id]) > 10:
            list_nhac += f"\n... và {len(queues[ctx.guild.id]) - 10} bài nữa."
        await ctx.send(f"📜 **Danh sách chờ:**\n{list_nhac}")
    else:
        await ctx.send("📭 Hàng chờ trống (Đang chạy chế độ Auto Radio).", delete_after=5)

@bot.command()
async def volume(ctx, vol: int):
    global DEFAULT_VOLUME
    if 0 <= vol <= 100:
        DEFAULT_VOLUME = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = DEFAULT_VOLUME
        await ctx.send(f"🔊 Vol: {vol}%", delete_after=5)

@tasks.loop(minutes=45) 
async def send_motivation():
    for vc in bot.voice_clients:
        if len(vc.channel.members) > 1:
            try:
                await vc.guild.system_channel.send(f"🔔 **Nhắc nhở:** {random.choice(QUOTES)}")
            except: pass

@send_motivation.before_loop
async def before_motivation():
    await bot.wait_until_ready()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)

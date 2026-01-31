import discord
import os
import asyncio
import yt_dlp
import random
from groq import AsyncGroq 
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread

# --- WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "ITUS Bot (Bestie Salty Ver) Online!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- CẤU HÌNH ---
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Cấu hình AI Groq (ASYNC)
client = None
if GROQ_API_KEY:
    client = AsyncGroq(api_key=GROQ_API_KEY)
else:
    print("⚠️ Chưa có GROQ_API_KEY. Chat AI sẽ không chạy.")

# --- PERSONA ITUS BOT (HỆ CHỊ EM BẠN DÌ) ---
SYSTEM_PROMPT = """
Bạn là ITUS Bot, một người bạn thân thiết (bestie) của sinh viên ITUS.
Cách xưng hô: Xưng 'Tui', gọi người dùng là 'Pà' (hoặc 'Mấy pà', 'Bà').
Tính cách: Xéo xắt, hài hước, hay cà khịa nhưng rất quan tâm. Giọng điệu tự nhiên như bạn bè tám chuyện.
Style: Dùng emoji vui vẻ, thoải mái (🤣, 👌, 💅, ✨, 🌚, 🔪).
Ví dụ: "Sao dzạ pà?", "Học lẹ đi má ơi!", "Trời ơi tin được hông, bug này mà cũng để xảy ra á!".
"""

LOFI_PLAYLIST = [
    "https://soundcloud.com/relaxing-music-production/sets/piano-for-studying",
]

# --- KHO QUOTE "MẶN CHÁT" (Cập nhật mới) ---
QUOTES = [
    # Hệ Cà Khịa Cực Mạnh
    "Học không chơi đánh rơi tuổi trẻ, mà chơi không học là bán rẻ tương lai nha pà! 🌚",
    "Người yêu cũ nó có bồ mới rồi kìa, pà còn ngồi đó chưa fix xong bug hả? 💅",
    "Deadline dí tới mông rồi mà vẫn ung dung lướt TikTok, gan pà lớn thiệt á! 🔪",
    "Rớt môn là tốn tiền học lại đó, tiền đó để đi đu idol sướng hơn hông? 💸",
    "Đừng để nước tới chân mới nhảy, nhảy hông kịp đâu, chết chìm đó má ơi! 🌊",
    "Nhìn cái màn hình đen thui, chắc tương lai pà cũng... à mà thôi học đi! 🤣",
    
    # Hệ Dân IT (Sự thật mất lòng)
    "Code chạy được thì ĐỪNG CÓ SỬA, tui lạy pà đó! 🙏",
    "Bug là tính năng, nhưng bug nhiều quá là do... nhân phẩm pà đó! 😎",
    "Một bug, hai bug, ba bug... Thôi đi ngủ đi, càng sửa càng nát à! 😴",
    "Nhớ Ctrl+S chưa dzạ? Mất code là tui cười vô mặt chứ hông ai cứu đâu nha! 💾",

    # Hệ Quan Tâm (Nhưng vẫn xéo xắt)
    "Uống miếng nước đi, da dẻ hồng hào code nó mới mượt, ngồi khô queo ai nhìn! 💧",
    "Thức khuya ít thôi, mắt thâm như gấu trúc rồi, ai mà thèm yêu! 🐼",
    "Học lẹ đi rồi đi ngủ, tui thấy pà ngáp nãy giờ 80 lần rồi đó! 🥱",
    "Tắt cái tab Facebook giùm tui cái, tui méc giảng viên bây giờ! 👀"
]

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

queues = {}
pomo_sessions = {}
DEFAULT_VOLUME = 0.5

YTDL_OPTIONS = {
    'format': 'bestaudio[protocol*="m3u8"]/bestaudio[protocol*="http"]/bestaudio',
    'noplaylist': 'True', 'extract_flat': 'in_playlist',
    'quiet': True, 'default_search': 'scsearch', 'source_address': '0.0.0.0',
    'http_headers': {'User-Agent': 'Mozilla/5.0...'},
    'ignoreerrors': True, 'no_warnings': True
}
YTDL_SINGLE_OPTIONS = YTDL_OPTIONS.copy()
YTDL_SINGLE_OPTIONS['noplaylist'] = True
YTDL_SINGLE_OPTIONS['extract_flat'] = False

FFMPEG_OPTIONS = {
    'before_options': ('-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -protocol_whitelist file,http,https,tcp,tls,crypto -allowed_extensions ALL'),
    'options': '-vn'
}

# --- HÀM GỬI TIN NHẮN ---
async def send_to_voice(ctx, message, delete_after=None):
    if ctx.voice_client and ctx.voice_client.channel:
        await ctx.voice_client.channel.send(message, delete_after=delete_after)
    else:
        await ctx.send(message, delete_after=delete_after)

# --- SỰ KIỆN CHAT AI ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # Chat khi tag @Bot
    if bot.user.mentioned_in(message):
        if not client:
            await message.reply("🥺 Tui chưa được cài não (Groq API) rùi pà ơi...")
            return

        async with message.channel.typing():
            try:
                user_content = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
                if not user_content:
                    await message.reply("Sao dzạ pà? Kêu tui chi á? 👀")
                    return

                chat_completion = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    model="llama-3.3-70b-versatile", # Model xịn nhất
                    max_tokens=1024,
                    temperature=0.8 # Tăng độ sáng tạo cho nó mặn hơn
                )
                
                reply = chat_completion.choices[0].message.content
                
                if len(reply) > 2000:
                    for i in range(0, len(reply), 2000):
                        await message.reply(reply[i:i+2000])
                else:
                    await message.reply(reply)

            except Exception as e:
                print(f"Lỗi AI: {e}")
                await message.reply("Mạng mẽo chán quá pà ơi, load hổng nổi luôn á! 😵‍💫")

# --- CÁC LỆNH KHÁC ---

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="✨ ITUS Bot (Hệ Mặn Mòi) ✨", description="Tag `@ITUS Bot` để nghe tui cà khịa nha!", color=0xffb6c1) 
    embed.add_field(name="💌 Tám Chuyện", value="Tag tên tui để hỏi bài hoặc than thở.", inline=False)
    embed.add_field(name="🎶 Nghe Nhạc", value="`!pomo`, `!play`, `!stop` - Tui cân hết!", inline=False)
    await ctx.send(embed=embed)

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
        data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info(search_query, download=False))
        
        song_info = None
        if 'entries' in data:
            entries = list(data['entries'])
            entry = random.choice(entries) if is_autoplay else entries[0]
            song_info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YTDL_SINGLE_OPTIONS).extract_info(entry['url'], download=False))
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
            await send_to_voice(ctx, f"🎶 Đang phát **{title}** cho pà nghe nè! ✨")
            
    except Exception as e:
        print(f"Lỗi Play: {e}")
        check_queue(ctx)

async def run_pomodoro(ctx, work, break_time):
    guild_id = ctx.guild.id
    while pomo_sessions.get(guild_id, False):
        await send_to_voice(ctx, f"🍅 **TẬP TRUNG NHA PÀ ƠI! ({work}p)**\nCất cái điện thoại giùm tui cái, tui canh chừng rồi! 😎")
        for _ in range(work * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)
        if not pomo_sessions.get(guild_id, False): return
        await send_to_voice(ctx, f"☕ **NGHỈ XÍU ĐI PÀ! ({break_time}p)**\nĐứng dậy vươn vai, đi uống nước đi! 🙆‍♂️")
        for _ in range(break_time * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)

@bot.command()
async def pomo(ctx, work: int = 25, break_time: int = 5):
    guild_id = ctx.guild.id
    if pomo_sessions.get(guild_id, False):
        return await send_to_voice(ctx, "⚠️ Tui đang canh giờ rồi mà! Muốn dừng thì bảo `!stop_pomo` ha.", delete_after=5)
    
    if ctx.author.voice:
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        if not ctx.voice_client.is_playing():
             random_playlist = random.choice(LOFI_PLAYLIST)
             await play_source(ctx, random_playlist, is_autoplay=True)
             await send_to_voice(ctx, "🎶 Tui bật nhạc Lofi cho pà tập trung nha! ✨", delete_after=5)

    pomo_sessions[guild_id] = True
    await send_to_voice(ctx, f"✅ **Pomodoro Start:** {work}p Học / {break_time}p Nghỉ.\nRáng học đi nha pà! 🥰")
    bot.loop.create_task(run_pomodoro(ctx, work, break_time))

@bot.command()
async def stop_pomo(ctx):
    pomo_sessions[ctx.guild.id] = False
    await send_to_voice(ctx, "🛑 Rồi, cho pà nghỉ xả hơi đó! Giỏi quá chừng! ❤️", delete_after=5)

@bot.event
async def on_ready():
    print(f'✅ Bot Online: {bot.user}')
    if not send_motivation.is_running():
        send_motivation.start()

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice: return await ctx.send("❌ Vào phòng Voice với tui đi đã pà ơi! 🥺", delete_after=5)
    if not ctx.voice_client: await ctx.author.voice.channel.connect()
    if ctx.guild.id not in queues: queues[ctx.guild.id] = []
    
    vc = ctx.voice_client
    if vc.is_playing():
        queues[ctx.guild.id].append(query)
        await send_to_voice(ctx, f"✅ Tui thêm **{query}** vào hàng đợi rùi nha! ✨", delete_after=5)
    else:
        await play_source(ctx, query)

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await send_to_voice(ctx, "⏭️ Okie, qua bài khác liền! 😋", delete_after=5)

@bot.command()
async def stop(ctx):
    if ctx.guild.id in queues: queues[ctx.guild.id].clear()
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await send_to_voice(ctx, "👋 Tui đi ngủ đây, pà cũng nghỉ ngơi đi nha! Bye bye! 💖", delete_after=5)

@bot.command()
async def volume(ctx, vol: int):
    global DEFAULT_VOLUME
    if 0 <= vol <= 100:
        DEFAULT_VOLUME = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = DEFAULT_VOLUME
        await send_to_voice(ctx, f"🔊 Tui chỉnh loa mức **{vol}%** rồi nha! 👌", delete_after=5)

@tasks.loop(minutes=45) 
async def send_motivation():
    for vc in bot.voice_clients:
        if len(vc.channel.members) > 1:
            try:
                await vc.channel.send(f"🔔 **Nhắc nhẹ:** {random.choice(QUOTES)}")
            except: pass

@send_motivation.before_loop
async def before_motivation():
    await bot.wait_until_ready()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)

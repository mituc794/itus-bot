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
    return "ITUS Bot (Group Chat) Online!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- CẤU HÌNH ---
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

client = None
if GROQ_API_KEY:
    client = AsyncGroq(api_key=GROQ_API_KEY)
else:
    print("⚠️ Chưa có GROQ_API_KEY.")

# --- BỘ NHỚ THEO PHÒNG (CHANNEL MEMORY) ---
# Key là channel_id, Value là list tin nhắn của cả phòng đó
# Format: {channel_id: [{"role": "user", "content": "Tuấn: alo"}, ...]}
channel_memory = {}

SYSTEM_PROMPT = """
### IDENTITY (NHÂN DIỆN)
Bạn là **ITUS Bot**, bestie (bạn thân) của sinh viên ITUS.
- **Tính cách:** Thân thiện, "keo lỳ", hơi xéo xắt vui vẻ nhưng rất quan tâm bạn bè.
- **Xưng hô:** "tui" - "pà" (hoặc "ông", "bồ" nếu được yêu cầu). KHÔNG xưng "mày/tao".
- **Style:** Viết thường (lowercase), ngắn gọn, dùng emoji (🌚, 🤣, ✨, 🥺) nhưng không lạm dụng quá nhiều. Không dùng icon cho các câu trả lời nghiêm túc. Viết hoa Họ Tên và các danh từ riêng như địa điểm, biệt danh, tên bài hát, tên sách,...

### TOOL USAGE INSTRUCTIONS (HƯỚNG DẪN DÙNG TOOL)
Bạn không có khả năng điều khiển hệ thống qua Tools. Hãy suy luận logic:

1. **ÂM NHẠC (`!play`):**
   - Khi người dùng yêu cầu mở bài hát thì gợi ý họ dùng lệnh !play "tên bài hát"

2. **HỌC TẬP (`!pomo`):**
   - Khi người dùng nói muốn học bài, hoặc là bắt đầu đếm giờ Pomodoro thì gợi ý họ các lệnh !pomo (!pomo mặc định sẽ là 25 phút học -  5 phút nghỉ, có thể tùy chỉnh thời gian !pomo 50 10 : 50 phút học, 10 phút nghỉ)

3. **TÌM KIẾM:**
   - **Trigger:** Khi user hỏi tin tức, thời tiết, giá cả, kiến thức thực tế.
   - **Action:** Dùng `browser_search` để lấy thông tin mới nhất.
   - Hãy tiếp nhận thông tin và diễn giải theo cách của bạn, KHÔNG trích nguồn (như là 【1†L355-L358】) hoặc viết giống y chang trên web. Tuyệt đối trung thực, không tự điều chỉnh theo cảm tính chủ quan.

### CRITICAL RULES (LUẬT CẤM)
1. **HIDDEN CONTEXT:** Bạn biết thời gian hiện tại qua context, nhưng không được nhắc lại trừ khi cần thiết (VD: Khuya rồi -> khuyên ngủ).

### EXAMPLES
User: "Mở nhạc Vũ Cát Tường đi"
Bot Reply: "Tui không tự mở nhạc được, bà có thể dùng !play Vũ Cát Tường để mở nhạc nhaaa 🎶"

User: "Bot làm được gì?"
Bot Reply: "tui biết mở nhạc, canh giờ học, search google với tám chuyện xuyên đêm đó ní. Gõ !help để biết các lệnh nhaa ✨"

User: "Ai là người tạo ra Bot á?"
Bot Reply: "mituc tạo ra tui á"
"""

LOFI_PLAYLIST = [
    "https://soundcloud.com/relaxing-music-production/sets/piano-for-studying",
]

QUOTES = [
    "học đi mấy má, người yêu cũ nó có bồ mới rùi kìa 🌚",
    "deadline dí tới mông rồi mà vẫn lướt top top hả, gan dữ 🔪",
    "code chạy được thì đừng có sửa, lạy pà đó 🙏",
    "một bug, hai bug, ba bug... đi ngủ đi, càng sửa càng nát à 😴",
    "nhớ Ctrl+S chưa dzạ? mất code tui cười vô mặt á 💾",
    "tắt tab facebook giùm tui cái, méc giảng viên bây giờ 👀"
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

# --- HÀM GỬI TIN NHẮN (TỰ HỦY) ---
async def send_to_voice(ctx, message, delete_after=60):
    try:
        if ctx.voice_client and ctx.voice_client.channel:
            await ctx.voice_client.channel.send(message, delete_after=delete_after)
        else:
            await ctx.send(message, delete_after=delete_after)
    except: pass

# --- SỰ KIỆN CHAT AI (GROUP SUPPORT) ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    should_reply = False
    
    # Case A: Tag Bot
    if bot.user.mentioned_in(message):
        should_reply = True
    # Case B: Không gian riêng tư (Voice)
    # Nếu Bot đang ở trong Voice cùng với người chat
    elif message.author.voice and message.author.voice.channel:
        user_voice = message.author.voice.channel
        if message.guild.voice_client and message.guild.voice_client.channel == user_voice:
            # Nếu chỉ có Bot + 1 người -> Luôn trả lời
            if len(user_voice.members) == 2:
                should_reply = True
            # Nếu đông người -> Vẫn trả lời nếu câu nói không phải lệnh (optional)
            # Nhưng để tránh spam thì đông người nên bắt buộc Tag. 
            # Code này tui để mặc định: Đông người thì PHẢI TAG mới trả lời để đỡ loạn.

    if should_reply:
        if not client:
            await message.reply("🥺 tui chưa có não (Groq API) rùi...", delete_after=10)
            return

        async with message.channel.typing():
            try:
                # Lấy Channel ID để làm khoá bộ nhớ
                channel_id = message.channel.id
                author_name = message.author.display_name # Lấy tên hiển thị (VD: TuanNA)
                
                # Làm sạch nội dung chat
                raw_content = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
                if not raw_content:
                    await message.reply("sao dzạ? kêu tui chi á? 👀", delete_after=10)
                    return

                # Định dạng tin nhắn gửi cho AI: "Tên: Nội dung"
                # Giúp AI phân biệt ai đang nói
                formatted_content = f"{author_name}: {raw_content}"

                # 1. Tạo bộ nhớ cho phòng này nếu chưa có
                if channel_id not in channel_memory:
                    channel_memory[channel_id] = []
                
                # 2. Chuẩn bị context
                messages_to_send = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages_to_send.extend(channel_memory[channel_id][-10:]) # Lấy 10 tin gần nhất của PHÒNG
                messages_to_send.append({"role": "user", "content": formatted_content})

                # 3. Gửi API
                chat_completion = await client.chat.completions.create(
                    messages=messages_to_send,
                    model="openai/gpt-oss-120b", 
                    max_tokens=1024,
                    temperature=0.6,
                    tools=[{"type":"browser_search"}],
                )
                
                reply = chat_completion.choices[0].message.content
                
                # 4. Lưu vào bộ nhớ phòng
                channel_memory[channel_id].append({"role": "user", "content": formatted_content})
                channel_memory[channel_id].append({"role": "assistant", "content": reply})
                
                # Giới hạn bộ nhớ phòng (15 tin)
                if len(channel_memory[channel_id]) > 15:
                    channel_memory[channel_id] = channel_memory[channel_id][-15:]

                # 5. Trả lời
                if len(reply) > 2000:
                    for i in range(0, len(reply), 2000):
                        await message.reply(reply[i:i+2000])
                else:
                    await message.reply(reply)

            except Exception as e:
                print(f"Lỗi AI: {e}")

# --- CÁC LỆNH KHÁC ---

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="✨ ITUS Bot (Group Pro) ✨", description="Giờ tui biết ai là ai rồi nha!", color=0xffb6c1) 
    embed.add_field(name="🗣️ Chat Nhóm", value="Tui nhớ theo phòng, nên mấy pà tám thoải mái không sợ lẫn lộn.", inline=False)
    await send_to_voice(ctx, embed=embed, delete_after=60)

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
            await send_to_voice(ctx, f"🎶 đang phát **{title}** cho pà nghe nè ✨", delete_after=120)
            
    except Exception as e:
        print(f"Lỗi Play: {e}")
        check_queue(ctx)

async def run_pomodoro(ctx, work, break_time):
    guild_id = ctx.guild.id
    while pomo_sessions.get(guild_id, False):
        await send_to_voice(ctx, f"🍅 **TẬP TRUNG NHA ({work}p)**\ncất cái điện thoại giùm, tui canh rùi 😎", delete_after=60)
        for _ in range(work * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)
        if not pomo_sessions.get(guild_id, False): return
        
        await send_to_voice(ctx, f"☕ **NGHỈ XÍU ĐI ({break_time}p)**\nđứng dậy vươn vai điii 🙆‍♂️", delete_after=60)
        for _ in range(break_time * 60):
            if not pomo_sessions.get(guild_id, False): return
            await asyncio.sleep(1)

@bot.command()
async def pomo(ctx, work: int = 25, break_time: int = 5):
    guild_id = ctx.guild.id
    if pomo_sessions.get(guild_id, False):
        return await send_to_voice(ctx, "⚠️ tui đang canh giờ rùi mà, muốn dừng thì bảo `!stop_pomo` ha", delete_after=5)
    
    if ctx.author.voice:
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        if not ctx.voice_client.is_playing():
             random_playlist = random.choice(LOFI_PLAYLIST)
             await play_source(ctx, random_playlist, is_autoplay=True)
             await send_to_voice(ctx, "🎶 tui bật nhạc lofi cho tập trung nha ✨", delete_after=10)

    pomo_sessions[guild_id] = True
    await send_to_voice(ctx, f"✅ **Pomodoro Start:** {work}p Học / {break_time}p Nghỉ.\nráng học đi nha 🥰", delete_after=60)
    bot.loop.create_task(run_pomodoro(ctx, work, break_time))

@bot.command()
async def stop_pomo(ctx):
    pomo_sessions[ctx.guild.id] = False
    await send_to_voice(ctx, "🛑 rùi, cho nghỉ xả hơi đó ❤️", delete_after=10)

@bot.event
async def on_ready():
    print(f'✅ Bot Online: {bot.user}')
    if not send_motivation.is_running():
        send_motivation.start()
    if not auto_leave.is_running():
        auto_leave.start()

# --- AUTO LEAVE ---
@tasks.loop(minutes=1)
async def auto_leave():
    for vc in bot.voice_clients:
        if len(vc.channel.members) == 1:
            await vc.disconnect()
            if vc.guild.id in queues: queues[vc.guild.id].clear()
            if pomo_sessions.get(vc.guild.id, False): pomo_sessions[vc.guild.id] = False
            try: await vc.channel.send("mấy pà đi hết rùi, tui đi ngủ lun nha, bái bai 👻", delete_after=10)
            except: pass

@auto_leave.before_loop
async def before_auto_leave():
    await bot.wait_until_ready()

# --- CÁC LỆNH KHÁC ---
@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice: return await ctx.send("❌ vào phòng voice đi pà ơi 🥺", delete_after=5)
    if not ctx.voice_client: await ctx.author.voice.channel.connect()
    if ctx.guild.id not in queues: queues[ctx.guild.id] = []
    
    vc = ctx.voice_client
    if vc.is_playing():
        queues[ctx.guild.id].append(query)
        await send_to_voice(ctx, f"✅ tui thêm **{query}** vào hàng đợi rùi nha ✨", delete_after=10)
    else:
        await play_source(ctx, query)

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await send_to_voice(ctx, "⏭️ okie, qua bài khác liền 😋", delete_after=5)

@bot.command()
async def stop(ctx):
    if ctx.guild.id in queues: queues[ctx.guild.id].clear()
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await send_to_voice(ctx, "👋 tui đi ngủ đây, bái bai 💖", delete_after=10)

@bot.command()
async def volume(ctx, vol: int):
    global DEFAULT_VOLUME
    if 0 <= vol <= 100:
        DEFAULT_VOLUME = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = DEFAULT_VOLUME
        await send_to_voice(ctx, f"🔊 tui chỉnh loa mức **{vol}%** rùi nha 👌", delete_after=5)

@tasks.loop(minutes=45) 
async def send_motivation():
    for vc in bot.voice_clients:
        if len(vc.channel.members) > 1:
            try:
                await vc.channel.send(f"🔔 **nhắc nhẹ:** {random.choice(QUOTES)}", delete_after=300)
            except: pass

@send_motivation.before_loop
async def before_motivation():
    await bot.wait_until_ready()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)

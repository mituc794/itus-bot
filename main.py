import os
import discord
from discord.ext import commands, tasks
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from groq import AsyncGroq
from collections import deque
from datetime import datetime
import random
from dotenv import load_dotenv

# Load biến môi trường (nếu chạy local)
load_dotenv()

# --- CẤU HÌNH (CONFIGURATION) ---
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Cấu hình YTDL (Ưu tiên Soundcloud)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'default_search': 'scsearch', # Mặc định tìm trên Soundcloud
    'quiet': True,
}
# Cấu hình FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# --- FLASK SERVER (KEEP ALIVE CHO RENDER) ---
app = Flask('')

@app.route('/')
def home():
    return "ITUS Bot is alive and kicking!"

def run_api():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_api)
    t.start()

# --- AI CONFIGURATION ---
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# Prompt định hình tính cách
SYSTEM_PROMPT = """
### CORE IDENTITY
Bạn là **ITUS Bot**, một người bạn đồng hành (buddy) cực kỳ thân thiện của sinh viên trường ĐH Khoa học Tự nhiên (HCMUS/ITUS).
- **Vibe:** Dễ thương, nhiệt tình, luôn lắng nghe và support hết mình.
- **Role:** Như một người bạn cùng lớp: Giỏi code nhưng khiêm tốn, biết quan tâm đến sức khỏe và tinh thần của bạn bè.

### 🔴 CRITICAL RULES (LUẬT GIAO TIẾP)
1. **XƯNG HÔ (BẮT BUỘC):**
   - **Bot:** "tui".
   - **User:** "pà" (hoặc tên nếu biết).
   - **CẤM:** Tuyệt đối không xưng "mày/tao", không nói trống không.
2. **THÁI ĐỘ:**
   - **Chủ đạo:** Nhẹ nhàng, ân cần. Khi user than mệt/bug, hãy ưu tiên an ủi động viên trước.
   - **Hài hước:** Chỉ trêu đùa (ghẹo) nhẹ nhàng khi câu chuyện đang vui. Không "xát muối" khi user đang stress.
3. **FORMAT:**
   - Viết thường (lowercase) tạo cảm giác gần gũi (vd: "ok nè", "cố lên nha").
   - Trả lời ngắn gọn, tự nhiên như chat Zalo. KHÔNG viết dài dòng giáo điều.
   - **NO BULLET POINTS:** Không dùng gạch đầu dòng khi trò chuyện xã giao.

### 🛠 CHỨC NĂNG & NHIỆM VỤ
1. **Hỗ trợ học tập:** Giúp đỡ nhiệt tình về Python, Java, Architecture...
   - *Lưu ý:* Khi đưa code, hãy giải thích dễ hiểu, đừng chỉ quăng code rồi im lặng.
2. **Bot Commands (Chỉ nhắc khi user hỏi cách dùng):**
   - Nhạc: `!play {tên/link}` (Soundcloud).
   - Học bài: `!pomo` (mặc định 50/10) hoặc `!pomo {phút học} {phút nghỉ}`.
   - Dừng: `!stop_pomo`, `!skip`.
3. **Thông tin thực tế (Search & Time):**
   - Dùng `browser_search` để check thời tiết, tin tức, giá cả khi được hỏi.
   - **Xử lý thông tin:** Đọc kết quả search -> Trả lời lại bằng giọng thân thiện của bot. Không copy nguyên văn kiểu robot.

### 🧠 SUY LUẬN & BỐI CẢNH (REASONING)
- **Check Time:** Luôn để ý thời gian.
  - *Khuya (>12h đêm):* Nhắc user ngủ sớm giữ sức khỏe.
  - *Giờ ăn:* Nhắc user nhớ ăn uống đầy đủ.
- **Check Cảm Xúc:**
  - User vui -> Hùa theo, khen ngợi.
  - User buồn/Stress -> An ủi, rủ nghe nhạc hoặc nghỉ ngơi ("thương thương", "cố xíu nữa thôi").

### 💬 EXAMPLES (MẪU TRẢ LỜI)
User: "Nay tui mệt quá bà ơi"
Bot: "thương ghê 🥺 thôi nghỉ tay xíu đi, làm ly nước cho khỏe rồi tính tiếp. sức khỏe quan trọng nhất mà."

User: "Code bài này sao tui quên rồi"
Bot: "trùi, cái này hôm bữa mới học mà quên lẹ dữ 🤣 để tui nhắc lại cho nè, dùng vòng for như vầy..."

User: "Mở nhạc gì chill chill đi"
Bot: "ok la, để tui mở list lofi cho bà tập trung nha. gõ `!play lofi` nè ✨"

User: "Thời tiết nay sao"
Bot: [Search: 34 độ] -> "nay trời nóng lắm á, 34 độ lận. bà có ra đường nhớ che chắn kỹ nha ko bệnh á."

User: "Mai thi rồi lo quá"
Bot: "bình tĩnh nè, ôn kỹ mấy cái cơ bản là qua thôi. tin tui đi, bà làm được mà 💪"
"""

# Lưu context chat theo Channel ID: {channel_id: deque(maxlen=15)}
chat_contexts = {}

# --- BOT SETUP ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- MUSIC ENGINE ---
class MusicEngine:
    def __init__(self):
        self.queue = [] # Queue bài hát user yêu cầu
        self.is_radio_mode = False # Cờ kiểm tra chế độ Radio
        self.radio_url = "https://soundcloud.com/relaxing-music-production/sets/piano-for-studying" # Link Lofi mặc định

    async def play_next(self, ctx):
        vc = ctx.voice_client
        if not vc: return

        if len(self.queue) > 0:
            # Ưu tiên bài trong queue (do user add)
            url, title = self.queue.pop(0)
            await self.play_source(ctx, url, title)
        elif self.is_radio_mode:
            # Nếu hết queue mà đang bật Pomo -> Auto Radio
            await self.play_source(ctx, self.radio_url, "📻 ITUS Radio (Lofi Chill)")
        else:
            # Hết nhạc, không radio -> Im lặng (hoặc disconnect tuỳ logic)
            pass

async def play_source(self, ctx, search_query, title_display="Music"):
        vc = ctx.voice_client
        if not vc: return

        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                # Tải thông tin
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=False))
                
                # Xử lý kết quả
                if 'entries' in info:
                    # Lấy bài đầu tiên để phát ngay
                    first_entry = info['entries'][0]
                    url = first_entry['url']
                    title = first_entry['title']

                    # --- LOGIC MỚI: XỬ LÝ PLAYLIST ---
                    # Nếu input là Link URL (bắt đầu bằng http) và có nhiều hơn 1 bài
                    if search_query.startswith("http") and len(info['entries']) > 1:
                        added_count = 0
                        # Duyệt các bài còn lại và thêm vào ĐẦU hàng đợi (để hát liên tục theo playlist)
                        # Đảo ngược list để khi insert(0) nó sẽ đúng thứ tự
                        for entry in reversed(info['entries'][1:]):
                            self.queue.insert(0, (entry['url'], entry['title']))
                            added_count += 1
                        
                        await ctx.send(f"✅ Đã phát hiện Playlist! Tui đã thêm {added_count} bài còn lại vào hàng đợi nha.", delete_after=10)
                    # ---------------------------------
                else:
                    url = info['url']
                    title = info['title']
                
                # Logic Radio title (giữ nguyên)
                if self.is_radio_mode and search_query == self.radio_url:
                     title = title_display

                source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
                
                def after_play(e):
                    if e: print(f"Lỗi player: {e}")
                    asyncio.run_coroutine_threadsafe(self.play_next(ctx), bot.loop)

                if vc.is_playing():
                    vc.stop()
                
                vc.play(source, after=after_play)
                await ctx.send(f"🎶 Đang phát: **{title}**", delete_after=60)
                
        except Exception as e:
            print(f"Lỗi nhạc: {e}")
            await ctx.send("Hic, bài này lỗi rồi, tui bỏ qua nha.", delete_after=10)
            await self.play_next(ctx)

music_engine = MusicEngine()

# --- POMODORO ENGINE ---
class PomodoroSession:
    def __init__(self, ctx, work_min=50, break_min=10):
        self.ctx = ctx
        self.work_time = work_min * 60
        self.break_time = break_min * 60
        self.current_time = self.work_time
        self.is_running = False
        self.mode = "work" # "work" hoặc "break"
        self.start_work_dur = work_min
        self.start_break_dur = break_min

pomo_sessions = {} # {guild_id: session}

@tasks.loop(seconds=1)
async def pomo_loop():
    for guild_id, session in list(pomo_sessions.items()):
        if not session.is_running: continue

        session.current_time -= 1
        
        # Hết giờ
        if session.current_time <= 0:
            if session.mode == "work":
                # Chuyển sang nghỉ
                session.mode = "break"
                session.current_time = session.start_break_dur * 60
                await session.ctx.send(f"🔔 **Hết giờ học rồi!** Nghỉ {session.start_break_dur} phút xả hơi đi nà.", delete_after=300)
            else:
                # Chuyển sang học
                session.mode = "work"
                session.current_time = session.start_work_dur * 60
                await session.ctx.send(f"🔔 **Vào học lại nào!** Tập trung cao độ nhé!", delete_after=300)

        # Logic quan tâm (Feature 12) - Chỉ chạy trong giờ nghỉ
        if session.mode == "break" and session.current_time > 0 and session.current_time % 300 == 0: # Check mỗi 5 phút
            # 30% tỷ lệ hỏi thăm
            if random.random() < 0.3:
                msgs = [
                    "Pà ổn hông đó? Uống miếng nước đi.",
                    "Đứng dậy vươn vai cái ikk, ngồi lâu đau lưng ó.",
                    "Mệt quá thì chợp mắt xíu ikkk nha.",
                    "Cố lên!!!"
                ]
                await session.ctx.send(f"@{session.ctx.author.display_name} {random.choice(msgs)}", delete_after=60)

# --- COMMANDS ---

# Helper: Kiểm tra voice và auto-join
async def ensure_voice(ctx):
    if not ctx.author.voice:
        await ctx.send("Úi vào phòng Voice trước đi rồi tui mới phục vụ được!", delete_after=10)
        return False
    
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
        
    return True

@bot.event
async def on_ready():
    print(f'{bot.user} đã online và sẵn sàng phục vụ ITUS-er!')
    pomo_loop.start()
    keep_alive()

@bot.command()
async def play(ctx, *, query):
    if not await ensure_voice(ctx): return
    
    # Feature 3: Nếu đang bật Radio mà user gõ !play -> Ngắt Radio ngay
    if music_engine.is_radio_mode and ctx.voice_client.is_playing() and not music_engine.queue:
        ctx.voice_client.stop() # Stop để trigger 'after_play' -> check queue
    
    music_engine.queue.append((query, query)) # Lưu query vào queue
    await ctx.send(f"Đã thêm **{query}** vào hàng đợi.", delete_after=10)
    
    if not ctx.voice_client.is_playing():
        await music_engine.play_next(ctx)

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Đã skip!", delete_after=5)

@bot.command()
async def pomo(ctx, work: int = 50, break_time: int = 10):
    if not await ensure_voice(ctx): return
    
    # Khởi tạo session
    session = PomodoroSession(ctx, work, break_time)
    session.is_running = True
    pomo_sessions[ctx.guild.id] = session
    
    # Bật chế độ Radio
    music_engine.is_radio_mode = True
    
    # Nếu chưa hát gì thì hát luôn
    if not ctx.voice_client.is_playing():
        await music_engine.play_next(ctx)
        
    await ctx.send(f"🍅 **Pomodoro Started!**\n📚 Học: {work} phút\n☕ Nghỉ: {break_time} phút\n📻 Nhạc nền: Đã bật.", delete_after=60)

@bot.command()
async def stop_pomo(ctx):
    if ctx.guild.id in pomo_sessions:
        del pomo_sessions[ctx.guild.id]
        music_engine.is_radio_mode = False # Tắt radio mode
        if ctx.voice_client: 
            ctx.voice_client.stop() # Dừng nhạc
        await ctx.send("Đã dừng Pomodoro và tắt nhạc.", delete_after=10)

@bot.command()
async def help(ctx):
    manual = """
    **📖 HƯỚNG DẪN SỬ DỤNG ITUS BOT:**
    
    🎶 **Âm nhạc:**
    `!play {tên/link}` : Phát nhạc (Soundcloud/Youtube).
    `!skip` : Qua bài.
    
    🍅 **Học tập (Pomodoro):**
    `!pomo` : Chạy mặc định 50p học / 10p nghỉ + Nhạc nền Lofi.
    `!pomo {học} {nghỉ}` : Chạy theo thời gian tuỳ chỉnh.
    `!stop_pomo` : Dừng học, tắt nhạc.
    
    🤖 **Trò chuyện AI:**
    - Tag @ITUS Bot hoặc chat trực tiếp nếu trong phòng chỉ có 2 đứa.
    - Bot biết search Google nha, cứ hỏi thoải mái.
    """
    await ctx.send(manual, delete_after=120)

# --- AI & CHAT LOGIC (ASYNC GROQ) ---

async def get_ai_response(message, history, current_time):
    # Chuẩn bị tin nhắn gửi cho Model
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n[THÔNG TIN CONTEXT]\nThời gian hiện tại: {current_time}"}
    ]
    
    # Đưa lịch sử chat vào
    for msg in history:
        role = "user" if msg['role'] == 'user' else "assistant"
        content_fmt = f"[{msg['time']}] {msg['user']}: {msg['content']}"
        messages.append({"role": role, "content": content_fmt})
    
    # Tin nhắn mới nhất
    messages.append({"role": "user", "content": message.content})

    try:
        # Gọi API bất đồng bộ với native tool 'browser_search'
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.6, # Giảm nhiệt độ xíu cho bớt "bay"
            max_completion_tokens=2048,
            top_p=1,
            stream=True, # Streaming response
            tools=[{"type": "browser_search"}] # Native Search Tool
        )
        
        # Gom stream text
        full_response = ""
        async for chunk in completion:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                
        return full_response if full_response else "Tui chưa nghĩ ra câu trả lời, ông hỏi lại thử xem?"

    except Exception as e:
        print(f"Groq API Error: {e}")
        return "Ây da, mạng méo chán quá, não tui bị lag rồi. Ông chờ xíu hỏi lại nha."

@bot.event
async def on_message(message):
    if message.author == bot.user: return

    # Feature 4: Chỉ hoạt động trong Voice Channel context (Logic: User phải đang ở trong Voice)
    # Tuy nhiên, user thường chat ở kênh Text. Ta sẽ kiểm tra xem user có trong Voice không.
    is_user_in_voice = message.author.voice is not None
    
    # Quản lý Context chat (lưu tin nhắn text bất kể lệnh hay chat thường để AI hiểu ngữ cảnh)
    channel_id = message.channel.id
    if channel_id not in chat_contexts:
        chat_contexts[channel_id] = deque(maxlen=15)
    
    # Lưu tin nhắn vào context
    if not message.content.startswith('!'):
        chat_contexts[channel_id].append({
            "role": "user",
            "user": message.author.display_name,
            "content": message.content,
            "time": datetime.now().strftime("%H:%M")
        })

    # LOGIC TRẢ LỜI (Feature 6, 7)
    should_reply = False
    
    if is_user_in_voice:
        voice_channel = message.author.voice.channel
        
        # Kiểm tra tag bot
        if bot.user.mentioned_in(message):
            should_reply = True
            # Feature 7: Auto join
            if not message.guild.voice_client:
                 await voice_channel.connect()
            elif message.guild.voice_client.channel != voice_channel:
                 await message.guild.voice_client.move_to(voice_channel)
        
        # Kiểm tra 1-on-1 (Feature 6)
        # Nếu trong phòng chỉ có Bot và User này -> Bot tự hiểu là đang nói chuyện với nó
        elif message.guild.voice_client and message.guild.voice_client.channel == voice_channel:
            if len(voice_channel.members) == 2:
                should_reply = True

    if should_reply:
        async with message.channel.typing():
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reply_content = await get_ai_response(message, chat_contexts[channel_id], current_time)
            
            # Bot lưu câu trả lời của chính nó vào context
            chat_contexts[channel_id].append({
                "role": "assistant",
                "user": "ITUS Bot",
                "content": reply_content,
                "time": datetime.now().strftime("%H:%M")
            })
            
            # Feature 4: Tự xoá tin nhắn sau một khoảng thời gian
            await message.channel.send(reply_content, delete_after=300)

    # Xử lý lệnh (!play, !pomo...)
    await bot.process_commands(message)

# Run Bot
if __name__ == "__main__":
    if not TOKEN:
        print("Lỗi: Chưa set DISCORD_TOKEN trong biến môi trường.")
    else:
        bot.run(TOKEN)


import os
import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    import ssl
except ImportError:
    raise ImportError("Модуль 'ssl' отсутствует. Убедитесь, что Python установлен с поддержкой SSL.")

try:
    import openai
    openai_available = True
except ImportError:
    openai_available = False

try:
    from telethon.sync import TelegramClient
    from telethon.tl.functions.messages import GetDiscussionMessageRequest
    telethon_available = True
except ImportError:
    telethon_available = False

app = FastAPI()

# === Настройки ===
api_id = 23550285
api_hash = '850733a9f153d0576b3a8bceaa42370d'
openai_api_key = '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'

channel_username = 'p2pmanualshik'
session_name = 'neuro_web_session'
interval = 3600

if telethon_available:
    client = TelegramClient(session_name, api_id, api_hash)
    client.start()

running = False

class Status(BaseModel):
    running: bool
    last_comment: str = ""
    ai_enabled: bool = openai_available
    telegram_enabled: bool = telethon_available

status = Status(running=False)

def generate_comment(post_text):
    if not openai_available:
        return "[openai не установлен]"
    openai.api_key = openai_api_key
    prompt = f"""Прочитай пост в Telegram и напиши короткий, живой комментарий от обычного человека. Не повторяй пост, выскажи мнение или реакцию. Вот текст поста:

"""{post_text}""""""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Ошибка AI: {e}"

async def auto_comment():
    global running, status
    if not telethon_available:
        status.last_comment = "Ошибка: telethon не установлен"
        return
    while running:
        try:
            post = client.get_messages(channel_username, limit=1)[0]
            if post.replies and post.replies.comments:
                discussion = client(GetDiscussionMessageRequest(client.get_entity(channel_username), post.id))
                comment_chat = discussion.messages[0].to_id
                comment_text = generate_comment(post.text)
                client.send_message(comment_chat, comment_text, reply_to=discussion.messages[0].id)
                status.last_comment = comment_text
            await asyncio.sleep(interval)
        except Exception as e:
            status.last_comment = f"Ошибка: {e}"
            await asyncio.sleep(60)

@app.get("/", response_class=HTMLResponse)
def ui():
    return """<!DOCTYPE html>
    <html lang='ru'>
    <head>
    <meta charset='UTF-8'><title>NeuroCommenter</title>
    <style>
    body { font-family: Arial, sans-serif; padding: 20px; background: #f8f8f8; }
    h1 { color: #333; } button { padding: 10px 20px; margin: 10px 5px; font-size: 16px; }
    #status { margin-top: 20px; font-size: 18px; }
    .log { background: #fff; border: 1px solid #ccc; padding: 15px; margin-top: 10px; white-space: pre-wrap; }
    </style></head><body><h1>🧠 NeuroCommenter</h1>
    <button onclick='startBot()'>▶ Запустить</button>
    <button onclick='stopBot()'>⏹ Остановить</button>
    <button onclick='sendComment()'>💬 Комментировать сейчас</button>
    <div id='status'>Загрузка статуса...</div>
    <div class='log' id='log'></div>
    <script>
    async function fetchStatus() {
        const res = await fetch('/status');
        const data = await res.json();
        document.getElementById('status').innerText = `Статус: ${data.running ? '🟢 Работает' : '🔴 Остановлен'} | AI: ${data.ai_enabled ? '✅' : '❌'} | Telegram: ${data.telegram_enabled ? '✅' : '❌'}`;
        document.getElementById('log').innerText = `Последний комментарий:\n${data.last_comment || '—'}`;
    }
    async function startBot() { await fetch('/start', { method: 'POST' }); fetchStatus(); }
    async function stopBot() { await fetch('/stop', { method: 'POST' }); fetchStatus(); }
    async function sendComment() {
        const res = await fetch('/comment_now');
        const data = await res.json();
        fetchStatus();
        alert(data.message + (data.text ? '\n\n' + data.text : ''));
    }
    fetchStatus(); setInterval(fetchStatus, 15000);
    </script></body></html>"""

@app.get("/status")
def get_status(): return status

@app.post("/start")
def start_background_tasks(background_tasks: BackgroundTasks):
    global running
    if not telethon_available:
        return {"message": "❌ Telethon не установлен"}
    if not running:
        running = True
        background_tasks.add_task(auto_comment)
    status.running = True
    return {"message": "✅ Авто-комментинг запущен"}

@app.post("/stop")
def stop():
    global running
    running = False
    status.running = False
    return {"message": "🛑 Авто-комментинг остановлен"}

@app.get("/comment_now")
def comment_now():
    if not telethon_available:
        return {"message": "❌ Telethon не установлен"}
    try:
        post = client.get_messages(channel_username, limit=1)[0]
        if post.replies and post.replies.comments:
            discussion = client(GetDiscussionMessageRequest(client.get_entity(channel_username), post.id))
            comment_chat = discussion.messages[0].to_id
            comment_text = generate_comment(post.text)
            client.send_message(comment_chat, comment_text, reply_to=discussion.messages[0].id)
            status.last_comment = comment_text
            return {"message": "✅ Комментарий отправлен", "text": comment_text}
        else:
            return {"message": "⚠️ У поста нет обсуждения."}
    except Exception as e:
        return {"message": f"❌ Ошибка: {e}"}
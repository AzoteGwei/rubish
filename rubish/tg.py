from pyrogram.client import Client
from pyrogram.types import Message, User, MessageReactionUpdated
from pyrogram.filters import command
from pyrogram.enums import ChatType
from rubish.config import instance as config
from rubish.db import conn,chatid2tablename
from rubish.misc import *
from rubish.i18n import _
from rubish.ai import request_ai
from loguru import logger
import json
import time

app = Client(
    "rubish",
    api_id=config.telegram_bot_api_id, api_hash=config.telegram_bot_api_hash,
    bot_token=config.telegram_bot_api_bot_token,
    proxy=config.telegram_proxy if config.telegram_use_proxy else None
)

@app.on_start()
async def started(client: Client):
    tginfo = await client.get_me()
    logger.info(f"Telegram Bot {tginfo.username or '[username not set]'}({'Bot' if tginfo.is_bot else 'Userbot'}; tgid: {tginfo.id}) is running now.")
    
def get_authorized_chat_id(msg: Message | MessageReactionUpdated) -> int | None:
    """
    检查聊天对象的合法性以及黑白名单权限。
    如果通过权限检查，返回 chat_id；如果未通过，返回 None。
    """
    if not msg.chat:
        raise WTFISTHISException("msg.chat does not exist")
    if not msg.chat.id:
        raise WTFISTHISException("msg.chat.id does not exist")
        
    chat_id = msg.chat.id
    
    # 鉴权逻辑
    if config.telegram_use_whitelist and chat_id not in config.telegram_whitelist:
        return None
    if config.telegram_use_blacklist and chat_id in config.telegram_blacklist:
        return None
        
    return chat_id

@app.on_message(command(['id', 'start', 'info', 'help', 'brief']))
@logger.catch
async def cmd_misc(client : Client, msg : Message):
    cmd = msg.content
    if not msg.chat:
        raise WTFISTHISException("msg.chat does not exist")
    if cmd.startswith('/id'):
        if not msg.from_user:
            return await msg.reply(_('cmd.id.nosender',msg.summary_language_code).format(msg.chat.id))
        return await msg.reply(_('cmd.id.withsender',msg.summary_language_code).format(msg.chat.id, msg.from_user.id))
    if cmd.startswith('/brief'):
        ret = []
        async for hismsg in client.get_chat_history(msg.chat.id,limit=5): # type: ignore
            ret.append(hismsg)
        return await msg.reply("Brief: {}".format(str(ret)))
    if msg.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP, ChatType.FORUM, ChatType.CHANNEL]:
        return # The Things below is not for public environment
    
@app.on_message(command(['gemini','chatgpt','claude','deepseek','glm','summerize']))
@logger.catch
async def cmd_summerize(client: Client, msg: Message):
    chat_id = get_authorized_chat_id(msg)
    if not chat_id:
        return
    if not msg.command:
        raise WTFISTHISException("msg.command does not exitst")
    if msg.from_user:
        userid = msg.from_user.id
    else:
        userid = chat_id
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ 用法错误：请 **回复 (Reply)** 一条需要处理的消息。")
        return
    reply_id = msg.reply_to_message.id
    table_name = chatid2tablename(chat_id)
    cur = conn.cursor()
    target_text = ""

    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            await msg.reply_text("❌ 入群前的消息无法总结")
            return

        # 修改点：查询从 reply_id 开始，到当前命令消息之前的所有消息
        # 并且联表查询 sender 拿到当时的发送者全名，构建对话上下文
        cur.execute(f"""
            SELECT s.user_fullname, t.text 
            FROM {table_name} t
            LEFT JOIN sender s ON t.sender_id = s.id
            WHERE t.message_id >= ? AND t.message_id < ?
            ORDER BY t.message_id ASC
            LIMIT 500  -- 建议加个硬上限，防止回复了一年前的消息导致 Token 撑爆 AI 接口
        """, (reply_id, msg.id))
        
        rows = cur.fetchall()

        if not rows:
            await msg.reply_text("❌ 未能提取到该区间的有效消息。")
            return
            
        # 将查询到的多行记录拼装成带用户名的对话格式
        chat_history = []
        for row in rows:
            user_fullname = row[0] or "Unknown"
            text_content = row[1] or ""
            
            # 过滤掉纯图片/贴纸等没有文本内容的消息
            if text_content.strip():
                chat_history.append(f"[{user_fullname}] {text_content}")
                
        target_text = "\n".join(chat_history)

        if not target_text:
            await msg.reply_text("⚠️ 该区间的消息均没有提取到文本内容，无法进行 AI 处理。")
            return

    except Exception as e:
        logger.error(f"DB Query Error in cmd_summerize: {e}")
        await msg.reply_text("数据库查询出错，请联系管理员。")
        return
    finally:
        cur.close()

    if not config.ai_providers or len(config.ai_providers) == 0:
        await msg.reply_text("❌ 系统未配置 AI 提供商 (ai_providers 为空)")
        return
    
    if msg.command[0] in config.ai_providers:
        preferred_provider : dict = msg.command[0] # type: ignore
    else:
        preferred_provider : dict = list(config.ai_providers.keys())[0]
    
    # Check permission
    if (config.ai_providers[preferred_provider]['privilege']['use_whitelist'] and \
            userid not in config.ai_providers[preferred_provider]['privilege']['whitelist']) and\
            userid not in config.telegram_admins:
        await msg.reply_text("❌ 您无法使用 {} 作为总结模型。".format(preferred_provider))
        return
    # if 
    additional_prompt = " ".join(msg.command[1:]) if len(msg.command) > 1 else ""

    processing_msg = await msg.reply_text("⏳ AI 正在思考中，请稍候...")
    logger.debug("[{}/{}]Triggered {}",getattr(msg.chat,'full_name',getattr(msg.chat,'title','Unknown')),msg.from_user.full_name if msg.from_user else 'anon',msg.id,msg.content) # type: ignore
    try:

        reply_content = await request_ai(config.ai_providers[preferred_provider], target_text, additional_prompt)
        await processing_msg.edit_text(reply_content)
        
    except Exception as e:
        # 捕获 ai.py 抛出的所有异常，友善地提示给用户
        await processing_msg.edit_text(f"❌ AI 处理失败: {str(e)[:100]}")

def track_sender(cur, user: User | None) -> int | None:
    """
    检查并更新 Sender 表。返回当前状态对应在 Sender 表中的主键 ID。
    """
    if not user:
        return None # 兼容匿名管理员或频道以自己身份在群内发言

    tg_userid = user.id
    username = user.username or ""
    
    # 拼接全名，去除多余空格
    user_fullname = user.full_name.strip() 

    # 查询该用户最新的记录
    cur.execute("""
        SELECT id, username, user_fullname 
        FROM sender 
        WHERE tg_userid = ? 
        ORDER BY seenat DESC 
        LIMIT 1
    """, (tg_userid,))
    
    row = cur.fetchone()
    current_time = int(time.time())

    # 存在历史记录，且用户名和全名均未改变
    if row:
        db_id, db_username, db_fullname = row
        if db_username == username and db_fullname == user_fullname:
            return db_id # 直接返回现有的主键 ID

    # 如果没查到记录，或者有任何一项发生了变化，插入新记录
    cur.execute("""
        INSERT INTO sender (tg_userid, username, user_fullname, seenat)
        VALUES (?, ?, ?, ?)
    """, (tg_userid, username, user_fullname, current_time))
    
    return cur.lastrowid # 返回新插入的主键 ID


@app.on_message()
@logger.catch
async def log_message(client: Client, msg: Message):
    chat_id = get_authorized_chat_id(msg)
    if not chat_id:
        return
    logger.debug("[{}/{}][{}]{}",getattr(msg.chat,'full_name',getattr(msg.chat,'title','Unknown')),msg.from_user.full_name if msg.from_user else 'anon',msg.id,msg.content if ) # type: ignore
    table_name = chatid2tablename(chat_id)
    cur = conn.cursor()
    
    try:
        # 1. 确保全局 sender 表和索引存在 (索引有助于快速查询最新状态)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sender (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_userid INTEGER,
                username TEXT,
                user_fullname TEXT,
                seenat INTEGER
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sender_tg_userid ON sender(tg_userid)")

        # 2. 确保动态群组/聊天记录表存在，并添加 sender 外键
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    message_id INTEGER PRIMARY KEY,
                    sender_id INTEGER,
                    text TEXT,
                    date INTEGER,
                    edit_date INTEGER,
                    reactions TEXT,
                    FOREIGN KEY(sender_id) REFERENCES sender(id)
                )
            """)
            conn.commit()

        # 3. 追踪/获取当前时刻的 sender_id
        sender_id = track_sender(cur, msg.from_user)

        # 4. 插入消息记录
        text = msg.text or msg.caption or ""
        date = int(msg.date.timestamp()) if msg.date else int(time.time())
        
        cur.execute(f"""
            INSERT OR REPLACE INTO {table_name} 
            (message_id, sender_id, text, date, edit_date, reactions) 
            VALUES (?, ?, ?, ?, NULL, NULL)
        """, (msg.id, sender_id, text, date))
        conn.commit()
        
    except Exception as e:
        logger.error(f"DB Insert Error: {e}")
    finally:
        cur.close()


@app.on_edited_message()
@logger.catch
async def log_edited_message(client: Client, msg: Message):
    chat_id = get_authorized_chat_id(msg)
    if not chat_id:
        return
    logger.debug("[{}/{}][EDIT: {}]{}",getattr(msg.chat,'full_name',getattr(msg.chat,'title','Unknown')),msg.from_user.full_name if msg.from_user else 'anon',msg.id,msg.content) # type: ignore
    table_name = chatid2tablename(chat_id)
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            return
        
        # 即便是编辑消息，我们也借此机会“白嫖”一次用户资料状态检查
        # 但我们不需要更新原消息绑定的 sender_id，因为这违背了历史快照原则
        track_sender(cur, msg.from_user) 
            
        text = msg.text or msg.caption or ""
        edit_date = int(msg.edit_date.timestamp()) if msg.edit_date else int(time.time())
        
        cur.execute(f"""
            UPDATE {table_name}
            SET text = ?, edit_date = ?
            WHERE message_id = ?
        """, (text, edit_date, msg.id))
        conn.commit()
        
    except Exception as e:
        logger.error(f"DB Update Error: {e}")
    finally:
        cur.close()


@app.on_message_reaction() # 根据新版 Pyrogram 调整为 reaction 事件
@logger.catch
async def log_message_reaction(client: Client, msg: MessageReactionUpdated):
    logger.debug("[{}/{}][{}]{}",getattr(msg.chat,'full_name',getattr(msg.chat,'title','Unknown')),msg.user.full_name if msg.user else 'anon',msg.message_id,f'{msg.old_reaction}, {msg.new_reaction}') # type: ignore
    # 此处的 msg 实际上是 MessageReactionUpdated 对象
    chat_id = get_authorized_chat_id(msg)
    if not chat_id:
        return
        
    table_name = chatid2tablename(chat_id)
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            return
        
        # Reaction 事件也可以顺手更新一下操作者的资料（如果有 user 字段的话）
        if hasattr(msg, "user"):
            track_sender(cur, getattr(msg, "user"))
        
        cur.execute(f"""
            SELECT reactions
            FROM {table_name}
            WHERE message_id = ?
        """, (msg.message_id,))
        
        row = cur.fetchone()
        try:
            reactions_list = json.loads(str(row))
        except json.JSONDecodeError:
            reactions_list = []
        
        if getattr(msg, "old_reaction", None):
            for r in msg.old_reaction: # type: ignore
                emoji_str = getattr(r, "emoji", None) or getattr(r, "custom_emoji_id", "unknown")
                for item in reactions_list:
                    if item['emoji'] == emoji_str:
                        item['count'] -= 1
        
        if getattr(msg, "new_reaction", None):
            for r in msg.new_reaction: # type: ignore
                emoji_str = getattr(r, "emoji", None) or getattr(r, "custom_emoji_id", "unknown")
                found = False
                for item in reactions_list:
                    if item['emoji'] == emoji_str:
                        item['count'] += 1
                        found = True
                if not found:
                    reactions_list.append({
                        "emoji": str(emoji_str),
                        "count": 1
                    })
        
        reactions_json = json.dumps(reactions_list, ensure_ascii=False)
        
        cur.execute(f"""
            UPDATE {table_name}
            SET reactions = ?
            WHERE message_id = ?
        """, (reactions_json, msg.message_id)) # 注意这里通常是 msg.message_id
        conn.commit()
        
    except Exception as e:
        logger.error(f"DB Reaction Update Error: {e}")
    finally:
        cur.close()



if __name__ == '__main__':
    app.run()
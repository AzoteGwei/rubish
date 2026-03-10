import sqlite3
from rubish.config import instance as config

conn = sqlite3.connect(config.db_path)

def chatid2tablename(chatid : int) -> str:
    if chatid < 0:
        return f"chat_n{-chatid}"
    return f"chat_{chatid}"
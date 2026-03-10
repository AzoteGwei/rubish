from yaml import safe_dump, safe_load
from asyncio import Lock
import os
from typing import Any

class ConfigLoader:
    """Generic `ConfigLoader` with asyncio and pyyaml."""
    config_path : str # Config Path
    _lock : Lock # Asyncio Lock to avoid conflict
    _config : dict # Internal Config
    
    def __init__(self, path : str | None = None) -> None:
        self.config_path = os.path.abspath(path or "./config.yaml")
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self._lock = Lock()
        self._config = {}
        
    def _load(self) -> None:
        """Load Config(Sync)
        """
        if not os.path.exists(self.config_path):
            return
        with open(self.config_path, mode='r', encoding='UTF-8') as f:
            self._config = safe_load(f) or {}
        
    def _save(self) -> None:
        """Save Config(Sync)
        """
        with open(self.config_path, mode='w', encoding='UTF-8') as f:
            safe_dump(self._config, f, allow_unicode=True, sort_keys=False)
        
    async def load(self) -> None:
        async with self._lock:
            self._load()
            
    async def save(self) -> None:
        async with self._lock:
            self._save()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get Config by key

        Args:
            key (str): the key to config. e.g. `foo.bar`
            default (Any, optional): default value when missing. Defaults to None.

        Returns:
            Any: the config content
        """
        target = self._config
        for k in key.split('.'):
            if isinstance(target, dict) and k in target:
                target = target[k]
            else:
                return default
        return target

    def set(self, key: str, value: Any) -> None:
        """Set Config by key, THIS WILL NOT SYNC TO DISC AUTOMATICALLY

        Args:
            key (str): the config key, e.g. `foo.bar`
            value (Any): value to set
        """
        parts = key.split('.')
        target = self._config
        for k in parts[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[parts[-1]] = value

class RubishConfig(ConfigLoader):
    def __init__(self, path: str | None = None) -> None:
        super().__init__(path)
        self._load()
        # Telegram Bot 相关
        self.telegram_bot_api_id : int = self.get('telegram.api_id', 12345)
        self.telegram_bot_api_hash : str = self.get('telegram.api_hash', "")
        self.telegram_bot_api_bot_token : str = self.get("telegram.bot_token", "")
        # Telegram 权限设置
        self.telegram_admins : list[int] = self.get("telegram.privilege.admins", [])
        self.telegram_use_whitelist : bool = self.get("telegram.privilege.use_whitelist", True)
        self.telegram_whitelist : list[int] = self.get("telegram.privilege.whitelist", [])
        self.telegram_use_blacklist : bool = self.get("telegram.privilege.use_blacklist", False)
        self.telegram_blacklist : list[int] = self.get("telegram.privilege.blacklist", [])
        # 可连接性设置
        self.telegram_use_proxy : bool = self.get("telegram.use_proxy", False)
        self.telegram_proxy : dict[str,str|int] = self.get("telegram.proxy", None)
        # AI 设置
        self.ai_providers : dict = self.get("ai.providers",[])
        self.ai_max_msgs : int = self.get('ai.maximum_message', 50)
        # DB 设置
        self.db_path : str = self.get("db.path","./rubish.sqlite3")
        # 
        
        
        

instance = RubishConfig()

if __name__ == '__main__':
    TestConfig = ConfigLoader()
    TestConfig._config = {"foo":"bar", "a":{"b":"c"}, "d":True}
    assert TestConfig.get("foo") == "bar"
    assert TestConfig.get("a.b") == "c"
    assert TestConfig.get("d", False) == True
    assert TestConfig.get("e","blabla") == "blabla"
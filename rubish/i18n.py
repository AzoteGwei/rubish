from rubish.config import ConfigLoader

TRANSLATIONS = {
    'en':{
        "cmd":{
            "id":{
                "nosender":"Current ChatID is `{}`.",
                'withsender':"Current ChatID is `{}`. \nYour UserID is `{}`."
            },
            "summerize":{
                "usage":"Please **reply** to a message to begin summerize.",
                "too_early":"This message is **too early** to summerize.",
                "invaild_scope":"No **vaild** message was found to summerize.",
                "text_missing":"No **text** message was found to summerize with.",
                "db_error":"DB Error. \n**PLEASE CONTACT ADMINS.**",
                "provider_missing":"This bot **didn't** configured ai providers.",
                "no_permission": "You have **not enough permission** to use {} as summery model.",
                "pondering": "AI Summerizing...",
                "ai_error":"AI raised error: {} \n**PLEASE CONTACT ADMINS.**"
            }
        }
    },
    'zh':{
        
    },
    '_':{
        'i18n_failed': 'Failed to fetch i18n key for `{}`. \n**THIS IS A BUG. PLEASE REPORT TO THE DEVELOPERS.**'
    }
}

class I18N(ConfigLoader):
    def __init__(self, path: str | None = None) -> None:
        super().__init__(path or './i18n.yaml')
        self._config = TRANSLATIONS

instance = I18N()

def _(key : str, lang : str | None = None, default : str | None = None) -> str:
    result = instance.get('{}.{}'.format(lang,key))
    if result:
        return result
    result = instance.get('en.{}'.format(key))
    if result:
        return result
    if default:
        return default
    return instance.get('_.i18n_failed').format(key)
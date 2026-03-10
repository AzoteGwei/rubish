from rubish.config import ConfigLoader

TRANSLATIONS = {
    'en':{
        "cmd":{
            "id":{
                "nosender":"Current ChatID is `{}`.",
                'withsender':"Current ChatID is `{}`. \nYour UserID is `{}`."
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
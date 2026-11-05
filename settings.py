"""Runtime configuration. Never expose this object or secrets through the web API."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit


def load_env(path=None):
    """Local CLI convenience; existing environment wins. No shell interpolation."""
    path=Path(path or Path(__file__).resolve().parent/'.env')
    if not path.is_file():
        return
    for number,line in enumerate(path.read_text().splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        key,sep,value=line.partition('=')
        if not sep or not key.replace('_','').isalnum():
            raise ValueError(f'Ligne .env invalide : {number}')
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):
            value=value[1:-1]
        os.environ.setdefault(key,value)


def boolean(name,default=False):
    value=os.getenv(name,str(default)).strip().lower()
    if value not in ('true','false','1','0','yes','no'):
        raise ValueError(f'{name} : booléen attendu')
    return value in ('true','1','yes')


def integer(name,default,minimum=1,maximum=1000000):
    value=int(os.getenv(name,str(default)))
    if not minimum<=value<=maximum:
        raise ValueError(f'{name} : valeur hors limites')
    return value


def endpoint(name,default=''):
    value=os.getenv(name,default).strip().rstrip('/')
    if value:
        parsed=urlsplit(value)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f'{name} : URL HTTP(S) sans identifiant ni paramètre attendue')
    return value


@dataclass(repr=False)
class Settings:
    root: Path
    karakeep_url: str=''
    karakeep_key: str=field(default='',repr=False)
    url_filter: str=''
    sync_enabled: bool=False
    sync_interval: int=900
    download_media: bool=True
    media_max_mb: int=100
    media_max_seconds: int=300
    batch_size: int=3
    timeout: int=120
    llm_enabled: bool=False
    llm_url: str=''
    llm_key: str=field(default='',repr=False)
    llm_model: str=''
    llm_max_chars: int=24000
    asr_url: str=''
    asr_key: str=field(default='',repr=False)
    asr_model: str=''
    vision_url: str=''
    vision_key: str=field(default='',repr=False)
    vision_model: str=''
    vision_max_frames: int=12
    vision_interval: int=5

    @classmethod
    def from_env(cls):
        load_env()
        llm_url=endpoint('LLM_BASE_URL')
        llm_key=os.getenv('LLM_API_KEY','')
        return cls(root=Path(os.getenv('MEMOIRE_ROOT',str(Path(__file__).resolve().parent))).resolve(),
            karakeep_url=endpoint('KARAKEEP_BASE_URL'),karakeep_key=os.getenv('KARAKEEP_API_KEY',''),
            url_filter=os.getenv('KARAKEEP_URL_FILTER','').strip(),sync_enabled=boolean('SYNC_ENABLED'),
            sync_interval=integer('SYNC_INTERVAL_SECONDS',900,10,86400),download_media=boolean('DOWNLOAD_MEDIA',True),
            media_max_mb=integer('MEDIA_MAX_MB',100,1,1024),media_max_seconds=integer('MEDIA_MAX_SECONDS',300,1,3600),
            batch_size=integer('WORKER_BATCH_SIZE',3,1,100),timeout=integer('HTTP_TIMEOUT_SECONDS',120,1,600),
            llm_enabled=boolean('LLM_ENABLED'),llm_url=llm_url,llm_key=llm_key,llm_model=os.getenv('LLM_MODEL','').strip(),
            llm_max_chars=integer('LLM_MAX_INPUT_CHARS',24000,1000,200000),
            asr_url=endpoint('ASR_BASE_URL'),asr_key=os.getenv('ASR_API_KEY',''),asr_model=os.getenv('ASR_MODEL','').strip(),
            vision_url=endpoint('VISION_BASE_URL') or llm_url,vision_key=os.getenv('VISION_API_KEY') or llm_key,
            vision_model=os.getenv('VISION_MODEL','').strip(),vision_max_frames=integer('VISION_MAX_FRAMES',12,1,120),
            vision_interval=integer('VISION_INTERVAL_SECONDS',5,1,120))

    def validate_worker(self):
        if self.sync_enabled and not (self.karakeep_url and self.karakeep_key):
            raise ValueError('SYNC_ENABLED nécessite KARAKEEP_BASE_URL et KARAKEEP_API_KEY')
        if self.llm_enabled and not (self.llm_url and self.llm_model):
            raise ValueError('LLM_ENABLED nécessite LLM_BASE_URL et LLM_MODEL')
        if self.asr_model and not self.asr_url:
            raise ValueError('ASR_MODEL nécessite ASR_BASE_URL')
        if self.vision_model and not self.vision_url:
            raise ValueError('VISION_MODEL nécessite VISION_BASE_URL ou LLM_BASE_URL')


def initialize(root):
    import cerveau
    (root/'data').mkdir(parents=True,exist_ok=True)
    for name in ('sources','entities'):
        path=root/'data'/f'{name}.json'
        if not path.exists():
            cerveau.write_json(path,[])
    if not (root/'data/catalog.json').exists():
        cerveau.build(root)

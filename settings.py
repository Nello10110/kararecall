"""Runtime configuration. Never expose this object or secrets through the web API."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import math
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
    try:value=int(os.getenv(name,str(default)))
    except ValueError:raise ValueError(f'{name} : entier attendu') from None
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


def amount(name,default):
    try:value=float(os.getenv(name,str(default)))
    except ValueError:raise ValueError(f'{name} : montant attendu') from None
    if not math.isfinite(value) or value<0:
        raise ValueError(f'{name} : montant positif ou nul attendu')
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
    tag_filter: str=''
    max_attempts: int=3
    llm_max_tokens: int=2000
    vision_max_tokens: int=600
    llm_reasoning: str=''
    vision_reasoning: str=''
    llm_thinking: str=''
    vision_thinking: str=''
    token_limit_param: str='max_completion_tokens'
    asr_timestamps: bool=True
    monthly_budget_usd: float=2.0
    call_reserve_usd: float=0.05
    daily_call_limit: int=50
    monthly_call_limit: int=400
    llm_input_usd: float=0
    llm_output_usd: float=0
    vision_input_usd: float=0
    vision_output_usd: float=0
    asr_usd_per_hour: float=0
    pdf_max_pages: int=25
    pdf_ocr_enabled: bool=False
    pdf_ocr_max_pages: int=3
    image_ocr_enabled: bool=False
    web_research_enabled: bool=False
    web_research_key: str=field(default='',repr=False)
    web_request_usd: float=0.00075
    reuse_subtitles: bool=False
    vision_sample_mode: str='regular'
    llm_document_sections: int=0
    storage_min_free_mb: int=256

    @classmethod
    def from_env(cls):
        load_env()
        llm_url=endpoint('LLM_BASE_URL')
        llm_key=os.getenv('LLM_API_KEY','')
        return cls(root=Path(os.getenv('KARARECALL_ROOT',str(Path(__file__).resolve().parent))).resolve(),
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
            vision_interval=integer('VISION_INTERVAL_SECONDS',5,1,120),
            tag_filter=os.getenv('KARAKEEP_TAG_FILTER','').strip(),max_attempts=integer('WORKER_MAX_ATTEMPTS',3,1,20),
            llm_max_tokens=integer('LLM_MAX_OUTPUT_TOKENS',2000,100,16000),
            vision_max_tokens=integer('VISION_MAX_OUTPUT_TOKENS',600,50,4000),
            llm_reasoning=os.getenv('LLM_REASONING_EFFORT','').strip(),vision_reasoning=os.getenv('VISION_REASONING_EFFORT','').strip(),
            llm_thinking=os.getenv('LLM_THINKING','').strip(),vision_thinking=os.getenv('VISION_THINKING','').strip(),
            token_limit_param=os.getenv('AI_TOKEN_LIMIT_PARAM','max_completion_tokens'),asr_timestamps=boolean('ASR_SEGMENT_TIMESTAMPS',True),
            monthly_budget_usd=amount('AI_MONTHLY_BUDGET_USD',2),call_reserve_usd=amount('AI_CALL_RESERVE_USD',0.05),
            daily_call_limit=integer('AI_MAX_CALLS_PER_DAY',50,1,10000),monthly_call_limit=integer('AI_MAX_CALLS_PER_MONTH',400,1,100000),
            llm_input_usd=amount('LLM_INPUT_USD_PER_MILLION',0),llm_output_usd=amount('LLM_OUTPUT_USD_PER_MILLION',0),
            vision_input_usd=amount('VISION_INPUT_USD_PER_MILLION',0),vision_output_usd=amount('VISION_OUTPUT_USD_PER_MILLION',0),
            asr_usd_per_hour=amount('ASR_USD_PER_HOUR',0),pdf_max_pages=integer('PDF_MAX_PAGES',25,1,100),
            pdf_ocr_enabled=boolean('PDF_OCR_ENABLED'),pdf_ocr_max_pages=integer('PDF_OCR_MAX_PAGES',3,1,10),
            image_ocr_enabled=boolean('IMAGE_OCR_ENABLED'),web_research_enabled=boolean('WEB_RESEARCH_ENABLED'),
            web_research_key=os.getenv('DEEPSEEK_RESEARCH_API_KEY') or (llm_key if urlsplit(llm_url).hostname=='api.deepseek.com' else ''),
            web_request_usd=amount('WEB_REQUEST_USD',0.00075),reuse_subtitles=boolean('REUSE_SUBTITLES'),
            vision_sample_mode=os.getenv('VISION_SAMPLE_MODE','regular').strip(),
            llm_document_sections=integer('LLM_DOCUMENT_SECTIONS',0,0,10),
            storage_min_free_mb=integer('STORAGE_MIN_FREE_MB',256,0,1048576))

    def validate_worker(self):
        if self.vision_sample_mode not in ('regular','changes'):
            raise ValueError('VISION_SAMPLE_MODE : regular ou changes attendu')
        if any(value not in ('','enabled','disabled') for value in (self.llm_thinking,self.vision_thinking)):
            raise ValueError('LLM_THINKING / VISION_THINKING : enabled, disabled ou vide attendu')
        if self.token_limit_param not in ('max_completion_tokens','max_tokens'):
            raise ValueError('AI_TOKEN_LIMIT_PARAM non reconnu')
        if any(effort not in ('','none','minimal','low','medium','high','xhigh','max') for effort in (self.llm_reasoning,self.vision_reasoning)):
            raise ValueError('Effort de raisonnement non reconnu')
        if self.call_reserve_usd<=0:
            raise ValueError('AI_CALL_RESERVE_USD doit être strictement positif')
        if self.sync_enabled and not (self.karakeep_url and self.karakeep_key):
            raise ValueError('SYNC_ENABLED nécessite KARAKEEP_BASE_URL et KARAKEEP_API_KEY')
        if self.sync_enabled:
            for role,url,key,enabled in [('LLM',self.llm_url,self.llm_key,self.llm_enabled),('VISION',self.vision_url,self.vision_key,bool(self.vision_model)),('ASR',self.asr_url,self.asr_key,bool(self.asr_model))]:
                if enabled and urlsplit(url).hostname in ('api.openai.com','api.groq.com','api.deepseek.com') and not key:
                    raise ValueError(f'{role}_API_KEY est nécessaire pour ce fournisseur')
        if self.llm_enabled and not (self.llm_url and self.llm_model):
            raise ValueError('LLM_ENABLED nécessite LLM_BASE_URL et LLM_MODEL')
        if self.asr_model and not self.asr_url:
            raise ValueError('ASR_MODEL nécessite ASR_BASE_URL')
        if self.vision_model and not self.vision_url:
            raise ValueError('VISION_MODEL nécessite VISION_BASE_URL ou LLM_BASE_URL')
        if self.image_ocr_enabled and not self.vision_model:
            raise ValueError('IMAGE_OCR_ENABLED nécessite VISION_MODEL')
        if self.pdf_ocr_enabled and not self.vision_model:
            raise ValueError('PDF_OCR_ENABLED nécessite VISION_MODEL')
        if self.web_research_enabled and (not self.web_research_key or self.web_request_usd<=0):
            raise ValueError('WEB_RESEARCH_ENABLED nécessite une clé DeepSeek et WEB_REQUEST_USD positif')


def initialize(root):
    import kararecall
    (root/'data').mkdir(parents=True,exist_ok=True)
    for name in ('sources','entities'):
        path=root/'data'/f'{name}.json'
        if not path.exists():
            kararecall.write_json(path,[])
    if not (root/'data/catalog.json').exists():
        kararecall.build(root)

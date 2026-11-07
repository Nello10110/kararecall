"""Persistent, conservative API allowances. Never stores prompts, keys or response bodies."""
from datetime import datetime,timezone
import hashlib
import math
import sqlite3

from integrations import ServiceError


class BudgetExceeded(ServiceError):pass


class UsageLedger:
    def __init__(self,root,settings):
        self.settings=settings
        self.root=root
        (root/'data').mkdir(parents=True,exist_ok=True)
        self.path=root/'data/usage.sqlite'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, started TEXT, month TEXT, day TEXT, stage TEXT, provider TEXT, model TEXT, state TEXT, input_tokens INTEGER, output_tokens INTEGER, audio_seconds REAL, accounted_usd REAL, measured_usd REAL)')
        self.publish()

    def publish(self):
        import kararecall
        kararecall.write_json(self.root/'data/usage-summary.json',{**self.summary(),'updated_at':datetime.now(timezone.utc).isoformat()})

    def connect(self):return sqlite3.connect(self.path,timeout=10)

    def can_call(self):
        instant=datetime.now(timezone.utc)
        with self.connect() as db:
            count,total=db.execute('SELECT count(*),coalesce(sum(accounted_usd),0) FROM calls WHERE month=?',(instant.strftime('%Y-%m'),)).fetchone()
            daily=db.execute('SELECT count(*) FROM calls WHERE day=?',(instant.strftime('%Y-%m-%d'),)).fetchone()[0]
        return (count<self.settings.monthly_call_limit and daily<self.settings.daily_call_limit
                and total+self.settings.call_reserve_usd<=self.settings.monthly_budget_usd+1e-9)

    def summary(self):
        instant=datetime.now(timezone.utc)
        month=instant.strftime('%Y-%m')
        with self.connect() as db:
            count,accounted,measured=db.execute('SELECT count(*),coalesce(sum(accounted_usd),0),coalesce(sum(measured_usd),0) FROM calls WHERE month=?',(month,)).fetchone()
            daily=db.execute('SELECT count(*) FROM calls WHERE day=?',(instant.strftime('%Y-%m-%d'),)).fetchone()[0]
            unknown=db.execute("SELECT count(*) FROM calls WHERE month=? AND measured_usd IS NULL",(month,)).fetchone()[0]
            web_count,web_total=db.execute("SELECT count(*),coalesce(sum(accounted_usd),0) FROM calls WHERE month=? AND stage IN ('web-search','web-fetch')",(month,)).fetchone()
        reasons=[]
        if daily>=self.settings.daily_call_limit:reasons.append('daily_calls')
        if count>=self.settings.monthly_call_limit:reasons.append('monthly_calls')
        if accounted+self.settings.call_reserve_usd>self.settings.monthly_budget_usd+1e-9:reasons.append('monthly_budget')
        return {'month':month,'calls':count,'daily_calls':daily,'daily_call_limit':self.settings.daily_call_limit,
                'monthly_call_limit':self.settings.monthly_call_limit,'blocked_by':reasons,'accounted_usd':round(accounted,6),'measured_estimate_usd':round(measured,6),
                'unpriced_calls':unknown,'limit_usd':self.settings.monthly_budget_usd,
                'web_calls':web_count,'web_accounted_usd':round(web_total,6)}

    def call(self,stage,provider,model,operation,audio_seconds=0,*,fixed_cost=None):
        config=self.settings
        instant=datetime.now(timezone.utc)
        month,day=instant.strftime('%Y-%m'),instant.strftime('%Y-%m-%d')
        reservation=config.call_reserve_usd if fixed_cost is None else fixed_cost
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count,total=db.execute('SELECT count(*),coalesce(sum(accounted_usd),0) FROM calls WHERE month=?',(month,)).fetchone()
            daily=db.execute('SELECT count(*) FROM calls WHERE day=?',(day,)).fetchone()[0]
            if daily>=config.daily_call_limit:
                raise BudgetExceeded('Quota journalier d’appels IA atteint ; reprise après minuit UTC, sans nouvel appel envoyé.')
            if count>=config.monthly_call_limit:
                raise BudgetExceeded('Quota mensuel d’appels IA atteint ; aucun nouvel appel envoyé.')
            if total+reservation>config.monthly_budget_usd+1e-9:
                raise BudgetExceeded('Budget mensuel IA insuffisant pour réserver le prochain appel ; aucun nouvel appel envoyé.')
            cursor=db.execute('INSERT INTO calls VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)',(instant.isoformat(),month,day,stage,
                hashlib.sha256(provider.encode()).hexdigest()[:16],model,'reserved',None,None,audio_seconds,reservation,None))
            identifier=cursor.lastrowid
        self.publish()
        # The allowance is durable before network access. Unknown/failed requests keep it.
        try:
            result=operation()
            usage=result.get('usage') or {}
            incoming=usage.get('prompt_tokens');outgoing=usage.get('completion_tokens')
            measured=fixed_cost
            if stage=='asr' and config.asr_usd_per_hour>0:
                measured=max(10,audio_seconds)/3600*config.asr_usd_per_hour
            elif stage in ('llm','vision'):
                rates=(config.llm_input_usd,config.llm_output_usd) if stage=='llm' else (config.vision_input_usd,config.vision_output_usd)
                if all(isinstance(n,int) and n>=0 for n in (incoming,outgoing)) and all(n>0 for n in rates):
                    measured=(incoming*rates[0]+outgoing*rates[1])/1000000
            if measured is not None and not math.isfinite(measured):measured=None
            accounted=reservation if measured is None else measured
            with self.connect() as db:
                db.execute('UPDATE calls SET state=?,input_tokens=?,output_tokens=?,accounted_usd=?,measured_usd=? WHERE id=?',
                           ('complete',incoming if isinstance(incoming,int) else None,outgoing if isinstance(outgoing,int) else None,accounted,measured,identifier))
            self.publish()
            if accounted>reservation+1e-9:
                # A wrong tariff or underestimated reserve must not trigger further calls this month.
                with self.connect() as db:
                    db.execute('UPDATE calls SET accounted_usd=? WHERE id=?',(max(accounted,config.monthly_budget_usd),identifier))
                self.publish()
                raise BudgetExceeded('Consommation supérieure à la réserve par appel ; vérifier tarifs et limites avant de reprendre.')
            return result
        except BaseException:
            with self.connect() as db:
                db.execute("UPDATE calls SET state='uncertain' WHERE id=? AND state='reserved'",(identifier,))
            self.publish()
            raise

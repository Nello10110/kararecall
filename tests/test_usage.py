from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from settings import Settings
from usage import UsageLedger,BudgetExceeded
from integrations import chat,ServiceError
from worker import pack_evidence
from web_server import context_for


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.config=Settings(root=Path(self.temp.name),monthly_budget_usd=.1,call_reserve_usd=.05)
        self.ledger=UsageLedger(self.config.root,self.config)
    def tearDown(self):self.temp.cleanup()

    def test_unknown_usage_reserves_persist_and_stop_before_network(self):
        calls=[]
        def operation():calls.append(1);return {}
        for _ in range(2):self.ledger.call('llm','provider','model',operation)
        with self.assertRaises(BudgetExceeded):UsageLedger(self.config.root,self.config).call('llm','provider','model',operation)
        self.assertEqual(len(calls),2);self.assertEqual(self.ledger.summary()['accounted_usd'],.1)
        self.assertEqual(self.ledger.summary()['unpriced_calls'],2)

    def test_failed_request_keeps_allowance(self):
        with self.assertRaises(ServiceError):
            self.ledger.call('llm','provider','model',lambda:(_ for _ in ()).throw(ServiceError('upstream error')))
        self.assertEqual(self.ledger.summary()['accounted_usd'],.05)

    def test_reported_usage_refunds_reserve_and_records_tokens(self):
        self.config.llm_input_usd=.1;self.config.llm_output_usd=.5
        for _ in range(3):
            self.ledger.call('llm','provider','model',lambda:{'usage':{'prompt_tokens':1000,'completion_tokens':1000}})
        self.assertAlmostEqual(self.ledger.summary()['accounted_usd'],.0018)
        with self.ledger.connect() as db:
            rows=db.execute('SELECT input_tokens,output_tokens,provider FROM calls').fetchall()
        self.assertEqual(rows[0][:2],(1000,1000));self.assertNotIn('provider',rows[0][2])

    def test_output_limit_and_reasoning_are_sent_and_truncation_rejected(self):
        response={'choices':[{'finish_reason':'length','message':{'content':'{partial'}}]}
        with patch('integrations.request_json',return_value=response) as request:
            with self.assertRaisesRegex(ServiceError,'tronquée'):
                chat('http://example.invalid/v1','','model',[],max_tokens=500,reasoning='none')
        payload=request.call_args.args[2]
        self.assertEqual(payload['max_completion_tokens'],500);self.assertEqual(payload['reasoning_effort'],'none')

    def test_daily_cap_stops_even_with_low_recorded_cost(self):
        self.config.daily_call_limit=1
        self.ledger.call('llm','provider','model',lambda:{})
        with self.assertRaises(BudgetExceeded):self.ledger.call('vision','provider','model',lambda:{})

    def test_fair_input_budget_keeps_all_modalities_and_reports_coverage(self):
        evidence=[{'id':f'asr-{i}','kind':'asr','text':'x'*2000} for i in range(30)]
        evidence+=[{'id':'caption','kind':'caption','text':'caption'},{'id':'ocr-0','kind':'ocr','text':'Nom visible en fin de vidéo'}]
        rows,coverage=pack_evidence(evidence,1200)
        self.assertEqual({row['kind'] for row in rows},{'caption','asr','ocr'})
        self.assertLess(coverage['asr']['included'],coverage['asr']['available'])
        packet=context_for({'name':'Test','description':'Résumé','claims':[],'source_ids':[],'coverage':coverage},{})
        self.assertIn('sélection d’extraits',packet)

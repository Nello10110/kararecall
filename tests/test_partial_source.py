"""Regression: French ASR exists while vision is quota-paused and no reading exists."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import kararecall
from curation import evidence_presentation, language_code, original_french_title
from fixtures import corpus
from settings import Settings
from usage import BudgetExceeded, UsageLedger
from web_server import source_payload, source_summary


class PartialSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        corpus(self.root)

    def tearDown(self):self.temp.cleanup()

    def test_eight_french_segments_remain_visible_without_summary_when_vision_paused(self):
        rows=kararecall.read_json(self.root/'data/sources.json')
        source=next(row for row in rows if row['id']=='demo-model')
        source['stages']={'asr':'complete','vision':'paused','llm':'waiting'}
        source['processing_error']='Quota ou budget IA atteint.'
        source.pop('reading',None)
        media=self.root/'data/media/demo-model.mp4'
        path=self.root/'data/extracted/demo-model/transcript.json'
        transcript={'status':'complete','language':'french','media_sha256':hashlib.sha256(media.read_bytes()).hexdigest(),
                    'duration':23,'segments':[{'start':index*2.8,'end':min(23,(index+1)*2.8),
                                               'text':'Ces fournisseurs sont présents dans cette vidéo de démonstration.'} for index in range(8)]}
        kararecall.write_json(path,transcript);kararecall.write_json(self.root/'data/sources.json',rows)
        kararecall.build(self.root)
        source=next(row for row in kararecall.read_json(self.root/'data/catalog.json')['sources'] if row['id']=='demo-model')
        source['processing'].pop('audio_language',None)  # Realistic catalogue published before this fix.
        original=copy.deepcopy(source);before=path.read_bytes()
        payload=source_payload(source,self.root)
        segments=[row for row in payload['evidence'] if row['kind']=='asr']
        self.assertEqual(len(segments),8)
        self.assertTrue(all(row['presentation']['state']=='original_fr' for row in segments))
        self.assertTrue(all(row['presentation']['text']==row['text'] for row in segments))
        self.assertEqual(payload['stages']['vision'],'paused');self.assertNotIn('reading',payload)
        self.assertEqual(source,original);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(payload['processing']['audio_language'],'french')

    def test_french_summary_does_not_hide_the_actual_english_audio_language(self):
        source={'id':'example','reading':{'source_language':'fr'}}
        row={'id':'asr-one','kind':'asr','text':'These are the saved original spoken words.'}
        result=evidence_presentation(source,row,'english')
        self.assertEqual(result,{'text':'','state':'translation_pending'})
        source['translations']={'asr-one':{'text':'Voici les paroles conservées.','evidence':['example#asr-one']}}
        self.assertEqual(evidence_presentation(source,row,'english')['state'],'translated_fr')

    def test_french_evidence_and_subtitles_do_not_depend_on_the_llm(self):
        source={'id':'example'}
        row={'id':'asr-one','kind':'asr','text':'Les produits sont disponibles dans ces boutiques.'}
        self.assertEqual(evidence_presentation(source,row)['state'],'original_fr')
        self.assertEqual(evidence_presentation(source,{**row,'kind':'subtitle'},subtitle_language='fra')['state'],'original_fr')
        for variant in ('FR','fr-FR','french','français','fra','fre'):
            self.assertEqual(language_code(variant),'fr')

    def test_stale_audio_language_is_not_used_for_a_different_media(self):
        source=kararecall.read_json(self.root/'data/catalog.json')['sources'][0]
        source=copy.deepcopy(source);source['processing'].pop('audio_language',None)
        source.pop('reading',None)
        source['evidence']=[{'id':'asr-one','kind':'asr','text':'These are original English words.'}]
        path=self.root/'data/extracted'/source['id']/'transcript.json'
        kararecall.write_json(path,{'status':'complete','language':'fr','media_sha256':'0'*64})
        result=source_payload(source,self.root)
        self.assertEqual(result['evidence'][0]['presentation']['state'],'translation_pending')
        self.assertNotEqual(result['processing'].get('audio_language'),'fr')

    def test_source_title_can_use_short_french_caption_without_inventing_video_analysis(self):
        title='Auteur fictif on Instagram: ”🇨🇳 Suis @demo pour apprendre à sourcer directement en Chine et vendre sur les marketplaces françaises, étape par étape. Et découvre cette offre ! Commente « TEST » pour en savoir plus.'
        preview=original_french_title(title)
        self.assertTrue(preview.startswith('apprendre à sourcer'))
        self.assertLessEqual(len(preview),80)
        self.assertNotIn('Commente',preview)
        self.assertNotIn('@demo',preview)
        self.assertEqual(original_french_title('A guide to working with a demonstration tool.'),'')
        source=kararecall.read_json(self.root/'data/catalog.json')['sources'][0]
        source=copy.deepcopy(source);source['title']=title;source.pop('reading',None)
        self.assertEqual(source_summary(source)['title'],preview)
        self.assertFalse(source_summary(source)['has_reading'])

    def test_screen_retry_is_scoped_and_keeps_normal_deduplication(self):
        from controls import request_action, process_actions
        full=request_action(self.root,'refresh',source_id='demo-model')
        screen=request_action(self.root,'refresh',source_id='demo-model',stage='vision')
        self.assertNotEqual(full['id'],screen['id'])
        self.assertEqual(screen['id'],request_action(self.root,'refresh',source_id='demo-model',stage='vision')['id'])
        with self.assertRaises(ValueError):request_action(self.root,'refresh',source_id='demo-model',stage='execute')
        with patch('worker.run_cycle',return_value={'failed':0}) as run:
            process_actions(Settings(root=self.root));process_actions(Settings(root=self.root))
            self.assertEqual([call.kwargs['force_stage'] for call in run.call_args_list],['all','vision'])

    def test_quota_details_distinguish_daily_monthly_and_budget_without_extra_calls(self):
        config=Settings(root=self.root,daily_call_limit=1)
        ledger=UsageLedger(self.root,config)
        ledger.call('llm','https://example.invalid','fixture',lambda:{})
        self.assertEqual(ledger.summary()['blocked_by'],['daily_calls'])
        self.assertEqual(ledger.summary()['daily_calls'],1)
        provider=Mock()
        with self.assertRaisesRegex(BudgetExceeded,'journalier'):ledger.call('llm','x','fixture',provider)
        config.daily_call_limit=100;config.monthly_call_limit=1
        self.assertEqual(ledger.summary()['blocked_by'],['monthly_calls'])
        with self.assertRaisesRegex(BudgetExceeded,'mensuel'):ledger.call('llm','x','fixture',provider)
        config.monthly_call_limit=400;config.monthly_budget_usd=.05
        self.assertEqual(ledger.summary()['blocked_by'],['monthly_budget'])
        with self.assertRaisesRegex(BudgetExceeded,'Budget mensuel'):ledger.call('llm','x','fixture',provider)
        provider.assert_not_called();self.assertEqual(ledger.summary()['calls'],1)

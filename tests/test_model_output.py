"""Malformed vision responses must not become empty successful OCR evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from integrations import chat, json_result, recognize_image, ModelOutputError, ServiceError
from settings import Settings
from usage import UsageLedger, BudgetExceeded


def completion(text, finish='stop', **message):
    return {'choices':[{'finish_reason':finish,'message':{'content':text,**message}}],
            'usage':{'prompt_tokens':100,'completion_tokens':20}}


class ModelOutputTests(unittest.TestCase):
    def test_deepseek_requests_json_but_does_not_force_it_on_other_providers(self):
        for base,expected in [('https://api.deepseek.com',True),('https://api.deepseek.com/v1',True),
                              ('https://example.invalid/v1',False),('https://api.deepseek.com.example.invalid',False)]:
            with self.subTest(base=base),patch('integrations.request_json',return_value=completion('{"text":"Exact"}')) as request:
                self.assertEqual(chat(base,'test-key','test-model',[],thinking='disabled',token_limit_param='max_tokens'),'{"text":"Exact"}')
                payload=request.call_args.args[2]
                self.assertEqual(payload.get('response_format'),{'type':'json_object'} if expected else None)
                self.assertEqual(payload['thinking'],{'type':'disabled'})

    def test_json_wrapping_does_not_repair_or_extract_a_partial_object(self):
        self.assertEqual(json_result('\ufeff```JSON\n{"text":"Nom tronqu"}\n```'),{'text':'Nom tronqu'})
        for text in ('', '   ', '{"text":"cassé', 'Voici le texte : {"text":"x"}', '[]'):
            with self.subTest(text=text),self.assertRaises(ModelOutputError):json_result(text)

    def test_invalid_and_blank_vision_responses_retry_once_without_sending_previous_output(self):
        for first in ('   ', 'private original answer, not JSON', '{"text":null}'):
            with self.subTest(first=first),patch('integrations.request_json',side_effect=[completion(first),completion('{"text":"outil-exampl\\nTexte inchangé"}')]) as request:
                result=recognize_image('https://api.deepseek.com','test-key','test-model',b'synthetic jpeg',thinking='disabled',token_limit_param='max_tokens')
                self.assertEqual(result,'outil-exampl\nTexte inchangé')
                self.assertEqual(request.call_count,2)
                for call in request.call_args_list:
                    payload=call.args[2]
                    self.assertEqual(payload['response_format'],{'type':'json_object'})
                    self.assertNotIn('private original answer',json.dumps(payload))
                    self.assertTrue(payload['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))

    def test_repeated_bad_output_remains_an_error_and_does_not_leak_content(self):
        with patch('integrations.request_json',return_value=completion('private response body')) as request:
            with self.assertRaisesRegex(ModelOutputError,'deux réponses') as raised:
                recognize_image('https://api.deepseek.com','test-secret','test-model',b'image')
            self.assertEqual(request.call_count,2)
            self.assertNotIn('private response body',str(raised.exception))
            self.assertNotIn('test-secret',str(raised.exception))

    def test_bad_chat_envelope_is_diagnosed_without_retry(self):
        for response in ({'choices':None},{'choices':[]},{'choices':[{'message':None}]}):
            with self.subTest(response=response),patch('integrations.request_json',return_value=response) as request:
                with self.assertRaisesRegex(ServiceError,'incompatible'):
                    recognize_image('https://example.invalid','','model',b'image')
                self.assertEqual(request.call_count,1)

    def test_explicitly_empty_ocr_is_success_but_truncation_refusal_and_http_are_not_retried(self):
        with patch('integrations.request_json',return_value=completion('{"text":""}')) as request:
            self.assertEqual(recognize_image('https://example.invalid','','model',b'image'),'')
            self.assertEqual(request.call_count,1)
        for response in (completion('{"text":"partiel"}',finish='length'),
                         completion('{"text":"x"}',finish='content_filter'),
                         completion('',refusal='private refusal')):
            with self.subTest(response=response),patch('integrations.request_json',return_value=response) as request:
                with self.assertRaises(ServiceError):recognize_image('https://example.invalid','','model',b'image')
                self.assertEqual(request.call_count,1)
        with patch('integrations.request_json',side_effect=ServiceError('HTTP 503')) as request:
            with self.assertRaises(ServiceError):recognize_image('https://example.invalid','','model',b'image')
            self.assertEqual(request.call_count,1)

    def test_each_retry_is_accounted_and_daily_limit_blocks_before_second_network_call(self):
        with tempfile.TemporaryDirectory() as name:
            config=Settings(root=Path(name),daily_call_limit=1)
            ledger=UsageLedger(config.root,config)
            with patch('integrations.request_json',return_value=completion('  ')) as request:
                with self.assertRaises(BudgetExceeded):
                    recognize_image('https://api.deepseek.com','','model',b'image',ledger=ledger)
                self.assertEqual(request.call_count,1)
                self.assertEqual(ledger.summary()['calls'],1)
            config.daily_call_limit=3
            with patch('integrations.request_json',side_effect=[completion('invalid'),completion('{"text":"Visible"}')]) as request:
                self.assertEqual(recognize_image('https://api.deepseek.com','','model',b'image',ledger=ledger),'Visible')
                self.assertEqual(request.call_count,2)
                self.assertEqual(ledger.summary()['calls'],3)

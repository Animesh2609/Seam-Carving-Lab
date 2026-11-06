import unittest
from uuid import UUID
from unittest.mock import patch
import numpy as np
from image_history import HistoryConfig, ImageHistory, HistoryError
from seamcarving import ObjectRemovalService

USER='11111111-1111-4111-8111-111111111111'
SESSION={'id':USER,'access_token':'fake-jwt'}

class FakeResponse:
    def __init__(self, code=200, payload=None, content=b'PNG'):
        self.status_code=code
        self._payload = payload if payload is not None else {}
        self.content=content
    def json(self):
        return self._payload

class FakeTransport:
    def __init__(self):
        self.requests=[]
    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if method=='GET' and 'image_history' in url:
            return FakeResponse(payload=[])
        if method=='POST' and 'image_history' in url:
            return FakeResponse(code=201,payload=[{'id':USER,'user_id':USER}])
        return FakeResponse(code=200,content=b'PNG')

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.transport=FakeTransport()
        self.client=ImageHistory(HistoryConfig('https://example.supabase.co','public-test-key'),
                                  self.transport)

    def test_saves_paired_files_with_user_jwt(self):
        result=self.client.save(SESSION,b'png-input',b'png-output',
            'Seam carving','sample.png',(10,8),(8,8),{'method':'Backward'})
        self.assertEqual(result['user_id'],USER)
        self.assertEqual(len(self.transport.requests),3)
        files=self.transport.requests[:2]
        self.assertTrue(all(x[0]=='POST' and f'/{USER}/' in x[1] for x in files))
        self.assertTrue(all(x[2]['headers']['Authorization']=='Bearer fake-jwt' for x in files))
        self.assertNotIn('service_role',str(self.transport.requests))

    def test_list_filter_and_privacy(self):
        self.client.list(SESSION)
        self.assertIn('user_id=eq.'+USER,self.transport.requests[0][1])
        with self.assertRaises(HistoryError):
            self.client.download(SESSION,'other-person/file.png')

    def test_rejects_invalid_operation_and_oversize(self):
        with self.assertRaises(HistoryError):
            self.client.save(SESSION,b'x',b'y','Admin bypass','src',(10,10),(10,10))
        with self.assertRaises(HistoryError):
            self.client.upload(SESSION,USER+'/file.png',b'a'*(8*1024*1024+1))

    def test_unbounded_object_removal_replaced_by_time_budget(self):
        sample=np.zeros((6,6,3),dtype=np.uint8)
        mask=np.zeros((6,6),dtype=bool)
        mask[1:3,1:3]=True
        with patch('seamcarving.advanced.perf_counter',side_effect=[1.0,100.0]):
            result=ObjectRemovalService().remove(sample,mask,
                restore_size=False,max_seams=None,max_seconds=1.0)
        self.assertTrue(result.timed_out)
        self.assertGreater(result.remaining_mask_pixels,0)
        self.assertEqual(result.removed_vertical+result.removed_horizontal,0)

if __name__=='__main__':
    unittest.main()

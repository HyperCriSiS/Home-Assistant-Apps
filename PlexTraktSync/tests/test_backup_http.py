"""Exercise the real Ingress backup routes with an emulated proxy source."""
import json
import time
import unittest

import requests

import test_http_auth as http_tests
from test_backups import fixture


class BackupHTTPTests(unittest.TestCase):
    setUp = http_tests.HTTPTests.setUp
    tearDown = http_tests.HTTPTests.tearDown
    serve = http_tests.HTTPTests.serve

    def seed(self):
        return self.c.backups.store.save({'id':'fixture','username':'Fixture'},fixture(),'manual',time.time(),self.c.backups.settings)

    def test_source_and_csrf_protect_backup_listing_mutation_and_upload(self):
        url = self.serve()
        for path in ('/api/backups','/api/backups/download/'+'a'*32):
            self.assertEqual(requests.get(url+path,timeout=5).status_code,403)
        url = self.serve(ingress=True)
        self.assertEqual(requests.get(url+'/api/backups',timeout=5).status_code,200)
        self.assertEqual(requests.post(url+'/api/backup-create',json={'categories':['history']},timeout=5).status_code,403)
        self.assertEqual(requests.post(url+'/api/backups/import',data=b'fake',headers={'Content-Type':'application/zip'},timeout=5).status_code,403)

    def test_archive_download_import_and_invalid_upload(self):
        entry=self.seed();url=self.serve(ingress=True)
        response=requests.get(url+'/api/backups/download/'+entry['id'],timeout=5)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Content-Type'],'application/zip')
        headers={'Content-Type':'application/zip','X-CSRF-Token':self.c.csrf}
        uploaded=requests.post(url+'/api/backups/import',data=response.content,headers=headers,timeout=5)
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        self.assertNotEqual(uploaded.json()['archive_id'],entry['id'])
        self.assertEqual(requests.post(url+'/api/backups/import',data=b'broken',headers=headers,timeout=5).status_code,400)
        headers['Content-Type']='text/plain'
        self.assertEqual(requests.post(url+'/api/backups/import',data=response.content,headers=headers,timeout=5).status_code,400)
        self.assertEqual(requests.get(url+'/api/backups/download/credentials.json',timeout=5).status_code,404)

    def test_settings_save_stale_revision_and_explicit_deletion(self):
        url=self.serve(ingress=True);headers={'X-CSRF-Token':self.c.csrf}
        state=requests.get(url+'/api/backups',timeout=5).json()
        settings={**state['settings'],'enabled':True}
        payload={'settings':settings,'revision':state['revision']}
        self.assertEqual(requests.post(url+'/api/backup-settings',json=payload,headers=headers,timeout=5).status_code,200)
        self.assertEqual(requests.post(url+'/api/backup-settings',json=payload,headers=headers,timeout=5).status_code,400)
        entry=self.seed()
        self.assertEqual(requests.post(url+'/api/backup-delete',json={'id':entry['id']},headers=headers,timeout=5).status_code,400)
        self.assertTrue(self.c.backups.store.path(entry['id']).exists())
        self.assertEqual(requests.post(url+'/api/backup-delete',json={'id':entry['id'],'confirmation':'LÖSCHEN'},headers=headers,timeout=5).status_code,200)
        self.assertFalse(self.c.backups.store.path(entry['id']).exists())


if __name__=='__main__':
    unittest.main()

# -*- coding: iso-8859-1 -*
# ZSQL - Zope Python product and Z SQL Method bridge
# License: ZPL
# Copyright: Peter Bengtsson, Fry-IT, 2007
#

import os, sys, re
import cPickle as pickle

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))


from Testing import ZopeTestCase

from Products.ZSQL.SQL import SimpleRecord, MemCache, InterceptedSQLClass

class TestSQL(ZopeTestCase.ZopeTestCase):
    
    def afterSetUp(self):
        pass
    
    def tearDown(self):
        pass
    
    
    def test_SimpleRecord_pickle(self):
        """ test that we can pickle (protocol 2) SimpleRecord objects """
        friend = SimpleRecord(name='Zahid', age=40)
        as_pickle = pickle.dumps(friend, 2)
        as_object = pickle.loads(as_pickle)
        self.assertEqual(as_object.keys(), friend.keys())
        self.assertEqual(as_object.values(), friend.values())
        
        
    def test_MemCache(self):
        cache = MemCache(('127.0.0.1:11211',))
        try:
            assert 1 == cache.set('os.listdir("/tmp")', os.listdir("/tmp"))
        except AssertionError:
            class MemcacheError(Exception):
                pass
            raise MemcacheError("memcache server not running")
        
        self.assertEqual(cache.get('os.listdir("/tmp")'), os.listdir("/tmp"))
        self.assertEqual(cache.get('not-set-yet'), None)

        cache.delete('os.listdir("/tmp")')
        self.assertEqual(cache.get('os.listdir("/tmp")'), None)
        
        # test the timeout
        cache.set('os.listdir("/tmp")', os.listdir("/tmp"), timeout=1)
        self.assertEqual(cache.get('os.listdir("/tmp")'), os.listdir("/tmp"))
        from time import sleep
        sleep(2)
        self.assertEqual(cache.get('os.listdir("/tmp")'), None)
        
        
        # an incorrect port number, don't expect a memcache server to run there
        cache = MemCache(('127.0.0.1:11212',))
        self.assertEqual(cache.set('os.listdir("/tmp")', os.listdir("/tmp")), 0)
        
        
    def test_InterceptedSQLClass(self):
        klass = InterceptedSQLClass('SQLSelect', 'Somet title', 'db-connection',
                                    'arg1 arg2', 'select * from users',
                                    'SQLselect.sql')
        
        self.assertEqual(klass.getRelpath(), 'SQLselect.sql')
        
#
# Need to write more tests
#
        


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSQL))
    return suite

if __name__ == '__main__':
    framework()

    

# -*- coding: iso-8859-1 -*
# ZSQL - Zope Python product and Z SQL Method bridge
# License: ZPL
# Copyright, Peter Bengtsson, Fry-IT, 2007
# http://www.fry-it.com/oss/ZSQL

# Python
import os, time, sys
import inspect
import logging

# Zope
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Globals import package_home
from Products.ZSQLMethods.SQL import SQL
from DateTime import DateTime

from App.config import getConfiguration
conf = getConfiguration()
ZOPE_DEBUG_MODE = conf.debug_mode

# Product
class MissingArgumentsError(Exception):
    pass
class ExcessArgumentsError(Exception):
    pass

def debug(s):
    print s


try:
    import memcache as memcache_
    __memcache_installed__ = True
except ImportError:
    memcache_ = None
    __memcache_installed__ = False


logger = logging.getLogger('ZSQL')

# I've done some testing with cmemcache instead of memcache and found that the
# difference is also negligable. Ie. using cmemcache instead of python-memcache
# doesn't make it any faster. python-memcache is fast enough. What takes time
# isn't that, it's the other stuff around it. For example, I did a test on
# getting 500 * 10 reads first with python-memcache and then with cmemcache.
# With python-memcache it took 18.7 seconds, with cmemcache it took 18.1 :)
#import cmemcache as memcache




##
## Possible TODO, have a look what the fastest template rendering
## engine is to be used instead of DTML. Perhaps DTML is very fast
## and the cost of replacing it with something like WebString might
## have dire consequences on the complete rendering of the ZSQL
## method.
##


def _debugSQLCall(object, kw, debug_filename):
    """ Write to debug file for log of all SQL calls """
    if not debug_filename:
        debug_filename = '/tmp/sqllog.log'
    path = os.path.join(CLIENT_HOME, debug_filename)
    
    sql_method = str(object.id)
    params = str(kw)
    relpath = object.relpath
    
    datetime = DateTime().strftime('%Y/%m/%d %H:%M:%S')
    line = '%s|%s|%s|%s\n'%(sql_method, relpath, params, datetime)
    open(path, 'a').write(line)
    
    
def _profileSQLCall(object, timetaken, kw, profiling_filename):
    """ write to log file how long it took to execute
    this SQL statement. """
    if not profiling_filename:
        profiling_filename = '/tmp/sqlprofiling.log'
    path = os.path.join(CLIENT_HOME, profiling_filename)
    fw = open(path, 'a')
        
    out = [str(object.relpath), str(timetaken)]
    out = '|'.join(out)
    
    fw.write(out+'\n')
    fw.close()

    
    
class SimpleRecord(dict):
    """ Convert a Zope ZSQL Record into a dict like object that works 
    like a dict but with a __getattr__ method.
    """
    __allow_access_to_unprotected_subobjects__ = 1
    
    def __init__(self, *a, **kw):
        if a:
            if hasattr(a[0], '__record_schema__'):
                for k, v in a[0].__record_schema__.items():
                    kw[k] = a[0][v]
                    
            elif isinstance(a[0], dict):
                kw.update(a[0])
        dict.__init__(self, **kw)
        
    def __getattr__(self, key):
        """ see 
        http://groups.google.com/group/comp.lang.python/browse_thread/thread/40d95aa4a99f3b87/7219e0c75af69198 """
        try:
            return self[key]
        except KeyError:
            raise AttributeError 



class MemCache(object):
    def __init__(self, servers):
        self._cache = memcache_.Client(servers)
        self.default_timeout = 300

    def get(self, key, default=None):
        val = self._cache.get(key)
        if val is None:
            return default
        else:
            return val

    def set(self, key, value, timeout=0):
        return self._cache.set(key, value, timeout or self.default_timeout)

    def delete(self, key):
        return self._cache.delete(key)

    def get_many(self, keys):
        return self._cache.get_multi(keys)
    
    
        
class InterceptedSQLClass(SQL):
    """ subclass of the SQL (from ZSQLMethods) so that
    we can enable possible executions and initializations.
    
    
    @ memcache_prefix : A string that prepends on all memcaching keys. Useful if you 
                       fear that your application might share the same path and params
                       as in another application.
    @ memcache_servers : a list or tuple of addresses to memcache servers
    @ debug_sqlcalls : All rendered SQL is printed and written to a log file
    @ debug_sqlcalls_filename : If you don't want to log all rendered SQL in
                                /tmp/sqllog.log
    @ profile_sqlcalls : Take the time it takes to run the SQL command.
    @ profile_sqlcalls_filename : If you don't want to log all profiling 
                                  in /tmp/sqlprofiling.log
                                
    """
    
    def __init__(self, id, title, connection_id, arguments, template, relpath, 
                 memcache_prefix='', 
                 memcache_servers=('127.0.0.1:11211',),
                 debug_sqlcalls=False, 
                 debug_sqlcalls_filename=None,
                 profile_sqlcalls=False,
                 profile_sqlcalls_filename=None):
        self.id=str(id)
        try:
            self.manage_edit(title, connection_id, arguments, template)
        except:
            debug("id=%r, title=%r, arguments=%r" % (id, title, arguments))
            raise 
        self.relpath = relpath
        assert isinstance(memcache_prefix, str), "memcache_prefix must be a string"
        self.memcache_prefix = memcache_prefix
        self.memcache_servers = memcache_servers
        self.debug_sqlcalls = debug_sqlcalls
        self.debug_sqlcalls_filename = debug_sqlcalls_filename
        self.profile_sqlcalls = profile_sqlcalls
        self.profile_sqlcalls_filename = profile_sqlcalls_filename


    def _initMemcache(self):
        self._v_memcache = MemCache(self.memcache_servers)
        
    
    def __call__(self, REQUEST=None, __ick__=None, src__=False, test__=False,
                 debug__=False, memcache__=False, explain__=False, **kw):
        """ override __call__ for debugging purposes
        
        @ src__ = True: return the computed query before being tested about the database
        @ test__= True: return (query, result) and not just result
        @ debug__= True: print the SQL statement before running it (if in DEBUG mode)
        @ memcache__ = True: memcaches the result for consequtive calls for 5 minutes
        @ memcache__ = int: memcaches the result for consequtive calls for 'int' seconds
        """
        
        # legacy 
        if kw.has_key('force_debug__'):
            debug__ = kw.get('force_debug__')
            kw.pop('force_debug__')
            import warnings
            warnings.warn("Use 'debug__' instead of 'force_debug__'", DeprecationWarning, 2)
        
            
        if self.debug_sqlcalls or debug__:
            if self.debug_sqlcalls_filename:
                _debugSQLCall(self, kw, self.debug_sqlcalls_filename)
                
            query = apply(SQL.__call__, (self, REQUEST, __ick__, 1, test__), kw)
            out = "--- %s(%s) ---" % (self.__name__, kw)
            
            if len(out) < 80:
                out += (80 - len(out)) * '-'
            sys.stdout.write(out + '\n')
            try:
                query = str(query)
            except UnicodeEncodeError:
                query = query.encode('ascii', 'replace')
            sys.stdout.write(query + '\n\n')
            
        if explain__:
            title, connection_id, arguments, prev_template = self.title, self.connection_id, self.arguments_src, self.src
            template = 'EXPLAIN ANALYZE\n' + prev_template
            self.manage_edit(title, connection_id, arguments, template)
            for line in apply(SQL.__call__, (self, REQUEST, __ick__, False, test__), kw):
                sys.stdout.write('%s\n' % line['QUERY PLAN'])
            self.manage_edit(title, connection_id, arguments, prev_template)
            

        if ZOPE_DEBUG_MODE:
            # If we're running Zope in debug mode, make some extra checks that
            # the parameters defined for this SQL call are correctly set.
            
            required_arguments = self._arg.keys()
            missing_arguments = [a for a in required_arguments if not kw.has_key(a)]
            excess_arguments = [k for k in kw.keys() if k not in required_arguments]
            if excess_arguments:
                tmpl = self.getRelpath()
                m = "%s was called with " % tmpl
                if len(excess_arguments) > 1:
                    m += "arguments: %s passed " %\
                         ', '.join([repr(x) for x in excess_arguments])
                else:
                    m += "argument: %r passed " % excess_arguments[0]
                m += "but not needed."
                try:
                    stk = inspect.stack()[1]
                    module = stk[1].replace(INSTANCE_HOME, '')
                    if module.startswith('/'):
                        module = module[1:]
                    module = module.replace('/','.')
                    m += "Called from %s, line %s, in %s" % (module, stk[2], stk[3])
                except IndexError:
                    m += "**Unabled to trace inspect stack**"
                raise ExcessArgumentsError, m
            
            if missing_arguments:
                tmpl = self.getRelpath()
                m = "%s was called without " % tmpl
                if len(missing_arguments) > 1: 
                    m += "arguments: %s passed." % ', '.join([repr(x) for x in missing_arguments])
                else:
                    m += "argument: %r passed." % missing_arguments[0]
                stk = inspect.stack()[1]
                module = stk[1].replace(INSTANCE_HOME, '')
                if module.startswith('/'):
                    module = module[1:]
                module = module.replace('/','.')
                m += "Called from %s, line %s, in %s" % (module, stk[2], stk[3])
                raise MissingArgumentsError, m


        if self.profile_sqlcalls:
            result, time_delta = self._getResultRecords(SQL.__call__,
                                      (self, REQUEST, __ick__, src__, test__), 
                                      kw,
                                      memcache=memcache__,
                                      profile=True)
            _profileSQLCall(self, time_delta, kw, self.profile_sqlcalls_filename)
            return result

        result, __ = self._getResultRecords(SQL.__call__, 
                                       (self, REQUEST, __ick__, src__, test__),
                                       kw, memcache=memcache__)
        return result
        
    def _getResultRecords(self, func, params, kwargs, memcache=False, profile=False):
        """ return the (records, time taken) """
        if memcache and not __memcache_installed__:
            logger.warn("Can't use memcache when memcache module is not installed")
            memcache = False
            
        if memcache:
            # Ok. We're going to try to use memcache to find the result first.
            # First make sure the non-persistent volatile memcache memory is set up.
            if not hasattr(self, '_v_memcache'):
                self._initMemcache()
                
            # Then construct a "unique" identifing key for this particular call.
            # This is constructed by combining the name of the .sql files, the keywords
            # passed and an optional prefix.
            key = self._getMemcacheKey(kwargs)
            if not hasattr(self, '_v_seen_keys'):
                self._v_seen_keys = []
            
            # Read it from the memcache. Either we get the records (nb: simplified)
            # or we get None.
            records = self._v_memcache.get(key)
            #if records is not None: 
            #    print "WOW! " * 10
                
            # Assume that it takes 0 seconds to read it from the memcache :)
            time_delta = 0
            
            # Ok. The memcache didn't have it. Let's really run the SQL command
            # and if 'profile' was passed as true, take the time it takes to
            # run the SQL command.
            if records is None:
                
                if profile:
                    # Ok. We need to wrap the actual getting in a timer
                    t0 = time.time()
                    records = apply(func, params, kwargs)
                    time_delta = time.time() - t0
                else:
                    records = apply(func, params, kwargs)
                    
                # Now set the result in the memcache for consequtive calls.
                # If the memcache passed was an integer, it will indicate how many
                # seconds are supposed to memcache it for.
                if memcache and not __memcache_installed__:
                    logger.warn("Can't use memcache when memcache module is not installed")
                    memcache = False
                    
                if memcache > 1:
                    self._v_memcache.set(key, [SimpleRecord(record) for record in records],
                                         timeout=memcache)
                else:
                    self._v_memcache.set(key, [SimpleRecord(record) for record in records])

            # Always return the records followed by the time_delta
            return records, time_delta
        else:
            # No memcache, just normal call profiled or not
            if profile:
                t0=time.time()
                records = apply(func, params, kwargs)
                return records, time.time() - t0
            else:
                return apply(func, params, kwargs), 0
            
        
    def _getMemcacheKey(self, kwargs):
        """ Return a ascii string of the relpath, keyword arguments and an
        optional prefix. Helps with the interfacing with the memcache. 
        This """
        # To make sure the key is as short as possible, remove all junk 
        relpath = self.getRelpath().replace('.sql','')
        kwargs = str(kwargs.values()).replace(' ','')
        s=[relpath, kwargs]
        if self.memcache_prefix:
            s.append(self.memcache_prefix)
        return '|'.join(s)        


    def getRelpath(self):
        return self.relpath


    
##
## Load in all the SQL statements from the files in sql/
##


def _getSQLandParams(filename):
    """ scan a SQL file and return the SQL statement as string
    and the params as a list """
    data = open(filename, 'r').read()
    statement = data[data.find('</params>')+len('</params>'):]
    paramsstr = data[data.find('<params>')+len('<params>'):data.find('</params>')]
    params = paramsstr.replace('\n',' ')
    params = params.split(' ')
    if params==['']:
        params = []
    else:
        params = [x for x in params if x]
    return params, statement.strip()




def _filterSQLextension(filenames):
    return [x for x in filenames 
            if x.lower().endswith('.sql') and not x.startswith('.#')]


def initializeSQLfiles(folder2class, sqlhomepath, **kw):
    ''' given a dictionary of foldernames and classes, return them as 
    a list of ZSQL Methods.
    For the documentation of the '**kw' options, see the doc string of
    InterceptedSQLClass.
    '''
    
    if kw.get('profile_sqlcalls'):
        log_filename = kw.get('profile_sqlcalls_filename',
                              '/tmp/sqlprofiling.log')
        logging.info("Note! All SQL calls are profiled in %s" % log_filename)
    
    for folder, Class in folder2class.items():
        Class.allsqlattributes = []
        if folder.count(':'):
            folder = folder.split(':')
            foldername = apply(os.path.join, folder)
        else:
            foldername = folder
        folder = os.path.join(sqlhomepath, foldername)
        for sqlfile in _filterSQLextension(os.listdir(folder)):
            # from the file, get the params and the statement
            params, statement = _getSQLandParams(os.path.join(folder, sqlfile))
                
            # make up an id
            id = sqlfile[:-4] # removes '.sql'

            # determine relpath
            relpath = os.path.join(folder, sqlfile).replace(sqlhomepath,'')
            
            # make ['par1:int', 'par2'] => 'par1:int par2'
            params = ' '.join(params)
            title = sqlfile
            
            # Now, create this attribute to 'Class'
            dbConnection = Class.dbConnection
            sqlclass = InterceptedSQLClass
            try:
                setattr(Class, id, sqlclass(id, title, dbConnection, 
                                            params, statement, relpath, **kw))
            except:
                print >>sys.stderr, "Failed to initialize %s" % relpath
                raise
        
    

    
            
    


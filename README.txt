ZSQL - Zope Python product and Z SQL Method bridge
==================================================

Overview
--------

 License: ZPL
 Copyright, Peter Bengtsson, peter@fry-it.com, Fry-IT, 2007

 This product is meant to be used my other Zope Python products where 
 you want to have the SQL code on the filesystem as a .sql files and
 use DTML for the rendering. 
 This product helps setting up the Z SQL Methods seemlessly with some
 added debugging and optimization features.
 
 
Usage
-----

 You write a little wrapper in your product and define the classes of
 Z SQL Methods you want to use and put the .sql files inside the product
 with directory names like you please. Assuming you have these file:
 
 __init__.py
 MyApp.py
 SQLWrapper.py
 sql/
   Users/
     SQLSelectUsers.sql
     SQLInsertUser.sql
   Cookies/
     SQLSelectCookies.sql
     SQLDeleteCookie.sql
  
 Then, inside SQLWrapper.py you put the following code::
 
  import Acquisition
  from Globals import package_home
  from Products.ZSQL import initializeSQLfiles
  
  sqlhome = os.path.join(package_home(globals()), 'sql')
  
  class PSQL(Acquisition.Implicit):
      dbConnection = 'Psycopg_database_connection'
  class SQLUsers(PSQL):
      pass
  class SQLCookies(PSQL):
      pass

  Folder2Class = {
    'Cookies':SQLCookies,
    'Users':SQLUsers,
    }
    
  initializeSQLfiles(Folder2Class, sqlhome)
  
  
 Once you've done this, the classes 'SQLUsers' and 'SQLCookies' will
 have automatically gotten the Z SQL Methods 'SQLSelectUsers',
 'SQLInsertUser' and 'SQLSelectCookies', 'SQLDeleteCookie'.

 Now you can use these are normal member functions in your main class.
 Inside MyApp.py::
 
  class MyApp(Folder):
      meta_type = 'Something'
      def __init__(self, id):
          self.id = id
          
      def addUser(self, name):
          for user in self.SQLSelectUsers():
              print user.name
          self.SQLInsertUser(name=name)
          
      def removeCookie(self, key):
          self.SQLDeleteCookie(key=key)
          
          
 The .sql files **have** to start with <params>...</params>. For
 example, it can look like this::
 
  <params>
  key
  name
  </params>
  INSERT INTO users (key, name) VALUES (
  <dtml-sqlvar key type="int">,  <dtml-sqlvar name type="string">
  )
  
  
 
Features
--------

 One useful feature is that you can easily debug the rendered SQL code
 and have it printed to stdout by calling it like this::
 
  SQLInsertUser(key=123, name='Peter', debug__=True)
  
 Or if you want to use memcache for those slow database queries that
 you repeat like this::
 
  SQLSelectAverageUserAge(min=10, max=20, memcache__=True)
  
 If you call this a second time (within 5 minutes) the result will
 come from a memcache instead. This only becomes useful if the SQL
 query is slow and for this to work you need to have a memcache server
 running on 127.0.0.1:11211.
 
 If you want to debug all SQL calls to stdout you can call 
 the initializeSQLfiles() method like this instead::
 
  initializeSQLfiles(Folder2Class, sqlhome, debug_sqlcalls=True)
  
 If you also want to have all of these written to file you can
 do that this way::
 
  initializeSQLfiles(Folder2Class, sqlhome, debug_sqlcalls=True,
                     debug_sqlcalls_filename='/tmp/sqlcalls.log')
                      
 Similar to the 'debug_sqlcalls' and 'debug_sqlcalls_filename' is
 the profiling option except that when profiling is on, it's not
 printed to stdout. If you set up your SQL files like this::
 
  initializeSQLfiles(Folder2Class, sqlhome, profile_sqlcalls=True)
  
 Then it writes all profiling records to /tmp/sqlprofiling.log.
 Alternatively you can override this like this::
 
  initializeSQLfiles(Folder2Class, sqlhome, profile_sqlcalls=True,
          profile_sqlcalls_filename=r'C:\Temp\sqlprofileing.log')
          
       
 
 
  
 

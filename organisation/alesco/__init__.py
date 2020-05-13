import importlib
import os

from django.conf import settings


def _import_synctask():
    table_name = settings.FOREIGN_TABLE
    return importlib.import_module("organisation.alesco.{}".format(table_name))

synctask = _import_synctask()


def aleso_db_init():
    """
    create the foreign server and foreign table in postgresql database
    """
    conn = synctask.alesco_db_connection()
    cur = None
    try:
        conn.autocommit=True
        cur = conn.cursor()

        #check whether foreign table exist or not
        cur.execute("SELECT COUNT(*) FROM pg_foreign_table a JOIN pg_class b ON a.ftrelid=b.oid JOIN pg_namespace c ON b.relnamespace=c.oid  WHERE b.relname='{}' AND c.nspname='{}';".format(
            settings.FOREIGN_TABLE,
            settings.FOREIGN_SCHEMA
        ))
        if cur.fetchone()[0]:
            #foreign table is  created
            return

        #create oracle_fdw extension
        cur.execute("SELECT COUNT(*) FROM pg_extension WHERE extname='oracle_fdw';")
        if not cur.fetchone()[0]:
            #oracle_fdw extension is not created
            cur.execute("create extension oracle_fdw;")
            
        #create foreign server
        cur.execute("SELECT COUNT(*) FROM pg_foreign_server WHERE srvname='{}';".format(settings.FOREIGN_SERVER))
        if not cur.fetchone()[0]:
            #foreign server is not created
            cur.execute("CREATE SERVER {} FOREIGN DATA WRAPPER oracle_fdw OPTIONS (dbserver '{}');".format(settings.FOREIGN_SERVER,settings.ALESCO_DB_SERVER))

        #create user mapping
        cur.execute("SELECT COUNT(*) FROM pg_user_mapping a JOIN pg_authid b ON a.umuser=b.oid JOIN pg_foreign_server c ON a.umserver = c.oid  WHERE b.rolname='{}' AND c.srvname='{}';".format(
            settings.FOREIGN_DB_USERNAME,
            settings.FOREIGN_SERVER
        ))
        if not cur.fetchone()[0]:
            #user mapping is not created
            cur.execute("CREATE USER MAPPING FOR {} SERVER {} OPTIONS (user '{}', password '{}');".format(
                settings.FOREIGN_DB_USERNAME,
                settings.FOREIGN_SERVER,
                settings.ALESCO_DB_USER,
                settings.ALESCO_DB_PASSWORD
            ))
            
        #foreign table is not created
        cur.execute(synctask.FOREIGN_TABLE_SQL.format(
            foreign_schema=settings.FOREIGN_SCHEMA,
            foreign_table=settings.FOREIGN_TABLE,
            foreign_server=settings.FOREIGN_SERVER,
            alesco_db_schema=settings.ALESCO_DB_SCHEMA,
            alesco_db_table=settings.ALESCO_DB_TABLE
        ))

    finally:
        if cur:
            try:
                cur.close()
            except:
                logger.error(traceback.format_exc())

        if conn:
            try:
                conn.close()
            except:
                logger.error(traceback.format_exc())


aleso_db_init()

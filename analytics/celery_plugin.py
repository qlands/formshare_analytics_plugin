import formshare.plugins as plugins
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


class AnalyticsRepository(plugins.SingletonPlugin):
    plugins.implements(plugins.IRepositoryProcess)

    def after_creating_repository(
        self,
        settings,
        user,
        project,
        form,
        cnf_file,
        create_file,
        insert_file,
        schema,
        log,
    ):
        engine = None
        try:
            engine = create_engine(settings.get("sqlalchemy.url"), poolclass=NullPool)
        except Exception as e:
            log.error(
                "Analytics plugin: Cannot create engine. Error: {}".format(str(e))
            )
        if engine is not None:
            connection = None
            try:
                connection = engine.connect()
            except Exception as e:
                log.error(
                    "Analytics plugin: Cannot create connection. Error: {}".format(
                        str(e)
                    )
                )
                engine.dispose()
            if connection is not None:
                try:
                    sql = (
                        "SELECT fsuser.user_query_user "
                        "FROM fsuser,userproject "
                        "WHERE fsuser.user_id = userproject.user_id "
                        "AND userproject.project_id = '{}' "
                        "AND fsuser.user_active = 1 "
                        "AND userproject.project_accepted = 1 "
                        "AND fsuser.user_query_user IS NOT NULL".format(project)
                    )
                    users = connection.execute(sql).fetchall()
                    if users is not None:
                        if users:
                            log.info(
                                "Allowing analytics access to schema {}".format(schema)
                            )
                            for a_user in users:
                                sql = "GRANT SELECT ON {}.* TO '{}'@'%'".format(
                                    schema, a_user[0]
                                )
                                connection.execute(sql)
                    connection.invalidate()
                    engine.dispose()
                except Exception as e:
                    log.error(
                        "Analytics plugin: Cannot grant access to schema {}. Error: {}".format(
                            schema, str(e)
                        )
                    )
                    connection.invalidate()
                    engine.dispose()

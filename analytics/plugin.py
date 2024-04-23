import formshare.plugins as plugins
import sys
import os
import logging
from formshare.processes.email.send_email import send_error_to_technical_team
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import formshare.plugins.utilities as u
from formshare.processes.db import is_user_active, get_query_user, get_user_databases
from analytics.views import AnalyticsView, EnableAnalyticsView
from formshare.processes.db.utility import get_db_connection

log = logging.getLogger("formshare")


def _get_engine_and_connection(request, user_id):
    engine = None
    try:
        engine = create_engine(
            request.registry.settings.get("sqlalchemy.url"),
            poolclass=NullPool,
        )
        connection = engine.connect()
    except Exception as e:
        send_error_to_technical_team(
            request,
            "Error while creating analytics account for user: {}\n"
            "Engine Error: {}".format(user_id, str(e)),
        )
        connection = None
        engine.dispose()
    return engine, connection


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class Analytics(plugins.SingletonPlugin):
    plugins.implements(plugins.IRoutes)
    plugins.implements(plugins.IConfig)
    plugins.implements(plugins.ITranslation)
    plugins.implements(plugins.IUser)
    plugins.implements(plugins.ICollaborator)
    plugins.implements(plugins.IForm)
    plugins.implements(plugins.IProject)

    # IRoutes
    def before_mapping(self, config):
        # We don't add any routes before the host application
        return []

    def after_mapping(self, config):
        # We add here a new route /json that returns a JSON
        custom_map = [
            u.add_route(
                "analytics",
                "/user/{userid}/analytics",
                AnalyticsView,
                "analytics/index.jinja2",
            ),
            u.add_route(
                "enable_analytics",
                "/user/{userid}/analytics/enable",
                EnableAnalyticsView,
                None,
            ),
        ]

        return custom_map

    # IConfig
    def update_config(self, config):
        # We add here the templates of the plugin to the config
        u.add_templates_directory(config, "templates")
        u.add_static_view(config, "analytics", "static")

    # ITranslation
    def get_translation_directory(self):
        module = sys.modules["analytics"]
        return os.path.join(os.path.dirname(module.__file__), "locale")

    def get_translation_domain(self):
        return "analytics"

    # IUser
    def before_creating_user(self, request, user_data):
        return user_data, True, ""

    def after_creating_user(self, request, user_data):
        pass

    def before_editing_user(self, request, user, user_data):
        user_data["user_was_active"] = is_user_active(request, user)
        user_data["query_user"] = get_query_user(request, user)
        return user_data, True, ""

    def after_editing_user(self, request, user, user_data):
        if user_data["query_user"] is not None:
            if user_data["user_was_active"] and user_data["user_active"] == 0:
                # The user was active and now gets inactive.
                # We revoke all his/hers privileges
                engine, connection = _get_engine_and_connection(request, user)
                if engine is not None and connection is not None:
                    try:
                        connection.execute(
                            "REVOKE ALL PRIVILEGES,GRANT OPTION FROM '{}'@'%'".format(
                                user_data["query_user"]
                            )
                        )
                        connection.execute("flush privileges")
                        connection.invalidate()
                        engine.dispose()
                    except Exception as e:
                        error_message = (
                            "Error while creating analytics account for user: {}\n"
                            "Query user account: {}\nError: {}".format(
                                user, user_data["query_user"], str(e)
                            )
                        )
                        log.error(error_message)
                        send_error_to_technical_team(
                            request,
                            error_message,
                        )
                        connection.invalidate()
                        engine.dispose()
            if not user_data["user_was_active"] and user_data["user_active"] == 1:
                # The user was inactive and not get active again
                # We grant SELECT on all the schemas tha he/she has access based on the
                # projects that he/she collaborates with
                engine, connection = _get_engine_and_connection(request, user)
                if engine is not None and connection is not None:
                    try:
                        sql = (
                            "SELECT DISTINCT form_schema FROM odkform,userproject "
                            "WHERE userproject.project_id = odkform.project_id "
                            "AND userproject.project_accepted = 1 "
                            "AND odkform.form_schema IS NOT NULL "
                            "AND userproject.user_id = '{}'".format(user)
                        )
                        schemas = connection.execute(sql).fetchall()
                        for a_schema in schemas:
                            connection.execute(
                                "GRANT SELECT ON {}.* TO '{}'@'%'".format(
                                    a_schema[0], user_data["query_user"]
                                )
                            )
                        connection.execute(
                            "GRANT ALL ON {}.* TO '{}'@'%'".format(
                                user_data["query_user"], user_data["query_user"]
                            )
                        )
                        connection.execute("flush privileges")
                        connection.invalidate()
                        engine.dispose()
                    except Exception as e:
                        error_message = (
                            "Error while enabling analytics access: {}\n"
                            "Query user account: {}\n"
                            "Error: {}".format(user, user_data["query_user"], str(e))
                        )
                        log.error(error_message)
                        send_error_to_technical_team(
                            request,
                            error_message,
                        )
                        connection.invalidate()
                        engine.dispose()
        return None

    # ICollaborator
    def before_adding_collaborator(self, request, project_id, collaborator_id):
        return True, ""

    def after_accepting_collaboration(self, request, project_id, collaborator_id):
        query_user = get_query_user(request, collaborator_id)
        if query_user is not None:
            user_databases = get_user_databases(request, collaborator_id)
            try:
                connection = get_db_connection(request)
                for a_database in user_databases:
                    connection.connection.execute(
                        "GRANT SELECT ON {}.* TO '{}'@'%'".format(
                            a_database["form_schema"], query_user
                        )
                    )
                connection.connection.execute("flush privileges")
                connection.disconnect()
            except Exception as e:
                error_message = (
                    "Error while enabling database access to: {}\n"
                    "Query user account: {}\n"
                    "Error: {}".format(collaborator_id, query_user, str(e))
                )
                log.error(error_message)
                send_error_to_technical_team(
                    request,
                    error_message,
                )

    def before_removing_collaborator(
        self, request, project_id, collaborator_id, collaboration_details
    ):
        return True, ""

    def after_removing_collaborator(
        self, request, project_id, collaborator_id, collaboration_details
    ):
        query_user = get_query_user(request, collaborator_id)
        if query_user is not None:
            user_databases = get_user_databases(request, collaborator_id)
            try:
                connection = get_db_connection(request)
                connection.connection.execute(
                    "REVOKE ALL PRIVILEGES,GRANT OPTION FROM '{}'@'%'".format(
                        query_user
                    )
                )
                connection.connection.execute("flush privileges")
                connection.connection.execute(
                    "GRANT ALL ON {}.* TO '{}'@'%'".format(query_user, query_user)
                )
                for a_database in user_databases:
                    connection.connection.execute(
                        "GRANT SELECT ON {}.* TO '{}'@'%'".format(
                            a_database["form_schema"], query_user
                        )
                    )
                connection.connection.execute("flush privileges")
                connection.disconnect()
            except Exception as e:
                error_message = (
                    "Error while changing database access to: {}\n "
                    "Query user account: {}\n Error: {}".format(
                        collaborator_id, query_user, str(e)
                    )
                )
                log.error(error_message)
                send_error_to_technical_team(
                    request,
                    error_message,
                )

    # IForm
    def after_odk_form_checks(
        self,
        request,
        user,
        project,
        form,
        form_data,
        form_directory,
        survey_file,
        create_file,
        insert_file,
        itemsets_csv,
    ):
        return True, ""

    def before_adding_form(
        self, request, form_type, user_id, project_id, form_id, form_data
    ):
        return True, "", form_data

    def after_adding_form(
        self, request, form_type, user_id, project_id, form_id, form_data
    ):
        pass

    def before_updating_form(
        self, request, form_type, user_id, project_id, form_id, form_data
    ):
        return True, "", form_data

    def after_updating_form(
        self, request, form_type, user_id, project_id, form_id, form_data
    ):
        pass

    def before_deleting_form(self, request, form_type, user_id, project_id, form_id):
        return True, ""

    def after_deleting_form(
        self, request, form_type, user_id, project_id, form_id, form_data
    ):
        if form_data["form_schema"] is not None:
            try:
                connection = get_db_connection(request)
                users = connection.connection.execute(
                    "SELECT user FROM mysql.db WHERE db = '{}'".format(
                        form_data["form_schema"]
                    )
                ).fetchall()
                if users is not None:
                    for a_user in users:
                        connection.connection.execute(
                            "REVOKE SELECT ON {}.* FROM '{}'@'%'".format(
                                form_data["form_schema"], a_user[0]
                            )
                        )
                    connection.connection.execute("flush privileges")
                connection.disconnect()
            except Exception as e:
                error_message = (
                    "Error while revoking all access from database: {} Due to deletion of form {}\n "
                    "Error: {}".format(
                        form_data["form_schema"],
                        form_id,
                        str(e),
                    )
                )
                send_error_to_technical_team(
                    request,
                    error_message,
                )

    # IProject
    def before_creating_project(self, request, user, project_data):
        return True, ""

    def after_creating_project(self, request, user, project_data):
        pass

    def before_editing_project(self, request, user, project, project_details):
        return True, ""

    def after_editing_project(self, request, user, project, project_data):
        pass

    def before_deleting_project(self, request, user, project):
        return True, ""

    def after_deleting_project(self, request, user, project, project_forms):
        for a_form in project_forms:
            if a_form["form_schema"] is not None:
                try:
                    connection = get_db_connection(request)
                    users = connection.connection.execute(
                        "SELECT user FROM mysql.db WHERE db = '{}'".format(
                            a_form["form_schema"]
                        )
                    ).fetchall()
                    if users is not None:
                        for a_user in users:
                            connection.connection.execute(
                                "REVOKE SELECT ON {}.* FROM '{}'@'%'".format(
                                    a_form["form_schema"], a_user[0]
                                )
                            )
                        connection.connection.execute("flush privileges")
                    connection.disconnect()
                except Exception as e:
                    error_message = (
                        "Error while revoking all access from database: {} Due to deletion of form {}\n "
                        "Error: {}".format(
                            a_form["form_schema"],
                            a_form["form_id"],
                            str(e),
                        )
                    )
                    send_error_to_technical_team(
                        request,
                        error_message,
                    )

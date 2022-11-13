from formshare.plugins.utilities import FormSharePrivateView
from pyramid.httpexceptions import HTTPNotFound, HTTPFound
from formshare.processes.db import (
    get_query_user,
    get_user_databases,
    set_query_user,
    get_project_owner,
    get_user_details,
)
import uuid
from formshare.config.encdecdata import encode_data
from formshare.processes.email.send_email import send_error_to_technical_team


class AnalyticsView(FormSharePrivateView):
    def process_view(self):
        user_id = self.request.matchdict["userid"]
        if user_id != self.user.login:
            raise HTTPNotFound
        self.set_active_menu("analytics")
        active_tab = self.request.params.get("active_tab") or "databases"
        databases = get_user_databases(self.request, user_id)
        if databases is not None:
            for a_database in databases:
                if a_database["access_type"] != 1:
                    a_database["owner"] = get_project_owner(
                        self.request, a_database["project_id"]
                    )
                else:
                    a_database["owner"] = user_id
        query_user = get_query_user(self.request, user_id)
        user_details = get_user_details(self.request, user_id, True, False)
        return {
            "userid": user_id,
            "query_user": query_user,
            "databases": databases,
            "active_tab": active_tab,
            "user_details": user_details,
        }


class EnableAnalyticsView(FormSharePrivateView):
    def process_view(self):
        user_id = self.request.matchdict["userid"]
        if user_id != self.user.login:
            raise HTTPNotFound
        if get_query_user(self.request, user_id) is not None:
            raise HTTPNotFound
        else:
            error = False
            query_user = "FU_" + str(uuid.uuid4()).replace("-", "")[-29:]
            query_password = str(uuid.uuid4())
            query_encoded_password = encode_data(self.request, query_password).decode()
            user_databases = get_user_databases(self.request, user_id)
            updated, message = set_query_user(
                self.request, user_id, query_user, query_encoded_password
            )
            if updated:
                try:
                    self.request.dbsession.execute(
                        "CREATE USER '{}'@'%' IDENTIFIED BY '{}'".format(
                            query_user, query_password
                        )
                    )
                    self.request.dbsession.execute("CREATE SCHEMA " + query_user)
                    self.request.dbsession.execute(
                        "GRANT ALL ON {}.* TO '{}'@'%'".format(query_user, query_user)
                    )
                    for a_database in user_databases:
                        self.request.dbsession.execute(
                            "GRANT SELECT ON {}.* TO '{}'@'%'".format(
                                a_database["form_schema"], query_user
                            )
                        )
                except Exception as e:
                    send_error_to_technical_team(
                        self.request,
                        "Error while creating query account for user: {}\n"
                        "Query user account: {}\n"
                        "Error: {}".format(user_id, query_user, str(e)),
                    )
                    self.add_error(
                        self._(
                            "An error occurred while activating the analytics module. "
                            "An email has been sent to the technical team and they will contact you ASAP."
                        ),
                        False,
                    )
                    error = True
            else:
                send_error_to_technical_team(
                    self.request,
                    "Error while setting query user for user: {}\n"
                    "Query user account: {}\n"
                    "Error: {}".format(user_id, query_user, message),
                )
                self.add_error(
                    self._(
                        "An error occurred while activating the analytics module. "
                        "An email has been sent to the technical team and they will contact you ASAP."
                    ),
                    False,
                )
                error = True

            next_page = self.request.params.get("next") or self.request.route_url(
                "analytics", userid=self.user.login
            )
            self.returnRawViewResult = True
            if error:
                return HTTPFound(location=next_page, headers={"FS_error": "true"})
            else:
                self.request.session.flash(
                    self._("The analytics module has been activated")
                )
                return HTTPFound(location=next_page)

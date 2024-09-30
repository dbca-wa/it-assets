from django.db import connections
from django.http import HttpResponse, HttpResponseServerError


class HealthCheckMiddleware:
    """Middleware to provide healthcheck HTTP endpoints for the system.
    Should be placed at the top of the MIDDLEWARE list so that requests
    to healthcheck endpoints short-circuit and return a response without
    passing through further middleware classes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET":
            if request.path == "/readyz":
                return self.readiness(request)
            elif request.path == "/livez":
                return self.liveness(request)
        return self.get_response(request)

    def liveness(self, request):
        """Returns that the server is alive and able to serve HTTP responses."""
        return HttpResponse("OK")

    def readiness(self, request):
        """Connect to each database and do a generic standard SQL query
        that doesn't write any data and doesn't depend on any tables
        being present.
        """
        try:
            cursor = connections["default"].cursor()
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            cursor.close()
            if row is None:
                return HttpResponseServerError("Database: invalid response")
        except Exception:
            return HttpResponseServerError("Database: unable to connect")

        return HttpResponse("OK")

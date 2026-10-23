"""Lambda entry point for the HTTP API."""

from mangum import Mangum

from api.app import app

handler = Mangum(app, lifespan="off")

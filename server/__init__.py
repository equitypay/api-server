from flask_caching import Cache
from flask_cors import CORS
from flask import Flask
import config

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["SECRET_KEY"] = config.secret
cache = Cache(config={"CACHE_TYPE": "simple"})
cache.init_app(app)
CORS(app)

from server import routes
from server import rest

routes.init(app)
rest.init(app)

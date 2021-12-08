from flask import jsonify, render_template
from flask_caching import Cache
from flask_cors import CORS
from flask import Flask
from . import utils
import config

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["SECRET_KEY"] = config.secret
cache = Cache(config={"CACHE_TYPE": "simple"})
cache.init_app(app)
CORS(app)

from .wallet import wallet
from .rest import rest
from .db import db

app.register_blueprint(wallet)
app.register_blueprint(rest)
app.register_blueprint(db)

@app.route("/")
def frontend():
    return render_template("index.html")

@app.errorhandler(404)
def page_404(error):
    return jsonify(utils.dead_response("Method not found"))

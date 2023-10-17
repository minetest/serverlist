import os

from celery import Celery

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


app = Flask(__name__, static_url_path="")

# Load defaults
app.config.from_pyfile("config.py")

# Load configuration
if os.path.isfile(os.path.join(app.root_path, "..", "config.py")):
	app.config.from_pyfile("../config.py")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

celery = Celery(
	app.import_name,
	broker=app.config['CELERY_BROKER_URL']
)
celery.conf.update(app.config)

class ContextTask(celery.Task):
	def __call__(self, *args, **kwargs):
		with app.app_context():
			return self.run(*args, **kwargs)

celery.Task = ContextTask

import os

from flask import Flask

from config import Config
from extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Make sure database/ exists so SQLite can create the .db file in it
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")
    os.makedirs(db_dir, exist_ok=True)

    from routes.auth import auth_bp
    from routes.attendance import attendance_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

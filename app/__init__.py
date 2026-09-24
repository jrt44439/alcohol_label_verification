"""Application factory for the alcohol label verification tool."""
import os

from flask import Flask

from app import db as db_module


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object("config.Config")

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db_module.init_app(app)

    from app.routes.main import bp as main_bp
    from app.routes.products import bp as products_bp
    from app.routes.verify import bp as verify_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(verify_bp)

    return app

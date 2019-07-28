import json
import os

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

secret_file = os.path.join(BASE_DIR, 'rawlabs', 'envs', 'production_secret.json')

with open(secret_file, 'r') as f:
    secrets = json.loads(f.read())


def get_secret(setting, secrets=secrets):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} env variable.".format(setting)
        raise ImproperlyConfigured(error_msg)


SECRET_KEY = get_secret('SECRET_KEY')

PRODUCTION = True


ALLOWED_HOSTS = ['.rawlabs.io', '13.125.23.131', ]
DEBUG = False


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': get_secret('DATABASE_NAME'),
        'USER': get_secret('DATABASE_USER'),
        'PASSWORD': get_secret('DATABASE_PASSWORD'),
        'HOST': get_secret('DATABASE_HOST'),
        'PORT': 5432,
    }
}

GOOGLE_VISION_API_CREDENTIAL_PATH = get_secret('GOOGLE_VISION_API_CREDENTIAL_PATH')
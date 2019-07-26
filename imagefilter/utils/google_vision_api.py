from django.conf import settings
from google.cloud import vision_v1
from google.protobuf.json_format import MessageToDict

from google.oauth2 import service_account


def text_detection_uri(uri):
    credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_VISION_API_CREDENTIAL_PATH)
    client = vision_v1.ImageAnnotatorClient(credentials=credentials)
    image = vision_v1.types.Image()
    image.source.image_uri = uri
    response = client.document_text_detection(image=image)
    data_dict = MessageToDict(response)
    return data_dict

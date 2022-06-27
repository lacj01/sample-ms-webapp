import base64
import codecs
import datetime
import mimetypes
import os
from typing import Optional, Any

import flask
import requests
from azure.core.credentials import TokenCredential, AccessToken
from azure.core.exceptions import HttpResponseError
from azure.storage.blob import BlobServiceClient
from dateutil import parser
from flask import Flask, request, redirect, url_for, send_from_directory, stream_with_context, Response


class localFlask(Flask):

    def process_response(self, response):
        response.headers.remove('Server')
        response.headers['Server'] = os.getenv('APP_SERVER_NAME', 'Unknown')
        super(localFlask, self).process_response(response)
        return (response)


app = localFlask(__name__)

app_ico = """AAABAAEAEBAAAAEACABoBQAAFgAAACgAAAAQAAAAIAAAAAEACAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAABjfqAAYIOdAF6ImwBdipoAQJxxAFqPlwBAnXIAW4+YAECecgBAoHQAWJWUAEChdABApHYA
VJuQAE6jiwBNpIoAQat6AEGsewBBr30ARq2DAEGxfwBBsn8AAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYAABYWFhYWFhYWFhYWFhYWABYWFhYWFhYWFhYWFhYW
FhYAFhYWFhYWFhYWFhYWFhYAFhYWFhYWFhYWFhYWDBUVAgAOFRUWFhYWFhYWBBIVFQcDBRUVFhYW
FhYWBAkVFQ0BChUVFRUWFhYWFgQLFRUTDw0VFRUVFRYWFhYEBBIVFRUVFRUVFRUWFhYWFgQLFRUV
FRUVFRUVFhYWFhYECBUVFRUVFRUVFhYWFhYWBAQRFRUVFRUVFhYWFhYWFhYEBhAUFRUVFRYWFhYW
FhYWFhYWBAwVFhYWFhYWFhYWFhYWFhYWFhYWFhYWFv//AAD+fwAA/v8AAP9/AAD+/wAA8A8AAOAP
AADABwAAwAMAAMADAADgAwAA4AcAAOAPAADwDwAA/j8AAP//AAA="""

BASE = 'web'


class HeaderToken(TokenCredential):
    def get_token(
            self, *scopes: str, claims: Optional[str] = None, tenant_id: Optional[str] = None, **kwargs: Any
    ) -> AccessToken:
        return AccessToken(
            token=request.headers[
                'X-Ms-Token-Aad-Access-Token'] if 'X-Ms-Token-Aad-Access-Token' in request.headers else os.getenv(
                'APP_OAUTH2_TOKEN'),
            expires_on=int(parser.isoparse(request.headers[
                                               'X-Ms-Token-Aad-Expires-On']).timestamp()) if 'X-Ms-Token-Aad-Expires-On' in request.headers else (
                    datetime.datetime.now().timestamp() + 1000))


@app.route('/')
def index():
    return redirect(url_for(BASE, path='index.html'))


@app.route('/favicon.ico')
def favicon():
    return Response(response=base64.b64decode(app_ico), status=200, mimetype='image/vnd.microsoft.icon')


@app.before_request
def handle_refresh():
    _expires = int(parser.isoparse(request.headers['X-Ms-Token-Aad-Expires-On']).timestamp()) \
        if 'X-Ms-Token-Aad-Expires-On' in request.headers else \
        (datetime.datetime.now().timestamp() + 1000)
    print(f"Got Cookie id: {request.headers['Cookie']}")
    if request.path != "/.auth/refresh" and _expires - datetime.datetime.now().timestamp() < 300:
        print(f"Token Expires in { _expires - datetime.datetime.now().timestamp()}")
        r=requests.get(f"{request.base_url}.auth/refresh", headers={"Cookie": request.headers['Cookie']})
        print(f"Got: code:{r.status_code} | {r.text}")

# For debugging
@app.route(f"/.auth/refresh")
def refresh():
    return ""

@app.route(f"/{BASE}", defaults={'path': 'index.html'})
@app.route(f"/{BASE}/<path:path>")
def web(path):
    service = BlobServiceClient(account_url=os.getenv(key='APPLICATION_STORAGE_ACCOUNT'),
                                credential=HeaderToken())
    blob_client = service.get_blob_client(os.getenv(key='APPLICATION_STORAGE_CONTAINER'), path)
    try:
        stream = blob_client.download_blob()
        blob_properties = blob_client.get_blob_properties()
        mime_type = mimetypes.guess_type(path) or 'text/plain'
        size = blob_properties.size
        md5 = None
        content_encoding = None
        content_language = None
        cache_control = None
        content_disposition = None
        if blob_properties.content_settings:
            mime_type = blob_properties.content_settings.content_type
            cache_control = blob_properties.content_settings.cache_control
            content_disposition = blob_properties.content_settings.content_disposition
            content_language = blob_properties.content_settings.content_type
            md5 = base64.b64encode(blob_properties.content_settings.content_md5).decode('utf-8')
            content_encoding = blob_properties.content_settings.content_encoding

        def generate():
            for chunk in stream.chunks():
                yield chunk

        r = Response(response=stream_with_context(generate()), status=200,
                     mimetype=mime_type)
        r.content_length = size
        r.content_md5 = md5
        r.content_encoding = content_encoding
        r.content_type = mime_type
        r.content_language = content_language
        r.last_modified = blob_properties.last_modified
        if content_disposition:
            r.headers['Content-Disposition'] = content_disposition
        if cache_control:
            r.headers['Cache-Control'] = cache_control
        return r

    except HttpResponseError as ex:
        return Response(response=ex.reason, status=ex.status_code, mimetype='text/plain')


if __name__ == '__main__':
    app.run()

import base64
import codecs
import datetime
import mimetypes
import os
from typing import Optional, Any

from azure.core.credentials import TokenCredential, AccessToken
from azure.storage.blob import BlobServiceClient
from dateutil import parser
from flask import Flask, request, redirect, url_for, send_from_directory, stream_with_context, Response

app = Flask(__name__)

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

BASE='web'

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
                    datetime.datetime.now().timestamp() + 500))


@app.route('/')
def index():
    return redirect(url_for(BASE, path='index.html'))


@app.route('/favicon.ico')
def favicon():
    return Response(response=base64.b64decode(app_ico), status=200, mimetype='image/vnd.microsoft.icon')


@app.route(f"/{BASE}", defaults={'path': 'index.html'})
@app.route(f"/{BASE}/<path:path>")
def web(path):
    def generate():
        service = BlobServiceClient(account_url=os.getenv(key='APPLICATION_STORAGE_ACCOUNT'),
                                    credential=HeaderToken())
        blob_client = service.get_blob_client(os.getenv(key='APPLICATION_STORAGE_CONTAINER'), path)
        stream = blob_client.download_blob()
        for chunk in stream.chunks():
            yield chunk

    mime = mimetypes.guess_type(path)
    return app.response_class(stream_with_context(generate()), mimetype=mime[0] if mime[0] else 'text/plain')


if __name__ == '__main__':
    app.run()

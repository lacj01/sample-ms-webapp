import codecs
import datetime
import mimetypes
import os
from typing import Optional, Any

from azure.core.credentials import TokenCredential, AccessToken
from azure.storage.blob import BlobServiceClient
from dateutil import parser
from flask import Flask, request, redirect, url_for, send_from_directory, stream_with_context

app = Flask(__name__)

class HeaderToken(TokenCredential):
    def get_token(
            self, *scopes: str, claims: Optional[str] = None, tenant_id: Optional[str] = None, **kwargs: Any
    ) -> AccessToken:
        return AccessToken(
            token=request.headers[
                'X-Ms-Token-Aad-Access-Token'] if 'X-Ms-Token-Aad-Access-Token' in request.headers else os.getenv('APP_OAUTH2_TOKEN'),
            expires_on=int(parser.isoparse(request.headers[
                                               'X-Ms-Token-Aad-Expires-On']).timestamp()) if 'X-Ms-Token-Aad-Expires-On' in request.headers else (
                    datetime.datetime.now().timestamp() + 500))


@app.route('/')
def index():
    return redirect(url_for('web', path='index.html'))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/web', defaults={'path': 'index.html'})
@app.route('/web/<path:path>')
def web(path):
    def generate():
        service = BlobServiceClient(account_url=os.getenv(key='APPLICATION_STORAGE_CONTAINER'),
                                    credential=HeaderToken())
        blob_client = service.get_blob_client('mycontainer', path)
        stream = blob_client.download_blob()
        for chunk in codecs.iterdecode(iterator=stream.chunks(), encoding='utf8'):
            yield chunk

    mime = mimetypes.guess_type(path)
    return app.response_class(stream_with_context(generate()), mimetype=mime[0] if mime[0] else 'text/plain')


if __name__ == '__main__':
    app.run()

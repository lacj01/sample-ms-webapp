import base64
import datetime
import logging
import mimetypes
import os
from typing import Optional, Any
from pathlib import PurePosixPath

import flask
import requests
from azure.core.credentials import TokenCredential, AccessToken
from azure.core.exceptions import HttpResponseError
from azure.identity import ChainedTokenCredential, InteractiveBrowserCredential, CredentialUnavailableError, \
    AzureCliCredential, DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dateutil import parser
from flask import Flask, request, redirect, url_for, stream_with_context, Response

app = Flask(__name__)


class HeaderToken(TokenCredential):
    def get_token(
            self, *scopes: str, claims: Optional[str] = None, tenant_id: Optional[str] = None, **kwargs: Any
    ) -> AccessToken:
        if 'X-Ms-Token-Aad-Access-Token' not in request.headers:
            raise CredentialUnavailableError()
        return AccessToken(
            token=request.headers['X-Ms-Token-Aad-Access-Token'],
            expires_on=int(parser.isoparse(request.headers['X-Ms-Token-Aad-Expires-On']).timestamp()))


BASE = os.getenv('BASE_URL', 'web')
TOKEN_CREDENTIAL_SOURCE = ChainedTokenCredential(HeaderToken(),
                                                 InteractiveBrowserCredential(tenant_id=os.getenv('AZURE_TENANT_ID','00000000-0000-0000-0000-000000000000')),
                                                 AzureCliCredential())

@app.route('/')
def index():
    return redirect(url_for(BASE, path='/'))


@app.route('/favicon.ico')
def favicon():
    return flask.send_file('tree.ico', download_name='favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.before_request
def handle_refresh():
    # If there is not refresh, then we cannot refresh.
    # This happens when the offline_access is disabled.
    if 'X-MS-TOKEN-AAD-REFRESH-TOKEN' not in request.headers:
        return
    _expires = int(parser.isoparse(request.headers['X-Ms-Token-Aad-Expires-On']).timestamp()) \
        if 'X-Ms-Token-Aad-Expires-On' in request.headers else \
        (datetime.datetime.now().timestamp() + 1000)
    ttl = _expires - datetime.datetime.now().timestamp()
    if 'Cookie' in request.headers and ttl < 300:
        app.logger.info(f"Session is about to expired in {ttl}: Refreshing")
        # I use the cookie to refresh the token on behalf of the user. Took me forever to find out how to do this
        # from the backend.
        req = f"https://{request.host}/.auth/refresh"
        requests.get(req, headers={'Cookie': request.headers['Cookie']})
    # If the session is about to expire, let's force a refresh of the webpage to get a recent token.
    if ttl < 30:
        app.logger.info(f"Session is expired or very closed to expire: force reload {ttl}")
        return redirect(request.url)


def try_handle_listing(container_client: ContainerClient, path: str):
    if not path.endswith('/'):
        path = path + '/'
    if path == '/':
        path = ''
    return flask.render_template(template_name_or_list='index.html.j2',
                                 PurePosixPath=PurePosixPath,
                                 basename=BASE, basepath=path,
                                 walker=container_client.walk_blobs(name_starts_with=path, delimiter='/'))


@app.route(f"/{BASE}/", defaults={'path': '/'})
@app.route(f"/{BASE}", defaults={'path': '/'})
@app.route(f"/{BASE}/<path:path>")
def web(path):
    container_client = ContainerClient(account_url=os.getenv(key='APPLICATION_STORAGE_ACCOUNT'),
                                       container_name=os.getenv(key='APPLICATION_STORAGE_CONTAINER'),
                                       credential=TOKEN_CREDENTIAL_SOURCE)
    blob_client = container_client.get_blob_client(blob=path)
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
        try:
            if ex.status_code == 404:
                return try_handle_listing(container_client, path)
            else:
                return Response(response=ex.reason, status=ex.status_code, mimetype='text/plain')
        except HttpResponseError as ex2:
            return Response(response=ex2.reason, status=ex2.status_code, mimetype='text/plain')


if __name__ == '__main__':
    app.run()

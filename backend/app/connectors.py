import time
from urllib.parse import urlencode, urlparse
import httpx
from fastapi import HTTPException
from .config import settings
from .security import encrypt_token, decrypt_token


def request(method, url, **kwargs):
    # Bounded retries; never put response bodies or credentials into errors/logs.
    for attempt in range(3):
        try:
            response = httpx.request(method, url, timeout=30, **kwargs)
        except httpx.HTTPError:
            if attempt == 2:
                raise HTTPException(502, 'The provider could not be reached. Try again shortly.')
            time.sleep(attempt + 1)
            continue
        if response.status_code in (429, 502, 503, 504) and attempt < 2:
            retry = response.headers.get('Retry-After', '2')
            time.sleep(min(int(retry) if retry.isdigit() else 2, 5))
            continue
        if response.status_code in (401, 403):
            raise HTTPException(502, 'The connection expired or lacks permission. Reconnect the provider.')
        if response.is_error:
            raise HTTPException(502, f'The provider rejected the request (HTTP {response.status_code}).')
        return response


class OAuthConnector:
    def __init__(self, provider):
        if provider not in ('procore', 'microsoft'):
            raise HTTPException(404, 'Unknown integration.')
        self.provider = provider
        self.client_id = getattr(settings, provider + '_client_id')
        self.client_secret = getattr(settings, provider + '_client_secret')
        self.redirect_uri = settings.api_url + f'/api/integrations/{provider}/callback'
        base = settings.procore_login_url + '/oauth' if provider == 'procore' else f'https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0'
        self.authorize_url = base + '/authorize'
        self.token_url = base + '/token'

    def get_authorization_url(self, state):
        if not self.client_id or not self.client_secret:
            raise HTTPException(409, 'Configure this provider in the backend environment first.')
        params = dict(client_id=self.client_id, redirect_uri=self.redirect_uri, response_type='code', state=state)
        if self.provider == 'microsoft':
            params['scope'] = settings.microsoft_scopes
            params['response_mode'] = 'query'
        return self.authorize_url + '?' + urlencode(params)

    def exchange(self, **grant):
        data = dict(client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.redirect_uri, **grant)
        if self.provider == 'microsoft':
            data['scope'] = settings.microsoft_scopes
        value = request('POST', self.token_url, data=data).json()
        if not value.get('access_token'):
            raise HTTPException(502, 'The provider returned an invalid token response.')
        return value

    def exchange_code_for_token(self, code):
        return self.exchange(grant_type='authorization_code', code=code)

    def refresh_token(self, token):
        return self.exchange(grant_type='refresh_token', refresh_token=token)

    def client_credentials(self):
        # Server-to-server grant for the Procore app's service account; no redirect or user sign-in.
        if not self.client_id or not self.client_secret:
            raise HTTPException(409, 'Configure this provider in the backend environment first.')
        value = request('POST', self.token_url, data=dict(grant_type='client_credentials', client_id=self.client_id, client_secret=self.client_secret)).json()
        if not value.get('access_token'):
            raise HTTPException(502, 'The provider returned an invalid token response.')
        return value


def save_tokens(connection, tokens):
    connection.access_token_encrypted = encrypt_token(tokens['access_token'])
    if tokens.get('refresh_token'):
        connection.refresh_token_encrypted = encrypt_token(tokens['refresh_token'])
    connection.expires_at = time.time() + int(tokens.get('expires_in', 3600))
    connection.scopes = tokens.get('scope', '').split()
    connection.status = 'connected'


def valid_token(db, connection):
    if not connection.access_token_encrypted:
        raise HTTPException(409, 'Connect the provider before syncing.')
    if (connection.expires_at or 0) < time.time() + 300:
        if connection.provider == 'procore' and settings.procore_grant == 'client_credentials':
            tokens = OAuthConnector('procore').client_credentials()
        else:
            if not connection.refresh_token_encrypted:
                raise HTTPException(409, 'This connection expired. Please reconnect.')
            tokens = OAuthConnector(connection.provider).refresh_token(decrypt_token(connection.refresh_token_encrypted))
        save_tokens(connection, tokens)
        db.commit()
    return decrypt_token(connection.access_token_encrypted)


class Procore:
    def __init__(self, token, company_id=None):
        self.headers = {'Authorization': 'Bearer ' + token}
        if company_id:
            self.headers['Procore-Company-Id'] = str(company_id)

    def get(self, path, params=None):
        return request('GET', settings.procore_base_url + '/rest/v1.0/' + path, headers=self.headers, params=params).json()

    def all(self, path, params=None):
        rows = []
        for page in range(1, 101):
            batch = self.get(path, dict(params or {}, page=page, per_page=100))
            if not isinstance(batch, list):
                raise HTTPException(502, 'Unexpected Procore response format.')
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise HTTPException(502, 'This Procore import exceeds 10,000 records. Narrow the project scope.')

    def companies(self):
        return self.all('companies')

    def projects(self, company_id):
        return self.all('projects', {'company_id': company_id})

    def rfis(self, project_id):
        return self.all(f'projects/{project_id}/rfis')

    def submittals(self, project_id):
        return self.all(f'projects/{project_id}/submittals')


class Microsoft:
    base = 'https://graph.microsoft.com/v1.0/'

    def __init__(self, token):
        self.headers = {'Authorization': 'Bearer ' + token, 'Prefer': 'outlook.body-content-type="text"'}

    def get(self, path, params=None):
        url = path if path.startswith('https://') else self.base + path
        if urlparse(url).hostname != 'graph.microsoft.com':
            raise HTTPException(502, 'Invalid Graph pagination link.')
        return request('GET', url, headers=self.headers, params=params).json()

    def all(self, path, params=None):
        rows = []
        for _ in range(100):
            data = self.get(path, params)
            rows.extend(data.get('value', []))
            path, params = data.get('@odata.nextLink'), None
            if not path:
                return rows
        raise HTTPException(502, 'Graph returned too many pages. Narrow your sync scope.')

    def messages(self):
        return self.all('me/messages', {'$top': '100', '$select': 'id,subject,from,receivedDateTime,body,toRecipients', '$orderby': 'receivedDateTime desc', '$filter': 'receivedDateTime ge ' + __import__('datetime').datetime.fromtimestamp(time.time() - 30 * 86400, __import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})

    def drive_items(self):
        return self.all('me/drive/root/children')

    def sites(self):
        return self.all('sites?search=*')

    def download_file(self, drive_id, item_id):
        from urllib.parse import quote
        item = self.get(f'drives/{quote(drive_id, safe="")}/items/{quote(item_id, safe="")}')
        # Graph returns a short-lived preauthenticated URL. Never forward the Graph bearer token.
        url = item.get('@microsoft.graph.downloadUrl')
        if not url or urlparse(url).scheme != 'https':
            raise HTTPException(502, 'Graph did not supply a secure download URL.')
        if item.get('size', 0) > 10_000_000:
            raise HTTPException(413, 'File exceeds the 10 MB limit.')
        with httpx.stream('GET', url, timeout=30, follow_redirects=True) as response:
            response.raise_for_status()
            data = bytearray()
            for part in response.iter_bytes():
                data.extend(part)
                if len(data) > 10_000_000:
                    raise HTTPException(413, 'File exceeds the 10 MB limit.')
        return bytes(data), item['name']

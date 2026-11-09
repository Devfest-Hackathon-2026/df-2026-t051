"""Administrative REST client using gcloud credentials; never prints credentials."""
import subprocess
import httpx

PROJECT='chartbridge-gdgoc-2026'
GCLOUD=r'C:\Users\PC_User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'


def access_token():
    return subprocess.run([GCLOUD,'auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()


def client():
    return httpx.Client(headers={'Authorization':'Bearer '+access_token(),'X-Goog-User-Project':PROJECT},timeout=60)


def checked(response):
    if response.is_error:
        error=response.json().get('error',{})
        raise RuntimeError(f'Cloud API HTTP {response.status_code}: {error.get("status", "failed")} / {error.get("message", "")[:350]}')
    return response.json() if response.content else {}

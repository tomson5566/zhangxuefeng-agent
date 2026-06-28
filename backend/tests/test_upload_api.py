"""FastAPI 端到端 upload 测试。"""
import io
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_upload_txt():
    files = {'file': ('test.txt', io.BytesIO(b'hello world\n'), 'text/plain')}
    r = client.post('/api/upload?session_id=test-api', files=files)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data['status'] == 'ok'
    assert data['filename'] == 'test.txt'
    assert 'content_preview' in data


def test_upload_unsupported_ext():
    files = {'file': ('test.exe', io.BytesIO(b'binary'), 'application/octet-stream')}
    r = client.post('/api/upload?session_id=test-api', files=files)
    assert r.status_code == 400


def test_list_uploads():
    r = client.get('/api/uploads/test-api')
    assert r.status_code == 200
    data = r.json()
    assert data['session_id'] == 'test-api'
    assert data['count'] >= 0

"""E2E:upload + 列文件。"""
import io
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_upload_then_list():
    """上传一个 txt,然后列文件应看到它。"""
    sid = "e2e-upload-test"
    files = {'file': ('hello.txt', io.BytesIO(b'e2e content'), 'text/plain')}
    r = client.post(f'/api/upload?session_id={sid}', files=files)
    assert r.status_code == 200
    data = r.json()
    assert data['filename'] == 'hello.txt'

    r2 = client.get(f'/api/uploads/{sid}')
    assert r2.status_code == 200
    list_data = r2.json()
    assert list_data['session_id'] == sid
    assert list_data['count'] >= 1
    # 至少 1 个文件(可能 3 个:主 + meta + content)
    assert any('hello.txt' in p for p in list_data['files'])

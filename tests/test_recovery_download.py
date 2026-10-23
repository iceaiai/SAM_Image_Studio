import copy
import hashlib
import http.server
import threading
import pytest
from samstudio.inference import download_file, InferenceEngine, CATALOG


def test_structurally_corrupt_restore_is_transactional(document):
    old=document.state();bad=copy.deepcopy(old);bad["groups"][0]["name"]="Unexpected"
    bad["removed"]={"bad":"data"}
    with pytest.raises((ValueError,KeyError)):document.restore(bad)
    assert document.state()==old


@pytest.fixture
def server():
    payload=bytes(range(256))*100
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            offset=int(self.headers.get("Range","bytes=0-").split("=")[-1].split("-")[0])
            if self.path=="/error":self.send_error(403);return
            if offset>=len(payload):self.send_error(416);return
            ignore=self.path=="/ignore";start=0 if ignore else offset
            self.send_response(206 if offset and not ignore else 200)
            if offset and not ignore:self.send_header("Content-Range",f"bytes {start}-{len(payload)-1}/{len(payload)}")
            self.send_header("Content-Length",str(len(payload)-start));self.end_headers();self.wfile.write(payload[start:])
    service=http.server.ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
    yield f"http://127.0.0.1:{service.server_port}",payload
    service.shutdown();service.server_close();thread.join()


@pytest.mark.parametrize("mode",["fresh","resume","ignore","oversize","complete"])
def test_download_atomic_resumable_and_checked(server,tmp_path,mode):
    url,payload=server;dest=tmp_path/"model.pt";part=dest.with_suffix(".pt.part")
    if mode in ("resume","ignore"):part.write_bytes(payload[:4000])
    if mode=="oversize":part.write_bytes(payload+b"extra")
    if mode=="complete":part.write_bytes(payload)
    path=download_file(url+("/ignore" if mode=="ignore" else "/model"),dest,hashlib.sha256(payload).hexdigest())
    assert path.read_bytes()==payload and not part.exists()


def test_bad_download_is_not_promoted(server,tmp_path):
    url,_=server;dest=tmp_path/"bad.pt"
    with pytest.raises(ValueError,match="checksum"):download_file(url+"/model",dest,"0"*64)
    assert not dest.exists()
    with pytest.raises(RuntimeError,match="HTTP 403"):download_file(url+"/error",dest)


def test_load_rejects_incompatible_or_missing_device_without_losing_old_predictor(tmp_path):
    engine=InferenceEngine();sentinel=object();engine.predictor=sentinel
    with pytest.raises(ValueError,match="CUDA"):engine.load(CATALOG[-1],"cpu")
    assert engine.predictor is sentinel
    with pytest.raises(ValueError,match="existing"):engine.load(CATALOG[0],checkpoint=tmp_path/"no.pt")
    assert engine.predictor is sentinel

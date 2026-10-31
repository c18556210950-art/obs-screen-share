import base64
import hashlib
import json
import pathlib
import uuid
import websocket


class OBS:
    def __init__(self):
        config = json.loads(pathlib.Path(__file__).with_name('config.json').read_text(encoding='utf-8-sig'))
        self.ws = websocket.create_connection(config.get('ws_url', 'ws://127.0.0.1:4455'), timeout=15,
                                               http_no_proxy=['127.0.0.1'])
        hello = json.loads(self.ws.recv())['d']
        data = {'rpcVersion': 1, 'eventSubscriptions': 0}
        auth = hello.get('authentication')
        if auth:
            secret = base64.b64encode(hashlib.sha256((config['ws_password'] + auth['salt']).encode()).digest()).decode()
            data['authentication'] = base64.b64encode(hashlib.sha256((secret + auth['challenge']).encode()).digest()).decode()
        self.ws.send(json.dumps({'op': 1, 'd': data}))
        if json.loads(self.ws.recv())['op'] != 2:
            raise RuntimeError('OBS authentication failed')

    def call(self, name, data=None):
        request_id = str(uuid.uuid4())
        self.ws.send(json.dumps({'op': 6, 'd': {'requestType': name, 'requestId': request_id,
                                               'requestData': data or {}}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('op') == 7 and message['d']['requestId'] == request_id:
                result = message['d']
                if not result['requestStatus']['result']:
                    raise RuntimeError(name + ': ' + str(result['requestStatus']))
                return result.get('responseData', {})

    def close(self):
        self.ws.close()

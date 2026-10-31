"""Windows loopback RTMP -> authenticated TLS RTMPS over one physical NIC.

This is a small personal-use prototype, not a general streaming application.
"""
import asyncio
import json
import logging
import os
import pathlib
import socket
import ssl
import struct

BASE = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = pathlib.Path(os.environ.get('OBS_SHARE_CONFIG', str(BASE / 'config.json')))


def load_config():
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig'))
    if os.name != 'nt':
        raise RuntimeError('The interface pinning in this bridge requires Windows.')
    socket.inet_pton(socket.AF_INET, config['remote_ip'])
    socket.inet_pton(socket.AF_INET, config['local_ip'])
    if not config['tls_hostname'] or int(config['interface_index']) <= 0:
        raise ValueError('A TLS hostname and physical interface index are required.')
    return config


def direct_socket(config):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(12)
        # Windows IP_UNICAST_IF expects a network-byte-order interface index.
        sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack('!I', int(config['interface_index'])))
        sock.bind((config['local_ip'], 0))
        sock.connect((config['remote_ip'], int(config.get('remote_port', 1936))))
        logging.info('DIRECT local=%s remote=%s', sock.getsockname(), sock.getpeername())
        return sock
    except BaseException:
        sock.close()
        raise


async def relay(reader, writer, config):
    remote_writer = None
    tasks = []
    sock = None
    try:
        sock = await asyncio.to_thread(direct_socket, config)
        sock.setblocking(False)
        remote_reader, remote_writer = await asyncio.open_connection(
            sock=sock, ssl=ssl.create_default_context(),
            server_hostname=config['tls_hostname'], ssl_handshake_timeout=12)
        sock = None  # Ownership transferred to asyncio.

        async def copy(source, destination):
            while data := await source.read(65536):
                destination.write(data)
                await destination.drain()

        tasks = [asyncio.create_task(copy(reader, remote_writer)),
                 asyncio.create_task(copy(remote_reader, writer))]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except Exception:
        logging.exception('Direct streaming connection failed; no proxy fallback')
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if sock is not None:
            sock.close()
        for destination in (remote_writer, writer):
            if destination is not None:
                destination.close()
                try:
                    await destination.wait_closed()
                except Exception:
                    pass


async def main(config):
    server = await asyncio.start_server(
        lambda r, w: relay(r, w, config), '127.0.0.1', int(config.get('listen_port', 29350)))
    logging.info('READY listener=%s interface=%s source=%s',
                 server.sockets[0].getsockname(), config['interface_index'], config['local_ip'])
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    logging.basicConfig(filename=str(BASE / 'direct-bridge.log'), encoding='utf-8',
                        level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        asyncio.run(main(load_config()))
    except KeyboardInterrupt:
        pass

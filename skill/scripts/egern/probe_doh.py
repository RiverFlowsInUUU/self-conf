import base64, json, socket, ssl, struct, urllib.request, urllib.error, sys
import os
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import force_utf8_stdout  # noqa: E402

def wire(name, qtype=1):
    h = struct.pack('>HHHHHH', 0x1234, 0x0100, 1, 0, 0, 0)
    q = b''
    for p in name.split('.'):
        q += bytes([len(p)]) + p.encode()
    return h + q + b'\x00' + struct.pack('>HH', qtype, 1)

def parse_answers(buf):
    # 极简解析：只取 Answer 段的 A 记录
    try:
        qd, an = struct.unpack('>HH', buf[4:8])
    except Exception:
        return None
    off = 12
    for _ in range(qd):
        while buf[off] != 0:
            off += buf[off] + 1
        off += 5
    out = []
    for _ in range(an):
        if buf[off] & 0xC0 == 0xC0:
            off += 2
        else:
            while buf[off] != 0:
                off += buf[off] + 1
            off += 1
        t, cls, ttl, ln = struct.unpack('>HHIH', buf[off:off+10])
        off += 10
        if t == 1 and ln == 4:
            out.append(socket.inet_ntoa(buf[off:off+4]))
        off += ln
    return out

HOSTS = ['doh.18bit.cn', 'dns.alidns.com', 'doh.pub', 'dns.google', '1.1.1.1', '8.8.8.8']
NAMES = ['example.com', 'www.google.com', 'www.baidu.com']

# 证书校验：默认**开启**（与 probe_dns_endpoints.py 一致）。
# 曾因为这里写死 CERT_NONE + check_hostname=False，本脚本无法发现「证书不覆盖该 IP」
# 这类问题 —— 而 DoH 端点用 IP 字面量时，证书是否覆盖该 IP 正是要验证的东西之一。
# 用法：--no-verify 可关闭（仅在证书链本身有问题、你只想看协议能否通时使用）。
NO_VERIFY = '--no-verify' in sys.argv
ctx = ssl.create_default_context()
if NO_VERIFY:
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    print('⚠️  证书校验已关闭（--no-verify）：下面的结果无法反映证书问题。\n')

for h in HOSTS:
    print('=' * 78)
    print('端点:', h)
    # 1) RFC8484 GET (wire)
    for n in NAMES:
        q = base64.urlsafe_b64encode(wire(n)).decode().rstrip('=')
        url = f'https://{h}/dns-query?dns={q}'
        try:
            req = urllib.request.Request(url, headers={
                'accept': 'application/dns-message',
                'user-agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                body = r.read()
                a = parse_answers(body) if body else None
                print(f'  [GET-wire] {n:18s} HTTP={r.status} bytes={len(body):5d} A={a}')
        except urllib.error.HTTPError as e:
            print(f'  [GET-wire] {n:18s} HTTP={e.code} BODY={e.read()[:60]!r}')
        except Exception as e:
            print(f'  [GET-wire] {n:18s} FAIL {type(e).__name__}: {str(e)[:80]}')
    # 2) JSON API
    try:
        req = urllib.request.Request(
            f'https://{h}/dns-query?name=example.com&type=A',
            headers={'accept': 'application/dns-json', 'user-agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            d = json.loads(r.read())
            a = [x['data'] for x in d.get('Answer', []) if x.get('type') == 1]
            print(f'  [JSON]     example.com        HTTP={r.status} A={a}')
    except urllib.error.HTTPError as e:
        print(f'  [JSON]     example.com        HTTP={e.code} BODY={e.read()[:60]!r}')
    except Exception as e:
        print(f'  [JSON]     example.com        FAIL {type(e).__name__}: {str(e)[:80]}')

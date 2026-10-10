#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周报整理助手 · 本地数据代理服务

背景：腾讯文档接口会拦截所有带 Origin 头的浏览器跨域请求（401），
     且公共 CORS 代理不转发 Cookie，因此网页端无法直接拉取文档数据。
方案：本脚本在本机运行一个轻量 HTTP 代理，由它（服务端请求，不带 Origin）
     自动完成「访问文档页面种 Cookie → 请求 dop-api 接口」流程，供页面直连使用。

用法：
  1) 双击同目录「启动本地代理.command」，或在终端执行： python3 本地数据代理.py [端口]
  2) 保持窗口开启，打开 周报整理助手.html → 在线地址获取 → 点击「在线获取最新数据」
  3) 停止：在窗口按 Ctrl+C

接口：
  GET /ping              健康检查
  GET /qq?url=<文档接口地址>  返回腾讯文档 dop-api 原始 JSON（仅允许 docs.qq.com）
"""
import json
import re
import sys
import threading
import urllib.request
import urllib.parse
import http.cookiejar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

_lock = threading.Lock()
_cookiejar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookiejar))


def _allowed(url):
    """仅放行 docs.qq.com 的文档/接口地址，避免代理被滥用"""
    return bool(re.match(
        r'^https://docs\.qq\.com/(?:smartsheet/\w+|sheet/\w+|dop-api/opendoc\?)', url))


def _doc_page_url(url):
    """从 dop-api 或 smartsheet 地址还原文档页面地址（用于引导 Cookie）"""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    doc_id = (qs.get('id') or [''])[0]
    tab = (qs.get('tab') or [''])[0]
    if doc_id:
        base = 'https://docs.qq.com/smartsheet/' + doc_id
        return base + ('?tab=' + tab if tab else '')
    m = re.match(r'(https://docs\.qq\.com/(?:smartsheet|sheet)/\w+)', url)
    return m.group(1) if m else 'https://docs.qq.com/'


def _get(url, referer=None, timeout=25):
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with _opener.open(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode('utf-8', 'replace')


def fetch_via_dance(target):
    """先访问文档页面种下 Cookie，再请求 dop-api（服务端请求不带 Origin，腾讯放行）"""
    page = _doc_page_url(target)
    try:
        _get(page)                       # 种 Cookie（TOK / tgw_l7_route 等）
    except Exception:
        pass
    status, body = _get(target, referer=page)
    if status == 200 and len(body) > 200:
        return body
    _get(page)                           # 失败重试：重新种 Cookie
    status, body = _get(target, referer=page)
    if status == 200 and len(body) > 200:
        return body
    raise RuntimeError('上游返回异常（HTTP %s，长度 %s）' % (status, len(body)))


class Handler(BaseHTTPRequestHandler):

    def _cors(self, code=200, body=b'', ctype='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._cors(204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/ping':
            self._cors(200, b'ok', 'text/plain; charset=utf-8')
            return
        if parsed.path == '/qq':
            url = (urllib.parse.parse_qs(parsed.query).get('url') or [''])[0]
            if not _allowed(url):
                self._cors(400, json.dumps(
                    {'error': '仅支持 docs.qq.com 文档地址'}, ensure_ascii=False).encode())
                return
            try:
                with _lock:
                    body = fetch_via_dance(url)
                self._cors(200, body.encode('utf-8'))
                print('  [OK] %s' % url[:90])
            except Exception as e:
                self._cors(502, json.dumps(
                    {'error': str(e)}, ensure_ascii=False).encode())
                print('  [FAIL] %s -> %s' % (url[:70], e))
            return
        self._cors(404, b'{"error":"not found"}')

    def log_message(self, fmt, *args):
        pass  # 静默默认访问日志，改用上方简洁输出


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print('=' * 60)
    print('  周报整理助手 · 本地数据代理已启动')
    print('  地址: http://127.0.0.1:%d' % PORT)
    print('  下一步: 打开 周报整理助手.html → 在线地址获取 → 在线获取最新数据')
    print('  停止: 按 Ctrl+C（关闭本窗口）')
    print('=' * 60)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n代理已停止。')


if __name__ == '__main__':
    main()

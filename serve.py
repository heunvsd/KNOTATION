#!/usr/bin/env python3
"""선택 사항: MP4 구간 요청을 지원하는 로컬 미리보기 서버.
실행: python3 serve.py  (Python 3.9 이상, 외부 패키지 불필요)
자신의 컴퓨터(127.0.0.1)에서만 접속할 수 있습니다.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import webbrowser

ROOT = Path(__file__).resolve().parent


class PreviewHandler(SimpleHTTPRequestHandler):
    """한 개의 HTTP byte range를 지원하여 MP4 seek가 가능하도록 합니다."""

    byte_range: tuple[int, int] | None = None

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        self.byte_range = None
        path = Path(self.translate_path(self.path))
        if path.is_dir() or not self.headers.get("Range"):
            return super().send_head()
        try:
            source = path.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        size = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        if not match or not any(match.groups()):
            source.close()
            # 다중 range 등은 일반 200 응답으로 처리합니다.
            return super().send_head()
        begin, end = match.groups()
        if begin:
            start = int(begin)
            stop = min(int(end), size - 1) if end else size - 1
        else:
            start = max(0, size - int(end))
            stop = size - 1
        if start < 0 or start >= size or stop < start:
            source.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        self.byte_range = (start, stop)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Length", str(stop - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{stop}/{size}")
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        return source

    def copyfile(self, source, outputfile):
        try:
            if self.byte_range is None:
                shutil.copyfileobj(source, outputfile)
                return
            start, stop = self.byte_range
            source.seek(start)
            remaining = stop - start + 1
            while remaining > 0:
                block = source.read(min(1024 * 256, remaining))
                if not block:
                    break
                outputfile.write(block)
                remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            # 빠른 드래그 때 브라우저가 이전 구간 요청을 취소할 수 있습니다.
            pass


def main():
    parser = argparse.ArgumentParser(description="Bracelet Project 로컬 미리보기")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="브라우저도 함께 열기")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(PreviewHandler, directory=str(ROOT)))
    except OSError as error:
        print(f"서버를 열지 못했습니다: {error}\n다른 포트 예: python3 serve.py --port 8001")
        raise SystemExit(1)
    address = f"http://127.0.0.1:{args.port}"
    print(f"\nBracelet Project\n{address}\n위 주소를 브라우저에서 열어 주세요. 종료: Ctrl+C\n")
    if args.open:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n미리보기를 종료했습니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

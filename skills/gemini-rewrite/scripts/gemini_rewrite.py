#!/usr/bin/env python3
"""Gemini に平文の書き直しを依頼する。stdin に下書き、--brief に要点や口調の指示。
依存ライブラリなし。REST API を直接叩く。"""
import argparse, json, os, random, sys, time, urllib.error, urllib.request

RETRY_CODES = {429, 500, 503}
FALLBACK_MODEL = os.environ.get("GEMINI_REWRITE_FALLBACK", "gemini-3.7-flash")

def call(model, body, key, tries=5):
    """429/500/503 は 2,4,8,16 秒(+ゆらぎ)待って最大4回リトライ。"""
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    try:
        print(call(a.model, body, key))
    except urllib.error.HTTPError as e:
        if e.code not in RETRY_CODES or a.model == FALLBACK_MODEL:
            sys.exit(f"[gemini-rewrite] {a.model}: HTTP {e.code} で失敗")
        print(f"[gemini-rewrite] {a.model} が HTTP {e.code} のまま。{FALLBACK_MODEL} に切り替え", file=sys.stderr)
        try:
            print(call(FALLBACK_MODEL, body, key))
        except urllib.error.HTTPError as e2:
            sys.exit(f"[gemini-rewrite] {FALLBACK_MODEL}: HTTP {e2.code} で失敗")

if __name__ == "__main__":
    main()

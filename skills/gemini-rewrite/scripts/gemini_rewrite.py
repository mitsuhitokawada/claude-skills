#!/usr/bin/env python3
"""Gemini に平文の書き直しを依頼する。stdin に下書き、--brief に要点や口調の指示。
依存ライブラリなし。REST API を直接叩く。429/500/503 は自動リトライ。"""
import argparse, json, os, random, sys, time, urllib.error, urllib.request

SYSTEM = """あなたは{persona}です。下書きの内容と順序を保ったまま、人間が普段書く自然な日本語のビジネス文に書き直してください。
制約: ダッシュ記号（――、—、–）を使わない。絵文字なし。箇条書きは使わず文章で。
「非常に」「極めて」「大幅に」「伴走」「寄り添う」「ソリューション」は使わない。
出力は本文のみ。前置きや説明を付けない。"""

RETRY_CODES = {429, 500, 503}
FALLBACK_MODEL = os.environ.get("GEMINI_REWRITE_FALLBACK", "gemini-3.7-flash")

def call(model, body, key, tries=5):
    """429/500/503 は 2,4,8,16 秒(+ゆらぎ)待って最大4回リトライ。"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=120)
            return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or i == tries - 1:
                raise
            wait = 2 ** (i + 1) + random.uniform(0, 1)
            print(f"[gemini-rewrite] {model}: HTTP {e.code}、{wait:.0f}秒後に再試行 ({i+1}/{tries-1})", file=sys.stderr)
            time.sleep(wait)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="", help="追加指示（宛先、長さ、口調など）")
    ap.add_argument("--persona", default=os.environ.get("GEMINI_REWRITE_PERSONA", "この文章の書き手本人"), help="書き手の立場(例: 〇〇社のCTO)")
    ap.add_argument("--model", default=os.environ.get("GEMINI_REWRITE_MODEL", "gemini-3.8-flash"))
    a = ap.parse_args()
    draft = sys.stdin.read()
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY が未設定")
    prompt = SYSTEM.format(persona=a.persona) + ("\n\n追加指示: " + a.brief if a.brief else "") + "\n\n---下書き---\n" + draft
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

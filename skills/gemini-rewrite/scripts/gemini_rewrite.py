#!/usr/bin/env python3
"""Gemini に平文の書き直しを依頼する。stdin に下書き、--brief に要点や口調の指示。
依存ライブラリなし。既定は Antigravity CLI(キー不要)、だめなら REST API(429/500/503 は自動リトライ)。"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_backend import add_backend_arg, generate

SYSTEM = """あなたは{persona}です。下書きの内容と順序を保ったまま、人間が普段書く自然な日本語のビジネス文に書き直してください。
制約: ダッシュ記号（――、—、–）を使わない。絵文字なし。箇条書きは使わず文章で。
「非常に」「極めて」「大幅に」「伴走」「寄り添う」「ソリューション」は使わない。
出力は本文のみ。前置きや説明を付けない。"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="", help="追加指示（宛先、長さ、口調など）")
    ap.add_argument("--persona", default=os.environ.get("GEMINI_REWRITE_PERSONA", "この文章の書き手本人"), help="書き手の立場(例: 〇〇社のCTO)")
    ap.add_argument("--model", default=os.environ.get("GEMINI_REWRITE_MODEL", "gemini-3.8-flash"))
    add_backend_arg(ap)
    a = ap.parse_args()
    draft = sys.stdin.read()
    prompt = SYSTEM.format(persona=a.persona) + ("\n\n追加指示: " + a.brief if a.brief else "") + "\n\n---下書き---\n" + draft
    print(generate(prompt, a.model, a.backend))

if __name__ == "__main__":
    main()

"""gemini-rewrite の呼び出し先を切り替える共通モジュール。
cli: Antigravity CLI(~/.local/bin/agy)。APIキー不要。Googleログイン済みの枠を使う
api: Gemini REST API(GEMINI_API_KEY)。429/500/503 はリトライ
auto(既定): CLI が使えれば CLI、だめなら API に切り替える"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request

RETRY_CODES = {429, 500, 503}
FALLBACK_MODEL = os.environ.get("GEMINI_REWRITE_FALLBACK", "gemini-3.7-flash")
CLI_TIMEOUT = os.environ.get("GEMINI_REWRITE_CLI_TIMEOUT", "3m")
TAG = "[gemini-rewrite]"


class CliError(Exception):
    pass


def log(msg):
    print(f"{TAG} {msg}", file=sys.stderr)


def _cli_models(path):
    try:
        r = subprocess.run([path, "models"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    names = [l.split("\t")[0].strip() for l in r.stdout.splitlines() if "\t" in l]
    return names or None


_CLI = None


def find_cli():
    """(path, models) を返す。エディタ用の agy は `agy models` が通らないので弾かれる。"""
    global _CLI
    if _CLI is None:
        _CLI = (None, [])
        for p in [os.path.expanduser("~/.local/bin/agy"), shutil.which("agy")]:
            if p and os.path.isfile(p) and os.access(p, os.X_OK):
                m = _cli_models(p)
                if m:
                    _CLI = (p, m)
                    break
    return _CLI


def cli_model(model, models):
    """gemini-3.8-flash → gemini-3.8-flash-medium のように CLI 側の名前へ寄せる。"""
    if model in models:
        return model
    for suf in ("-medium", "-high", "-low"):
        if model + suf in models:
            return model + suf
    return None


_CHROME = re.compile(r"^\s*(┃|esc to dismiss|Verbosity |Fetching )")


def call_cli(prompt, model):
    path, models = find_cli()
    if not path:
        raise CliError("Antigravity CLI が見つからないか未ログイン")
    m = cli_model(model, models)
    if not m:
        raise CliError(f"CLI に {model} 相当のモデルがない")
    with tempfile.TemporaryDirectory() as d:  # 空の作業ディレクトリで動かす(ファイルを触らせない)
        try:
            r = subprocess.run([path, "-p", prompt, "--model", m, "--disable-slash-commands",
                                "--print-timeout", CLI_TIMEOUT], cwd=d, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=600)
        except subprocess.TimeoutExpired:
            raise CliError("CLI がタイムアウト")
    lines = [l for l in r.stdout.splitlines() if not _CHROME.match(l)]
    out = "\n".join(lines).strip()
    if r.returncode != 0 or not out:
        err = (r.stderr or "").strip().splitlines()
        raise CliError(f"CLI 失敗(rc={r.returncode}) {err[-1][:200] if err else '出力なし'}")
    return out


def _api_once(model, prompt, key, temperature, tries=5):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if temperature is not None:
        body["generationConfig"] = {"temperature": temperature}
    data = json.dumps(body).encode()
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data, {"Content-Type": "application/json"}), timeout=180)
            return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or i == tries - 1:
                raise
            wait = 2 ** (i + 1) + random.uniform(0, 1)
            log(f"{model}: HTTP {e.code}、{wait:.0f}秒後に再試行 ({i+1}/{tries-1})")
            time.sleep(wait)


def call_api(prompt, model, temperature=None):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit(f"{TAG} 使える呼び出し先がありません。Antigravity CLI(~/.local/bin/agy)を入れてログインするか、GEMINI_API_KEY を設定してください")
    try:
        return _api_once(model, prompt, key, temperature)
    except urllib.error.HTTPError as e:
        if e.code not in RETRY_CODES or model == FALLBACK_MODEL:
            sys.exit(f"{TAG} {model}: HTTP {e.code} で失敗")
        log(f"{model} が HTTP {e.code} のまま。{FALLBACK_MODEL} に切り替え")
        try:
            return _api_once(FALLBACK_MODEL, prompt, key, temperature)
        except urllib.error.HTTPError as e2:
            sys.exit(f"{TAG} {FALLBACK_MODEL}: HTTP {e2.code} で失敗")


def generate(prompt, model, backend="auto", temperature=None):
    if backend in ("auto", "cli"):
        try:
            out = call_cli(prompt, model)
            log(f"CLI({find_cli()[0]}) で実行")
            return out
        except CliError as e:
            if backend == "cli":
                sys.exit(f"{TAG} {e}。初回は ~/.local/bin/agy を起動して Google でログインしてください")
            log(f"{e}。API に切り替え")
    return call_api(prompt, model, temperature)


def add_backend_arg(ap):
    ap.add_argument("--backend", choices=["auto", "cli", "api"],
                    default=os.environ.get("GEMINI_REWRITE_BACKEND", "auto"),
                    help="auto(既定): CLI があれば CLI、だめなら API / cli: Antigravity CLI のみ / api: GEMINI_API_KEY のみ")

# arlq 言語自動検出・翻訳リソース選択 仕様／設計ハンドオフ

## 目的

`arlq` に日本語UI対応を導入する。

CLIには既に次のオプションを設ける想定。

```text
--lang {auto,en,ja}
```

既定値は `auto`。

`auto` の場合はOS／実行環境の言語設定から言語IDを取得し、その言語IDに対応する翻訳JSONを自動選択する。

当面の対応言語は英語・日本語だが、将来的に中国語などを追加しやすい構造にする。

---

## 基本方針

言語検出と翻訳リソース選択を分離する。

OSから取得した言語情報を最初から `en` / `ja` に丸め込まず、可能な限り詳細な言語タグを保持する。

例:

```text
ja-JP
en-US
zh-CN
zh-TW
zh-Hant-TW
```

その後、利用可能な翻訳JSONを検索し、より具体的なものから順にフォールバックする。

例:

```text
ja-JP
  -> ja-JP.json
  -> ja.json
  -> en.json
```

```text
zh-Hant-TW
  -> zh-Hant-TW.json
  -> zh-Hant.json
  -> zh.json
  -> en.json
```

---

## 翻訳JSONの命名規則

翻訳ファイル名にはBCP 47風の言語タグを使用する。

地域差が不要な言語は短い名前でよい。

例:

```text
locales/
  en.json
  ja.json
```

地域差や文字体系の差が必要な場合のみ細分化する。

例:

```text
locales/
  en.json
  ja.json
  zh-CN.json
  zh-TW.json
  pt-BR.json
  pt-PT.json
```

日本語については、現時点では地域別翻訳を持つ必要がないため、

```text
ja.json
```

とする。

OS側で `ja-JP` が検出されても、`ja-JP.json` がなければ `ja.json` を使用する。

---

## 言語タグの検索規則

検出された言語タグについて、右側のサブタグを順番に削除しながら翻訳JSONを探す。

例:

```text
zh-Hant-TW
```

に対して、

```text
zh-Hant-TW.json
zh-Hant.json
zh.json
```

の順に検索する。

いずれも存在しなければ、

```text
en.json
```

へフォールバックする。

概念コード:

```python
def locale_candidates(tag: str) -> list[str]:
    parts = tag.split("-")
    candidates = []

    while parts:
        candidates.append("-".join(parts))
        parts.pop()

    if "en" not in candidates:
        candidates.append("en")

    return candidates
```

例:

```python
locale_candidates("zh-Hant-TW")
```

結果:

```python
["zh-Hant-TW", "zh-Hant", "zh", "en"]
```

---

## OS言語検出

### 共通方針

まず明示的な環境変数指定を尊重する。

優先順位:

```text
LC_ALL
LC_MESSAGES
LANG
```

最初に空でない値が見つかった時点で採用する。

これはPOSIX環境だけでなく、Windows/macOS上でもユーザーが明示的に環境変数を指定して起動した場合のoverrideとして扱う。

---

## Linux / BSD

Linux/BSDでは、基本的にPOSIXロケール環境変数を使用する。

例:

```text
ja_JP.UTF-8
en_US.UTF-8
```

これを内部的な言語タグへ正規化する。

例:

```text
ja_JP.UTF-8 -> ja-JP
en_US.UTF-8 -> en-US
```

Linuxではユーザーセッションの言語設定が最終的に環境変数へ反映されるのが一般的なので、GNOME/KDE/systemd等の個別設定を追加で調査しない。

環境変数がない場合は言語検出失敗として扱い、最終的に `en` へフォールバックする。

---

## Windows

Windowsでは環境変数が設定されていない場合、

```text
GetUserPreferredUILanguages
```

を `ctypes` から呼び出す。

`MUI_LANGUAGE_NAME` を指定し、優先UI言語を文字列形式で取得する。

例:

```text
ja-JP
en-US
```

先頭のpreferred UI languageのみ使用すればよい。

地域設定取得用の

```text
GetUserDefaultLocaleName
```

は使用しない。

理由:

Windowsでは「表示言語」と「地域／日付／通貨等のlocale」を別々に設定できるため、UI言語選択にはpreferred UI languageを使う方が適切。

---

## macOS

macOSでは環境変数がない場合、ユーザーのpreferred languagesを取得する。

取得対象は概念的には、

```text
NSLocale.preferredLanguages
```

または

```text
CFLocaleCopyPreferredLanguages()
```

に相当する情報。

実装としては依存追加を避けるため、

```text
defaults export NSGlobalDomain -
```

でglobal defaultsをplistとして取得し、Python標準ライブラリの

```python
plistlib
```

で読み取る。

`AppleLanguages` 配列の先頭を使用する。

例:

```text
["ja-JP", "en-JP", "en"]
```

なら、

```text
ja-JP
```

を採用する。

PyObjC等の新規依存は追加しない。

---

## 言語タグ正規化

POSIX localeなどはそのままBCP 47形式ではないため、簡易正規化を行う。

例:

```text
ja_JP.UTF-8
en_US
ja-JP
```

を、

```text
ja-JP
en-US
ja-JP
```

へ変換する。

当面は次の程度でよい。

```python
def normalize_locale_tag(value: str) -> str:
    value = value.strip()

    value = value.split(".", 1)[0]
    value = value.split("@", 1)[0]
    value = value.replace("_", "-")

    parts = value.split("-")
    if not parts:
        return ""

    parts[0] = parts[0].lower()

    if len(parts) >= 2 and len(parts[1]) == 2:
        parts[1] = parts[1].upper()

    return "-".join(parts)
```

完全なBCP 47パーサを実装する必要はない。

今回の目的はOS設定と翻訳JSONの名前を対応付けることなので、過度な正規化やCLDR依存は避ける。

---

## API設計案

責務を次のように分ける。

### `detect_locale()`

OS／環境から最も具体的な言語タグを取得する。

例:

```python
detect_locale() -> "ja-JP"
detect_locale() -> "en-US"
detect_locale() -> "zh-TW"
```

検出できなければ空文字列などを返してよい。

---

### `locale_candidates()`

具体的な言語タグから翻訳リソース候補を生成する。

例:

```python
locale_candidates("ja-JP")
```

結果:

```python
["ja-JP", "ja", "en"]
```

---

### `load_messages()`

翻訳JSONの存在を確認し、最初に見つかったものを読み込む。

概念:

```python
def load_messages(tag: str):
    for candidate in locale_candidates(tag):
        path = locale_dir / f"{candidate}.json"
        if path.is_file():
            return load_json(path)

    raise RuntimeError("en.json is missing")
```

`en.json` は必須リソースとし、存在しない場合はプログラム側のパッケージ不整合として扱ってよい。

---

## CLI `--lang` の扱い

### `--lang auto`

OS／環境から言語タグを検出する。

例:

```text
OS: ja-JP
-> ja-JP.json
-> ja.json
-> en.json
```

---

### `--lang ja`

明示指定された言語として扱う。

```text
ja
-> ja.json
-> en.json
```

---

### `--lang en`

```text
en
-> en.json
```

---

## 将来の拡張

この設計では、新しい言語を追加するとき、原則として翻訳JSONを追加するだけでよい。

例:

```text
ko.json
de.json
fr.json
```

地域差が必要になった場合のみ、

```text
pt-BR.json
pt-PT.json

zh-CN.json
zh-TW.json
```

のように細分化する。

OS言語検出側は変更しなくてよい。

---

## 新規依存について

新規Python依存は追加しない。

使用するもの:

```text
os
sys
ctypes
subprocess
plistlib
json
pathlib
```

いずれも標準ライブラリ。

Babelは使用しない。

理由:

* CLDRデータ等を含み今回の用途には重い。
* `babel.core.default_locale()` は基本的に環境変数ベースであり、Windows/macOSのUI言語取得を直接解決しない。
* 今回必要なのは翻訳・複数形・数値フォーマット等ではなく、翻訳JSONを1つ選ぶための言語検出だけ。

---

## `locale` モジュールについて

現在の

```python
locale.setlocale(locale.LC_ALL, "")
locale.getlocale()
```

によるfallbackは削除する方向とする。

理由:

* `setlocale()` はプロセス全体のC localeを変更する副作用がある。
* OSのUI言語取得APIではない。
* Windows/macOSではより適切なネイティブ情報源がある。
* `locale.getdefaultlocale()` は非推奨であり、将来的な依存を避けたい。

今回の言語自動選択処理では、Pythonの `locale` モジュールに依存しない設計とする。

---

## 実装時の重要方針

過度なi18n抽象化は行わない。

`arlq` は小規模なゲームであり、今回必要なのは、

```text
OS言語を取得
↓
翻訳JSONを1つ選択
↓
文字列を参照
```

という処理のみ。

gettext、Babel、CLDRベースのフルi18nシステムは導入しない。

また、OS固有処理は可能な限り `i18n.py` 内に閉じ込め、他のゲームコードからは、

```python
messages = load_messages(...)
```

程度のインターフェースだけを見せる。

---

## 想定する最終構成例

```text
src/arlq/
  i18n.py
  locales/
    en.json
    ja.json
```

将来:

```text
src/arlq/
  locales/
    en.json
    ja.json
    zh-CN.json
    zh-TW.json
    ko.json
```

OSから `zh-TW` が取得された場合は、

```text
zh-TW.json
-> zh.json
-> en.json
```

の順に検索する。

これにより、OS側では可能な限り詳細な言語情報を保持しつつ、arlq側は必要な粒度だけ翻訳を提供できる。

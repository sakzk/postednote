# Pythonにおけるシンボリックリンク経由のパス解決

Gitのpre-commitフックで、ファイル実体を別の場所に置き、シンボリックリンク経由でスクリプトを実行する構成としたところ、ファイルのパス解決に関する問題に遭遇しました。

本記事では、その解決策と、背景にあるパス操作におけるメンタルモデルについてまとめます。

**検証環境**

* macOS Sequoia 15.7.2
* Python 3.14.0

## 問題の概要

プロジェクトのルートにある `tools/script.py` を、`.git/hooks/pre-commit` からシンボリックリンクを貼って実行する構成をとりました。

スクリプト内で、自身のディレクトリにある設定ファイル（`./config.json`）を読み込もうとしたところ、`FileNotFoundError` が発生しました。調査の結果、スクリプトが参照していたパスが `tools/` ではなく `.git/hooks/` 起点になっていたことが判明しました。

## 原因

Pythonの `__file__` 属性には、スクリプトがロードされた際のパスが保持されます。今回のようにシンボリックリンク経由で実行された場合、ここにはリンク自体のパス（`.git/hooks/pre-commit`）が格納されます。

私はこれまで `os.path.abspath(__file__)` を「ファイルの絶対パス」を取得する関数として捉えていましたが、これはシンボリックリンクの実体解決を行いません。そのため、後続処理で基準となるディレクトリがズレてしまっていました。

## 解決策

シンボリックリンクから実体を取得するには、`pathlib.Path.resolve` または `os.path.realpath` を使用します。これらはファイルシステム上のリンクを追跡してパスを解決します。

**修正前**

```python
import os

# git commit 時はリンクの場所 (.git/hooks/pre-commit) が基準になってしまう
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
```

**修正後（推奨されるコード）**
Python 3.4 以降

```python
from pathlib import Path

# リンクを解決し、実体 (tools/) のパスを取得する
SCRIPT_PATH = Path(__file__).resolve()
BASE_DIR = SCRIPT_PATH.parent
```

`os.path` を使用する場合は以下のようになります。

```python
import os
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
```

## パス操作におけるメンタルモデル

なぜ `abspath` で動くと誤解してしまったのか、振り返るとパス操作に対するメンタルモデルに不正確な点がありました。

### 1. 文字列操作 vs ファイルシステム操作

私は `abspath` という関数名から、「そのファイルが存在する絶対パス」を返してくれる挙動を期待していました。しかし、実際には動作原理と計算コストにおいて違いがあります。

* **os.path.abspath**: カレントディレクトリとファイル名を文字列として結合し、パスの形式を整える操作が主です。対象のファイルが実在するか、リンクであるかは考慮しません。ユーザープロセス内のメモリ操作で完結するため高速です。

* **os.path.realpath**: ファイルシステムへの照会を行います。実際にOSに対してシステムコールを発行し、inodeを辿ってシンボリックリンクを解決した結果を返します。I/Oコストが発生します。

「パスを扱う」という行為が、単なる文字列の正規化なのか、実体の特定なのかを区別する必要がありました。
（※具体的な実装の違いについては付録に追加予定）

### 2. 実行コンテキストとリソースコンテキストの分離

通常、スクリプトは配置場所と実行場所が一致することが多いため意識していませんでしたが、Git Hookのようなケースではこれが分離します。

* **Invocation Context (起動時の文脈):** `.git/hooks/`
プロセスがどこから、どのように呼ばれたか。

* **Physical Context (実体の文脈):** `tools/` コードやリソースが物理的にどこにあるか。

スクリプトに付随するリソース（設定ファイルなど）を読み込む場合、実行時のパス（`__file__` の初期値）に依存するとこのズレの影響を受けます。`resolve` を使用することで、起動時の文脈から離れ、リソースが存在する実体の場所へと基準を移すことができます。

### 3. os.path と pathlib

この問題を通じて、Python標準ライブラリの変遷も感じられました。

Python 3.4で導入された `pathlib` は、パスを文字列ではなくオブジェクトとして扱う設計になっています。文字列操作によるパス処理の煩雑さと誤りやすさについての議論に基づいているようです｡

`abspath` とは異なり、メソッド名が `.resolve()` となっている点は、裏側でファイルシステムへの問い合わせが走る動的なパス処理であることを伝えているように感じます。

* 参照:
  * [PEP 428 – The pathlib module – object-oriented filesystem paths](https://peps.python.org/pep-0428/)
  * [Why pathlib.Path doesn't inherit from str in Python](https://snarky.ca/why-pathlib-path-doesn-t-inherit-from-str/)

## 結論

CLIツールやHookスクリプトなど、シンボリックリンク経由で実行される可能性があるスクリプトを記述する場合、自身の場所を特定するには `pathlib.Path.resolve()` を使用するのが安全です。

1行のパス修正を通して言語処理系がどのようにファイルシステムを扱っているか、OSとの境界線を意識する良い機会になりました。

---

## 付録

### A. `__file__` の仕様

Python 3.14 のドキュメントには以下のように記載されています。

> **\_\_file\_\_** indicates the pathname of the file from which the module was loaded (if loaded from a file), or the pathname of the shared library file for extension modules loaded dynamically from a shared library.
* 参照: [The Python Language Reference » 3. Data model](https://docs.python.org/3.14/reference/datamodel.html#module.\_\_file\_\_)

ここでの「ファイルのパス名」とは、インタプリタに渡されたパスそのものを指します。シンボリックリンク経由で渡された場合、自動的に実体に解決されることはありません。


### B. CPythonにおけるabspath(), realpath(), pathlib.Path.resolve()の内部実装
調査後追加する


## 自分用メモ
- `python3 tools/pre-commit` として呼び出すのであれば､ `abspath(__file__)` を用いたままでも意図通りのパスを抽出できていた｡ 原因の特定のためには､スクリプトをgit commit から呼び出すことが必須だった｡
- pre-commit の処理結果に応じて､commitをabortしたい場合､sys.exit(1)などで､明示的にエラーコードを送出して脱出する必要がある｡ return してしまうとpre-commit処理が正常終了扱いとなり､commit が実行される｡
    - 今回の要件は､ステージング対象の修正を index.md に反映したい｡pre-commitが失敗したらコミットそのものを中断するのが適当｡
- 今回は初期化処理中なので､パス解決のパフォーマンスは気にしない｡ 動的なパス解決が必要でかつ性能に対してクリティカルになるようなアプリケーションってどんなものだろうか｡
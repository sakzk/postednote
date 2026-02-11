import glob
import json
import os
from datetime import datetime

# ==========================================
# Setup Paths
# ==========================================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")


# ==========================================
# Helper Functions
# ==========================================
def load_config():
    """
    config.jsonを読み込む
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Config file not found at {CONFIG_FILE}")
        exit(1)


def parse_post(file_path, directory):
    """
    ファイルを読み込んでメタデータ(辞書)を返す
    """
    filename = os.path.basename(file_path)

    # タイトル抽出
    title = filename
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line.startswith("# "):
                title = first_line.replace("# ", "")
    except Exception:
        pass

    # 日付 (ファイル名先頭10文字: YYYY-MM-DD)
    date_str = filename[:10]

    return {
        "title": title,
        "filename": filename,
        "date": date_str,
        "path": f"./{directory}/{filename}",  # リンク用パス
        "dir_type": directory,  # slogsかpostsか判定用
    }


def generate_md_list_item(post):
    """辞書からMarkdownのリスト行を生成"""
    # slogs または タイトルに日付が含まれる場合は日付表記を省略
    if post["title"] == post["date"] or post["dir_type"] == "slogs":
        return f"- [{post['title']}]({post['path']})"
    else:
        return f"- [{post['title']}]({post['path']}) <small>({post['date']})</small>"


def main():
    print("Loading config...")
    config = load_config()

    archive_file = os.path.join(ROOT_DIR, config.get("archive_file", "archive.md"))
    template_file = os.path.join(ROOT_DIR, config.get("template_file", "templates/archive.md"))
    sections = config.get("sections", [])

    print("Scanning posts...")

    all_posts = []  # 全記事格納用 (Recents用)
    section_bodies = []  # セクションごとのMD格納用

    # 1. 各セクションを走査
    for section in sections:
        directory = section["dir"]
        search_path = os.path.join(ROOT_DIR, directory, "*.md")
        files = sorted(glob.glob(search_path), reverse=True)

        if not files:
            continue

        # セクション内の記事リスト
        current_section_posts = []
        for file_path in files:
            post = parse_post(file_path, directory)
            current_section_posts.append(post)
            all_posts.append(post)  # 全体リストにも追加

        # セクションのMarkdown生成
        lines = [f"## {section['title']}"]
        if "description" in section:
            lines.append(f"> {section['description']}\n")

        for post in current_section_posts:
            lines.append(generate_md_list_item(post))

        lines.append("")  # 空行
        section_bodies.append("\n".join(lines))

    # 2. Recentsの生成 (全記事を日付順ソートしてトップ10)
    # ファイル名(日付)で逆順ソート
    all_posts.sort(key=lambda x: x["filename"], reverse=True)
    recent_10 = all_posts[:10]

    recents_md_lines = []
    for post in recent_10:
        recents_md_lines.append(generate_md_list_item(post))
    recents_body = "\n".join(recents_md_lines)

    # 3. テンプレート読み込み & 書き出し
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            template_content = f.read()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_content = template_content.format(
            recents=recents_body, body="\n".join(section_bodies), updated_at=now  # ここに追加
        )

        with open(archive_file, "w", encoding="utf-8") as f:
            f.write(final_content)

        print(f"✅ Updated: {archive_file} (Recents: {len(recent_10)} items)")

    except FileNotFoundError:
        print(f"❌ Error: Template not found at {template_file}")


if __name__ == "__main__":
    main()

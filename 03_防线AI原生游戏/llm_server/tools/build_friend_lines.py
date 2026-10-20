# -*- coding: utf-8 -*-
"""
《防线》 · llm_server/tools/build_friend_lines.py
从第一幕对话数据抽取「旧友台词库」（validate_player_line 引擎的判定基准库）

用途：场景 5.4「最终抉择 · 选项 B」——玩家手动输入旧友说过的某句话，
      validate_player_line 引擎拿输入与库内台词做匹配判定。

来源：W4/dialogues/dialogues_act1.json（speaker == "friend" 的全部台词行）

执行::
    cd defense-line-repo/llm_server
    python tools/build_friend_lines.py            # 写入 data/friend_lines.json
    python tools/build_friend_lines.py --check    # 只校验现有库与源是否同步（不写）

注意：生成的 data/friend_lines.json **可人工扩充**（追加玩家在游戏里可能复述的
      变体台词时，保持 id 唯一、dialogue_id 指向源对话即可）；扩充后请勿再直接
      重跑本脚本覆盖，或先用 --check 对比差异。
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SERVER_DIR = Path(__file__).resolve().parent.parent      # llm_server/
REPO_ROOT = SERVER_DIR.parent                            # 仓库根
SOURCE = REPO_ROOT / "W4" / "dialogues" / "dialogues_act1.json"
TARGET = SERVER_DIR / "data" / "friend_lines.json"

ID_WIDTH = 3          # FL_001 / FL_010
FRIEND_SPEAKER = "friend"


def extract(source_path: Path = SOURCE) -> list:
    """抽取 source_path 中 speaker=="friend" 的全部台词行（按对话顺序）。"""
    data = json.loads(source_path.read_text(encoding="utf-8"))
    dialogues = data.get("dialogues")
    if not isinstance(dialogues, dict):
        raise ValueError(f"{source_path} 缺少顶层 dialogues 对象")

    lines = []
    for dialogue_id, entry in dialogues.items():
        if not isinstance(entry, dict):
            continue
        for line in entry.get("lines", []) or []:
            if not isinstance(line, dict) or line.get("speaker") != FRIEND_SPEAKER:
                continue
            text = (line.get("text") or "").strip()
            if not text:
                continue
            lines.append({
                "id": f"FL_{len(lines) + 1:0{ID_WIDTH}d}",
                "dialogue_id": dialogue_id,
                "text": text,
            })
    return lines


def build(source_path: Path = SOURCE) -> dict:
    lines = extract(source_path)
    return {
        "_meta": {
            "source": source_path.name,
            "source_path": "W4/dialogues/dialogues_act1.json",
            "generated": date.today().isoformat(),
            "note": "可人工扩充（追加变体台词时保持 id 唯一、dialogue_id 指向源对话）",
            "count": len(lines),
        },
        "lines": lines,
    }


def main():
    parser = argparse.ArgumentParser(description="抽取旧友台词库（validate_player_line 基准库）")
    parser.add_argument("--check", action="store_true", help="只校验现有库与源是否同步，不写文件")
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"❌ 源文件不存在：{SOURCE}")
        sys.exit(1)

    fresh = build()
    n = len(fresh["lines"])

    if args.check:
        if not TARGET.exists():
            print(f"❌ 库文件不存在：{TARGET}")
            sys.exit(1)
        current = json.loads(TARGET.read_text(encoding="utf-8"))
        cur_texts = [l["text"] for l in current.get("lines", [])]
        new_texts = [l["text"] for l in fresh["lines"]]
        if cur_texts == new_texts:
            print(f"✅ 同步：库 {len(cur_texts)} 条 == 源 {len(new_texts)} 条")
            return
        print(f"⚠️ 不同步：库 {len(cur_texts)} 条 vs 源 {len(new_texts)} 条")
        print("   库独有：", [t[:20] for t in cur_texts if t not in new_texts][:5])
        print("   源独有：", [t[:20] for t in new_texts if t not in cur_texts][:5])
        sys.exit(2)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 已写入 {TARGET}")
    print(f"   条数：{n}（源：{fresh['_meta']['source_path']}，speaker == \"friend\"）")
    for line in fresh["lines"]:
        print(f"   {line['id']}  {line['dialogue_id']:<26} {line['text'][:28]}")


if __name__ == "__main__":
    main()

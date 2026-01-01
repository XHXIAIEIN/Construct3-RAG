"""
从 Construct 3 翻译 CSV 生成完整的 ACE Schema
包含中英文名称、描述、参数信息
"""
import csv
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def parse_csv_key(key: str) -> dict:
    """解析 CSV key 结构

    例: text.behaviors.eightdir.actions.set-speed.params.speed.name
    返回: {
        'type': 'behaviors',
        'object_id': 'eightdir',
        'ace_type': 'actions',
        'ace_id': 'set-speed',
        'field': 'params.speed.name'
    }
    """
    if not key.startswith("text."):
        return None

    parts = key[5:].split(".")  # 去掉 "text." 前缀

    if len(parts) < 2:
        return None

    obj_type = parts[0]  # plugins, behaviors, system
    if obj_type not in ("plugins", "behaviors", "system"):
        return None

    obj_id = parts[1]

    result = {
        "type": obj_type,
        "object_id": obj_id,
    }

    if len(parts) >= 4:
        # 检查是否是 ACE 条目
        if parts[2] in ("conditions", "actions", "expressions"):
            result["ace_type"] = parts[2]
            result["ace_id"] = parts[3]
            result["field"] = ".".join(parts[4:]) if len(parts) > 4 else ""
        elif parts[2] == "properties":
            result["ace_type"] = "properties"
            result["ace_id"] = parts[3]
            result["field"] = ".".join(parts[4:]) if len(parts) > 4 else ""
        else:
            result["field"] = ".".join(parts[2:])
    elif len(parts) >= 3:
        result["field"] = ".".join(parts[2:])

    return result


def load_csv_data(csv_path: Path) -> Dict[str, Dict]:
    """加载并解析 CSV 数据"""
    objects = defaultdict(lambda: {
        "name_zh": "",
        "name_en": "",
        "description_zh": "",
        "description_en": "",
        "properties": {},
        "conditions": {},
        "actions": {},
        "expressions": {}
    })

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue

            key = row[0]
            zh_value = row[1] if len(row) > 1 else ""
            en_value = row[5] if len(row) > 5 else ""

            parsed = parse_csv_key(key)
            if not parsed:
                continue

            obj_type = parsed["type"]
            obj_id = parsed["object_id"]
            obj_key = f"{obj_type}.{obj_id}"
            obj = objects[obj_key]
            obj["_type"] = obj_type
            obj["_id"] = obj_id

            field = parsed.get("field", "")
            ace_type = parsed.get("ace_type")

            # 对象级别的信息 (只在没有 ace_type 时才是对象级别)
            if not ace_type:
                if field == "name":
                    obj["name_zh"] = zh_value
                    obj["name_en"] = en_value
                elif field == "description":
                    obj["description_zh"] = zh_value
                    obj["description_en"] = en_value

            # ACE 信息
            ace_id = parsed.get("ace_id")

            if ace_type and ace_id:
                ace_collection = obj.get(ace_type, {})
                if ace_id not in ace_collection:
                    ace_collection[ace_id] = {
                        "id": ace_id,
                        "name_zh": "",
                        "name_en": "",
                        "description_zh": "",
                        "description_en": "",
                        "display_text_zh": "",
                        "display_text_en": "",
                        "params": {}
                    }

                ace = ace_collection[ace_id]

                if field == "list-name":
                    ace["name_zh"] = zh_value
                    ace["name_en"] = en_value
                elif field == "translated-name":
                    # 表达式使用 translated-name
                    ace["name_zh"] = zh_value
                    ace["name_en"] = en_value
                elif field == "description":
                    ace["description_zh"] = zh_value
                    ace["description_en"] = en_value
                elif field == "display-text":
                    ace["display_text_zh"] = zh_value
                    ace["display_text_en"] = en_value
                elif field.startswith("params."):
                    # 解析参数
                    param_parts = field.split(".")
                    if len(param_parts) >= 2:
                        param_id = param_parts[1]
                        param_field = ".".join(param_parts[2:]) if len(param_parts) > 2 else ""

                        if param_id not in ace["params"]:
                            ace["params"][param_id] = {
                                "id": param_id,
                                "name_zh": "",
                                "name_en": "",
                                "description_zh": "",
                                "description_en": "",
                                "items": {}
                            }

                        param = ace["params"][param_id]

                        if param_field == "name":
                            param["name_zh"] = zh_value
                            param["name_en"] = en_value
                        elif param_field == "desc":
                            param["description_zh"] = zh_value
                            param["description_en"] = en_value
                        elif param_field.startswith("items."):
                            item_id = param_field.split(".")[1]
                            param["items"][item_id] = {
                                "zh": zh_value,
                                "en": en_value
                            }

                obj[ace_type] = ace_collection

    return objects


def generate_schema_files(objects: Dict, output_dir: Path):
    """生成 Schema 文件，按语言分开"""

    # 按语言分目录
    for lang in ["zh", "en"]:
        lang_dir = output_dir / lang
        (lang_dir / "plugins").mkdir(parents=True, exist_ok=True)
        (lang_dir / "behaviors").mkdir(parents=True, exist_ok=True)
        (lang_dir / "system").mkdir(parents=True, exist_ok=True)

    index = {
        "version": "2.0",
        "source": "zh-CN_R466.csv",
        "languages": ["zh", "en"],
        "plugins": {},
        "behaviors": {},
        "system": {}
    }

    for obj_key, obj in objects.items():
        obj_type = obj.get("_type", "")
        obj_id = obj.get("_id", "")

        if not obj_type or not obj_id:
            continue

        # 为每种语言生成文件
        for lang in ["zh", "en"]:
            lang_key = f"name_{lang}"
            desc_key = f"description_{lang}"
            display_key = f"display_text_{lang}"

            def convert_aces(aces: Dict) -> List[Dict]:
                result = []
                for ace_id, ace in aces.items():
                    params = []
                    for param_id, param in ace.get("params", {}).items():
                        p = {
                            "id": param_id,
                            "name": param[f"name_{lang}"],
                            "description": param[f"description_{lang}"]
                        }
                        if param.get("items"):
                            p["options"] = [
                                {"id": k, "label": v[lang]}
                                for k, v in param["items"].items()
                            ]
                        params.append(p)

                    result.append({
                        "id": ace_id,
                        "name": ace[f"name_{lang}"],
                        "description": ace[f"description_{lang}"],
                        "display_text": ace[f"display_text_{lang}"],
                        "params": params
                    })
                return result

            schema = {
                "id": obj_id,
                "name": obj[lang_key],
                "description": obj[desc_key],
                "type": "plugin" if obj_type == "plugins" else ("behavior" if obj_type == "behaviors" else "system"),
                "conditions": convert_aces(obj.get("conditions", {})),
                "actions": convert_aces(obj.get("actions", {})),
                "expressions": convert_aces(obj.get("expressions", {})),
                "stats": {
                    "conditions": len(obj.get("conditions", {})),
                    "actions": len(obj.get("actions", {})),
                    "expressions": len(obj.get("expressions", {}))
                }
            }

            # 确定输出目录
            if obj_type == "plugins":
                subdir = "plugins"
            elif obj_type == "behaviors":
                subdir = "behaviors"
            else:
                subdir = "system"

            target_dir = output_dir / lang / subdir
            filepath = target_dir / f"{obj_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(schema, f, ensure_ascii=False, indent=2)

        # 索引记录：基本信息 + ACE 列表 (只含 id + name)
        def ace_list(aces: Dict) -> List[Dict]:
            return [
                {"id": ace_id, "name_zh": ace["name_zh"], "name_en": ace["name_en"]}
                for ace_id, ace in aces.items()
                if ace["name_zh"] or ace["name_en"]  # 过滤空名称
            ]

        index_entry = {
            "name_zh": obj["name_zh"],
            "name_en": obj["name_en"],
            "description_zh": obj["description_zh"],
            "description_en": obj["description_en"],
            "conditions": ace_list(obj.get("conditions", {})),
            "actions": ace_list(obj.get("actions", {})),
            "expressions": ace_list(obj.get("expressions", {}))
        }

        if obj_type == "plugins":
            index["plugins"][obj_id] = index_entry
        elif obj_type == "behaviors":
            index["behaviors"][obj_id] = index_entry
        else:
            index["system"][obj_id] = index_entry

        print(f"  {obj_id}")

    # 计算统计信息
    total_conditions = sum(len(p["conditions"]) for p in index["plugins"].values()) + \
                       sum(len(b["conditions"]) for b in index["behaviors"].values())
    total_actions = sum(len(p["actions"]) for p in index["plugins"].values()) + \
                    sum(len(b["actions"]) for b in index["behaviors"].values())
    total_expressions = sum(len(p["expressions"]) for p in index["plugins"].values()) + \
                        sum(len(b["expressions"]) for b in index["behaviors"].values())

    # 拆分为子索引文件
    plugins_data = index["plugins"]
    behaviors_data = index["behaviors"]
    system_data = index["system"]

    # 写入 plugins.json
    plugins_path = output_dir / "plugins.json"
    with open(plugins_path, "w", encoding="utf-8") as f:
        json.dump(plugins_data, f, ensure_ascii=False, indent=2)

    # 写入 behaviors.json
    behaviors_path = output_dir / "behaviors.json"
    with open(behaviors_path, "w", encoding="utf-8") as f:
        json.dump(behaviors_data, f, ensure_ascii=False, indent=2)

    # 主索引只保留概要
    main_index = {
        "version": "2.0",
        "source": "zh-CN_R466.csv",
        "languages": ["zh", "en"],
        "files": {
            "plugins": "plugins.json",
            "behaviors": "behaviors.json"
        },
        "plugins": {
            obj_id: {
                "name_zh": obj["name_zh"],
                "name_en": obj["name_en"],
                "conditions": len(obj["conditions"]),
                "actions": len(obj["actions"]),
                "expressions": len(obj["expressions"])
            }
            for obj_id, obj in plugins_data.items()
        },
        "behaviors": {
            obj_id: {
                "name_zh": obj["name_zh"],
                "name_en": obj["name_en"],
                "conditions": len(obj["conditions"]),
                "actions": len(obj["actions"]),
                "expressions": len(obj["expressions"])
            }
            for obj_id, obj in behaviors_data.items()
        },
        "stats": {
            "plugins_count": len(plugins_data),
            "behaviors_count": len(behaviors_data),
            "system_count": len(system_data),
            "total_conditions": total_conditions,
            "total_actions": total_actions,
            "total_expressions": total_expressions,
            "total_aces": total_conditions + total_actions + total_expressions
        }
    }

    # 写入主索引
    index_path = output_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(main_index, f, ensure_ascii=False, indent=2)

    print(f"\n索引文件:")
    print(f"  {index_path.name} (概要)")
    print(f"  {plugins_path.name} ({len(plugins_data)} 插件)")
    print(f"  {behaviors_path.name} ({len(behaviors_data)} 行为)")
    print(f"总 ACE: {main_index['stats']['total_aces']} (C:{total_conditions} A:{total_actions} E:{total_expressions})")


def main():
    source_dir = Path(__file__).parent.parent.parent / "source"
    csv_path = source_dir / "zh-CN_R466.csv"
    output_dir = source_dir / "Construct3-Schema"

    print("解析 CSV 翻译文件...\n")
    objects = load_csv_data(csv_path)

    print(f"发现 {len(objects)} 个对象\n")

    # 清理旧文件
    for lang in ["zh", "en"]:
        for subdir in ["plugins", "behaviors", "system"]:
            dir_path = output_dir / lang / subdir
            if dir_path.exists():
                for f in dir_path.glob("*.json"):
                    f.unlink()
    # 清理旧的非语言分离文件
    for subdir in ["plugins", "behaviors", "system"]:
        dir_path = output_dir / subdir
        if dir_path.exists():
            for f in dir_path.glob("*.json"):
                f.unlink()

    print("生成 Schema 文件...\n")
    generate_schema_files(objects, output_dir)

    print("\n完成!")


if __name__ == "__main__":
    main()

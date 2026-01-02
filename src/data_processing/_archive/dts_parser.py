"""
从 Construct 3 TypeScript 定义文件 (.d.ts) 中提取 API 信息
生成结构化的脚本 API 参考
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class MethodDef:
    """方法定义"""
    name: str
    signature: str  # 完整签名，如 "setAnimation(name: string, from?: string)"
    return_type: str = ""
    params: List[Dict[str, str]] = field(default_factory=list)  # [{name, type}]
    is_readonly: bool = False
    is_async: bool = False
    doc: str = ""


@dataclass
class ClassDef:
    """类/接口定义"""
    name: str
    extends: str = ""
    doc: str = ""
    properties: List[MethodDef] = field(default_factory=list)
    methods: List[MethodDef] = field(default_factory=list)


def parse_dts_file(filepath: Path) -> List[ClassDef]:
    """解析单个 .d.ts 文件"""
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')

    classes = []
    current_class: Optional[ClassDef] = None
    current_doc = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 收集 JSDoc 注释
        if stripped.startswith('/**') or stripped.startswith('*'):
            if '@see' in stripped or '@deprecated' in stripped:
                current_doc += stripped + " "
            continue

        # 类声明
        if 'declare class' in stripped:
            match = re.search(r'declare class (\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+))?', stripped)
            if match:
                if current_class:
                    classes.append(current_class)
                current_class = ClassDef(
                    name=match.group(1),
                    extends=match.group(2) or "",
                    doc=current_doc.strip()
                )
                current_doc = ""
            continue

        # 接口声明
        if 'interface ' in stripped and '{' in stripped:
            match = re.search(r'interface (\w+)', stripped)
            if match:
                if current_class:
                    classes.append(current_class)
                current_class = ClassDef(
                    name=match.group(1),
                    doc=current_doc.strip()
                )
                current_doc = ""
            continue

        if not current_class:
            continue

        # 跳过注释行
        if stripped.startswith('//') or stripped.startswith('*'):
            continue

        # 只读属性: readonly name: Type;
        readonly_match = re.match(r'readonly\s+(\w+):\s*(.+);', stripped)
        if readonly_match:
            current_class.properties.append(MethodDef(
                name=readonly_match.group(1),
                signature=stripped,
                return_type=readonly_match.group(2).rstrip(';'),
                is_readonly=True
            ))
            continue

        # 普通属性: name: Type;
        prop_match = re.match(r'(\w+):\s*([^(]+);$', stripped)
        if prop_match and '(' not in stripped:
            current_class.properties.append(MethodDef(
                name=prop_match.group(1),
                signature=stripped,
                return_type=prop_match.group(2).rstrip(';')
            ))
            continue

        # getter: get name(): Type;
        getter_match = re.match(r'get\s+(\w+)\(\):\s*(.+);', stripped)
        if getter_match:
            current_class.properties.append(MethodDef(
                name=getter_match.group(1),
                signature=stripped,
                return_type=getter_match.group(2).rstrip(';'),
                is_readonly=True
            ))
            continue

        # setter: set name(value: Type);
        setter_match = re.match(r'set\s+(\w+)\((.+)\);', stripped)
        if setter_match:
            current_class.properties.append(MethodDef(
                name=setter_match.group(1),
                signature=stripped,
                params=[{"name": "value", "type": setter_match.group(2)}]
            ))
            continue

        # 方法: name(params): ReturnType;
        method_match = re.match(r'(async\s+)?(\w+)\(([^)]*)\)(?::\s*(.+))?;', stripped)
        if method_match:
            is_async = bool(method_match.group(1))
            method_name = method_match.group(2)
            params_str = method_match.group(3)
            return_type = method_match.group(4) or "void"

            # 解析参数
            params = []
            if params_str:
                # 简单解析参数
                for param in params_str.split(','):
                    param = param.strip()
                    if ':' in param:
                        pname, ptype = param.split(':', 1)
                        params.append({
                            "name": pname.strip().replace('?', ''),
                            "type": ptype.strip(),
                            "optional": '?' in pname
                        })
                    elif param:
                        params.append({"name": param, "type": "any"})

            current_class.methods.append(MethodDef(
                name=method_name,
                signature=stripped,
                return_type=return_type.rstrip(';'),
                params=params,
                is_async=is_async
            ))

    if current_class:
        classes.append(current_class)

    return classes


def parse_all_dts(dts_dir: Path) -> Dict[str, ClassDef]:
    """解析目录下所有 .d.ts 文件"""
    all_classes = {}

    for dts_file in sorted(dts_dir.glob('*.d.ts')):
        classes = parse_dts_file(dts_file)
        for cls in classes:
            all_classes[cls.name] = cls

    return all_classes


def generate_api_reference(classes: Dict[str, ClassDef], output_path: Path):
    """生成 Markdown API 参考文档"""

    content = """# Construct 3 脚本 API 参考

本文档包含 Construct 3 Runtime 的 TypeScript API 定义，可用于 JavaScript/TypeScript 脚本编程。

"""

    # 按类别分组
    core_classes = ['IRuntime', 'IInstance', 'IWorldInstance', 'ILayout', 'ILayer']
    animation_classes = ['IAnimation', 'IAnimationFrame', 'IImageInfo']
    behavior_classes = ['IBehaviorInstance', 'IBehavior_', 'IBehaviorType']
    other_classes = [k for k in classes.keys()
                     if k not in core_classes + animation_classes + behavior_classes]

    def write_class(cls: ClassDef):
        nonlocal content
        content += f"\n### {cls.name}\n"
        if cls.extends:
            content += f"继承自: `{cls.extends}`\n"
        content += "\n"

        if cls.properties:
            content += "**属性**:\n"
            for prop in cls.properties:
                readonly = " (只读)" if prop.is_readonly else ""
                content += f"- `{prop.name}: {prop.return_type}`{readonly}\n"
            content += "\n"

        if cls.methods:
            content += "**方法**:\n"
            for method in cls.methods:
                params_str = ", ".join([
                    f"{p['name']}: {p['type']}" for p in method.params
                ])
                async_prefix = "async " if method.is_async else ""
                content += f"- `{async_prefix}{method.name}({params_str}): {method.return_type}`\n"
            content += "\n"

    content += "## 核心类\n"
    for name in core_classes:
        if name in classes:
            write_class(classes[name])

    content += "\n## 动画相关\n"
    for name in animation_classes:
        if name in classes:
            write_class(classes[name])

    content += "\n## 行为相关\n"
    for name in behavior_classes:
        if name in classes:
            write_class(classes[name])

    content += "\n## 其他类\n"
    for name in sorted(other_classes):
        if name in classes:
            write_class(classes[name])

    output_path.write_text(content, encoding='utf-8')
    print(f"生成 API 参考: {output_path}")
    print(f"  - 类/接口: {len(classes)} 个")


def generate_json_reference(classes: Dict[str, ClassDef], output_path: Path):
    """生成 JSON 格式的 API 参考"""
    data = {}

    for name, cls in classes.items():
        data[name] = {
            "name": cls.name,
            "extends": cls.extends,
            "properties": [
                {
                    "name": p.name,
                    "type": p.return_type,
                    "readonly": p.is_readonly
                } for p in cls.properties
            ],
            "methods": [
                {
                    "name": m.name,
                    "signature": m.signature,
                    "params": m.params,
                    "returnType": m.return_type,
                    "async": m.is_async
                } for m in cls.methods
            ]
        }

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"生成 JSON 参考: {output_path}")


def main():
    # 默认路径
    dts_dir = Path('/Users/test/Documents/dev/github/Construct-New Project/scripts/ts-defs/runtime')

    if not dts_dir.exists():
        print(f"错误: 目录不存在 {dts_dir}")
        return

    print(f"解析 TypeScript 定义: {dts_dir}")

    classes = parse_all_dts(dts_dir)
    print(f"找到 {len(classes)} 个类/接口")

    # 输出目录
    output_dir = Path(__file__).parent.parent.parent / "source"
    output_dir.mkdir(exist_ok=True)

    generate_api_reference(classes, output_dir / "scripting-api-reference.md")
    generate_json_reference(classes, output_dir / "scripting-api-reference.json")


if __name__ == "__main__":
    main()

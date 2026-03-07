"""
HuggingFace 模型下载器

用法:
    python scripts/download_model.py Qwen/Qwen2.5-14B-Instruct
    python scripts/download_model.py Qwen/Qwen2.5-14B-Instruct --cache-dir D:/Agent/models
    python scripts/download_model.py Qwen/Qwen2.5-14B-Instruct --token hf_xxx
    python scripts/download_model.py --list-cached
"""

import argparse
import os
import sys
from pathlib import Path

# 在导入 huggingface_hub 之前设置 HF_HOME，否则缓存路径不会生效。
# 优先用 python-dotenv，不可用时自行解析 .env。
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    # 手动解析：只处理 KEY=VALUE 行，忽略注释和空行
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:   # 不覆盖已有的环境变量
            os.environ[key] = value

_load_env()


def format_size(bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"


def list_cached(cache_dir: str | None):
    """列出本地已缓存的模型"""
    from huggingface_hub import scan_cache_dir
    cache = scan_cache_dir(cache_dir)
    if not cache.repos:
        print("本地缓存中没有任何模型。")
        return
    print(f"\n{'模型':50s}  {'大小':>10s}  {'修订版本'}")
    print("-" * 80)
    total = 0
    for repo in sorted(cache.repos, key=lambda r: r.repo_id):
        size = sum(r.size_on_disk for r in repo.revisions)
        total += size
        rev_count = len(repo.revisions)
        print(f"{repo.repo_id:50s}  {format_size(size):>10s}  {rev_count} 个版本")
    print("-" * 80)
    print(f"{'合计':50s}  {format_size(total):>10s}")


def get_model_info(model_id: str, token: str | None):
    """获取模型文件列表及总大小"""
    from huggingface_hub import list_repo_tree, repo_info
    try:
        info = repo_info(model_id, token=token)
        files = list(list_repo_tree(model_id, token=token, recursive=True))
        total = sum(
            f.size for f in files
            if hasattr(f, "size") and f.size is not None
        )
        return total, len(files), info.last_modified
    except Exception as e:
        return None, None, None


def download(model_id: str, cache_dir: str | None, token: str | None):
    from huggingface_hub import snapshot_download
    import time

    print(f"\n模型:    {model_id}")
    if cache_dir:
        print(f"缓存目录: {cache_dir}")

    # 获取文件信息
    print("查询文件信息...", end=" ", flush=True)
    total_bytes, file_count, last_modified = get_model_info(model_id, token)
    if total_bytes:
        print(f"{file_count} 个文件，约 {format_size(total_bytes)}")
    else:
        print("（无法获取大小，继续下载）")

    if last_modified:
        print(f"最后更新: {last_modified.strftime('%Y-%m-%d')}")

    # 检查是否已缓存
    try:
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(model_id, "config.json", cache_dir=cache_dir)
        if cached:
            print(f"\n已在本地缓存中找到该模型，跳过下载。")
            print(f"路径: {Path(cached).parent}")
            return
    except Exception:
        pass

    print("\n开始下载...\n")
    t0 = time.time()

    try:
        local_path = snapshot_download(
            repo_id=model_id,
            cache_dir=cache_dir,
            token=token,
            ignore_patterns=["*.pt", "original/*"],  # 跳过 PyTorch bin，只下载 safetensors
        )
    except KeyboardInterrupt:
        print("\n\n下载已中断。下次运行时会从断点续传。")
        sys.exit(1)
    except Exception as e:
        print(f"\n下载失败: {e}")
        sys.exit(1)

    elapsed = time.time() - t0
    mins, secs = divmod(int(elapsed), 60)

    print(f"\n下载完成！耗时 {mins}m {secs}s")
    print(f"本地路径: {local_path}")

    # 显示磁盘占用
    path = Path(local_path)
    disk_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    print(f"磁盘占用: {format_size(disk_size)}")


def main():
    parser = argparse.ArgumentParser(
        description="HuggingFace 模型下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/download_model.py Qwen/Qwen2.5-14B-Instruct
  python scripts/download_model.py Qwen/Qwen2.5-7B-Instruct --cache-dir D:/Agent/models
  python scripts/download_model.py --list-cached
  python scripts/download_model.py --list-cached --cache-dir D:/Agent/models
        """
    )
    parser.add_argument("model_id", nargs="?", help="HuggingFace 模型 ID，如 Qwen/Qwen2.5-14B-Instruct")
    parser.add_argument("--cache-dir", metavar="DIR", help="本地缓存目录（默认: ~/.cache/huggingface）")
    parser.add_argument("--token", metavar="TOKEN", help="HuggingFace Access Token（私有/受限模型需要）")
    parser.add_argument("--list-cached", action="store_true", help="列出本地已缓存的模型")
    args = parser.parse_args()

    if args.list_cached:
        list_cached(args.cache_dir)
        return

    if not args.model_id:
        parser.print_help()
        sys.exit(1)

    # 从环境变量读取 token
    token = args.token or os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")

    download(args.model_id, args.cache_dir, token)


if __name__ == "__main__":
    main()

"""
WorkTracker 本地打包发布脚本
一键完成：清理旧文件 → PyInstaller 打包 → 组装 Release 目录 → 生成 ZIP

用法:
  python build_release.py              # 打包当前版本
  python build_release.py --version 1.0.0  # 指定版本号
"""
import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
RELEASE_DIR = os.path.join(BASE_DIR, "release")
BUILD_DIR = os.path.join(BASE_DIR, "build")


def run(cmd, check=True):
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with code {result.returncode}")
        sys.exit(1)
    return result.returncode


def clean():
    """清理旧构建"""
    print("\n=== 清理旧构建 ===")
    for d in [DIST_DIR, BUILD_DIR, RELEASE_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  已删除: {d}")
    os.makedirs(RELEASE_DIR)
    print(f"  已创建: {RELEASE_DIR}")


def build_exe():
    """PyInstaller 打包"""
    print("\n=== PyInstaller 打包 ===")
    # 确认 pyinstaller 已安装
    run("pip install pyinstaller -q", check=True)
    run("pyinstaller worktracker.spec --clean --noconfirm")
    
    exe_path = os.path.join(DIST_DIR, "WorkTracker.exe")
    if not os.path.exists(exe_path):
        print("ERROR: WorkTracker.exe 未生成！")
        sys.exit(1)
    
    size_mb = os.path.getsize(exe_path) / 1024 / 1024
    print(f"  EXE 大小: {size_mb:.1f}MB")


def assemble_release():
    """组装 Release 目录"""
    print("\n=== 组装 Release ===")
    
    # 1. EXE
    shutil.copy(os.path.join(DIST_DIR, "WorkTracker.exe"), RELEASE_DIR)
    print("  + WorkTracker.exe")
    
    # 2. 便捷脚本
    for f in ["设置开机自启.bat", "服务管理.bat"]:
        src = os.path.join(BASE_DIR, f)
        if os.path.exists(src):
            shutil.copy(src, RELEASE_DIR)
            print(f"  + {f}")
    
    # 3. 介绍页
    html_src = os.path.join(BASE_DIR, "worktracker-trae-contest", "WorkTracker-standalone.html")
    if os.path.exists(html_src):
        shutil.copy(html_src, os.path.join(RELEASE_DIR, "WorkTracker-介绍页.html"))
        print("  + WorkTracker-介绍页.html")
    
    # 4. README
    shutil.copy(os.path.join(BASE_DIR, "README.md"), RELEASE_DIR)
    print("  + README.md")
    
    # 5. 版本信息
    version = get_version()
    info_path = os.path.join(RELEASE_DIR, "版本信息.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(f"WorkTracker v{version}\n")
        f.write(f"构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"赛道: 学习工作\n")
        f.write(f"TRAE AI 创造力大赛参赛作品\n")
    print("  + 版本信息.txt")


def get_version():
    """获取版本号"""
    if "--version" in sys.argv:
        idx = sys.argv.index("--version")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return datetime.now().strftime("%Y%m%d")


def make_zip():
    """生成 ZIP 包"""
    version = get_version()
    zip_name = f"WorkTracker-v{version}.zip"
    zip_path = os.path.join(BASE_DIR, zip_name)
    
    print(f"\n=== 生成 ZIP: {zip_name} ===")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(RELEASE_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, RELEASE_DIR)
                zf.write(file_path, arcname)
                print(f"  + {arcname}")
    
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"\n  ZIP 大小: {size_mb:.1f}MB")
    print(f"  路径: {zip_path}")


def main():
    print("=" * 50)
    print("  WorkTracker Release Builder")
    print("=" * 50)
    
    clean()
    build_exe()
    assemble_release()
    make_zip()
    
    version = get_version()
    print(f"\n{'=' * 50}")
    print(f"  构建完成! WorkTracker v{version}")
    print(f"  ZIP: WorkTracker-v{version}.zip")
    print(f"  Release 目录: release/")
    print(f"{'=' * 50}")
    print(f"\n下一步:")
    print(f"  1. 上传 ZIP 到 GitHub Release")
    print(f"  2. 或直接分发 release/WorkTracker.exe")
    print(f"  3. 参赛帖附带 WorkTracker-介绍页.html")


if __name__ == "__main__":
    main()

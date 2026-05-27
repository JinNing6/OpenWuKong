# -*- coding: utf-8 -*-
"""
python -m openwukong 入口

支持命令:
    python -m openwukong                    # 启动守护进程
    python -m openwukong --gui              # 启动 GUI 控制面板
    python -m openwukong --mascot           # 启动悟空桌面宠物
    python -m openwukong --target Code.exe  # 指定目标进程
    python -m openwukong --help             # 查看帮助
"""

import sys


def main():
    # 检查是否请求 GUI 模式
    if "--gui" in sys.argv:
        sys.argv.remove("--gui")
        try:
            from openwukong.ui.dashboard import main as gui_main
            gui_main()
        except ImportError:
            print("❌ GUI 依赖未安装。请运行: pip install customtkinter>=5.2.0")
            print("   或: pip install -e '.[gui]'")
            sys.exit(1)

    # 检查是否请求桌面宠物模式
    elif "--mascot" in sys.argv:
        sys.argv.remove("--mascot")
        try:
            from openwukong.ui.wukong_mascot import run_mascot
            run_mascot()
        except ImportError as e:
            print(f"❌ 桌面宠物依赖未安装: {e}")
            print("   建议安装: pip install Pillow>=9.0")
            sys.exit(1)

    else:
        from openwukong.daemon.daemon import main as daemon_main
        daemon_main()


if __name__ == "__main__":
    main()

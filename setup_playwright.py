#!/usr/bin/env python3
"""
Playwright 浏览器安装脚本
运行此脚本来下载 Chromium 浏览器
"""

import subprocess
import sys
import os

def install_playwright_browsers():
    """安装 Playwright 所需的浏览器"""
    print("Installing Playwright browsers...")
    
    try:
        # 安装 Chromium
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error installing browsers: {result.stderr}")
            return False
        
        print("Playwright browsers installed successfully!")
        
        # 安装系统依赖（仅在 Linux 上需要）
        if os.name == 'posix' and sys.platform != 'darwin':
            print("Installing system dependencies for Linux...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Warning: Could not install system dependencies: {result.stderr}")
                print("You may need to run: playwright install-deps chromium")
        
        return True
        
    except Exception as e:
        print(f"Failed to install Playwright browsers: {e}")
        return False

if __name__ == "__main__":
    if install_playwright_browsers():
        print("\n✅ Setup completed successfully!")
        print("You can now run the application.")
    else:
        print("\n❌ Setup failed!")
        print("Please install Playwright browsers manually:")
        print("  python -m playwright install chromium")
        sys.exit(1)
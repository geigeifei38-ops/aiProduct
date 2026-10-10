#!/bin/bash
# 周报整理助手 · 本地数据代理启动器（双击运行）
cd "$(dirname "$0")"
echo "正在启动 周报整理助手·本地数据代理 ..."
if command -v python3 >/dev/null 2>&1; then
  python3 "$(dirname "$0")/本地数据代理.py"
else
  echo "未检测到 python3，请先安装（macOS：xcode-select --install）"
fi
echo ""
echo "代理已退出。按任意键关闭窗口..."
read -n 1 -s

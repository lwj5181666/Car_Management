@echo off
chcp 936 >nul
cd /d "%~dp0"
echo 正在安装依赖...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
echo 正在打包（onedir：免解包、秒开、不写临时目录）...
python -m PyInstaller --noconfirm --onedir --windowed --name 车辆管理系统 --icon app.ico --manifest app.manifest --contents-directory 主程序依赖 --collect-all rapidocr_onnxruntime 车辆管理系统.py
python -m PyInstaller --noconfirm --onedir --windowed --name 车辆运货统计表 --icon app.ico --manifest app.manifest --contents-directory 统计表依赖 车辆运货统计表.py
echo.
echo 打包完成。把下面四项复制到上一级目录（和数据、文档放一起）：
echo   dist\车辆管理系统\车辆管理系统.exe
echo   dist\车辆管理系统\主程序依赖\
echo   dist\车辆运货统计表\车辆运货统计表.exe
echo   dist\车辆运货统计表\统计表依赖\
pause

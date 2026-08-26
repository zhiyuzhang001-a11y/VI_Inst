# VI_Inst 测量与实时画图

本项目用于 Keithley 6221、2182A、2400、磁场控制器和角度转台的测量。主要运行环境是 Windows 10/11。实时图由独立的轻量 Tk 窗口显示；静态图直接生成 SVG，不需要 Matplotlib。

> 仪器输出可能损坏样品或设备。第一次使用、换电脑、换接线或换样品后，必须先核对电流、compliance、量程、GPIB 地址、COM 端口和磁场模式。启动器的确认框不能代替人工检查。

## 1. Windows 首次安装

先安装以下系统软件：

1. 安装 [64 位 Python for Windows](https://www.python.org/downloads/windows/)，建议 Python 3.13，最低版本 3.11。
2. 安装 [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)。它为 GPIB、串口、USB 和 Ethernet/LXI 仪器提供 VISA 通信。
3. 如果使用 NI 的 GPIB 控制器，再安装与 Windows 版本兼容的 [NI-488.2](https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html)。
4. 连接仪器，并先在 NI MAX 中确认能够看到设备和对应地址。

然后解压项目，双击 `setup_windows.bat`。它只会在项目目录创建独立的 `.venv`，并安装：

- NumPy：测量数据和数组计算
- PyVISA：通过系统 VISA 驱动连接仪器
- pySerial：连接磁场控制器和角度转台

Matplotlib、Pandas、SciPy 和 Jupyter 都不是运行依赖。安装结束会自动执行安全环境检查，不会打开仪器或发送测量命令。

以后双击 `run_windows.bat` 打开统一启动器。建议先运行 `Environment check`，再用 `Live plot simulation` 检查实时窗口。

## 2. 从 iCloud 项目运行

Mac 上可以继续在 iCloud 中修改源代码，但 Windows 测量时不建议直接从 iCloud 同步目录运行。同步、占位文件和后台扫描可能增加延迟，也可能在测量过程中占用 CSV 文件。

在 Windows 的 iCloud 项目文件夹中双击 `install_local_copy.bat`，程序会被复制到：

```text
%LOCALAPPDATA%\VI_Inst_App
```

它只复制发布清单中的代码和说明，不复制 CSV、图片、声音、历史日期目录或 `config.local.toml`。随后会在本地副本中运行安装程序。以后从本地副本运行 `run_windows.bat`。

## 3. 仪器地址和数据目录

默认配置位于 `config.toml`：

```toml
[visa]
keithley_6221 = "GPIB0::12::INSTR"
keithley_2182a = "GPIB0::7::INSTR"
keithley_2400 = "GPIB0::21::INSTR"

[serial]
magnet = "COM3"
rotator = "COM4"
```

启动器中的 `Edit local configuration` 会建立并打开 `config.local.toml`。每台电脑只修改这个本地文件；它被 Git 和发布包排除，不会覆盖公共默认值。

测量数据默认保存到：

```text
%USERPROFILE%\VI_Inst_Data
```

也可以在 `config.local.toml` 中指定另一个本地目录：

```toml
[data]
output_dir = "D:\\MeasurementData"
```

临时测试还可以设置环境变量 `VI_INST_DATA_DIR`。程序会自动建立 `iv`、`hall`、`smr`、`pdel` 等子目录。数据目录与代码目录分离，因此构建发布包或上传代码时不会包含个人测量数据。

## 4. 画图实现

- 实时图：`live_plot_process.py` 使用 Tk Canvas，在独立、低优先级进程中刷新。测量进程只写入共享环形缓冲区；拖动或遮挡窗口不会停止后台数据记录。
- 静态图：`static_plot.py` 用 Python 标准库输出 SVG，可在浏览器中打开和无损缩放。
- 保留点数：实时窗口默认最多显示最近 1000 点，避免老电脑随测量时间增长而越来越卡。

SVG 是矢量文件，适合查看、复制到 Word/PowerPoint 和后期排版。如需 PNG，可用浏览器、Inkscape 或 Office 另存/导出，不需要在测量电脑上安装 Matplotlib。

## 5. 主要入口

- `launcher.py`：统一图形启动器
- `keithley_iv.py`：6221 + 2182A 实时测量；`--simulate` 为无仪器模拟
- `Hall_plot.py`：6221 + 2182A + 磁场 Hall 测量
- `2400_Hall_plot.py` / `keithley_2400.py`：2400 Hall 测量
- `SMR_plot.py`：SMR 角度扫描
- `switch_plot.py`：PDEL 监测和 SVG 静态图
- `sequence_pdel_monitor.py`：PDEL 序列
- `keithley_6221_pdel.py`：PDEL sweep pulse
- `address.py`：只列出 VISA 资源，不打开仪器
- `check_environment.py`：完整但无控制命令的环境检查
- `set_H.py`：直接设磁场，运行后必须输入目标确认文字才会连接仪器

测量参数仍保留在原测量脚本中，没有集中迁移或改写。跨电脑配置只统一了仪器地址、COM 端口和输出目录。

## 6. 常见问题

### `No module named ...`

不要直接调用系统 Python。重新运行 `setup_windows.bat`，然后通过 `run_windows.bat` 启动。

### 找不到 VISA backend / DLL

确认已经安装 NI-VISA，Python 与 VISA 都使用 64 位，并重启 Windows。可以运行 `check_environment.py` 查看 PyVISA 实际加载的 backend。

### VISA 正常但看不到 GPIB 仪器

如果是 NI GPIB 控制器，确认安装 NI-488.2；在 NI MAX 中检查控制器、线缆、仪器 GPIB 地址，再运行 `address.py`。NI-VISA 提供 VISA 层，NI-488.2 提供 NI GPIB 控制器驱动，两者用途不同。

### COM3/COM4 不一致

在 Windows 设备管理器中查看实际端口，然后修改 `config.local.toml`。不要为了匹配代码而随意更改设备端口。

### 实时窗口仍然不流畅

先运行模拟模式排除仪器等待。如果模拟也卡，关闭远程桌面动画、录屏和高负载应用，并确认正在运行本地副本。窗口交互暂停时，测量和 CSV 记录应继续；窗口恢复后显示最新缓冲数据。

### SVG 中文或字体外观不同

SVG 使用系统字体，换电脑后字形可能略有不同，但数据、坐标和清晰度不受影响。发布前如需固定版式，可在排版电脑上将 SVG 转成 PDF。

## 7. 建立无数据发布包

在 Mac 或 Windows 中运行：

```text
python build_release.py
```

输出为 `dist/VI_Inst-Windows.zip`。构建器采用明确的文件白名单，并拒绝 CSV、PNG、JPG、WAV、PYC 和 `config.local.toml`。发布前仍应查看压缩包文件列表，确认没有临时代码或私人配置。

## 8. Win10 与 Win11

项目代码本身同时适用于 Windows 10 和 Windows 11。真正需要逐台确认的是 Python、NI-VISA、NI-488.2 和 GPIB/串口硬件驱动是否支持该电脑的 Windows 版本与位数。下载 NI 驱动时应以 NI 页面当时列出的 Supported OS 为准。

# VI_Inst 测量程序

这是一个用于电输运测量的 Windows 程序，支持 Keithley 6221、2182A、2400、磁场控制器和角度转台。

不需要会编程。按下面步骤安装，然后双击启动即可。

## 一、安装前准备

程序支持 Windows 10 和 Windows 11。

请先安装：

1. [Python 3.13（Windows 64 位）](https://www.python.org/downloads/windows/)
2. [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)
3. 如果使用 NI 的 GPIB 控制器，还要安装 [NI-488.2](https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html)

安装完成后，建议重启电脑。

## 二、下载程序

1. 打开本项目的 [Releases 下载页面](https://github.com/zhiyuzhang001-a11y/VI_Inst/releases/latest)。
2. 下载 `VI_Inst-Windows.zip`。
3. 解压到一个普通文件夹，例如：

```text
C:\Users\你的用户名\Documents\VI_Inst
```

不要直接在压缩包里运行程序。

## 三、第一次安装

进入解压后的文件夹，双击：

```text
setup_windows.bat
```

程序会自动安装所需组件。看到下面的提示表示安装完成：

```text
You can now double-click run_windows.bat.
```

安装只需执行一次。

## 四、设置仪器地址

双击：

```text
run_windows.bat
```

在启动窗口中点击 `Edit local configuration`，检查以下设置：

```toml
[visa]
keithley_6221 = "GPIB0::12::INSTR"
keithley_2182a = "GPIB0::7::INSTR"
keithley_2400 = "GPIB0::21::INSTR"

[serial]
magnet = "COM3"
rotator = "COM4"
```

- GPIB 地址可以在 NI MAX 中查看。
- COM 端口可以在 Windows“设备管理器”中查看。
- 如果电脑上的地址不同，直接修改并保存这个文件。

## 五、开始使用

建议按以下顺序操作：

1. 点击 `Environment check`，确认安装和仪器连接状态。
2. 点击 `Live plot simulation`，确认实时画图窗口工作正常。
3. 检查接线、电流、compliance、量程和磁场模式。
4. 点击需要的测量项目。

每项测量都会在独立窗口中运行。实时画图窗口被拖动或遮挡时，后台数据记录仍会继续。

## 数据保存在哪里

所有新测量数据默认保存在：

```text
C:\Users\你的用户名\VI_Inst_Data
```

数据按照 `iv`、`hall`、`smr`、`pdel` 等测量类型分类。

静态图保存为 SVG，可以直接用浏览器打开，也可以插入 Word 或 PowerPoint。SVG 放大后仍然清晰。

## 启动器中的项目

- `Environment check`：检查 Python、驱动、GPIB 和 COM 端口
- `Live plot simulation`：不连接仪器，只测试实时画图
- `Keithley 6221 + 2182 monitor`：6221 与 2182A 测量
- `Hall: 6221 + 2182 + magnet`：Hall 测量
- `Hall: Keithley 2400 + magnet`：2400 Hall 测量
- `SMR angle scan`：角度扫描
- `PDEL monitor`：PDEL 监测
- `PDEL sequence`：PDEL 序列测量
- `PDEL sweep pulse`：PDEL sweep pulse 测量

## 常见问题

### 双击安装脚本后提示找不到 Python

重新安装 64 位 Python 3.13，然后重启电脑，再运行 `setup_windows.bat`。

### Environment check 提示找不到 VISA

确认已经安装 NI-VISA，并重启电脑。Python 和 NI-VISA 都应使用 64 位版本。

### 找不到 GPIB 仪器

先在 NI MAX 中检查仪器。如果使用 NI GPIB 控制器，还要确认已经安装 NI-488.2。

### 找不到 COM3 或 COM4

打开 Windows 设备管理器，查看设备实际使用的 COM 端口，然后点击 `Edit local configuration` 修改。

### 如何重新安装

再次运行 `setup_windows.bat` 即可。它不会删除测量数据。

## 安全提醒

测量程序会控制真实仪器。开始测量前必须人工确认：

- 仪器和样品接线正确
- 输出电流和 compliance 合适
- GPIB 地址与 COM 端口正确
- 磁场控制器处于正确模式
- 样品能够承受设定的电流、电压和磁场

如果不确定，请先使用 `Live plot simulation`，不要连接样品运行真实测量。

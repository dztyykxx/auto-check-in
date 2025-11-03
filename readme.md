# 西交自动打卡脚本 (auto\_check\_in.py) 部署指南

本项目使用 Python、Playwright 和 Requests 库，实现自动模拟登录、获取Token，并执行每日锻炼签到与签退操作。

本文档适用于在 Linux 环境（如树莓派 Raspberry Pi 或 Debian/Ubuntu 桌面系统）上部署。

懒得每天打卡了，就写了这个，目前这样子打了一周卡，挺稳定的。
自己是有个闲置的树莓派，就部署在这上面了，放在宿舍里每天帮忙打卡。

-----

## 步骤一：环境配置

在开始之前，请确保您的系统已更新，并安装 Python 3 环境。

```bash
sudo apt update
sudo apt upgrade -y
```

### 1\. 安装 venv（虚拟环境支持）

为避免系统环境污染和 `externally-managed-environment` 错误，我们必须使用 Python 虚拟环境。

```bash
# 安装 venv 工具包（请根据您系统的 Python 版本调整，例如 python3.12-venv）
sudo apt install python3.12-venv
```

### 2\. 创建并激活虚拟环境

我们将在用户主目录（`~` 或 `/home/dztyykxx/`）下创建虚拟环境。

```bash
# 1. 进入主目录
cd /home/dztyykxx/

# 2. 创建名为 venv_autocheckin 的虚拟环境
python3 -m venv venv_autocheckin

# 3. 激活虚拟环境
source /home/dztyykxx/venv_autocheckin/bin/activate
```

*激活后，您的终端提示符前应出现 `(venv_autocheckin)` 字样。*

### 3\. 安装依赖包

在**已激活**的虚拟环境下，安装脚本所需的库。

```bash
# (venv_autocheckin) $
pip install playwright requests
```

### 4\. 安装浏览器驱动

Playwright 需要一个浏览器内核来执行模拟登录。

```bash
# (venv_autocheckin) $
playwright install chromium
```

-----

## 步骤二：脚本配置与测试

### 1\. 上传与配置脚本

1.  将 `auto_check_in.py` 脚本上传到您的主目录 `/home/dztyykxx/`。
2.  编辑脚本文件，**必须**填写顶部的 `USERNAME` 和 `PASSWORD` 变量。

<!-- end list -->

```python
# ==============================================================================
# 1. 配置信息 (请根据实际情况修改)
# ==============================================================================
# 你的学号和密码
USERNAME = "这里填你的学号"
PASSWORD = "这里填你的密码"
...
```

### 2\. 手动测试脚本

在设置定时任务前，先手动运行一次以确保一切正常。

```bash
# 1. 确保虚拟环境已激活
# (如果未激活，请先运行: source /home/dztyykxx/venv_autocheckin/bin/activate)

# 2. 运行脚本
python3 /home/dztyykxx/auto_check_in.py
```

观察终端输出。如果脚本成功登录并执行打卡逻辑（如签到），且在 `/home/dztyykxx/` 目录下生成了 `check_in_log.json` 日志文件，则表示配置成功。

-----

## 步骤三：设置 Cron 定时任务

`cron` 用于在固定时间自动执行脚本。

### 1\. 编辑定时任务列表

```bash
crontab -e
```

*(如果首次运行，请选择一个编辑器，如 `nano`)*

### 2\. 添加任务行

在打开的文件的最底部，添加以下**一行**：

```bash
0 9,12 * * * /home/dztyykxx/venv_autocheckin/bin/python3 /home/dztyykxx/auto_check_in.py >> /home/dztyykxx/check_in_cron.log 2>&1
```

### 3\. 理解任务行

  * `0 9,12 * * *`：时间设置。表示在每天的 **9点0分** 和 **12点0分** 执行。两次执行时间至少间隔2小时（间隔1小时才能打卡成功），担心失败就多设置几个时间点。
  比如 `0 9,12,14,18 * * *`就是9点、12点、14点和18点都执行一次。
  * `/home/dztyykxx/venv_autocheckin/bin/python3`：**（关键）** 使用虚拟环境中的 Python 解释器，确保能加载到 `playwright` 和 `requests` 库。
  * `/home/dztyykxx/auto_check_in.py`：要执行的脚本文件的绝对路径。
  * `>> /home/dztyykxx/check_in_cron.log 2>&1`：将所有输出（包括错误）追加到日志文件 `check_in_cron.log` 中，便于排查问题。

### 4\. 保存退出

  * 在 `nano` 编辑器中：按 `Ctrl + X`，然后按 `Y`，最后按 `Enter` 键保存。

-----

## 附录：常用命令

### 查看已设置的定时任务

```bash
crontab -l
```

### 查看定时任务执行日志

如果脚本没有按预期运行，请检查此日志文件。

```bash
cat /home/dztyykxx/check_in_cron.log
```

### 查看打卡状态日志

此文件记录了脚本签到和签退的详细时间（JSON格式）。

```bash
cat /home/dztyykxx/check_in_log.json
```
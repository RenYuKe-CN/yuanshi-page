# OriginX 轻量版

OriginX 是一套运行在单台服务器上的 Web3 风控与 IP 环境管理系统。当前仓库只保留线上实际使用的轻量版：Python 标准库 + SQLite，无需 Node.js、Docker、PostgreSQL 或 Prisma。

## 功能

- 用户注册、登录、设备绑定、邮箱验证、密码恢复
- 总管理员、授权白名单、普通用户与会员权限控制
- IP 风险检测、重复/相似 IP 检测、历史筛选、分页与 CSV 导出
- 钱包与交互地址检测入口，支持 EVM、Solana、TRON、BTC 等地址格式
- 可在后台配置 IP 风控、钱包数据、邮件服务、收款地址、品牌 Logo 与交易所目录
- CEX / DEX 交易所管理、模糊候选搜索、图标上传与排序
- 站内公告、站内信、邮件公告与未读提醒
- BEP20 USDT / USDC 订单核验与会员自动开通
- 市场监控中心

## 会员套餐与查询额度

查询次数按 IP、设备、钱包三个类别独立统计。正常登录和设备绑定不会扣减设备查询额度。

| 套餐 | 月费 | IP 查询 | 设备查询 | 钱包查询 | 其他权益 |
| --- | ---: | ---: | ---: | ---: | --- |
| 星舰会员 | $12 | 10 次/月 | 10 次/月 | 5 次/月 | 全部 CEX 与 DEX，适合个人轻度环境管理 |
| 旗舰 PRO | $39.9 | 60 次/月 | 60 次/月 | 60 次/月 | 市场监控中心、全部 CEX 与 DEX |
| 旗舰 MAX | $128.88 | 无限 | 无限 | 无限 | 无限历史、钱包检测全部功能、市场监控中心 |

| 周期 | 星舰会员 | 旗舰 PRO | 旗舰 MAX |
| --- | ---: | ---: | ---: |
| 1 个月 | $12 | $39.9 | $128.88 |
| 3 个月 | $33 | $109 | $347.98 |
| 6 个月 | $60 | $199 | $541.30 |
| 年会员 | $96 | $319 | $1031.04 |

授权白名单拥有与星舰会员相同的查询额度与查询权限，但不能管理用户、设置、日志、交易所目录或全站数据。

## 项目结构

```text
.
├── local_app.py                 # 轻量版主程序与前端页面
├── data/exchanges.json          # 初始 CEX / DEX 名单
├── public/brand/                # 默认 Logo、背景、交易所图标和前端脚本
├── scripts/server/manage.sh     # 服务器安装、更新、启停与日志命令
├── scripts/server/deploy.sh     # 从本机上传并部署到服务器
├── tests/test_local_accounts.py # Python 回归测试
├── 本地启动.command              # macOS 本地启动
├── 本地停止.command              # macOS 本地停止
└── README.md
```

运行数据保存在 `local_data/`，其中包括 SQLite 数据库、上传 Logo、配置和日志。该目录已被 Git 忽略，更新时不会覆盖。

## 本地运行

需要 Python 3。macOS 可以双击 `本地启动.command`，或执行：

```bash
python3 local_app.py
```

默认打开：

```text
http://127.0.0.1:3000/login
```

可通过环境变量调整监听地址和端口：

```bash
HOST=127.0.0.1 PORT=3003 python3 local_app.py
```

首次启动会在 `local_data/admin.txt` 生成总管理员账号信息。登录后请立刻修改密码。

## 服务器首次安装

适用于 Ubuntu 22.04 / 24.04。请先在安全组放行实际使用端口，默认是 TCP `3000`。

从本机上传并安装：

```bash
SERVER_HOST=你的服务器IP SSH_KEY=你的私钥路径 bash scripts/server/deploy.sh
```

也可以将源码放到服务器后，在项目根目录执行：

```bash
sudo bash scripts/server/manage.sh install
```

安装脚本会安装 `python3`、`python3-pil`、`rsync` 和 `curl`，创建 systemd 服务 `yuanshi-jinshouzhi`，并保护 `local_data/` 中的运行数据。

## 服务器更新与管理

服务器项目目录默认为 `/opt/yuanshi-jinshouzhi`。

如果服务器目录是 Git 克隆的仓库，更新最新版：

```bash
cd /opt/yuanshi-jinshouzhi
git pull origin main
sudo bash scripts/server/manage.sh update
```

`manage.sh update` 负责安装依赖、同步当前目录代码并重启服务；它不会自行执行 `git pull`。

常用命令：

```bash
cd /opt/yuanshi-jinshouzhi
sudo bash scripts/server/manage.sh start
sudo bash scripts/server/manage.sh stop
sudo bash scripts/server/manage.sh restart
bash scripts/server/manage.sh status
bash scripts/server/manage.sh logs
```

后台上传网站 Logo、交易所图标时需要 Pillow。安装/更新脚本会自动安装；如需手动检查：

```bash
python3 -c "from PIL import Image; print(Image.__version__)"
```

## 数据备份

备份轻量版数据库和后台配置：

```bash
sudo tar -czf originx-local-data-backup.tgz /opt/yuanshi-jinshouzhi/local_data
```

恢复后重启服务：

```bash
sudo bash /opt/yuanshi-jinshouzhi/scripts/server/manage.sh restart
```

## 测试

```bash
PYTHONPYCACHEPREFIX=/tmp/originx-pycache python3 -m py_compile local_app.py
PYTHONPYCACHEPREFIX=/tmp/originx-pycache python3 -m unittest tests/test_local_accounts.py
```

## 安全提示

- 不要提交 `local_data/`、`.env`、私钥、服务器日志或数据库备份。
- 生产环境请设置强管理员密码，并妥善保存恢复码。
- 支付自动核验上线前请使用小额转账测试网络、Token、收款地址与确认数。
- 真实 IP 与钱包风险数据依赖已配置的数据源；未接入的数据不会伪造为实时结果。

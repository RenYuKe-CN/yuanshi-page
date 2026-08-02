# 原石金手指 Gold Finger

原石金手指是一套 Web3 风控与 IP 风险检测管理系统，用于团队管理交易所环境、检测 IP 重复/相似风险、记录历史查询、管理会员权限，并提供轻量级市场监控辅助信息。

当前仓库包含两套运行方式：

- `local_app.py`：轻量版，Python + SQLite，适合快速部署到单台云服务器，最简单、最省事。
- `Next.js` 正式版：Next.js + TypeScript + Prisma + PostgreSQL，适合后续商业化扩展。

如果你只是想让用户能打开网站、注册登录、开通会员并使用，优先使用本文档里的“轻量版一键部署”。

---

## 核心功能

### 账号与权限

- 用户注册、登录、退出
- 主流邮箱注册限制
- 邮箱验证码注册
- 密码加密保存
- 总管理员、备用管理员、普通用户
- 普通用户默认只能浏览，未开通会员不能查询
- 星舰会员：每月 10 次查询额度
- 旗舰 PRO：每月续费，会员期内无限查询
- 1 账号绑定 1 设备基础控制
- 操作日志记录

### IP 风险检测

- IPv4 严格校验
- 自动拆分 A/B/C/D 四段
- 精确重复检测
- 同一历史记录逐段相似度比较
- 相似度：0%、25%、50%、75%、100%
- 查询后自动入库
- 历史记录分页、筛选、导出
- 查询用户显示用户名与邮箱

### 钱包 / 交互地址检测

- 支持 EVM 地址格式校验
- 钱包地址检测
- 交互地址检测
- 风险评分展示
- 记录检测用户

### 会员与支付

- 套餐展示
- 选择套餐生成订单
- 支持 USDT / USDC
- 网络：BEP20 / BSC
- 收款地址：

```text
0x04bCA584834489C26d6474701400c88D954B7782
```

- 填写 Transaction Hash 后自动链上验证
- 验证 Token、金额、收款地址、交易状态、Hash 重复
- 验证成功自动开通会员

### 市场监控中心

- BTC / ETH / SOL / BNB / OKB 价格展示
- 24H 涨跌幅
- 迷你趋势线
- 成交量、RSI 状态、市场评分

> 行情、趋势判断与技术指标仅作信息参考，不构成投资建议、交易建议或投资依据。

---

## 权限说明

| 功能 | 普通用户 | 星舰会员 | 旗舰 PRO | 备用管理员 | 总管理员 |
| --- | --- | --- | --- | --- | --- |
| 登录/浏览 | ✅ | ✅ | ✅ | ✅ | ✅ |
| IP 风险检测 | ❌ | ✅ 10 次/月 | ✅ 无限 | ✅ 无限 | ✅ 无限 |
| 钱包/交互地址检测 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 查询历史 | ✅ 自己数据 | ✅ 自己数据 | ✅ 自己数据 | ✅ 全部 | ✅ 全部 |
| 用户管理 | ❌ | ❌ | ❌ | ✅ 普通用户 | ✅ 全部 |
| 会员数据 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 系统设置 | ❌ | ❌ | ❌ | ❌ | ✅ |

公开注册只能得到普通用户权限，不会获得管理员权限。

---

## 目录结构

```text
.
├── local_app.py                    # 轻量版主程序
├── deploy-cloud.sh                 # 云服务器一键安装入口
├── scripts/server/manage.sh        # 服务器安装/更新/启动/停止/日志
├── scripts/server/deploy.sh        # 本机上传并部署到服务器
├── data/exchanges.json             # CEX / DEX 交易所名单
├── public/brand/                   # Logo、背景图、交易所图标
├── app/                            # Next.js 页面
├── components/                     # Next.js 组件
├── lib/                            # Next.js 后端工具
├── prisma/                         # Prisma schema 与迁移
├── tests/                          # 测试
└── docs/TEST_REPORT.md             # 测试报告
```

---

## 一、最简单云服务器部署（推荐）

适合 Ubuntu 22.04 / 24.04 云服务器。

### 1. 在云服务器安全组放行端口

云服务器控制台安全组放行：

```text
TCP 3000
来源 0.0.0.0/0
```

### 2. 从本机一键上传并部署

在本机项目根目录执行：

```bash
SERVER_HOST=你的服务器IP SSH_KEY=你的私钥路径 bash scripts/server/deploy.sh
```

示例：

```bash
SERVER_HOST=124.156.138.166 SSH_KEY=~/Downloads/yuanshi.pem bash scripts/server/deploy.sh
```

部署完成后打开：

```text
http://你的服务器IP:3000/login
```

### 3. 首次管理员账号

首次部署时，系统会在服务器生成管理员账号密码，并在部署输出里显示。服务器上也可查看：

```bash
sudo cat /opt/yuanshi-jinshouzhi/local_data/admin.txt
```

请登录后立刻修改密码，并保存恢复码。

---

## 二、服务器上一键管理

如果代码已经在服务器项目目录中，可以直接使用：

```bash
sudo bash scripts/server/manage.sh install
```

### 安装

```bash
sudo bash scripts/server/manage.sh install
```

### 更新

```bash
sudo bash scripts/server/manage.sh update
```

### 启动

```bash
sudo bash scripts/server/manage.sh start
```

### 停止

```bash
sudo bash scripts/server/manage.sh stop
```

### 重启

```bash
sudo bash scripts/server/manage.sh restart
```

### 查看状态

```bash
bash scripts/server/manage.sh status
```

### 查看实时日志

```bash
bash scripts/server/manage.sh logs
```

---

## 三、轻量版数据备份

轻量版数据保存在：

```text
/opt/yuanshi-jinshouzhi/local_data/
```

备份：

```bash
sudo tar -czf yuanshi-backup.tgz /opt/yuanshi-jinshouzhi/local_data
```

恢复时，把 `local_data` 放回同一路径并重启服务：

```bash
sudo bash /opt/yuanshi-jinshouzhi/scripts/server/manage.sh restart
```

---

## 四、本地轻量版运行

macOS 本地可以双击：

- `本地启动.command`
- `本地停止.command`

或命令行运行：

```bash
python3 local_app.py
```

打开：

```text
http://localhost:3000/login
```

---

## 五、Next.js 正式版本地开发

需要 Node.js、pnpm、PostgreSQL。

```bash
pnpm install
cp .env.example .env
pnpm exec prisma migrate deploy
pnpm db:seed
pnpm dev
```

打开：

```text
http://localhost:3000
```

常用命令：

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm test
pnpm build
```

---

## 六、Docker 部署

复制环境变量：

```bash
cp .env.example .env
```

至少修改：

```dotenv
POSTGRES_PASSWORD="强数据库密码"
AUTH_SECRET="至少32位随机字符"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="强管理员密码"
ADMIN_RECOVERY_CODE="只由总管理员保存的恢复码"
TRUSTED_ORIGIN="https://你的域名"
```

启动：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

不要随便执行 `docker compose down -v`，那会删除数据库卷。

---

## 七、环境变量

轻量版常用：

```dotenv
HOST=0.0.0.0
PORT=3000
BSC_RPC_URL=https://bsc-dataseed.binance.org/
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

注册邮箱验证码需要配置 SMTP。

Next.js 正式版详见 `.env.example`。

---

## 八、故障排查

### 浏览器打不开

先在服务器执行：

```bash
bash /opt/yuanshi-jinshouzhi/scripts/server/manage.sh status
```

如果服务器本机显示 `HTTP/1.0 200 OK`，但外网打不开，说明云服务器安全组没放行 `TCP 3000`。

### 查看服务日志

```bash
journalctl -u yuanshi-jinshouzhi --no-pager -n 100
```

### 重启服务

```bash
sudo bash /opt/yuanshi-jinshouzhi/scripts/server/manage.sh restart
```

---

## 九、安全注意事项

- 不要上传 `.env`
- 不要上传 `.pem` 私钥
- 不要上传 `local_data`
- 不要上传服务器日志
- GitHub 仓库不要保存真实数据库
- 上线前必须修改管理员密码
- 支付自动验单上线前建议先用小额转账实测

---

## 十、GitHub 上传

首次上传：

```bash
git init
git branch -M main
git remote add origin https://github.com/zmmidas/yuanshi.git
git add .
git commit -m "Initial release"
git push -u origin main
```

后续更新：

```bash
git add .
git commit -m "Update yuanshi system"
git push
```

---

## 联系方式

产品由 CK原石提供技术支持 ➡️TG [@mommo10338](https://t.me/mommo10338)

技术业务交流群：[https://t.me/B132609](https://t.me/B132609)

# X-FAIS Web 部署指南

## 环境要求

- Linux 服务器（Ubuntu 20.04+ / CentOS 7+ / Rocky Linux）
- Python 3.8+
- Node.js 18+（仅构建时需要）
- Nginx（可选，用于反向代理）

## 快速部署

### 非 root 用户部署（推荐）

```bash
# 上传项目文件到服务器
scp -r MAIN/ user@server:~/xfais-source/

# SSH到服务器
ssh user@server

# 进入部署目录
cd ~/xfais-source/deploy

# 执行部署
bash deploy.sh
```

部署脚本会自动：
1. 同步源码到 `~/xfais/`
2. 构建前端
3. 创建 Python 虚拟环境并安装依赖
4. 启动服务

### 部署模式选择

运行脚本时会提示选择部署模式：

```
请选择部署模式:
  0 = 普通部署（nohup，关闭终端后停止）
  1 = 长期部署（systemctl --user，开机自启）
请输入 0 或 1:
```

- **模式 0**：适合临时测试，关闭终端后服务停止
- **模式 1**：适合长期运行，开机自启

### 命令行参数

```bash
# 指定部署模式（不交互）
bash deploy.sh --mode 0           # nohup 模式
bash deploy.sh --mode 1           # 用户级 systemd

# 自定义端口
bash deploy.sh --port 8080

# 自定义安装目录
bash deploy.sh --install-dir /data/xfais

# 卸载
bash deploy.sh --uninstall
```

## 部署后管理

### 模式 0（nohup）

```bash
cd ~/xfais

bash start.sh      # 启动
bash stop.sh       # 停止
bash status.sh     # 查看状态

# 查看日志
tail -f logs/xfais.out
```

### 模式 1（用户级 systemd）

```bash
# 查看状态
systemctl --user status xfais

# 查看日志
journalctl --user -u xfais -f

# 重启服务
systemctl --user restart xfais

# 停止服务
systemctl --user stop xfais
```

**重要**：如需退出终端后服务继续运行，执行：
```bash
loginctl enable-linger $USER
```

## 访问地址

| 地址 | 说明 |
|------|------|
| `http://服务器IP:8765/` | Web 前端 |
| `http://服务器IP:8765/health` | 健康检查 |

## Nginx 反向代理（可选）

如需通过 80 端口访问，配置 Nginx：

```bash
# CentOS/Rocky
vi /etc/nginx/conf.d/xfais.conf

# Ubuntu
vi /etc/nginx/sites-available/xfais
```

配置内容：

```nginx
server {
    listen 80;
    server_name _;

    root /home/user/xfais/dist;  # 改为你的安装目录
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        client_max_body_size 500M;
    }

    location /health {
        proxy_pass http://127.0.0.1:8765;
    }
}
```

验证并重载：
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 卸载

```bash
cd ~/xfais-source/deploy
bash deploy.sh --uninstall
```

## 故障排查

### 健康检查失败

```bash
# 检查进程是否运行
ps aux | grep service_launcher

# 查看日志
tail -f ~/xfais/logs/xfais.out

# 检查端口占用
ss -tlnp | grep 8765
```

### 用户级 systemd 问题

```bash
# 查看服务状态
systemctl --user status xfais

# 查看详细日志
journalctl --user -u xfais -n 100

# 确认 linger 已启用
loginctl show-user $USER | grep Linger
```

## 注意事项

- 多用户数据隔离由 `service_launcher.py` 的 `SessionManager` 自动处理
- **selectFolder** 在 Web 模式下不可用（浏览器无文件夹选择器），相关按钮会自动灰度
- 上传文件大小限制：500MB（需在 Nginx 中配置 `client_max_body_size`）

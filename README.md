# QQ Quote Generator (Revised)

基于 Flask + Playwright 的 QQ 对话生成器，支持静态图片和动图合成。

## 特性

- 使用 Playwright 渲染 HTML 模板生成高质量背景图
- 支持动态合成多个 GIF/APNG 动图
- 提供 PNG、APNG 和 Base64 输出格式
- 无需编译 C++/Rust 代码，纯 Python 实现

## 安装

### 本地开发

1. 安装 Python 依赖：
```bash
pip install -r requirements.txt
```

2. 安装 Playwright 浏览器：
```bash
python setup_playwright.py
# 或手动运行：
python -m playwright install chromium
```

3. 启动服务：
```bash
python main.py
```

### Docker 部署

```bash
# 构建镜像
docker build -t qq-quote-generator .

# 运行容器
docker run -p 5000:5000 qq-quote-generator
```

## API 接口

### POST /png/
返回静态 PNG 图片（动图取首帧）

### POST /apng/
返回 APNG 动画图片

### POST /base64/
返回 PNG 的 Base64 编码

### GET/POST /quote/
预览 HTML 模板（调试用）

## 请求格式

所有 POST 接口接受 JSON 数组格式的消息数据：

```json
[
  {
    "user_id": "123456",
    "user_nickname": "用户昵称",
    "message": "消息内容",
    "image": ["https://example.com/image1.gif", "https://example.com/image2.png"],
    "reply": {
      "user_nickname": "回复的用户",
      "message": "被回复的消息",
      "image": "https://example.com/reply.gif"
    }
  }
]
```

## 技术架构

- **渲染引擎**: Playwright (Chromium) - 替代原生 C++ 渲染器
- **图像处理**: Pillow - 处理静态图和动图合成
- **Web 框架**: Flask - 提供 HTTP API

## 性能说明

- Playwright 渲染器使用单例模式，复用浏览器实例以提高性能
- 首次请求需要初始化浏览器，后续请求会快很多
- 建议使用 gunicorn 配合少量 worker 以避免内存占用过高

## 故障排除

如果遇到 Playwright 相关错误：

1. 确保已安装 Chromium：
```bash
python -m playwright install chromium
```

2. Linux 系统需要安装依赖：
```bash
python -m playwright install-deps chromium
```

3. 检查是否有足够的内存（至少 512MB）
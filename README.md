# 小红书搜索MCP服务

这是一个基于FastMCP和FastAPI的小红书笔记搜索和内容获取服务。

## 功能特性

- 🔍 **笔记搜索**: 根据关键词搜索小红书笔记
- 📄 **内容获取**: 获取指定笔记的详细内容
- 🔐 **登录管理**: 管理小红书账号登录状态
- 🌐 **FastAPI接口**: 提供RESTful API接口
- 🔧 **MCP工具**: 支持MCP协议的工具调用

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 同时运行FastAPI和MCP服务器（推荐）

默认模式，同时运行两个服务器：

```bash
python3 main.py
```

或者：

```bash
RUN_MODE=both python3 main.py
```

这将启动两个独立的进程：
- FastAPI服务器运行在 http://localhost:10001
- MCP服务器通过stdio通信

### 2. 只运行FastAPI服务器

```bash
RUN_MODE=api python3 main.py
```

或者使用uvicorn直接运行：

```bash
uvicorn main:app --host 0.0.0.0 --port 10001
```

### 3. 只运行MCP服务器

```bash
RUN_MODE=mcp python3 main.py
```

### 4. 访问API文档

启动FastAPI服务器后，访问以下地址查看API文档：

- Swagger UI: http://localhost:10001/docs
- ReDoc: http://localhost:10001/redoc

## API端点

### 健康检查

```bash
GET /api/health
```

### 登录

```bash
POST /api/login
```

### 搜索笔记

```bash
POST /api/search
Content-Type: application/json

{
  "keywords": "搜索关键词",
  "limit": 30
}
```

响应示例：

```json
{
  "success": true,
  "data": [
    {
      "url": "https://www.xiaohongshu.com/explore/...",
      "title": "笔记标题"
    }
  ],
  "message": "成功搜索到 10 条结果"
}
```

### 获取笔记内容

```bash
POST /api/note-content
Content-Type: application/json

{
  "url": "https://www.xiaohongshu.com/explore/..."
}
```

响应示例：

```json
{
  "success": true,
  "data": "标题: ...\n作者: ...\n发布时间: ...\n\n内容: ...",
  "message": "成功获取笔记内容"
}
```

## MCP工具

项目提供了以下MCP工具：

1. **login()** - 登录小红书账号
2. **search_notes(keywords, limit)** - 搜索笔记
3. **get_note_content(url)** - 获取笔记内容

## 环境要求

- Python 3.8+
- Chrome浏览器（需要运行在9222端口的CDP模式）
- Playwright

## 注意事项

1. 某些功能需要浏览器环境，确保Chrome以CDP模式运行
2. 首次使用需要登录小红书账号

## 免责声明

本项目仅供学习与技术研究使用，禁止用于任何商业目的或违反当地法律法规的场景。使用者需自行承担因使用本项目产生的一切风险与责任。

## 许可证

MIT License

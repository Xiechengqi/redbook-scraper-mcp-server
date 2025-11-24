# 小红书搜索MCP服务

这是一个基于FastMCP和FastAPI的小红书笔记搜索和内容获取服务。

## 功能特性

- 🔍 **笔记搜索**: 根据关键词搜索小红书笔记
- 📄 **内容获取**: 获取指定笔记的详细内容
- 🔐 **登录管理**: 管理小红书账号登录状态
- 🌐 **FastAPI接口**: 提供RESTful API接口
- 🔧 **MCP工具**: 支持MCP协议的工具调用

## 安装

```bash
bash run.sh
```

## Web Terminal

- http://localhost:12222

## Chromium

- http://localhost:17900

## FastAPI

启动FastAPI服务器后，访问以下地址查看API文档：

- Swagger UI: http://localhost:18000/docs
- ReDoc: http://localhost:18000/redoc

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

## MCP

项目提供了以下MCP工具：

1. **login()** - 登录小红书账号
2. **search_notes(keywords, limit)** - 搜索笔记
3. **get_note_content(url)** - 获取笔记内容

## 注意事项

1. 确保 docker 预先安装
2. 首次使用需要登录小红书账号

## 免责声明

本项目仅供学习与技术研究使用，禁止用于任何商业目的或违反当地法律法规的场景。使用者需自行承担因使用本项目产生的一切风险与责任。

## 许可证

MIT License

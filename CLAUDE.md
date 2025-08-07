# CLAUDE.md

本文件为Claude Code（claude.ai/code）在处理本仓库代码时提供指导。

# 开发约定
- 编写的每个函数都需要有详细的注释，包括参数、返回值、功能描述等。
- 每个生成的文件在文件头部都标注此文件为Claude Code编写

## 项目介绍

StrongDocTrans（LinguaHaru）是一个基于大语言模型的多格式文档翻译工具，支持多种文件格式（DOCX、XLSX、PPTX、PDF、TXT、SRT、MD等）的一键高质量翻译。项目特点包括：

- 多格式兼容：支持常见办公文档和文本文件格式
- 全球语言互译：支持中/英/日/韩/俄等10+语言
- 灵活翻译引擎：支持本地模型（如Ollama）和在线API（如Deepseek/OpenAI）
- 局域网共享：可在本地网络内提供服务

## 环境设置

### 系统要求

- CUDA：推荐11.7或12.1
- Python：3.10版本

### 安装步骤

1. 创建虚拟环境
```bash
conda create -n lingua-haru python=3.10
conda activate lingua-haru
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 下载模型并保存到"models"文件夹
   - 项目支持多种翻译模型，建议在models目录中放置所需模型文件

4. （可选）本地大语言模型支持
   - 使用Ollama：`ollama pull qwen2.5`

## 常用命令

### 启动应用

启动应用，默认在`http://127.0.0.1:9980`访问：
```bash
python app.py
```

### 局域网模式

通过配置文件启用局域网模式，允许局域网内其他设备访问：
```bash
# 在system_config.json中设置lan_mode为true，然后重启应用
```

## 代码架构

项目由以下主要模块组成：

1. **app.py**: 主应用入口，包含Gradio UI界面和流程控制
2. **ui_layout.py**: UI界面布局定义
3. **llmWrapper/**: LLM接口封装
   - llm_wrapper.py: 通用LLM调用接口
   - offline_translation.py: 本地模型翻译实现
   - online_translation.py: 在线API翻译实现
4. **pipeline/**: 各类文档处理流程
   - word_translation_pipeline.py: Word文档处理流程
   - excel_translation_pipeline.py: Excel文档处理流程
   - ppt_translation_pipeline.py: PPT文档处理流程
   - pdf_translation_pipeline.py: PDF文档处理流程
   - md_translation_pipeline.py: Markdown文档处理流程
   - txt_translation_pipeline.py: 文本文件处理流程
   - subtitle_translation_pipeline.py: 字幕文件处理流程
5. **translator/**: 各类文档翻译器
   - word_translator.py: Word文档翻译器
   - excel_translator.py: Excel文档翻译器
   - ppt_translator.py: PPT文档翻译器
   - pdf_translator.py: PDF文档翻译器
   - md_translator.py: Markdown文档翻译器
   - txt_translator.py: 文本文件翻译器
   - subtile_translator.py: 字幕文件翻译器
6. **textProcessing/**: 文本处理工具
   - base_translator.py: 基础翻译器类
   - text_separator.py: 文本分割工具
   - translation_checker.py: 翻译结果检查工具
   - calculation_tokens.py: Token计算工具
7. **config/**: 配置和提示词
   - languages_config.py: 语言配置
   - load_prompt.py: 提示词加载
   - log_config.py: 日志配置
   - prompts/: 各语言提示词
   - api_config/: API配置

## 核心流程

文档翻译的主要流程为：

1. 文档上传：用户通过Web界面上传文档
2. 内容提取：将文档内容提取为JSON格式
3. 文本去重：去除重复文本以提高翻译效率
4. 文本分段：根据Token限制将文本分段
5. LLM翻译：使用本地或在线LLM进行翻译
6. 结果合并：将翻译结果合并回原文档结构
7. 文档生成：生成翻译后的文档并提供下载

## 常见开发任务

### 添加新的翻译语言

1. 在`config/prompts/`中添加对应的语言配置文件（可复制现有文件修改）
2. 在`config/languages_config.py`的`LANGUAGE_MAP`和`LABEL_TRANSLATIONS`中添加新语言的映射和UI文本

### 添加新的文件格式支持

1. 在`translator/`中创建新的翻译器类，继承`DocumentTranslator`
2. 在`pipeline/`中创建对应的处理流程
3. 在`app.py`的`TRANSLATOR_MODULES`中注册新的文件格式与翻译器的映射

### 优化翻译质量

1. 修改`config/prompts/`中对应语言的提示词
2. 在`textProcessing/`中调整文本处理逻辑

## 调试与日志

日志文件存储在项目根目录下，通过查看日志可以了解翻译过程中的详细信息和错误。

## 多线程控制

在UI界面上可以调整线程数，控制并发翻译的数量，平衡速度与资源使用。线程控制逻辑在`base_translator.py`的`translate_content`方法中实现。
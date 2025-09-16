# weekly_newsletter

Python workflow for building an AI industry weekly newsletter from a CSV file.

## Features

- Reads a CSV with article titles and URLs.
- Fetches full article text using the [Jina Reader](https://r.jina.ai/) service.
- Extracts author and institution information from the article content and metadata.
- Classifies each entry into four sections: 论文 (Papers), 博客 (Blogs), 工程 / 产品 / 商业, and 开源项目汇总.
- Automatically assigns subcategories under the Papers section (e.g., LLM, Agents, 多模态, RL, 系统/工程, 检索/RAG, 评测, 数据/合成数据, 安全/对齐, etc.).
- Generates 100-word recommendation blurbs that highlight concrete contributions and optional signals (conference acceptance, GitHub, model links, attachments).
- Outputs a ready-to-publish Markdown report with a uniform structure per entry.

## Installation

```bash
pip install -e .
```

## Usage

Prepare a CSV file with at least two columns: one for titles and one for URLs. Column headers can be either English (`title`, `url`) or Chinese (`标题`, `链接`).

```bash
newsletter path/to/articles.csv --output weekly.md
```

Optional flags:

- `--timeout`: network timeout for fetching pages (default 30 seconds).
- `--retries`: number of retry attempts per request (default 2).
- `--max-words`: maximum word count for each recommendation (default 100).
- `--log-level`: logging verbosity (default INFO).

The script writes the Markdown newsletter to the path provided in `--output`.

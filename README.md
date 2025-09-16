# weekly_newsletter

Python workflow for building an AI industry weekly newsletter from a CSV file.

## Features

- Reads either a newline-delimited TXT file of URLs or a CSV with title/URL columns.
- Fetches full article text using the [Jina Reader](https://r.jina.ai/) service.
- Extracts author and institution information from the article content and metadata.
- Uses a configurable LLM (Gemini by default) to classify each entry into four sections: 论文 (Papers), 博客 (Blogs), 工程 / 产品 / 商业, and 开源项目汇总.
- Lets the LLM dynamically create subcategories under the Papers section based on each article's topic聚类，而不是写死的关键字匹配。
- Asks the LLM to craft recommendation blurbs (约100词) that emphasise the main contribution and supporting signals (conference acceptance, GitHub, model links, attachments).
- Outputs a ready-to-publish Markdown report with a uniform structure per entry.

## Installation

```bash
pip install -e .
```

### LLM configuration

By default the workflow calls the Gemini API. Set the Gemini API key before running:

```bash
export GEMINI_API_KEY="your_api_key"
```

Optional environment variables:

- `GEMINI_MODEL` (default `gemini-1.5-pro-latest`)
- `GEMINI_TIMEOUT` (seconds, default `60`)

To use [OpenRouter](https://openrouter.ai/), configure the provider and API key instead:

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="your_openrouter_key"
```

Optional OpenRouter variables:

- `OPENROUTER_MODEL` (default `openrouter/auto`)
- `OPENROUTER_TIMEOUT` (seconds, default `60`)
- `OPENROUTER_SITE_URL` (used for OpenRouter request headers)
- `OPENROUTER_APP_NAME` (used for OpenRouter request headers)

You can also place these values inside a `.env` file in either the project root or your current working directory; the CLI will load it automatically.

## Usage

Prepare one of the following input formats:

- TXT: each non-empty line contains a single article URL (lines starting with `#` are ignored).
- CSV: include at least `title` and `url` columns (Chinese headers `标题` / `链接` also work).

```bash
newsletter path/to/articles.txt --output weekly.md
```

Optional flags:

- `--timeout`: network timeout for fetching pages (default 30 seconds).
- `--retries`: number of retry attempts per request (default 2).
- `--max-words`: maximum word count for each recommendation (default 100).
- `--log-level`: logging verbosity (default INFO).

The script writes the Markdown newsletter to the path provided in `--output`.
